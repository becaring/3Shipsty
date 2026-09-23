"""Source-level regression checks for the hardware XAM selector contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
storage = (ROOT / 'platform/shipyard/save-storage/storage.cpp').read_text()
display = (ROOT / 'platform/shipyard/xenos/api.inc').read_text()

mount = storage[storage.index('void Mount(unsigned userIndex)'):storage.index('std::string SaveDirectory()')]
assert mount.index('SelectorEvents events(userIndex)') < mount.index('Fast::InitializeNativeDisplay()')
assert mount.index('Fast::InitializeNativeDisplay()') < mount.index('XShowDeviceSelectorUI(')
assert 'XGetOverlappedResult(&selection, NULL, TRUE)' not in mount
assert mount.index('XHasOverlappedIoCompleted(&selection)') < mount.index('Fast::PresentNativeStartupUI()')
assert mount.index('Fast::PresentNativeStartupUI()') < mount.index('XGetOverlappedResult(&selection,NULL,FALSE)')
assert mount.index('XCancelOverlapped(&selection)') < mount.index('CloseHandle(selection.hEvent)')
for guard in ('initial!=ERROR_IO_PENDING', 'result!=ERROR_CANCELLED',
              'signinsPending==signinsBefore', 'events.cancelled',
              'events.profileChanged', 'owner==INVALID_XUID',
              'events.Profile()!=owner', 'events.uiVisible'):
    assert guard in mount, guard
assert mount.index('CloseHandle(selection.hEvent)') < mount.index('XContentCreate(')
assert 'if(!xenos_device || !buffers.empty())return E_UNEXPECTED;' in display
assert 'xenos_device->Present(NULL,NULL,NULL,NULL)' in display
print('PASS: native display precedes selector; pending XAM UI is presented; retry is bounded to same-profile sign-in interruption')
