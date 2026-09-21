#include "soh/Enhancements/randomizer/SeedContext.h"
#include "soh/Enhancements/randomizer/trial.h"
#include <cstddef>

typedef char pointer_width[sizeof(void*) == 4 ? 1 : -1];
typedef char option_value_width[sizeof(Rando::OptionValue) == 1 ? 1 : -1];
typedef char full_context_layout[sizeof(Rando::Context) > sizeof(Rando::Hint) * RH_MAX + sizeof(Rando::ItemLocation) * RC_MAX ? 1 : -1];
typedef char hash_width[sizeof(((Rando::Context*)0)->hashIconIndexes) == 5 ? 1 : -1];
Rando::OptionValue& (Rando::Context::*option_signature)(RandomizerSettingKey) = &Rando::Context::GetOption;
void (Rando::Context::*ordered_hint_signature)(nlohmann::ordered_json&) = &Rando::Context::WriteHintJson;
extern "C" unsigned long shipyard_randomizer_layout[] = { sizeof(Rando::Context), sizeof(Rando::Hint), sizeof(Rando::ItemLocation), sizeof(CustomMessage), sizeof(Text), sizeof(Rando::TrialInfo), sizeof(Rando::Trials) };

void shipyard_randomizer_inline_defaults() {
    Text text;
    CustomMessage message;
    Rando::OptionValue value;
}
