"""Check in-memory autosave blockers before probing the save file.

Interval saves require an unpaused loaded game; soft resets retain their pause
policy. Eligible attempts still check disk so file deletion remains visible.
"""
from source_anchor import replace_once


def project(source):
    source = replace_once(source, 'static bool Autosave_CanSave() {',
                          'static bool Autosave_CanSave(bool requireUnpaused = false) {')
    source = replace_once(source,
        '!GameInteractor::IsSaveLoaded(false) || !SaveManager::Instance->SaveFile_Exist(gSaveContext.fileNum) ||',
        '!GameInteractor::IsSaveLoaded(false) ||')
    source = replace_once(source, '''    return true;
}

static void Autosave_PerformSave()''', '''    if (requireUnpaused && GameInteractor::IsGameplayPaused()) {
        return false;
    }
    return SaveManager::Instance->SaveFile_Exist(gSaveContext.fileNum);
}

static void Autosave_PerformSave()''')
    return replace_once(source, 'Autosave_CanSave() && !GameInteractor::IsGameplayPaused()',
                        'Autosave_CanSave(true)')
