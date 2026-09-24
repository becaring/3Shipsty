"""Inventory real projected sources and emit an inspectable compile-only XDK project.

Consumes the declarative subsystem report list, never executes a projection or
links old objects. Every application source remains selected or explicitly pending.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from source_inventory import ROOT, BASE, inventory
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
from xbox360_platform.build_policy import CXX_MSBUILD

CONFIG = ROOT / 'platform/shipyard/build/subsystems.json'
OUT = ROOT / 'scratch/project-xdk'
SDK = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
NS = 'http://schemas.microsoft.com/developer/msbuild/2003'
ET.register_namespace('', NS)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    resolved = Path(path).resolve()
    if resolved.is_relative_to(ROOT):
        return resolved.relative_to(ROOT).as_posix()
    if resolved.is_relative_to(PLATFORM_BASE):
        return 'shipyard/' + resolved.relative_to(PLATFORM_BASE).as_posix()
    raise ValueError('Production source outside consumer and Shipyard: ' + str(path))


def source_path(source):
    if source.startswith('shipyard/'):
        return PLATFORM_BASE / source[len('shipyard/'):]
    return ROOT / source


def portable(value):
    return value.replace('\\', '/').replace(PLATFORM_BASE.as_posix(), '$(ShipyardPlatformBase)').replace(ROOT.as_posix(), '$(ShipyardRoot)').replace(
        SDK.as_posix(), '$(XEDK)')


def command_rows(data):
    if isinstance(data, list):
        if data and isinstance(data[0], str):
            yield {'command': data}
        else:
            for item in data:
                yield from command_rows(item)
    elif isinstance(data, dict):
        if 'compile_command' in data:
            yield dict(data, command=data['compile_command'])
        elif 'command' in data:
            yield data
        else:
            for key in ('results', 'objects'):
                if key in data:
                    yield from command_rows(data[key])


def parse_command(record):
    command = record['command']
    if not command or Path(command[0]).name.lower() != 'cl.exe' or 'xbox 360 sdk' not in command[0].lower():
        raise ValueError('Report is not an XDK compiler recipe')
    if '/c' not in command:
        return None  # Explicit preprocessing-only records are not production TUs.
    sources = [arg for arg in command[1:] if not arg.startswith('/') and Path(arg).suffix.lower() in ('.cpp', '.cc', '.c', '.cxx', '.i')]
    if len(sources) != 1:
        raise ValueError('Expected exactly one source in compile recipe: ' + repr(command))
    source = relative(sources[0])
    options = [portable(arg) for arg in command[1:] if arg != sources[0] and not arg.lower().startswith('/fo')]
    language = 'c' if '/TC' in options or (source.endswith('.c') and '/TP' not in options) else 'cpp'
    # Explicit unified ABI requirements. Do not inherit old XDK /GR- defaults.
    options = [o for o in options if o not in ('/TC', '/TP', '/GR', '/GR-', '/MT', '/MTd', '/MD', '/MDd', '/EHsc', '/c', '/nologo')]
    options.insert(0, '/I$(ShipyardPlatformBase)')
    options.insert(1, '/I$(ShipyardPlatformBase)/sources')
    options.insert(2, '/I$(ShipyardPlatformBase)/sources/value_types')
    options.insert(3, '/I$(ShipyardPlatformBase)/sources/json/include')
    options += ['/MT', '/TP', '/EHsc', '/GR'] if language == 'cpp' else ['/MT', '/TC']
    return source, language, options


def canonical_headers(options, policies):
    # Earlier standalone stages emitted declarations before constructor helpers
    # were introduced. Production consumes the complete owner declaration even
    # when a consumer's original compile recipe predates that owner.
    for policy in policies:
        canonical='/I$(ShipyardRoot)/'+policy['root']
        shadow='/I$(ShipyardRoot)/'+policy['earlier_root']
        if shadow in options and canonical not in options:
            options.insert(options.index(shadow),canonical)


def upstream_for(source, record, known):
    if source in known:
        return source
    if record.get('path') in known:
        return record['path']
    if '/generated/' in source:
        suffix = source.split('/generated/', 1)[1]
        for candidate in (suffix, 'libultraship/' + suffix):
            if candidate in known:
                return candidate
    # Resource-manager glob C has been preprocessed into its build directory.
    if source == 'scratch/resource-manager-xdk/xdk/utils__glob.c':
        return 'libultraship/src/ship/utils/glob.c'
    return None


def object_name(source):
    return re.sub('[^a-zA-Z0-9_]', '_', Path(source).stem)[:55] + '_' + hashlib.sha256(source.encode()).hexdigest()[:20] + '.obj'


def project_option(option):
    # MSBuild expands these after quoting; a macro can hide spaces from Python.
    expanded = option.replace('$(ShipyardRoot)', '__SHIPYARD ROOT__').replace('$(XEDK)', '__XDK ROOT__')
    return subprocess.list2cmdline([expanded]).replace('__SHIPYARD ROOT__', '$(ShipyardRoot)').replace('__XDK ROOT__', '$(XEDK)')


def coverage(files, selected, platform_decisions=None):
    platform_decisions = platform_decisions or {}
    supplied = {r['upstream_source'] for r in selected if r['upstream_source']}
    rows = []
    for entry in files:
        row = dict(entry)
        row['status'] = 'selected' if row['path'] in supplied else (
            'excluded' if row['role'] in ('host-tool', 'upstream-excluded') else 'pending')
        if row['path'] in platform_decisions:
            if row['role'] not in ('lus-review','platform-review') or row['status']=='selected':
                raise ValueError('Platform decision would replace application or selected source: '+row['path'])
            row['status']='platform-replaced'
            row['platform_decision']=platform_decisions[row['path']]
        rows.append(row)
    return rows


def target_definitions(config, subsystem, record, source, options):
    policy = next((v for v in config['target_definition_policies'].values()
                   if subsystem in v['subsystems'] or source in v.get('sources', [])), None)
    if not policy:
        return []
    preprocessed = subsystem == 'game' or source == 'scratch/resource-manager-xdk/xdk/utils__glob.c'
    original = record.get('preprocess_command', record['command'])
    defined = [o[2:] for o in original if o.startswith('/D')]
    missing = [d for d in policy['definitions'] if d not in defined]
    for required in policy['definitions']:
        name = required.split('=')[0]
        conflicting = [d for d in defined if d.split('=')[0]==name and d != required]
        if conflicting:
            raise ValueError('Conflicting pinned target definition in '+source+': '+repr(conflicting))
        if not preprocessed and required in missing:
            options.append('/D'+required)
    return [dict(definition=d, action='regenerate_preprocessed_source' if preprocessed else 'added_to_project',
                 evidence=policy['evidence']) for d in missing]


def collect(config=None):
    config = config or json.loads(CONFIG.read_text())
    if config['upstream_commit'] != BASE:
        raise ValueError('Project configuration differs from the pinned upstream baseline')
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    lus = ROOT / 'libultraship'
    actual = subprocess.check_output(['git', '-c', 'safe.directory='+lus.as_posix(), '-C', str(lus),
                                      'rev-parse', 'HEAD'], env=env, text=True).strip()
    if actual != config['libultraship_commit']:
        raise ValueError('LUS submodule differs from the stable release pin')
    current = inventory()
    known = {r['path'] for r in current['files']}
    selected, exclusions, missing, seen_reports = {}, [], [], []
    for subsystem, patterns in config['reports'].items():
        reports = sorted({p for pattern in patterns for p in ROOT.glob(pattern)})
        if not reports:
            missing.append(subsystem)
        for report in reports:
            seen_reports.append(relative(report))
            for record in command_rows(json.loads(report.read_text(encoding='utf-8-sig'))):
                parsed = parse_command(record)
                if parsed is None:
                    continue
                source, language, options = parsed
                if language=='cpp':canonical_headers(options,config.get('canonical_header_providers',[]))
                reason = config['production_exclusions'].get(source)
                if source.startswith('tools/') or '/tests/' in source:
                    reason = 'Contract/test source, outside the production source set'
                if reason:
                    exclusions.append(dict(source=source, reason=reason))
                    continue
                if not source_path(source).is_file():
                    raise ValueError('Missing generated production source: ' + source)
                row = dict(source=source, subsystem=subsystem, language=language,
                           options=options, object=object_name(source), sha256=digest(source_path(source)),
                           upstream_source=upstream_for(source, record, known), report=relative(report),
                           prior_compile_exit=record.get('compile_exit', record.get('exit', record.get('returncode'))))
                row['target_definition_corrections'] = target_definitions(config, subsystem, record, source, options)
                if source in config.get('source_fragments', {}):
                    row['upstream_fragment'] = config['source_fragments'][source]
                # Reports supply recipes, not proof that current mutable inputs compiled.
                row['requires_fresh_build'] = True
                if source in selected and selected[source]['options'] != options:
                    raise ValueError('Conflicting production compile recipes: ' + source)
                selected[source] = row
    for entry in config['supplemental_sources']:
        source = entry['source']
        template = next(r for r in selected.values() if r['subsystem'] == entry['options_from'])
        selected[source] = dict(source=source, subsystem=entry['subsystem'], language='cpp',
            options=template['options'], object=object_name(source), sha256=digest(source_path(source)),
            upstream_source=source if source in known else None, report='explicit supplemental_sources; not a prior compile claim',
            prior_compile_exit=None, requires_fresh_build=True, target_definition_corrections=[])
    rows = sorted(selected.values(), key=lambda r: r['source'])
    upstream_sources = [r['upstream_source'] for r in rows if r['upstream_source']]
    if len(upstream_sources) != len(set(upstream_sources)):
        raise ValueError('Multiple production projections selected for one upstream source')
    if len({r['object'].lower() for r in rows}) != len(rows):
        raise ValueError('Object-name collision')
    decisions=config.get('platform_decisions',{})
    if set(decisions)-known:
        raise ValueError('Platform decision names unknown upstream source')
    cov = coverage(current['files'], rows,decisions)
    app = [r for r in cov if r['role'] == 'application']
    return dict(schema=1, upstream_commit=BASE, libultraship_commit=config['libultraship_commit'],
        inventory_sha256=hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest(),
        application_counts=dict(Counter(r['status'] for r in app)),
        subsystem_counts=dict(sorted(Counter(r['subsystem'] for r in rows).items())),
        final_application_ready=False, integration_gates=config['integration_gates'],
        target_definition_correction_counts=dict(sorted(Counter(c['definition'] for r in rows for c in r['target_definition_corrections']).items())),
        missing_subsystem_recipes=missing, compile_only=True, sources=rows,
        coverage=cov, production_exclusions=sorted(exclusions, key=lambda r:r['source']),
        recipe_reports=seen_reports)


def node(parent, name, value=None, **attributes):
    result = ET.SubElement(parent, '{'+NS+'}'+name, attributes)
    if value is not None:
        result.text = str(value)
    return result


def project(manifest, subsystem=None):
    p = ET.Element('{'+NS+'}Project', {'DefaultTargets':'Build', 'ToolsVersion':'4.0'})
    group = node(p, 'ItemGroup', Label='ProjectConfigurations')
    c = node(group, 'ProjectConfiguration', Include='Release|Xbox 360')
    node(c, 'Configuration', 'Release'); node(c, 'Platform', 'Xbox 360')
    g = node(p, 'PropertyGroup', Label='Globals')
    node(g, 'ProjectGuid', '{D072AB7D-9230-4346-BC71-022A79BC5D1F}')
    node(g, 'Keyword', 'Xbox360Proj'); node(g, 'RootNamespace', 'ShipyardCompile')
    node(g, 'ShipyardRoot', '$(MSBuildThisFileDirectory)..\\..')
    node(g, 'ShipyardPlatformBase', str(PLATFORM_BASE))
    node(g, 'XEDK', str(SDK), Condition="'$(XEDK)' == ''")
    node(p, 'Import', Project='$(VCTargetsPath)\\Microsoft.Cpp.Default.props')
    g = node(p, 'PropertyGroup', Label='Configuration')
    node(g, 'ConfigurationType', 'StaticLibrary'); node(g, 'PlatformToolset', '2010-01')
    node(g, 'CharacterSet', 'MultiByte')
    node(p, 'Import', Project='$(VCTargetsPath)\\Microsoft.Cpp.props')
    g = node(p, 'PropertyGroup')
    node(g, 'OutDir', '$(ProjectDir)build\\')
    node(g, 'IntDir', '$(OutDir)obj\\')
    node(g, 'TargetName', 'ShipyardCompileOnly')
    d = node(node(p, 'ItemDefinitionGroup'), 'ClCompile')
    for name, value in [('PrecompiledHeader','NotUsing'),('RuntimeLibrary','MultiThreaded'),
                        ('DebugInformationFormat',''),('WarningLevel','Level3'),*CXX_MSBUILD]:
        node(d, name, value)
    items = node(p, 'ItemGroup')
    for source in manifest['sources']:
        if subsystem and source['subsystem'] != subsystem:
            continue
        path = source['source']
        include = ('$(ShipyardPlatformBase)/'+path[len('shipyard/'):] if path.startswith('shipyard/')
                   else '$(ShipyardRoot)/'+path)
        item = node(items, 'ClCompile', Include=include)
        node(item, 'ObjectFileName', '$(IntDir)'+source['object'])
        node(item, 'CompileAs', 'CompileAsCpp' if source['language']=='cpp' else 'CompileAsC')
        node(item, 'RuntimeTypeInfo', 'true' if source['language']=='cpp' else 'false')
        node(item, 'ExceptionHandling', 'Sync' if source['language']=='cpp' else 'false')
        # Windows compiler arguments quoted with the standard list2cmdline rules.
        node(item, 'AdditionalOptions', ' '.join(project_option(o) for o in source['options'])+' %(AdditionalOptions)')
    node(p, 'Import', Project='$(VCTargetsPath)\\Microsoft.Cpp.targets')
    guard = node(p, 'Target', Name='RejectIncompleteApplication', BeforeTargets='Build;Rebuild;Lib;Link')
    node(guard, 'Error', Text='Compile-only port inventory: final application is incomplete. Use /t:ClCompile; inspect manifest.json pending coverage and integration gates. No library, EXE or XEX is emitted.')
    ET.indent(p, space='  ')
    return ET.tostring(p, encoding='utf-8', xml_declaration=True)+b'\n'


def write(manifest, subsystem=None):
    OUT.mkdir(parents=True, exist_ok=True)
    for path, content in (
        (OUT/'manifest.json', (json.dumps(manifest, indent=2)+'\n').encode('utf-8')),
        (OUT/'ShipyardCompile.vcxproj', project(manifest, subsystem)),
    ):
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subsystem', help='Emit only this compile group; complete coverage remains in manifest.json')
    parser.add_argument('--require-complete', action='store_true', help='Fail while any final application integration gate remains')
    args = parser.parse_args()
    manifest = collect()
    if args.subsystem and args.subsystem not in manifest['subsystem_counts']:
        parser.error('Unknown or unavailable subsystem')
    write(manifest, args.subsystem)
    print(json.dumps({k:manifest[k] for k in ('application_counts','subsystem_counts','missing_subsystem_recipes','final_application_ready')}))
    return 2 if args.require_complete and not manifest['final_application_ready'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
