#include "ship/Context.h"
#include "ship/window/Window.h"
#include "ship/window/gui/Gui.h"
#include "ship/config/ConsoleVariable.h"
namespace Fast {
void InitializeGuiForXenos(){
    // A fresh controller-driven Xbox installation must be able to open the
    // existing menu. Register preserves any explicit saved user preference.
    Ship::Context::GetInstance()->GetConsoleVariables()->RegisterInteger(CVAR_IMGUI_CONTROLLER_NAV,1);
    // Native backend uses its real device directly; no desktop handle union
    // member is repurposed. The actual current Gui owns windows/fonts/resources.
    Ship::GuiWindowInitData data={0};
    Ship::Context::GetInstance()->GetWindow()->GetGui()->Init(data);
}
}
