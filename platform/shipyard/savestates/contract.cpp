#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
// Data fixtures use actual game declarations. No game/service functions are supplied.
extern "C" { AudioContext gAudioContext; u8* gAudioHeap; PlayState* gPlayState; }
int main() {
    spdlog::set_pattern("%v");
    SaveStateMgr manager;
    CHECK(manager.GetCurrentSlot()==0);
    CHECK(manager.states.empty() && manager.requests.empty());
    manager.SetCurrentSlot(0xffffffffu);CHECK(manager.GetCurrentSlot()==0xffffffffu);
    gPlayState=nullptr;
    CHECK(manager.AddRequest(SaveStateRequest{3,RequestType::SAVE})==SaveStateReturn::FAIL_WRONG_GAMESTATE);
    CHECK(manager.requests.empty());
    PlayState play={};gPlayState=&play;
    CHECK(manager.AddRequest(SaveStateRequest{3,RequestType::LOAD})==SaveStateReturn::FAIL_INVALID_SLOT);
    CHECK(manager.AddRequest(SaveStateRequest{3,RequestType(9)})==SaveStateReturn::FAIL_BAD_REQUEST);
    CHECK(manager.requests.empty());
    CHECK(manager.AddRequest(SaveStateRequest{8,RequestType::SAVE})==SaveStateReturn::SUCCESS);
    manager.states[3]=std::shared_ptr<SaveState>();
    CHECK(manager.AddRequest(SaveStateRequest{3,RequestType::LOAD})==SaveStateReturn::SUCCESS);
    CHECK(manager.requests.size()==2 && manager.requests.front().slot==8);
    CHECK(manager.requests.front().type==RequestType::SAVE);manager.requests.pop();
    CHECK(manager.requests.front().slot==3 && manager.requests.front().type==RequestType::LOAD);manager.requests.pop();
    SaveState state(std::shared_ptr<SaveStateMgr>(),4);
    CHECK(state.slot==4 && state.info.get()!=nullptr);
    CHECK(state.info->sysHeapCopy[0]==0 && state.info->audioHeapCopy[AUDIO_HEAP_SIZE-1]==0);
    CHECK(state.info->rngSeed==0 && state.info->blueWarpTimerCopy==0);
    std::vector<u8> firstHeap(65536),secondHeap(65536);gAudioHeap=&firstHeap[0];
    for(unsigned i=0;i<4;++i){
        SeqScriptState& s=gAudioContext.seqPlayers[i].scriptState;
        s.value=10+i;s.depth=4;s.pc=gAudioHeap+1000+i*100;
        for(unsigned j=0;j<4;++j){s.remLoopIters[j]=2+i+j;s.stack[j]=gAudioHeap+4000+i*100+j*10;}
    }
    state.BackupSeqScriptState();
    for(unsigned i=0;i<4;++i){
        SeqScriptState& s=state.info->seqScriptStateCopy[i];
        CHECK(reinterpret_cast<uintptr_t>(s.pc)==1000+i*100);
        for(unsigned j=0;j<4;++j)CHECK(reinterpret_cast<uintptr_t>(s.stack[j])==4000+i*100+j*10);
        memset(&gAudioContext.seqPlayers[i].scriptState,0,sizeof(SeqScriptState));
    }
    gAudioHeap=&secondHeap[0];state.LoadSeqScriptState();
    for(unsigned i=0;i<4;++i){
        SeqScriptState& s=gAudioContext.seqPlayers[i].scriptState;
        CHECK(s.value==10+i && s.depth==4 && s.pc==gAudioHeap+1000+i*100);
        for(unsigned j=0;j<4;++j){CHECK(s.remLoopIters[j]==2+i+j);CHECK(s.stack[j]==gAudioHeap+4000+i*100+j*10);}
    }
    printf("slot/requests/defaults: passed; sequence relocation: 4 players, 20 pointers, 16 loop counters\n");
    return 0;
}
