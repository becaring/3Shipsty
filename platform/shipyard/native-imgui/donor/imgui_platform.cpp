#include "platform.h"
#include "imgui_xenos.h"
#include "native_window.h"
#include "libultraship/ImGuiImpl.h"
#include "libultraship/Cvar.h"
#include "Lib/ImGui/imgui_internal.h"
#include <xam.h>
#include <math.h>

extern "C" void SoH_KeyboardKeyDown(int);
extern "C" void SoH_KeyboardKeyUp(int);
extern "C" void SoH_KeyboardAllKeysUp();
void SoH_PollGamepadButtons(const XINPUT_STATE&,DWORD);
namespace {
struct Key { WORD vk; int scan; ImGuiKey imgui; const char* name; };
const Key keys[] = {
    {VK_ESCAPE,1,ImGuiKey_Escape,"Escape"},{VK_BACK,14,ImGuiKey_Backspace,"Backspace"},
    {VK_TAB,15,ImGuiKey_Tab,"Tab"},{VK_RETURN,28,ImGuiKey_Enter,"Enter"},
    {VK_SPACE,57,ImGuiKey_Space,"Space"},{VK_CAPITAL,58,ImGuiKey_CapsLock,"Caps Lock"},
    {VK_LEFT,0x14b,ImGuiKey_LeftArrow,"Left"},{VK_RIGHT,0x14d,ImGuiKey_RightArrow,"Right"},
    {VK_UP,0x148,ImGuiKey_UpArrow,"Up"},{VK_DOWN,0x150,ImGuiKey_DownArrow,"Down"},
    {VK_PRIOR,0x149,ImGuiKey_PageUp,"Page Up"},{VK_NEXT,0x151,ImGuiKey_PageDown,"Page Down"},
    {VK_HOME,0x147,ImGuiKey_Home,"Home"},{VK_END,0x14f,ImGuiKey_End,"End"},
    {VK_INSERT,0x152,ImGuiKey_Insert,"Insert"},{VK_DELETE,0x153,ImGuiKey_Delete,"Delete"},
    {VK_LSHIFT,42,ImGuiKey_LeftShift,"Left Shift"},{VK_RSHIFT,54,ImGuiKey_RightShift,"Right Shift"},
    {VK_LCONTROL,29,ImGuiKey_LeftCtrl,"Left Ctrl"},{VK_RCONTROL,0x11d,ImGuiKey_RightCtrl,"Right Ctrl"},
    {VK_LMENU,56,ImGuiKey_LeftAlt,"Left Alt"},{VK_RMENU,0x138,ImGuiKey_RightAlt,"Right Alt"},
    {0x5b,0x15b,ImGuiKey_LeftSuper,"Left Win"},{0x5c,0x15c,ImGuiKey_RightSuper,"Right Win"}, // USB Windows keys; no XDK VK aliases.
    {VK_APPS,0x15d,ImGuiKey_Menu,"Menu"},{VK_SNAPSHOT,0x137,ImGuiKey_PrintScreen,"Print Screen"},
    {VK_SCROLL,70,ImGuiKey_ScrollLock,"Scroll Lock"},{VK_PAUSE,0x159,ImGuiKey_Pause,"Pause"},
    {VK_NUMLOCK,69,ImGuiKey_NumLock,"Num Lock"},
    {VK_OEM_1,39,ImGuiKey_Semicolon,";"},{VK_OEM_PLUS,13,ImGuiKey_Equal,"="},
    {VK_OEM_COMMA,51,ImGuiKey_Comma,","},{VK_OEM_MINUS,12,ImGuiKey_Minus,"-"},
    {VK_OEM_PERIOD,52,ImGuiKey_Period,"."},{VK_OEM_2,53,ImGuiKey_Slash,"/"},
    {VK_OEM_3,41,ImGuiKey_GraveAccent,"`"},{VK_OEM_4,26,ImGuiKey_LeftBracket,"["},
    {VK_OEM_5,43,ImGuiKey_Backslash,"\\"},{VK_OEM_6,27,ImGuiKey_RightBracket,"]"},
    {VK_OEM_7,40,ImGuiKey_Apostrophe,"'"},
    {VK_DIVIDE,0x135,ImGuiKey_KeypadDivide,"Keypad /"},{VK_MULTIPLY,55,ImGuiKey_KeypadMultiply,"Keypad *"},
    {VK_SUBTRACT,74,ImGuiKey_KeypadSubtract,"Keypad -"},{VK_ADD,78,ImGuiKey_KeypadAdd,"Keypad +"},
    {VK_DECIMAL,83,ImGuiKey_KeypadDecimal,"Keypad ."}
};
const int letterScan[] = {30,48,46,32,18,33,34,35,23,36,37,38,50,49,24,25,16,19,31,20,22,47,17,45,21,44};
const int keypadScan[] = {82,79,80,81,75,76,77,71,72,73};
std::map<int,std::string> keyNames;
std::string clipboard;
double lastFrame;
WORD previousButtons;
bool pointerMode;
bool previousMenu;
ImVec2 pointer(640,360);
XOVERLAPPED keyboard;
std::vector<WCHAR> keyboardText, keyboardInitial;
ImGuiID keyboardTarget;
bool keyboardPending;
HANDLE systemEvents;
bool systemUI;
unsigned modifierKeys;
bool modifierTransitions;
const char* GetClipboard(void*) { return clipboard.c_str(); }
void SetClipboard(void*,const char* text) { clipboard=text?text:""; }
Key Translate(WORD vk, BYTE hid) {
    // USB drivers may report the generic modifier VK. HID distinguishes sides.
    if(vk==VK_SHIFT) vk=hid==229?VK_RSHIFT:VK_LSHIFT;
    else if(vk==VK_CONTROL) vk=hid==228?VK_RCONTROL:VK_LCONTROL;
    else if(vk==VK_MENU) vk=hid==230?VK_RMENU:VK_LMENU;
    Key key={vk,0,ImGuiKey_None,""};
    if(vk>='A' && vk<='Z') {key.scan=letterScan[vk-'A'];key.imgui=(ImGuiKey)(ImGuiKey_A+vk-'A');}
    else if(vk>='0' && vk<='9') {key.scan=vk=='0'?11:2+vk-'1';key.imgui=(ImGuiKey)(ImGuiKey_0+vk-'0');}
    else if(vk>=VK_F1 && vk<=VK_F12) {int n=vk-VK_F1;key.scan=n<10?59+n:87+n-10;key.imgui=(ImGuiKey)(ImGuiKey_F1+n);}
    else if(vk>=VK_NUMPAD0 && vk<=VK_NUMPAD9) {key.scan=keypadScan[vk-VK_NUMPAD0];key.imgui=(ImGuiKey)(ImGuiKey_Keypad0+vk-VK_NUMPAD0);}
    else for(unsigned i=0;i<sizeof(keys)/sizeof(keys[0]);++i) if(keys[i].vk==vk) {key=keys[i];break;}
    // XInput reports the same VK for both Return keys; HID distinguishes them.
    if(vk==VK_RETURN && hid==88) {key.scan=0x11c;key.imgui=ImGuiKey_KeypadEnter;}
    return key;
}
void Modifiers(ImGuiIO& io,const Key& key,bool down,WORD flags) {
    unsigned bit=0;
    switch(key.vk) {
        case VK_LSHIFT: bit=1; break; case VK_RSHIFT: bit=2; break;
        case VK_LCONTROL: bit=4; break; case VK_RCONTROL: bit=8; break;
        case VK_LMENU: bit=16; break; case VK_RMENU: bit=32; break;
    }
    if(bit) { modifierTransitions=true; if(down) modifierKeys|=bit; else modifierKeys&=~bit; }
    // Prefer explicit transitions when available. They also keep simultaneous
    // left/right modifiers correct when one side is released. Flags seed the
    // state for a keyboard attached while a modifier is already held.
    io.AddKeyEvent(ImGuiKey_ModShift,modifierTransitions?(modifierKeys&3)!=0:(flags&XINPUT_KEYSTROKE_SHIFT)!=0);
    io.AddKeyEvent(ImGuiKey_ModCtrl,modifierTransitions?(modifierKeys&12)!=0:(flags&XINPUT_KEYSTROKE_CTRL)!=0);
    io.AddKeyEvent(ImGuiKey_ModAlt,modifierTransitions?(modifierKeys&48)!=0:(flags&XINPUT_KEYSTROKE_ALT)!=0);
}
void NativeKeyboard(ImGuiIO& io, WORD buttons) {
    if(keyboardPending && XHasOverlappedIoCompleted(&keyboard)) {
        DWORD status=XGetOverlappedResult(&keyboard,NULL,FALSE);
        keyboardPending=false;
        if(status==ERROR_SUCCESS && GImGui->ActiveId==keyboardTarget && GImGui->InputTextState.ID==keyboardTarget) {
            GImGui->InputTextState.SelectAll();
            if(keyboardText[0]) for(size_t i=0;i<keyboardText.size() && keyboardText[i];++i) io.AddInputCharacterUTF16(keyboardText[i]);
            else {io.AddKeyEvent(ImGuiKey_Backspace,true);io.AddKeyEvent(ImGuiKey_Backspace,false);}
        }
    }
    if(!keyboardPending && io.WantTextInput && (buttons&XINPUT_GAMEPAD_Y) && !(previousButtons&XINPUT_GAMEPAD_Y)) {
        ImGuiInputTextState& state=GImGui->InputTextState;
        if(!state.ID || GImGui->ActiveId!=state.ID) return;
        // Keep the live ImGui field as owner. Confirmed text is fed through its
        // existing edit/undo path when the Xbox native keyboard returns.
        keyboardText.assign(std::max(256,std::min(state.BufCapacityA,65536)),0);
        size_t n=std::min((size_t)state.CurLenW,keyboardText.size()-1);
        for(size_t i=0;i<n;++i) keyboardText[i]=(WCHAR)state.TextW[(int)i];
        keyboardTarget=state.ID;ZeroMemory(&keyboard,sizeof(keyboard));
        keyboardInitial=keyboardText;
        DWORD status=XShowKeyboardUI(0,VKBD_DEFAULT, &keyboardInitial[0],L"Ship of Harkinian",L"Enter text",&keyboardText[0],(DWORD)keyboardText.size(),&keyboard);
        keyboardPending=status==ERROR_IO_PENDING;
        if(status==ERROR_SUCCESS) {keyboardPending=true;} // processed on the next frame
        else if(status!=ERROR_IO_PENDING) SoH_Log("native keyboard error=%lu",status);
    }
}
void Button(ImGuiIO& io,ImGuiKey key,WORD buttons,WORD bit) { io.AddKeyEvent(key,(buttons&bit)!=0); }
void Axis(ImGuiIO& io,ImGuiKey key,float value) { value=std::max(0.0f,std::min(1.0f,value));io.AddKeyAnalogEvent(key,value>.1f,value); }
void LayoutSaveCompleted(bool ok) {
    if(!ok)SohImGui::GetGameOverlay()->TextDrawNotification(6,true,"Could not save menu layout");
}
}

