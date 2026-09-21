"""Generate and build the pinned libzip/zlib runtime at its native file boundary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified

OUT = ROOT / 'scratch/libzip-xdk'
OWN = ROOT / 'platform/shipyard/libzip'
ZLIB_UNITS = 'adler32 compress crc32 deflate infback inffast inflate inftrees trees uncompr zutil'.split()


def stable(path, text):
    data = text.encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def prepare():
    source = verified('libzip')
    verified('zlib')
    generated = OUT / 'generated'
    transform = runpy.run_path(str(OWN / 'projection.py'))['transform']
    units = re.findall(r'^  (zip_\S+\.c)$', (source / 'lib/CMakeLists.txt').read_text().split('add_library(libzip::zip')[0], re.M)
    units += ['zip_err_str.c', 'zip_source_file_win32.c', 'zip_source_file_win32_named.c',
              'zip_source_file_win32_ansi.c', 'zip_source_file_win32_utf8.c',
              'zip_source_file_win32_utf16.c', 'zip_random_win32.c']
    pending = {}
    for path in sorted((source / 'lib').glob('*')):
        if path.suffix not in ('.h', '.c') or (path.suffix == '.c' and path.name not in units):
            continue
        pending[path.name] = '// Generated Shipyard XDK projection; do not edit.\n#line 1 "' + path.relative_to(ROOT).as_posix() + '"\n' + transform(path.name, path.read_text())
    enabled = set('ENABLE_FDOPEN HAVE__CLOSE HAVE__DUP HAVE__FDOPEN HAVE__FILENO HAVE__FSEEKI64 HAVE__FSTAT64 HAVE__SETMODE HAVE__SNPRINTF HAVE__SNPRINTF_S HAVE__SNWPRINTF_S HAVE__STAT64 HAVE__STRDUP HAVE__STRICMP HAVE__STRTOI64 HAVE__STRTOUI64 HAVE__UNLINK HAVE_LOCALTIME_S HAVE_MEMCPY_S HAVE_STRERROR_S HAVE_STRNCPY_S'.split())
    config = re.sub(r'^#cmakedefine (\w+).*$', lambda m: '#define ' + m[1] if m[1] in enabled else '/* unavailable: ' + m[1] + ' */', (source / 'config.h.in').read_text(), flags=re.M)
    config = config.replace('/* unavailable: SIZEOF_OFF_T */', '#define SIZEOF_OFF_T 4')
    config = config.replace('/* unavailable: SIZEOF_SIZE_T */', '#ifdef _XBOX\n#define SIZEOF_SIZE_T 4\n#define WORDS_BIGENDIAN\n#else\n#define SIZEOF_SIZE_T 8\n#endif')
    config = config.replace('@CMAKE_PROJECT_NAME@', 'libzip').replace('@CMAKE_PROJECT_VERSION@', '1.11.4')
    config = config.replace('/* END DEFINES */', '#ifndef _XBOX\n#define HAVE_SNPRINTF\n#endif\n/* END DEFINES */')
    pending['config.h'] = config
    config = (source / 'zipconf.h.in').read_text().replace('#cmakedefine ZIP_STATIC', '#define ZIP_STATIC')
    values = dict(libzip_VERSION='1.11.4', libzip_VERSION_MAJOR='1', libzip_VERSION_MINOR='11', libzip_VERSION_PATCH='4', LIBZIP_TYPES_INCLUDE='#include <stdint.h>')
    for width in (8, 16, 32, 64):
        values['ZIP_INT' + str(width) + '_T'] = 'int' + str(width) + '_t'
        values['ZIP_UINT' + str(width) + '_T'] = 'uint' + str(width) + '_t'
    for key, value in values.items():
        config = config.replace('${' + key + '}', value)
    if '${' in config or '#cmakedefine' in config:
        raise ValueError('Unresolved libzip public configuration')
    pending['zipconf.h'] = config
    errors = OUT / 'error-strings'; errors.mkdir(parents=True, exist_ok=True)
    subprocess.run(['cmake', '-DPROJECT_SOURCE_DIR=' + str(source), '-P', str(source / 'cmake/GenerateZipErrorStrings.cmake')], cwd=errors, check=True, capture_output=True)
    pending['zip_err_str.c'] = (errors / 'zip_err_str.c').read_text()
    for name, text in pending.items():
        stable(generated / name, text)
    manifest = dict(units=units, outputs={name: hashlib.sha256(text.encode()).hexdigest() for name, text in sorted(pending.items())})
    stable(OUT / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    return manifest


def build(host=False):
    manifest = prepare()
    folder = OUT / ('host' if host else 'xdk'); folder.mkdir(parents=True, exist_ok=True)
    sdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    env = os.environ.copy()
    if host:
        helpers = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))
        compiler, env = helpers['host_environment']()
        librarian = compiler.parent / 'lib.exe'
        flags = ['/nologo', '/c', '/MD', '/W3', '/D_CRT_SECURE_NO_WARNINGS']
    else:
        compiler = sdk / 'bin/win32/cl.exe'; librarian = sdk / 'bin/win32/lib.exe'
        flags = ['/nologo', '/c', '/MT', '/W3', '/D_XBOX', '/I' + str(sdk / 'include/xbox')]
    flags += ['/DNOMINMAX', '/I' + str(OUT / 'generated'), '/I' + str(ROOT / 'platform/shipyard'),
              '/I' + str(ROOT / 'scratch/deps/zlib')]
    groups = {'zip': [OUT / 'generated' / name for name in manifest['units']] + [OWN / 'native_boundary.cpp'],
              'zlib': [ROOT / 'scratch/deps/zlib' / (name + '.c') for name in ZLIB_UNITS],
              'tinyxml2': [verified('tinyxml2') / 'tinyxml2.cpp']}
    records = []; libraries = {}
    for group, sources in groups.items():
        objects = []
        for source in sources:
            obj = folder / (group + '-' + source.stem + '.obj'); objects.append(obj)
            command = [str(compiler)] + flags + (['/TP', '/EHsc', '/GR'] if source.suffix == '.cpp' else ['/TC']) + [str(source), '/Fo' + str(obj)]
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            stable(folder / (obj.stem + '.log'), result.stdout + result.stderr)
            records.append(dict(source=source.relative_to(ROOT).as_posix(), command=command, exit=result.returncode))
            if result.returncode:
                raise RuntimeError('Archive source failed, see ' + str(folder / (obj.stem + '.log')))
            if not host and struct.unpack_from('<H', obj.read_bytes())[0] != 0x1f2:
                raise ValueError('Expected Xenon PowerPC BE object')
        library = folder / (group + '.lib')
        response = folder / (group + '.rsp')
        stable(response, '/nologo\n/OUT:"' + str(library) + '"\n' + '\n'.join('"' + str(p) + '"' for p in objects))
        result = subprocess.run([str(librarian), '@' + str(response)], cwd=ROOT, env=env, capture_output=True, text=True)
        stable(folder / (group + '-archive.log'), result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Librarian failed: ' + group)
        libraries[group] = hashlib.sha256(library.read_bytes()).hexdigest()
    stable(folder / 'build.json', json.dumps(dict(objects=records, libraries=libraries, target_runtime_executed=False), indent=2) + '\n')
    print('Built ' + ('host' if host else 'Xenon') + ' libzip, zlib, tinyxml2 (' + str(len(records)) + ' objects)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--host', action='store_true')
    args = parser.parse_args()
    if args.build: build(args.host)
    else: prepare(); print('Generated verified libzip projection')
