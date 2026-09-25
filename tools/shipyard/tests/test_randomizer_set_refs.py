"""Verify selected seed wrappers retain values without copying their sets."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment
from prepare_randomizer_generation import prepare


class SeedSetTests(unittest.TestCase):
    def test_three_selected_wrappers_use_const_references(self):
        prepare()
        base=ROOT/'scratch/randomizer-generation-xdk/generated/soh/soh/Enhancements/randomizer/3drando'
        for name,expected in (('rando_main.cpp',1),('menu.cpp',1),('playthrough.cpp',2),
                              ('rando_main.hpp',1),('menu.hpp',1),('playthrough.hpp',2)):
            text=(base/name).read_text()
            self.assertEqual(text.count('const std::set<RandomizerCheck>& excludedLocations'),expected,name)
            self.assertEqual(text.count('const std::set<RandomizerTrick>& enabledTricks'),expected,name)
        for name in ('rando_main.cpp','menu.cpp','playthrough.cpp'):
            text=(base/name).read_text()
            self.assertNotIn('excludedLocations.insert(',text)
            self.assertNotIn('enabledTricks.insert(',text)
            self.assertNotIn('excludedLocations.erase(',text)
            self.assertNotIn('enabledTricks.erase(',text)
        code=r'''#include <set>
#include <cstdlib>
#include <new>
#include <cstdio>
static int allocations=0;
void* operator new(size_t size){++allocations;void* p=std::malloc(size?size:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void* p) noexcept {std::free(p);}
using Set=std::set<int>;
static int sum(const Set& a,const Set& b){int value=0;for(int n:a)value+=n;for(int n:b)value+=n;return value;}
static int oldThird(Set a,Set b){return sum(a,b);}
static int oldSecond(Set a,Set b){return oldThird(a,b);}
static int oldFirst(Set a,Set b){return oldSecond(a,b);}
static int newThird(const Set& a,const Set& b){return sum(a,b);}
static int newSecond(const Set& a,const Set& b){return newThird(a,b);}
static int newFirst(const Set& a,const Set& b){return newSecond(a,b);}
int main(){Set a,b;for(int i=0;i<7;++i)a.insert(i);for(int i=0;i<4;++i)b.insert(i+10);
    allocations=0;int oldValue=oldFirst(a,b);int oldAllocations=allocations;
    allocations=0;int newValue=newFirst(a,b);int newAllocations=allocations;
    if(oldValue!=newValue||oldAllocations!=39||newAllocations!=0)return 1;
    std::printf("seed wrapper set-node allocations %d -> %d, values equal\n",oldAllocations,newAllocations);return 0;
}
'''
        compiler,env=host_environment()
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as folder:
            out=Path(folder);src=out/'contract.cpp';src.write_text(code)
            exe=out/'contract.exe'
            built=subprocess.run([str(compiler),'/nologo','/EHsc','/MD',str(src),'/Fe:'+str(exe)],
                                 cwd=out,env=env,capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            result=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('allocations 39 -> 0',result.stdout)
