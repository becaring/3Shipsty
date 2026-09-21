"""Real synthesis, native application/engine compilation and endian/lifetime contracts."""
import ctypes,hashlib,json,re,runpy,struct,subprocess,unittest
from pathlib import Path
from prepare_speech import ROOT,OWN,OUT,GEN,DEP,PIN,SDK,prepare_engine,build_engine,build_application,engine_flags
from prepare_archives import stable
ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))
DATA=OUT/'host-ninja/espeak-ng-data'
def invoke(command,folder,label,env=None):
    r=ENV['invoke'](command,folder,label,env,success=False)
    assert r['returncode']==0,(r['stdout']+r['stderr'])[-6000:]
    return r

def build_host_tools():
    compiler,env=ENV['host_environment']();env['PATH']='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64;'+env['PATH']
    sonic=OUT/'sonic';assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=sonic,text=True).strip()=='fbf75c3d6d846bad3bb3d456cbc5d07d9fd8c104'
    subprocess.run(['git','diff','--exit-code','--quiet','HEAD','--'],cwd=sonic,check=True)
    cmake='C:/Program Files/CMake/bin/cmake.exe'
    args=['-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DBUILD_TESTING=OFF','-DUSE_ASYNC=OFF','-DUSE_LIBPCAUDIO=OFF','-DUSE_LIBSONIC=OFF','-DUSE_MBROLA=OFF','-DUSE_SPEECHPLAYER=OFF',
      '-DCMAKE_RC_COMPILER=C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/rc.exe','-DCMAKE_MT=C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/mt.exe',
      '-DFETCHCONTENT_SOURCE_DIR_SONIC-GIT='+str(sonic),'-DCMAKE_MAKE_PROGRAM=C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe']
    invoke([cmake,'-S',DEP,'-B',OUT/'host-ninja','-G','Ninja']+args,OUT,'host-configure',env)
    invoke([cmake,'--build',OUT/'host-ninja','--parallel','4'],OUT,'host-build',env)
    stable(OUT/'data-manifest.json',json.dumps(dict(commit=PIN,format='Original eSpeak NG little-endian PC-generated files; Xbox converts native structure regions during load',files={p.relative_to(DATA).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DATA.rglob('*')) if p.is_file()}),indent=2)+'\n')

def build_host_engine():
    compiler,env=ENV['host_environment']();folder=OUT/'host-projected-engine';folder.mkdir(exist_ok=True);objects=[]
    units=json.loads((OUT/'engine-manifest.json').read_text())['units']
    # Original host compatibility headers forward to the installed host CRT;
    # target-specific CRT spelling is not imported into this host execution.
    roots=[OWN/'include',ROOT/'platform/shipyard',GEN/'src/include',DEP/'src/include/compat',GEN/'src/ucd-tools/src/include']
    for name in units:
        obj=folder/(name.replace('/','__')[:-2]+'.obj');objects.append(obj)
        invoke([compiler,'/nologo','/c','/TC','/std:c11','/O2','/MD','/DSHIPYARD_ESPEAK_STATIC','/D_CRT_SECURE_NO_WARNINGS']+['/I'+str(p) for p in roots]+[GEN/name,'/Fo'+str(obj)],folder,obj.stem,env)
    return objects