const char* SoH_KeyboardName(int scan) {
    std::map<int,std::string>::iterator it=keyNames.find(scan);
    return it==keyNames.end()?"Unknown":it->second.c_str();
}
bool SoH_InputEditorIsOpen() { return ImGui::GetCurrentContext() && SohImGui::GetInputEditor()->IsOpened(); }
bool SoH_SystemUIActive() { return systemUI || keyboardPending; }
bool SoH_ImGuiCapturesGamepad() { return pointerMode && CVar_GetS32("gOpenMenuBar",0); }
void SoH_ImGuiPlatformInit() {
    ImGuiIO& io=ImGui::GetIO();
    io.BackendPlatformName="SoH360_XInput";
    io.BackendFlags|=ImGuiBackendFlags_HasGamepad;
    io.ConfigFlags|=ImGuiConfigFlags_NavEnableKeyboard;
    io.IniFilename=NULL; io.LogFilename="cache:\\imgui_log.txt";
    io.GetClipboardTextFn=GetClipboard;io.SetClipboardTextFn=SetClipboard;
    std::vector<unsigned char> ini;
    if(SoH_ReadSave("imgui.ini",ini) && !ini.empty()) ImGui::LoadIniSettingsFromMemory((const char*)&ini[0],ini.size());
    for(unsigned i=0;i<sizeof(keys)/sizeof(keys[0]);++i) keyNames[keys[i].scan]=keys[i].name;
    for(int i=0;i<26;++i) keyNames[letterScan[i]]=std::string(1,(char)('A'+i));
    for(int i=0;i<10;++i) {keyNames[i?i+1:11]=std::string(1,(char)('0'+i));keyNames[keypadScan[i]]="Keypad "+std::string(1,(char)('0'+i));}
    for(int i=0;i<12;++i) {char name[8];sprintf_s(name,"F%d",i+1);keyNames[i<10?59+i:87+i-10]=name;}
    keyNames[0x11c]="Keypad Enter";
    lastFrame=SoH_Time();
    systemEvents=XNotifyCreateListener(XNOTIFY_SYSTEM);
    if(!systemEvents) SoH_Fatal("system input notifications",HRESULT_FROM_WIN32(GetLastError()));
}
void SoH_ImGuiPlatformShutdown() {
    // XShowKeyboardUI retains its buffers until the overlapped result completes.
    if(keyboardPending) XGetOverlappedResult(&keyboard,NULL,TRUE);
    keyboardPending=false;
    if(systemEvents) CloseHandle(systemEvents);
    systemEvents=NULL;
    SoH_KeyboardAllKeysUp();
}
void SoH_ImGuiPlatformNewFrame() {
    SoH_PollSaveWrites();
    ImGuiIO& io=ImGui::GetIO();double now=SoH_Time();
    io.DeltaTime=(float)std::max(.000001,now-lastFrame);lastFrame=now;
    io.DisplaySize=ImVec2(1280,720);io.DisplayFramebufferScale=ImVec2(1,1);
    DWORD notification;ULONG_PTR parameter;
    while(XNotifyGetNext(systemEvents,0,&notification,&parameter)) {
        if(notification==XN_SYS_UI) {
            systemUI=parameter!=0;
            // Retain the active ImGui text edit while the native keyboard is
            // open, but release held inputs to avoid stuck keys on return.
            io.ClearInputKeys();SoH_KeyboardAllKeysUp();
            modifierKeys=0;modifierTransitions=false;
            previousButtons=0;
        } else if(notification==XN_SYS_INPUTDEVICESCHANGED || notification==XN_SYS_INPUTDEVICECONFIGCHANGED) {
            io.ClearInputKeys();SoH_KeyboardAllKeysUp();
            modifierKeys=0;modifierTransitions=false;
        }
    }
    if(io.WantSaveIniSettings) {
        size_t size;const char* text=ImGui::SaveIniSettingsToMemory(&size);
        if(!SoH_QueueSettingsWrite("imgui.ini",std::string(text,size),LayoutSaveCompleted))LayoutSaveCompleted(false);
        io.WantSaveIniSettings=false;
    }
    XINPUT_KEYSTROKE event;
    while(XInputGetKeystroke(XUSER_INDEX_ANY,XINPUT_FLAG_KEYBOARD,&event)==ERROR_SUCCESS) {
        // Xenia returns a successful, empty event while a native system UI is
        // active. Do not spin forever waiting for a real transition in it.
        if(!(event.Flags&(XINPUT_KEYSTROKE_KEYDOWN|XINPUT_KEYSTROKE_KEYUP|XINPUT_KEYSTROKE_REPEAT)))break;
        if(systemUI || keyboardPending) continue;
        bool down=(event.Flags&(XINPUT_KEYSTROKE_KEYDOWN|XINPUT_KEYSTROKE_REPEAT))!=0;
        // A keyboard menu shortcut should return focus to menu navigation even
        // if the controller was last used as a pointer.
        if(down && (event.VirtualKey==VK_F1 || (event.VirtualKey==VK_INSERT && !io.WantTextInput))) pointerMode=false;
        Key key=Translate(event.VirtualKey,event.HidCode);
        if(key.imgui!=ImGuiKey_None) io.AddKeyEvent(key.imgui,down);
        Modifiers(io,key,down,event.Flags);
        if(down && (event.Flags&XINPUT_KEYSTROKE_VALIDUNICODE)) io.AddInputCharacterUTF16(event.Unicode);
        if(key.scan) {
            if(down) {SoH_KeyboardKeyDown(key.scan);Ship::Window::GetInstance()->SetLastScancode(key.scan);}
            else SoH_KeyboardKeyUp(key.scan);
        }
    }
    XINPUT_STATE state;ZeroMemory(&state,sizeof(state));DWORD sourceStatus=XInputGetState(0,&state);
    static WORD lastRawButtons;
    if((state.Gamepad.wButtons^lastRawButtons)&XINPUT_GAMEPAD_START)
        SoH_Log("INPUT Start raw=%04x system_ui=%d keyboard=%d menu=%d nav=%d pointer=%d",
            state.Gamepad.wButtons,systemUI,keyboardPending,CVar_GetS32("gOpenMenuBar",0),
            CVar_GetS32("gControlNav",1),pointerMode);
    lastRawButtons=state.Gamepad.wButtons;
    if(systemUI || keyboardPending) ZeroMemory(&state,sizeof(state));
    WORD buttons=state.Gamepad.wButtons;
    SoH_PollGamepadButtons(state,sourceStatus);
    bool menu=CVar_GetS32("gOpenMenuBar",0)!=0;
    bool opened=menu && !previousMenu;
    bool pointerChanged=menu && (buttons&XINPUT_GAMEPAD_RIGHT_THUMB) &&
        (!(previousButtons&XINPUT_GAMEPAD_RIGHT_THUMB) || opened);
    if(pointerChanged) pointerMode=!pointerMode;
    // The desktop starts with mouse focus. On a controller, opening the menu
    // must also put navigation on its menu bar, including after pointer mode.
    if(menu && !pointerMode && (opened || pointerChanged)) {
        ImGuiWindow* window=ImGui::FindWindowByName("Main - Deck");
        if(window) {
            ImGui::FocusWindow(window);
            GImGui->NavLayer=ImGuiNavLayer_Menu;
            ImGui::NavInitWindow(window,true);
            GImGui->NavDisableHighlight=false;
            GImGui->NavDisableMouseHover=true;
        }
    }
    previousMenu=menu;
    Button(io,ImGuiKey_GamepadBack,buttons,XINPUT_GAMEPAD_BACK);
    if(pointerMode && menu) {
        io.ConfigFlags&=~ImGuiConfigFlags_NavEnableGamepad;
        float x=state.Gamepad.sThumbRX,y=state.Gamepad.sThumbRY;
        if(fabsf(x)>8000) pointer.x=std::max(0.0f,std::min(1279.0f,pointer.x+x/32768.0f*900*io.DeltaTime));
        if(fabsf(y)>8000) pointer.y=std::max(0.0f,std::min(719.0f,pointer.y-y/32768.0f*900*io.DeltaTime));
        io.AddMousePosEvent(pointer.x,pointer.y);io.MouseDrawCursor=true;
        io.AddMouseButtonEvent(0,(buttons&XINPUT_GAMEPAD_A)!=0);io.AddMouseButtonEvent(1,(buttons&XINPUT_GAMEPAD_B)!=0);
        float scroll=(state.Gamepad.bLeftTrigger-state.Gamepad.bRightTrigger)/255.0f;
        if(fabsf(scroll)>.1f) io.AddMouseWheelEvent(0,scroll*8*io.DeltaTime);
    } else {
        if(menu && CVar_GetS32("gControlNav",1)) io.ConfigFlags|=ImGuiConfigFlags_NavEnableGamepad;
        else io.ConfigFlags&=~ImGuiConfigFlags_NavEnableGamepad;
        io.AddMousePosEvent(-FLT_MAX,-FLT_MAX);
        io.AddMouseButtonEvent(0,false);io.AddMouseButtonEvent(1,false);io.MouseDrawCursor=false;
    }
    WORD nav=pointerMode&&menu?0:buttons;
    Button(io,ImGuiKey_GamepadStart,nav,XINPUT_GAMEPAD_START);
    Button(io,ImGuiKey_GamepadFaceDown,nav,XINPUT_GAMEPAD_A);Button(io,ImGuiKey_GamepadFaceRight,nav,XINPUT_GAMEPAD_B);
    Button(io,ImGuiKey_GamepadFaceLeft,nav,XINPUT_GAMEPAD_X);Button(io,ImGuiKey_GamepadFaceUp,nav,XINPUT_GAMEPAD_Y);
    Button(io,ImGuiKey_GamepadDpadLeft,nav,XINPUT_GAMEPAD_DPAD_LEFT);Button(io,ImGuiKey_GamepadDpadRight,nav,XINPUT_GAMEPAD_DPAD_RIGHT);
    Button(io,ImGuiKey_GamepadDpadUp,nav,XINPUT_GAMEPAD_DPAD_UP);Button(io,ImGuiKey_GamepadDpadDown,nav,XINPUT_GAMEPAD_DPAD_DOWN);
    Button(io,ImGuiKey_GamepadL1,nav,XINPUT_GAMEPAD_LEFT_SHOULDER);Button(io,ImGuiKey_GamepadR1,nav,XINPUT_GAMEPAD_RIGHT_SHOULDER);
    Button(io,ImGuiKey_GamepadL3,nav,XINPUT_GAMEPAD_LEFT_THUMB);Button(io,ImGuiKey_GamepadR3,nav,XINPUT_GAMEPAD_RIGHT_THUMB);
    float x=pointerMode&&menu?0:state.Gamepad.sThumbLX,y=pointerMode&&menu?0:state.Gamepad.sThumbLY;
    Axis(io,ImGuiKey_GamepadLStickLeft,(-x-8000)/24767);Axis(io,ImGuiKey_GamepadLStickRight,(x-8000)/24767);
    Axis(io,ImGuiKey_GamepadLStickUp,(y-8000)/24767);Axis(io,ImGuiKey_GamepadLStickDown,(-y-8000)/24767);
    Axis(io,ImGuiKey_GamepadL2,state.Gamepad.bLeftTrigger/255.0f);Axis(io,ImGuiKey_GamepadR2,state.Gamepad.bRightTrigger/255.0f);
    NativeKeyboard(io,buttons);
    previousButtons=buttons;
}
