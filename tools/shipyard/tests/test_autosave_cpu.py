"""Check save eligibility and disk-probe counts across blocked conditions."""
import argparse
from pathlib import Path
from test_backend_cpu import function, host_environment, invoke, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    code = r'''
#include <cassert>
#include <cstdint>
enum {SCENE_CHAMBER_OF_THE_SAGES=1,SCENE_CUTSCENE_MAP=2,QUEST_SONG_TIME=3,ITEM_OCARINA_TIME=4};
bool loaded,paused,exists,quest,ocarina;int probes,saves,pauseChecks;
struct PlayState {unsigned gameplayFrames;int sceneNum;} play,*gPlayState=&play;
struct SaveContext {int fileNum;} gSaveContext={0};
namespace GameInteractor {
 bool IsSaveLoaded(bool){return loaded;}
 bool IsGameplayPaused(){assert(loaded);++pauseChecks;return paused;}
}
struct SaveManager {static SaveManager* Instance;bool SaveFile_Exist(int){++probes;return exists;}} manager;
SaveManager* SaveManager::Instance=&manager;
#define CHECK_QUEST_ITEM(x) quest
#define INV_CONTENT(x) (ocarina ? ITEM_OCARINA_TIME : 0)
uint64_t lastSaveTimestamp=0,now=200000;
const uint64_t THREE_MINUTES_IN_UNIX=180000;
uint64_t GetUnixTimestamp(){return now;}
void Autosave_PerformSave(){++saves;}
'''
    code += '\n'.join(function(source, name) for name in (
        'static bool Autosave_CanSave(', 'static void Autosave_IntervalSave()',
        'static void Autosave_SoftResetSave()'))
    code += r'''
int main(){
 for(unsigned bits=0;bits<256;++bits){
  loaded=(bits&1)!=0;paused=(bits&2)!=0;exists=(bits&4)!=0;quest=(bits&8)!=0;ocarina=(bits&16)!=0;
  play.gameplayFrames=(bits&32)?100:10;play.sceneNum=(bits&64)?SCENE_CHAMBER_OF_THE_SAGES:(bits&128)?SCENE_CUTSCENE_MAP:0;
  gPlayState=loaded?&play:0;
  bool cheap=loaded&&play.gameplayFrames>=60&&play.sceneNum==0&&(quest||!ocarina);
  probes=saves=pauseChecks=0;lastSaveTimestamp=0;now=200000;
  Autosave_IntervalSave();
  assert(saves==(cheap&&!paused&&exists));
  assert(probes==(cheap&&!paused));
  assert(lastSaveTimestamp==(saves?now:0));
  probes=saves=0;Autosave_SoftResetSave();
  assert(saves==(cheap&&exists));assert(probes==cheap);
  probes=saves=0;lastSaveTimestamp=now;Autosave_IntervalSave();
  assert(probes==0&&saves==0);
 }
}
'''
    folder = ROOT / 'scratch/xenon-cpu-audit/autosave/host'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'contract.cpp'
    path.write_text(code)
    compiler, env = host_environment()
    invoke([compiler, '/nologo', '/std:c++20', '/EHsc', path,
            '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')], folder, 'build', env)
    invoke([folder / 'contract.exe'], folder, 'run')
    print('Autosave retains eligibility and probes disk only after cheap blockers pass.')


if __name__ == '__main__':
    main()
