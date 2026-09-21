#pragma once
#include "ship/debug/Console.h"
namespace Shipyard { namespace GuiCompat {
inline Ship::CommandEntry MakeCommand(Ship::CommandHandler handler,const std::string& description,
                                      const std::vector<Ship::CommandArgument>& arguments){
    Ship::CommandEntry value;
    value.Handler=handler;value.Description=description;value.Arguments=arguments;return value;
}
}}
