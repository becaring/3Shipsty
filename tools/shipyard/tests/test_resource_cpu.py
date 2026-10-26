"""Compare borrowed string lookup and packet retention with their owned paths."""

from pathlib import Path
import re
import sys
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
import resource_cpu_projection
import overlap_resource_cpu_projection
from test_tri2_packed_reuse import host_environment


def method(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


class ResourceCpu(unittest.TestCase):
    def test_lookup_and_retention_contracts(self):
        header = (ROOT / 'scratch/resource-manager-xdk/generated/include/ship/resource/ResourceManager.h').read_text()
        original = (ROOT / 'scratch/resource-manager-xdk/generated/src/ship/resource/ResourceManager.cpp').read_text()
        changed = resource_cpu_projection.source(original)
        key = header[header.index('struct ResourceIdentifier {'):header.index('\nclass ResourceManager {')]
        key_methods = original[original.index('size_t ResourceIdentifier::GetHash()'):original.index('ResourceManager::ResourceManager()')]
        signatures = [
            'ResourceManager::CheckCache(const ResourceIdentifier&',
            'ResourceManager::CheckCache(const std::string&',
            'std::shared_ptr<IResource> ResourceManager::GetCachedResource(const ResourceIdentifier&',
            'std::shared_ptr<IResource> ResourceManager::GetCachedResource(const std::string&',
            'ResourceManager::GetCachedResource(const xbox_compat::variant<',
            'std::shared_ptr<IResource> ResourceManager::LoadResource(const ResourceIdentifier&',
            'std::shared_ptr<IResource> ResourceManager::LoadResource(const std::string&',
            'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const ResourceIdentifier&',
            'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const std::string&',
        ]
        bodies = []
        for reference, source in ((True, original), (False, changed)):
            for signature in signatures:
                body = method(source, signature)
                if signature.startswith('ResourceManager::CheckCache'):
                    body = 'xbox_compat::variant<ResourceManager::ResourceLoadError, std::shared_ptr<IResource>>\n' + body
                elif signature.startswith('ResourceManager::GetCachedResource'):
                    body = 'std::shared_ptr<IResource>\n' + body
                if reference:
                    body = re.sub(r'\b(CheckCache|GetCachedResource|LoadResourceProcess|LoadResource)\(', r'Reference\1(', body)
                    body = body.replace('->ReferenceLoadResource(', '->LoadResource(')
                bodies.append(body)
        declarations = []
        for body in bodies:
            declaration = body[:body.index('{')].replace('ResourceManager::', '')
            declaration = declaration.replace('bool loadExact,', 'bool loadExact = false,')
            declaration = declaration.replace('bool loadExact)', 'bool loadExact = false)')
            declaration = declaration.replace('initData)', 'initData = nullptr)')
            declarations.append(declaration + ';')
        template = Path(__file__).with_name('test_resource_alt_contract.cpp').read_text()
        template = template[:template.index('struct Context {')] + '}\n'
        template = template.replace('// SELECTED KEY', key)
        template = template.replace('// ACTUAL DECLARATIONS', '\n'.join(declarations))
        keep = 'static std::shared_ptr<IResource> Shipyard_OverlapKeepResource(const std::shared_ptr<IResource>& p) { return p; }\n'
        template = template.replace('// ACTUAL METHODS', keep + key_methods + '\n'.join(bodies))
        owner = overlap_resource_cpu_projection.runtime('typedef std::vector<std::shared_ptr<Ship::IResource> > ResourceOwners;')
        template += owner + '\n' + Path(__file__).with_name('test_resource_cpu_contract.cpp').read_text()
        out = ROOT / 'scratch/xenon-cpu-audit/resource-contract'
        out.mkdir(parents=True, exist_ok=True)
        path = out / 'contract.cpp'; path.write_text(template)
        base = resolve(ROOT)
        compiler, env = host_environment()
        built = subprocess.run([str(compiler), '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
                                '/I' + str(base / 'sources'), '/I' + str(base / 'sources/value_types'),
                                str(path), '/Fe:' + str(out / 'contract.exe')],
                               cwd=out, env=env, capture_output=True, text=True)
        (out / 'build.log').write_text(built.stdout + built.stderr)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        run = subprocess.run([str(out / 'contract.exe')], cwd=out, capture_output=True, text=True)
        (out / 'run.log').write_text(run.stdout + run.stderr)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        print(run.stdout)
