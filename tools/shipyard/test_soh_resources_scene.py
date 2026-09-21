"""Complete Scene XML method/type/logger audit with no invented runtime services."""
import hashlib
import json
import runpy
import subprocess
import re
from prepare_soh_resources import ROOT, OUT, OWN, SCENE_COMMANDS, prepare, includes
from prepare_archives import stable
from dependency_sources import verified
from cpp_ast import PARSER, walk

SERVICE_COMMANDS = ('SetAlternateHeaders', 'SetCollisionHeader', 'SetCutscenes', 'SetPathways')


def functions(text):
    return [n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == 'function_definition']


def main():
    prepare()
    environment = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))
    compiler, env = environment['host_environment']()
    outputs = []; records = []
    for projected in (False, True):
        folder = OUT / ('scene-projected' if projected else 'scene-original'); folder.mkdir(parents=True, exist_ok=True)
        base = OUT / 'generated' if projected else ROOT
        source = base / 'soh/soh/resource'
        headers = ['#include "soh/resource/type/scenecommand/' + n + '.h"\n'
                   '#include "soh/resource/importer/scenecommand/' + n + 'Factory.h"' for n in SCENE_COMMANDS]
        prefix = '\n'.join(headers) + '''
#include "soh/resource/importer/SceneFactory.h"
#include "soh/resource/type/SohResourceType.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include "soh-resources/enum.h"
#include <tinyxml2.h>
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstdio>
#include <cstring>
namespace SOH {
'''
        methods = []
        for n in SCENE_COMMANDS:
            if n in SERVICE_COMMANDS: continue
            original = (source / ('importer/scenecommand/' + n + 'Factory.cpp')).read_text(encoding='utf-8-sig')
            method = [f for f in functions(original) if n + 'FactoryXML::ReadResource' in f]
            assert len(method)==1, n
            methods += method
        common = (source / 'importer/scenecommand/SceneCommandFactory.cpp').read_text(encoding='utf-8-sig')
        method = functions(common)[0].replace('SceneCommandFactoryBinaryV0::ReadCommandId', 'ReadBinaryCommandId')
        methods.append(method)
        scene = (source / 'importer/SceneFactory.cpp').read_text(encoding='utf-8-sig')
        start = scene.index('static const char* const commandNameValues[]' if projected else 'std::vector<std::string> commandNames =')
        table = scene[start:scene.index('SceneCommandID GetCommandID')]
        methods += [f for f in functions(scene) if f.startswith('SceneCommandID GetCommandID')]
        # Test fixture registers only real factories whose dependencies are in
        # this executable. The production constructor still retains all 25.
        registrations = re.findall(r'sceneCommandFactories\[SceneCommandID::(\w+)\]\s*=\s*std::make_shared<(\w+FactoryXML)>\(\);', scene)
        local = [(key, factory) for key, factory in registrations if factory.removesuffix('FactoryXML') not in SERVICE_COMMANDS]
        assert len(local)==21
        if projected:
            table += 'std::unordered_map<SceneCommandID, std::shared_ptr<SceneCommandFactoryXMLV0>> ResourceFactoryXMLSceneV0::sceneCommandFactories;\n'
        table += 'void RegisterAuditXMLFactories() {\n' + '\n'.join(
            'ResourceFactoryXMLSceneV0::sceneCommandFactories[SceneCommandID::' + key + '] = std::make_shared<' + factory + '>();'
            for key, factory in local) + '\n}\n'
        table += 'std::shared_ptr<ISceneCommand> ParseSceneCommand(std::shared_ptr<Scene> scene, tinyxml2::XMLElement* child, uint32_t index);\n'
        methods += [f.replace('ResourceFactoryXMLSceneV0::', '', 1) for f in functions(scene)
                    if 'ResourceFactoryXMLSceneV0::ParseSceneCommand' in f.split('{',1)[0]]
        logger = (source / 'logging/SceneCommandLoggers.cpp').read_text(encoding='utf-8-sig')
        declarations = '\n'.join(f.split('{',1)[0].strip() + ';' for f in functions(logger))
        audit = prefix + table + '\n'.join(methods) + '\n' + declarations + '\n}\n' + (OWN / 'scene_contract.cpp').read_text(encoding='utf-8-sig')
        stable(folder / 'audit.cpp', audit)
        resources = ROOT / 'scratch/resources-xdk/generated' if projected else ROOT / 'libultraship'
        binary = ROOT / 'scratch/binary-xdk/generated' if projected else ROOT / 'libultraship'
        sources = [folder / 'audit.cpp', source / 'logging/SceneCommandLoggers.cpp', verified('tinyxml2') / 'tinyxml2.cpp']
        sources += [source / 'type/scenecommand' / (n + '.cpp') for n in SCENE_COMMANDS]
        sources += [source / 'type' / (n + '.cpp') for n in ('Scene', 'CollisionHeader', 'Cutscene')]
        sources += [resources / 'src/ship/resource' / (n + '.cpp') for n in ('Resource',)]
        sources += [binary / 'src/ship/utils/binarytools' / (n + '.cpp') for n in ('BinaryReader', 'MemoryStream', 'Stream')]
        if projected:
            sources += [ROOT / 'platform/shipyard/async/native.cpp', ROOT / 'platform/shipyard/logging/chrono/chrono.cpp', ROOT / 'platform/shipyard/logging/environment.cpp']
        paths = includes(projected) + [ROOT / 'platform/shipyard']
        command = [str(compiler), '/nologo', '/std:c++20', '/utf-8', '/EHsc', '/GR', '/MD', '/DNOMINMAX', '/DSPDLOG_ACTIVE_LEVEL=0']
        command += ['/I' + str(p) for p in paths] + [str(p) for p in sources]
        command += ['/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'audit.exe')]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / 'build.log', result.stdout + result.stderr)
        if result.returncode: raise RuntimeError('See ' + str(folder / 'build.log'))
        result = subprocess.run([str(folder / 'audit.exe')], cwd=folder, capture_output=True, text=True)
        stable(folder / 'run.log', result.stdout + result.stderr)
        if result.returncode: raise RuntimeError('Scene method audit failed: ' + str(folder))
        outputs.append(result.stdout)
        records.append(dict(command=command, exit=result.returncode, audit_sha256=hashlib.sha256(audit.encode()).hexdigest(),
                            method_sha256=[hashlib.sha256(m.encode()).hexdigest() for m in methods],
                            output_sha256=hashlib.sha256(result.stdout.encode()).hexdigest()))
    assert outputs[0] == outputs[1], 'Original/projected scene method or logger output differs'
    stable(OUT / 'scene-verification.json', json.dumps(dict(cases=records, xml_command_factories=21,
           scope='Complete extracted XML methods for 21 non-service commands, Scene XML parser methods with 21 real factories registered in the fixture; complete production type/logger TUs; binary ID and name lookup methods',
           service_command_factories=list(SERVICE_COMMANDS), target_runtime_executed=False), indent=2)+'\n')
    print('Original/projected Scene: 21 XML command methods, all 25 type/loggers, mesh variants, ID truncation/LE/BE and name mappings agree')


if __name__ == '__main__': main()
