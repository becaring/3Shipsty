"""Keep resolution buttons on the existing percentage widget and update callback."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_soh_menus import project

def main():
    source = (ROOT / 'soh/soh/SohGui/SohMenuSettings.cpp').read_text(encoding='utf-8-sig')
    output = project('SohMenuSettings.cpp', source)
    def widget(text):
        start = text.index('    AddWidget(path, "Internal Resolution",')
        return text[start:text.index('\n#ifndef __WIIU__', start)]
    original, actual = widget(source), widget(output)
    # Exact comparison protects range, percentage formatting, CVar, disables,
    # and the immediate renderer callback from accidental replacement.
    expected = original.replace('.ShowButtons(false)', '.ShowButtons(true)')
    expected = expected.replace('FloatSliderOptions()', 'FloatSliderOptions(Shipyard::SohUI::ValueInit())')
    assert actual == expected
    assert '.Min(0.5f)' in actual and '.Max(2.0f)' in actual
    assert '.IsPercentage()' in actual and 'SetResolutionMultiplier(' in actual
    options = (ROOT / 'soh/soh/SohGui/UIWidgets.hpp').read_text()
    assert 'float step = 0.01f;' in options
    print('Resolution controls: existing callback/range and one-percent step retained')

if __name__ == '__main__':
    main()
