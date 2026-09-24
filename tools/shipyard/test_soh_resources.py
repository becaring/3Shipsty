"""Run original and projected complete SoH resource TUs against identical fixtures."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from prepare_soh_resources import ROOT, OUT, OWN, prepare, includes, units
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from dependency_sources import verified


def main():
    prepare()
    environment = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))
    compiler, env = environment['host_environment']()
    outputs = []; records = []
    for projected in (False, True):
        folder = OUT / ('host-projected' if projected else 'host-original'); folder.mkdir(parents=True, exist_ok=True)
        base = OUT / 'generated' if projected else ROOT
        resources = ROOT / 'scratch/resources-xdk/generated' if projected else ROOT / 'libultraship'
        binary = ROOT / 'scratch/binary-xdk/generated' if projected else ROOT / 'libultraship'
        # Execute the complete self-contained TUs. Context/archive/CVar-dependent
        # factories have separate pure-method audits; no fake service APIs link here.
        executable_names = ('Background', 'PlayerAnimation', 'Text', 'Array', 'Cutscene', 'CollisionHeader', 'SkeletonLimb')
        sources = [p for p in units(base) if p.stem.removesuffix('Factory') in executable_names]
        if not projected:
            # This unused umbrella include drags in SDL/native GUI declarations.
            # Keep every original method and header definition verbatim.
            limb = base / 'soh/soh/resource/importer/SkeletonLimbFactory.cpp'
            source = limb.read_text().replace('#include "libultraship/libultraship.h"', '// Unused umbrella include omitted for host contract.')
            destination = folder / limb.name; stable(destination, source)
            sources[sources.index(limb)] = destination
        sources += [OWN / 'contract.cpp', verified('tinyxml2') / 'tinyxml2.cpp']
        sources += [resources / 'src/ship/resource' / (n + '.cpp') for n in ('Resource', 'ResourceFactoryBinary', 'ResourceFactoryXML')]
        sources += [binary / 'src/ship/utils/binarytools' / (n + '.cpp') for n in ('BinaryReader', 'MemoryStream', 'Stream')]
        if projected:
            sources += [PLATFORM_BASE / 'sources/async/native.cpp', PLATFORM_BASE / 'sources/clock/chrono.cpp', ROOT / 'platform/shipyard/logging/environment.cpp']
        command = [str(compiler), '/nologo', '/std:c++20', '/utf-8', '/EHsc', '/MD', '/DNOMINMAX', '/DSPDLOG_ACTIVE_LEVEL=0']
        command += ['/I' + str(p) for p in includes(projected)+[PLATFORM_BASE/'sources']] + [str(p) for p in sources]
        command += ['/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / 'build.log', result.stdout + result.stderr)
        if result.returncode: raise RuntimeError('See ' + str(folder / 'build.log'))
        result = subprocess.run([str(folder / 'contract.exe')], cwd=folder, capture_output=True, text=True)
        record = dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        stable(folder / 'run.json', json.dumps(record, indent=2) + '\n')
        if result.returncode: raise RuntimeError('Contract failed: ' + str(record))
        outputs.append(result.stdout); records.append(record)
    if outputs[0] != outputs[1]: raise AssertionError('Original/projected factory behavior differs')
    stable(OUT / 'verification.json', json.dumps(dict(cases=records, executed_resource_pairs=list(executable_names),
           original_header_normalization='SkeletonLimbFactory.cpp unused libultraship umbrella include only', target_runtime_executed=False,
           native_objects={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT / 'xdk').glob('*.obj')}), indent=2) + '\n')
    print(outputs[0])


if __name__ == '__main__': main()
