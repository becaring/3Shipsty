"""Keep install-side Xbox mods discoverable despite a save-container placeholder."""
from prepare_context import prepare, OUT, ROOT

prepare()
source = (OUT / 'generated/src/ship/Context.cpp').read_text()
start = source.index('std::string Context::LocateFileAcrossAppDirs(')
lookup = source[start:source.index('\n}\n', start)]
assert lookup.index('if (path == "mods")') < lookup.index('// app configuration dir')
assert 'xbox_compat::filesystem::is_directory(bundledMods)' in lookup
assert lookup.index('return bundledMods;') < lookup.index('return fpath;')
assert 'if (xbox_compat::filesystem::exists(fpath))' in lookup
application = (ROOT / 'soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
mod_menu = (ROOT / 'soh/soh/Enhancements/mod_menu.cpp').read_text(encoding='utf-8')
assert 'LocateFileAcrossAppDirs("mods", appShortName)' in application
assert 'LocateFileAcrossAppDirs("mods", appShortName)' in mod_menu
print('PASS: Xbox install-side mods precede the save placeholder; both real callers use the lookup')
