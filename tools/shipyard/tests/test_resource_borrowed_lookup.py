"""Exercise the selected resource key and cache-hit method with real map ownership."""
from pathlib import Path
import re
import runpy
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'scratch/resource-borrowed-test'


def main():
    header=(ROOT/'scratch/resource-manager-xdk/generated/include/ship/resource/ResourceManager.h').read_text()
    source=(ROOT/'scratch/resource-manager-xdk/generated/src/ship/resource/ResourceManager.cpp').read_text()
    key=header[header.index('struct ResourceIdentifier {'):header.index('\nclass ResourceManager {')]
    methods=source[source.index('size_t ResourceIdentifier::GetHash()'):source.index('ResourceManager::ResourceManager()')]
    signature='std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const char* filePath'
    fast=''
    if signature in source:
        start=source.index(signature)
        end=source.index('\n}\n',start)+3
        fast=source[start:end]
    declaration=('std::shared_ptr<IResource> LoadResourceProcess(const char*, bool=false, '
                 'std::shared_ptr<ResourceInitData> = std::shared_ptr<ResourceInitData>());') if fast else ''
    template=Path(__file__).with_name('test_resource_borrowed_contract.cpp').read_text()
    output=template.replace('// SELECTED KEY',key).replace('// SELECTED METHODS',methods+fast)
    output=output.replace('// FAST DECLARATION',declaration)
    cache_start=source.index('ResourceManager::GetCachedResource(xbox_compat::variant<') if 'ResourceManager::GetCachedResource(xbox_compat::variant<' in source else source.index('ResourceManager::GetCachedResource(const xbox_compat::variant<')
    cache_end=source.index('\n}',cache_start)+2
    cache_body='std::shared_ptr<IResource>\n'+source[cache_start:cache_end]
    cache_decl=cache_body[:cache_body.index('{')].replace('ResourceManager::','')+';'
    output=output.replace('// CACHE DECLARATION',cache_decl).replace('// CACHE METHOD',cache_body)
    OUT.mkdir(exist_ok=True)
    (OUT/'contract.cpp').write_text(output)
    environment=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler,env=environment['host_environment']()
    base=runpy.run_path(str(ROOT/'tools/shipyard/platform_base.py'))['resolve'](ROOT)
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/O2','/MD','/I'+str(base/'sources'),
             '/I'+str(base/'sources/value_types'),
             str(OUT/'contract.cpp'),'/Fe:'+str(OUT/'contract.exe'),'/Fo:'+str(OUT)+'/']
    built=subprocess.run(command,cwd=OUT,env=env,capture_output=True,text=True)
    (OUT/'build.log').write_text(built.stdout+built.stderr)
    assert built.returncode==0,built.stdout+built.stderr
    result=subprocess.run([str(OUT/'contract.exe')],cwd=OUT,capture_output=True,text=True)
    (OUT/'run.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    print(result.stdout)
    # Exercise the complete selected loader and cache methods, with only file I/O
    # and resource decoding replaced by deterministic boundary fixtures.
    signatures = [
        'std::shared_ptr<IResource> ResourceManager::GetSettledAlternate(const char* path)',
        'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const char* filePath',
        'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const std::string& filePath',
        'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const ResourceIdentifier& identifier',
        'ResourceManager::CheckCache(const ResourceIdentifier& identifier',
        'std::shared_ptr<IResource> ResourceManager::GetCachedResource(const ResourceIdentifier& identifier',
        'std::shared_ptr<IResource> ResourceManager::GetCachedResource(const std::string& filePath',
        'ResourceManager::LoadResourceAsync(const ResourceIdentifier& identifier',
        'std::shared_ptr<IResource> ResourceManager::LoadResource(const ResourceIdentifier& identifier',
        'std::shared_ptr<IResource> ResourceManager::LoadResource(const std::string& filePath',
    ]
    bodies=[]
    for signature in signatures:
        start=source.index(signature)
        end=source.index('\n}',start)+2
        body=source[start:end]
        if signature.startswith('ResourceManager::CheckCache'):
            body='xbox_compat::variant<ResourceManager::ResourceLoadError, std::shared_ptr<IResource>>\n'+body
        if signature.startswith('ResourceManager::LoadResourceAsync'):
            body='Shipyard::Async::shared_future<std::shared_ptr<IResource>>\n'+body
        bodies.append(body)
    bodies.append(cache_body)
    declarations=[]
    for body in bodies:
        declaration=body[:body.index('{')].replace('ResourceManager::','')
        if 'LoadResourceAsync(' in declaration:
            declaration=declaration.replace('initData)','initData = nullptr)')
        elif 'LoadResourceProcess(' in declaration or 'LoadResource(' in declaration:
            declaration=declaration.replace('bool loadExact,','bool loadExact = false,').replace('initData)','initData = nullptr)')
        elif 'GetCachedResource(const std::string&' in declaration:
            declaration=declaration.replace('bool loadExact)', 'bool loadExact = false)')
        declarations.append(declaration+';')
    alt=Path(__file__).with_name('test_resource_alt_contract.cpp').read_text()
    alt=alt.replace('// SELECTED KEY',key).replace('// ACTUAL DECLARATIONS','\n'.join(declarations))
    alt=alt.replace('// ACTUAL METHODS',methods+'\n'+'\n'.join(bodies))
    # Compile the real projected graphics bridge beside its upstream reference.
    # Only Context, preflight and worker execution are deterministic boundaries.
    import sys
    sys.path.insert(0,str(ROOT/'tools/shipyard'))
    from prepare_application_core import project
    helper_path='soh/soh/ResourceManagerHelpers.cpp'
    upstream=(ROOT/helper_path).read_text(encoding='utf-8-sig')
    projected=project(helper_path,upstream)
    def function(text,signature):
        start=text.index(signature)
        return text[start:text.index('\n}',start)+2]
    bridge=function(projected,'std::shared_ptr<Ship::IResource> ResourceMgr_GetResourceByNameHandlingMQ(')
    bridge+='\n'+function(upstream,'extern "C" Gfx* ResourceMgr_LoadGfxByName(').replace('ResourceMgr_LoadGfxByName','ReferenceLoadGfxByName')
    bridge+='\n'+function(projected,'extern "C" Gfx* ResourceMgr_LoadGfxByName(')
    alt=alt.replace('// ACTUAL GRAPHICS BRIDGE',bridge)
    (OUT/'alt_contract.cpp').write_text(alt)
    alt_command=[part.replace('contract.cpp','alt_contract.cpp').replace('contract.exe','alt_contract.exe') for part in command]
    built=subprocess.run(alt_command,cwd=OUT,env=env,capture_output=True,text=True)
    (OUT/'alt_build.log').write_text(built.stdout+built.stderr)
    assert built.returncode==0,built.stdout+built.stderr
    result=subprocess.run([str(OUT/'alt_contract.exe')],cwd=OUT,capture_output=True,text=True)
    (OUT/'alt_run.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    print(result.stdout)


if __name__=='__main__':main()
