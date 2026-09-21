#include "ship/window/gui/GuiElement.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>

class Element : public Ship::GuiElement {
public:
    Element() : initializations(0), updates(0), visibilityCalls(0), failOnce(true) {}
    explicit Element(bool visible) : GuiElement(visible), initializations(0), updates(0), visibilityCalls(0), failOnce(false) {}
    int initializations, updates, visibilityCalls;
    bool failOnce;
    void Draw() { DrawElement(); }
    void DrawElement() {}
protected:
    void InitElement() { ++initializations; if (failOnce) { failOnce=false; throw std::runtime_error("retry"); } }
    void UpdateElement() { ++updates; }
    void SetVisibility(bool visible) { ++visibilityCalls; GuiElement::SetVisibility(visible); }
};

int main() {
    Element first;
    assert(!first.IsVisible() && !first.IsInitialized());
    try { first.Init(); assert(false); } catch (const std::runtime_error&) {}
    assert(!first.IsInitialized() && first.initializations==1);
    first.Init(); first.Init();
    assert(first.IsInitialized() && first.initializations==2);
    first.Update(); first.Show(); first.Update(); first.Hide(); first.ToggleVisibility();
    assert(first.IsVisible() && first.visibilityCalls==3 && first.updates==2);
    Element visible(true); visible.Init(); visible.Hide(); visible.Update();
    assert(!visible.IsVisible() && visible.IsInitialized() && visible.initializations==1 && visible.updates==1);
    std::puts("GUI element initialization/retry, visibility dispatch and hidden updates agree");
}
