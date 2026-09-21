#include <cassert>
#include <cstring>
#include <iostream>
int main() {
    StateFixture state;
    state.InitElement();
    assert(state.mGameInputBlockTimer == INT32_MAX && state.mMappingInputBlockTimer == INT32_MAX);
    assert(!state.TestingRumble() && !state.mInputEditorPopupOpen && !state.mRumbleMappingToTest);
    assert(state.buttons.size() == 15 && state.buttonNames.size() == 15);
    assert(state.mButtonsBitmasks.size() == 10 && state.mDpadBitmasks.size() == 4);
    assert(state.mModifierButtonsBitmasks.size() == 2 && state.mCustomOcarinaButtonsBitmasks.size() == 5);
    const std::set<N64ButtonMask>* sets[] = {&state.mButtonsBitmasks, &state.mDpadBitmasks,
        &state.mModifierButtonsBitmasks, &state.mCustomOcarinaButtonsBitmasks};
    for (unsigned i = 0; i < 4; ++i) {
        for (std::set<N64ButtonMask>::const_iterator p = sets[i]->begin(); p != sets[i]->end(); ++p)
            std::cout << i << ':' << *p << '\n';
    }
    for (std::list<std::pair<N64ButtonMask,const char*> >::const_iterator p = state.buttons.begin(); p != state.buttons.end(); ++p) {
        assert(state.buttonNames[p->first]->first == p->first);
        std::cout << p->first << ':' << p->second << '\n';
    }
    state.addButtonName(BTN_A, "replacement A");
    assert(state.buttons.size() == 16 && state.buttonNames.size() == 15);
    assert(std::strcmp(state.buttons.front().second, "A") == 0);
    assert(std::strcmp(state.buttonNames[BTN_A]->second, "replacement A") == 0);
    state.addButtonName(0x80000000u, "high bit");
    assert(state.buttonNames[0x80000000u]->first == 0x80000000u);
    state.mRumbleTimer = 0; assert(state.TestingRumble());
    state.mRumbleTimer = 1; assert(state.TestingRumble());
    state.mRumbleTimer = INT32_MAX; assert(!state.TestingRumble());
    for (int device = -1; device <= 4; ++device) {
        ImVec4 normal,hover;
        state.GetButtonColorsForDeviceType((Ship::PhysicalDeviceType)device, normal, hover);
        std::cout << device << ':' << normal.x << ',' << normal.y << ',' << normal.z << ',' << normal.w
                  << ':' << hover.x << ',' << hover.y << ',' << hover.z << ',' << hover.w << '\n';
    }
    std::cout << "actual initialization, ordered names, mask widths, rumble sentinel and device colors agree\n";
}
