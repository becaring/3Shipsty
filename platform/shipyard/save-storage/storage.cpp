#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include "xenos/native_display.h"
#include "xenos/services.h"
#include <xam.h>
#include <limits.h>
#include <string.h>
namespace Shipyard { namespace Storage {
namespace {
Async::mutex mutex;
bool mounted;
const char* const root = "shipyard";
void Check(DWORD result, const char* operation) {
    if (result != ERROR_SUCCESS) throw Async::native_error(operation, result);
}
void RequireMounted() {
    if (!mounted) throw std::logic_error("Shipyard save storage is not mounted");
}
void Flush() { Check(XContentFlush(root, NULL), "XContentFlush"); }
struct SelectorEvents {
    HANDLE listener;
    unsigned signins;
    bool uiVisible;
    bool cancelled;
    bool profileChanged;
    unsigned user;
    XUID owner;
    explicit SelectorEvents(unsigned selectedUser) : listener(XNotifyCreateListener(XNOTIFY_SYSTEM)),
        signins(0), uiVisible(false), cancelled(false), profileChanged(false),
        user(selectedUser), owner(INVALID_XUID) {
        if(listener==INVALID_HANDLE_VALUE)listener=NULL;
        Poll();
    }
    ~SelectorEvents(){if(listener)CloseHandle(listener);}
    XUID Profile() const {
        XUSER_SIGNIN_INFO info={0};
        if(XUserGetSigninInfo(user,XUSER_GET_SIGNIN_INFO_OFFLINE_XUID_ONLY,&info)!=ERROR_SUCCESS ||
           info.UserSigninState==eXUserSigninState_NotSignedIn)return INVALID_XUID;
        return info.xuid;
    }
    void Poll(){
        DWORD id; ULONG_PTR value;
        while(listener && XNotifyGetNext(listener,0,&id,&value)) {
            if(id==XN_SYS_UI)uiVisible=value!=0;
            else if(id==XN_SYS_SIGNINCHANGED)++signins;
        }
        XINPUT_STATE input={0};
        if(XInputGetState(user,&input)==ERROR_SUCCESS &&
           (input.Gamepad.wButtons&XINPUT_GAMEPAD_B))cancelled=true;
        if(owner!=INVALID_XUID && Profile()!=owner)profileChanged=true;
    }
};
}
void Mount(unsigned userIndex) {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (mounted) return;
    // The retail XAM selector requires an active D3D device and continued
    // presentation. Context/Fast3D is intentionally initialized only later.
    SelectorEvents events(userIndex);
    Fast::InitializeNativeDisplay();
    events.Poll();
    const XUID owner=events.Profile();
    XCONTENT_DATA content = {0};
    ULARGE_INTEGER requested = {0}; requested.QuadPart = 16 * 1024 * 1024;
    DWORD result=ERROR_CANCELLED;
    for(unsigned attempt=0;attempt<2;++attempt) {
        events.Poll();
        if(attempt && (events.uiVisible || events.cancelled || events.profileChanged ||
                       events.Profile()!=owner))break;
        content.DeviceID=XCONTENTDEVICE_ANY;
        XOVERLAPPED selection={0};
        selection.hEvent=CreateEvent(NULL,TRUE,FALSE,NULL);
        if(!selection.hEvent)throw Async::native_error("save device selection event",GetLastError());
        const unsigned signinsBefore=events.signins;
        unsigned signinsPending=signinsBefore;
        result=XShowDeviceSelectorUI(userIndex,XCONTENTTYPE_SAVEDGAME,0,
                                     requested,&content.DeviceID,&selection);
        const DWORD initial=result;
        HRESULT presentation=S_OK;
        if(result==ERROR_IO_PENDING) {
            while(!XHasOverlappedIoCompleted(&selection)) {
                events.Poll();
                signinsPending=events.signins;
                presentation=Fast::PresentNativeStartupUI();
                if(FAILED(presentation)) {
                    XCancelOverlapped(&selection);
                    // XAM retains the device pointer and overlapped on our
                    // stack until its cancellation has completed.
                    while(!XHasOverlappedIoCompleted(&selection))Sleep(1);
                    break;
                }
            }
            result=XGetOverlappedResult(&selection,NULL,FALSE);
            if(FAILED(presentation) && result==ERROR_SUCCESS)result=ERROR_CANCELLED;
        }
        events.Poll();
        Shipyard_Log("storage selector attempt=%u initial=%lu result=%lu extended=%08lx signin_events=%u profile_changed=%d cancel_observed=%d",
                     attempt+1,initial,result,selection.dwExtendedError,
                     events.signins-signinsBefore,events.profileChanged,events.cancelled);
        CloseHandle(selection.hEvent);
        // Hardware-tested Smash360 behavior: XAM can cancel during sign-in
        // notifications while the same offline profile remains signed in.
        // A normal B cancel, changed profile, or failed presentation never retries.
        if(attempt || initial!=ERROR_IO_PENDING || result!=ERROR_CANCELLED ||
           FAILED(presentation) || signinsPending==signinsBefore ||
           events.cancelled || events.profileChanged || owner==INVALID_XUID)break;
        const DWORD hideStart=GetTickCount();
        while(events.uiVisible && DWORD(GetTickCount()-hideStart)<5000) {
            presentation=Fast::PresentNativeStartupUI();
            if(FAILED(presentation))break;
            events.Poll();
        }
        if(events.uiVisible || FAILED(presentation) || events.cancelled ||
           events.profileChanged || events.Profile()!=owner)break;
        Shipyard_Log("storage selection interrupted by sign-in notification; retrying once after UI hide");
    }
    Check(result, "save device selection");
    if (content.DeviceID == XCONTENTDEVICE_ANY)
        throw Async::native_error("no save device selected", ERROR_CANCELLED);
    content.dwContentType = XCONTENTTYPE_SAVEDGAME;
    strcpy_s(content.szFileName, "3Shipsty");
    wcscpy_s(content.szDisplayName, L"Ship of Harkinian");
    Check(XContentCreate(userIndex, root, &content, XCONTENTFLAG_OPENALWAYS, NULL, NULL, NULL), "XContentCreate");
    mounted = true;
}
void RecordBootStage(unsigned stage) {
    static const char* const paths[] = {
        NULL,
        "shipyard:\\boot-1-mounted",
        "shipyard:\\boot-2-preflight",
        "shipyard:\\boot-3-archives",
        "shipyard:\\boot-4-config",
        "shipyard:\\boot-5-logging",
        "shipyard:\\boot-6-context"
    };
    if(stage==0 || stage>=sizeof(paths)/sizeof(paths[0]))return;
    Async::lock_guard<Async::mutex> lock(mutex);
    if(!mounted)return;
    HANDLE file=CreateFileA(paths[stage],GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE){Shipyard_Log("boot stage %u create error=%lu",stage,GetLastError());return;}
    DWORD written=0;
    const DWORD length=static_cast<DWORD>(strlen(paths[stage]));
    const BOOL wrote=WriteFile(file,paths[stage],length,&written,NULL);
    const DWORD writeError=wrote && written==length ? ERROR_SUCCESS : GetLastError();
    const BOOL flushed=FlushFileBuffers(file);
    const DWORD flushError=flushed ? ERROR_SUCCESS : GetLastError();
    CloseHandle(file);
    const DWORD contentError=XContentFlush(root,NULL);
    if(writeError || flushError || contentError)
        Shipyard_Log("boot stage %u write=%lu flush=%lu content=%lu",stage,writeError,flushError,contentError);
}
std::string SaveDirectory() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    return "shipyard:\\Save";
}
void Commit() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted(); Flush();
}
void Replace(const xbox_compat::filesystem::path& temporary,
             const xbox_compat::filesystem::path& destination) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    HANDLE file = CreateFileA(temporary.c_str(), GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) throw Async::native_error("open completed save", GetLastError());
    DWORD error = FlushFileBuffers(file) ? ERROR_SUCCESS : GetLastError();
    if (!CloseHandle(file) && error == ERROR_SUCCESS) error = GetLastError();
    Check(error, "flush completed save");
    if (!MoveFileExA(temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw Async::native_error("replace completed save", GetLastError());
    Flush();
}
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    WriteAtomicFile(destination, bytes); Flush();
}

void Shutdown() {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (!mounted) return;
    Flush(); Check(XContentClose(root, NULL), "XContentClose"); mounted = false;
}
}}
