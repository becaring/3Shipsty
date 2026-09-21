#pragma once
#include "soh/SaveManager.h"
// XDK nested capture frontend defect: namespace function access avoids a
// spurious implicit __this capture for the actual static singleton member.
inline SaveManager* ShipyardSaveInstance() { return SaveManager::Instance; }
