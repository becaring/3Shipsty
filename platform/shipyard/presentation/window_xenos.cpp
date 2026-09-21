#include "window_xenos.h"
#include "native_display.h"
#include "services.h"
#include "input/physical.h"

namespace Fast {
GfxWindowBackendXenos::GfxWindowBackendXenos() : mAllKeysUp(NULL), mRefreshRate(60) {
    mOnFullscreenChanged=NULL; mOnKeyDown=NULL; mOnKeyUp=NULL;
    mOnMouseButtonDown=NULL; mOnMouseButtonUp=NULL; mFullScreen=true;
}
void GfxWindowBackendXenos::Init(const char*,const char*,bool,uint32_t,uint32_t,int32_t,int32_t) {
    InitializeNativeDisplay();
    D3DDISPLAYMODE mode;
    Shipyard_Check(xenos_device->GetDisplayMode(0,&mode),"display mode");
    mPacing.SetRefresh(mode.RefreshRate); mRefreshRate=mode.RefreshRate;
    mIsRunning=true;
}
void GfxWindowBackendXenos::Close(){mIsRunning=false;ShipyardInput_StopPhysicalRumble();}
void GfxWindowBackendXenos::SetKeyboardCallbacks(bool (*down)(int),bool (*up)(int),void (*all)()){mOnKeyDown=down;mOnKeyUp=up;mAllKeysUp=all;}
void GfxWindowBackendXenos::SetMouseCallbacks(bool (*down)(int),bool (*up)(int)){mOnMouseButtonDown=down;mOnMouseButtonUp=up;}
void GfxWindowBackendXenos::SetFullscreenChangedCallback(void (*callback)(bool)){mOnFullscreenChanged=callback;if(callback)callback(true);}
void GfxWindowBackendXenos::SetFullscreen(bool){if(mOnFullscreenChanged)mOnFullscreenChanged(true);}
void GfxWindowBackendXenos::GetActiveWindowRefreshRate(uint32_t* hz){*hz=mRefreshRate;}
// This native target currently exposes controllers, with no pointer device.
// Retained modern mappings receive no invented keyboard or pointer events.
void GfxWindowBackendXenos::SetCursorVisibility(bool){}
void GfxWindowBackendXenos::SetMousePos(int32_t,int32_t){}
void GfxWindowBackendXenos::GetMousePos(int32_t* x,int32_t* y){*x=*y=0;}
void GfxWindowBackendXenos::GetMouseDelta(int32_t* x,int32_t* y){*x=*y=0;}
void GfxWindowBackendXenos::GetMouseWheel(float* x,float* y){*x=*y=0;}
bool GfxWindowBackendXenos::GetMouseState(uint32_t){return false;}
void GfxWindowBackendXenos::SetMouseCapture(bool){}
bool GfxWindowBackendXenos::IsMouseCaptured(){return false;}
void GfxWindowBackendXenos::GetDimensions(uint32_t* w,uint32_t* h,int32_t* x,int32_t* y){*w=1280;*h=720;*x=*y=0;}
void GfxWindowBackendXenos::HandleEvents(){ShipyardInput_PumpGamepads();}
bool GfxWindowBackendXenos::IsFrameReady(){
    if(!mIsRunning)return false;
    uint32_t intervals=mPacing.Next();
    if(!intervals)return false;
    const DWORD values[]={D3DPRESENT_INTERVAL_ONE,D3DPRESENT_INTERVAL_TWO,D3DPRESENT_INTERVAL_THREE,D3DPRESENT_INTERVAL_FOUR};
    if(intervals>4){
        const double until=Shipyard_Time()+double(intervals-4)/mRefreshRate;
        while(Shipyard_Time()<until)Sleep(1);
        intervals=4;
    }
    Shipyard_Check(xenos_device->SetRenderState(D3DRS_PRESENTINTERVAL,values[intervals-1]),"presentation interval");
    ShipyardInput_BeginGamepadPresentation();
    return true;
}
void GfxWindowBackendXenos::SwapBuffersBegin(){Shipyard_Check(xenos_device->Present(NULL,NULL,NULL,NULL),"Present");}
void GfxWindowBackendXenos::SwapBuffersEnd(){}
double GfxWindowBackendXenos::GetTime(){return Shipyard_Time();}
int GfxWindowBackendXenos::GetTargetFps(){return mTargetFps;}
void GfxWindowBackendXenos::SetTargetFps(int fps){if(fps<=0)throw std::invalid_argument("presentation rate must be positive");mPacing.SetRate(fps);mTargetFps=fps;}
void GfxWindowBackendXenos::SetMaxFrameLatency(int frames){Shipyard_Check(xenos_device->SetRenderState(D3DRS_BUFFER2FRAMES,frames>=2),"frame latency");}
const char* GfxWindowBackendXenos::GetKeyName(int){return "Unknown";}
bool GfxWindowBackendXenos::CanDisableVsync(){return false;}
bool GfxWindowBackendXenos::IsRunning(){return mIsRunning;}
void GfxWindowBackendXenos::Destroy(){Close();}
bool GfxWindowBackendXenos::IsFullscreen(){return true;}
}