def host_synthesis(projected,objects):
    compiler,env=ENV['host_environment']();folder=OUT/('synthesis-projected' if projected else 'synthesis-original');folder.mkdir(exist_ok=True)
    libs=objects if projected else [OUT/'host-ninja/src/libespeak-ng/espeak-ng.lib',OUT/'host-ninja/src/ucd-tools/ucd.lib']
    header=GEN/'src/include' if projected else DEP/'src/include'
    # LIBESPEAK_NG_EXPORT is upstream's static-library consumer setting.
    flag='/DSHIPYARD_ESPEAK_STATIC' if projected else '/DLIBESPEAK_NG_EXPORT'
    invoke([compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/MD',flag,'/DNOMINMAX','/I'+str(header),'/I'+str(ROOT/'platform/shipyard'),OWN/'synthesis_contract.cpp',OWN/'data_boundary.c']+libs+['advapi32.lib','/Fo'+str(folder)+'/', '/Fe'+str(folder/'contract.exe')],folder,'compile',env)
    return invoke([folder/'contract.exe',DATA],folder,'run',env)['stdout']

def boundary_library():
    compiler,env=ENV['host_environment']();folder=OUT/'host-boundary';folder.mkdir(exist_ok=True)
    invoke([compiler,'/nologo','/LD','/TC','/O2',OWN/'data_boundary.c','/Fo'+str(folder/'boundary.obj'),'/Fe'+str(folder/'boundary.dll'),'/link','/EXPORT:ShipyardSpeechFixupData','/EXPORT:ShipyardSpeechPcmToNative'],folder,'compile',env)
    dll=ctypes.CDLL(str(folder/'boundary.dll'));dll.ShipyardSpeechFixupData.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p];dll.ShipyardSpeechFixupData.restype=ctypes.c_int
    dll.ShipyardSpeechPcmToNative.argtypes=[ctypes.POINTER(ctypes.c_short),ctypes.c_void_p,ctypes.c_size_t]
    return dll

def expected_swap(name,data):
    out=bytearray(data);regions=[]
    def swap(offset,width):out[offset:offset+width]=out[offset:offset+width][::-1];regions.append((offset,width))
    if name=='phonindex':
        for i in range(0,len(data),2):swap(i,2)
    if name=='phontab':
        offset=4
        for table in range(data[0]):
            count=data[offset];offset+=36
            for j in range(count):swap(offset,4);swap(offset+4,4);swap(offset+8,2);offset+=16
        assert offset==len(data)
    if name=='intonations':
        assert len(data)%68==0
        for i in range(64,len(data),68):swap(i,4)
    if name=='phondata':
        for line in (DATA/'phondata-manifest').read_text().splitlines():
            if not line.startswith('S'):continue
            offset=int(line.split()[1],16);count=data[offset+2];stride=64 if struct.unpack_from('<H',data,offset+4)[0]&1 else 44
            swap(offset,2)
            for i in range(count):
                for j in range(8):swap(offset+4+i*stride+2*j,2)
    return bytes(out),regions

class SpeechContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native=build_engine();cls.application=build_application();build_host_tools();cls.host_objects=build_host_engine();cls.boundary=boundary_library()
    def test_complete_native_engine_and_application(self):
        self.assertTrue(self.native);self.assertTrue(self.application)
    def test_native_abi(self):
        from test_custom_message import coff_symbols
        from prepare_game import lower_c
        folder=OUT/'xdk-application';obj=folder/'native_contract.obj'
        flags=engine_flags()+['/I'+str(GEN/'src/libespeak-ng')]
        pre=subprocess.run(flags+['/E',str(OWN/'native_contract.c')],capture_output=True);self.assertEqual(pre.returncode,0,pre.stderr.decode(errors='replace'))
        lowered,_=lower_c(pre.stdout);source=folder/'native_contract.c';stable(source,lowered.decode())
        invoke(flags+['/c',source,'/Fo'+str(obj)],folder,'native-contract')
        values=struct.unpack('>16I',coff_symbols(obj)['ShipyardSpeechABI'][:64])
        self.assertEqual(values,(16,0,4,8,68,64,64,44,0,2,16,16,2,4,4,4321))
        stable(OUT/'native-abi-verification.json',json.dumps(dict(values=values,object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),native_runtime_executed=False),indent=2)+'\n')
    def test_real_synthesis_and_worker_queue(self):
        original=host_synthesis(False,self.host_objects);projected=host_synthesis(True,self.host_objects);self.assertEqual(original,projected)
        stable(OUT/'synthesis-verification.json',json.dumps(dict(stdout=original,sha256=hashlib.sha256(original.encode()).hexdigest(),native_runtime_executed=False),indent=2)+'\n')
    def test_real_asset_boundaries(self):
        records={}
        for name in ['phontab','phonindex','phondata','intonations']:
            data=(DATA/name).read_bytes();expected,regions=expected_swap(name,data);buffer=ctypes.create_string_buffer(data)
            self.assertEqual(self.boundary.ShipyardSpeechFixupData(buffer,len(data),name.encode(),str(DATA).encode()),1,name)
            self.assertEqual(buffer.raw[:len(data)],expected,name);records[name]=dict(bytes=len(data),converted_fields=len(regions),source_sha256=hashlib.sha256(data).hexdigest())
        buffer=ctypes.create_string_buffer(b'\0'*3)
        for name in ['phontab','phonindex','phondata','intonations','unknown']:self.assertEqual(self.boundary.ShipyardSpeechFixupData(buffer,3,name.encode(),str(DATA).encode()),0,name)
        missing=OUT/'missing-data';missing.mkdir(exist_ok=True);buffer=ctypes.create_string_buffer((DATA/'phondata').read_bytes())
        self.assertEqual(self.boundary.ShipyardSpeechFixupData(buffer,len(buffer)-1,b'phondata',str(missing).encode()),0)
        samples=[0,1,-1,32767,-32768,0x1234,-0x1234];source=ctypes.create_string_buffer(struct.pack('<7h',*samples));target=(ctypes.c_short*7)();self.boundary.ShipyardSpeechPcmToNative(target,source,7);self.assertEqual(list(target),samples)
        stable(OUT/'endian-verification.json',json.dumps(records,indent=2)+'\n')
    def test_production_function_inventory(self):
        from cpp_ast import PARSER,walk
        def names(text):return [n.child_by_field_name('declarator').text.decode().split('(')[0] for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
        for name in ['soh/soh/Enhancements/tts/tts.cpp','soh/soh/Enhancements/randomizer/ShuffleSpeak.cpp','soh/soh/Enhancements/speechsynthesizer/SpeechSynthesizer.cpp','soh/soh/Enhancements/speechsynthesizer/SpeechLogger.cpp']:
            self.assertEqual(names((ROOT/name).read_text(encoding='utf-8-sig')),[n for n in names((OUT/'generated'/name).read_text()) if not n.startswith('ShipyardInitPaths')])
    def test_repeatability(self):
        before=(OUT/'engine-manifest.json').read_bytes();prepare_engine();self.assertEqual(before,(OUT/'engine-manifest.json').read_bytes())

if __name__=='__main__':unittest.main()
