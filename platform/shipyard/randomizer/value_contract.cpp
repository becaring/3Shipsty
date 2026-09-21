int main() {
    using namespace Rando;
    for (unsigned i = 0; i < 256; ++i) {
        OptionValue value;
        assert(value.Get() == 0 && !value);
        value.Set(static_cast<uint8_t>(i));
        assert(value.Get() == i && value.Is(i) && value.IsNot(i + 256));
        assert(static_cast<bool>(value) == (i != 0));
        OptionValue direct(static_cast<uint8_t>(i));
        assert(direct.Get() == i && static_cast<bool>(direct) == (i != 0));
    }
    Text empty;
    assert(empty.english.empty() && empty.french.empty() && empty.german.empty() && empty.spanish.empty());
    Text text("apple", "pomme", "Apfel");
    assert(text.GetSpanish() == "apple");
    assert(text.GetForLanguage(0) == "apple" && text.GetForLanguage(1) == "Apfel" && text.GetForLanguage(2) == "pomme");
    Text four("apple", "pomme", "Apfel", "manzana");
    assert(four.spanish.empty() && four.GetSpanish() == "apple");
    Text sum = text + "!";
    assert(sum.GetEnglish() == "apple!" && sum.GetFrench() == "pomme!" && sum.GetGerman() == "Apfel!");
    text.Replace("apple", "pear");
    assert(text.GetEnglish() == "pear" && text.GetSpanish() == "pear");
    Text plural("|a|two| apples"); plural.SetForm(PLURAL);
    assert(plural.GetEnglish() == "two apples");
    Text singular("|one|many| apples"); singular.SetForm(SINGULAR);
    assert(singular.GetEnglish() == "one apples");
    assert(Text("apple").Capitalize().GetEnglish() == "Apple");

    ItemOverride overrideValue;
    assert(overrideValue.GetLocation() == RC_UNKNOWN_CHECK && overrideValue.LooksLike() == RG_NONE);
    overrideValue.SetLocation(static_cast<RandomizerCheck>(1));
    overrideValue.RefLooksLike() = static_cast<RandomizerGet>(1);
    overrideValue.SetTrickName(Text("test"));
    assert(overrideValue.GetLocation() == 1 && overrideValue.LooksLike() == 1 && overrideValue.GetTrickName() == "test");
    ItemOverride explicitOverride(static_cast<RandomizerCheck>(2), static_cast<RandomizerGet>(3));
    assert(explicitOverride.GetLocation() == 2 && explicitOverride.LooksLike() == 3);

    for (unsigned i = 0; i < 2; ++i) {
        ItemLocation location = i ? ItemLocation(static_cast<RandomizerCheck>(7)) : ItemLocation();
        assert(location.GetRandomizerCheck() == (i ? 7 : RC_UNKNOWN_CHECK));
        assert(location.hintedBy.empty() && !location.hintAccesible && !location.isHintable && !location.addedToPool);
        assert(location.placedItem == RG_NONE && location.delayedItem == RG_NONE);
        assert(location.excludedOption.Get() == RO_LOCATION_INCLUDE && location.price == 0);
        assert(location.parentRegion == RR_NONE && location.areas.empty() && !location.hasCustomPrice);
        assert(!location.hidden && !location.visibleInImGui && !location.wothCandidate && !location.barrenCandidate);
        assert(location.status == RCSHOW_UNCHECKED && !location.isSkipped && !location.isAvailable);
        location.SetAsHintable(); assert(location.IsHintable());
        location.SetHidden(true); assert(!location.IsHintable());
        location.SetHidden(false); assert(location.IsHintable());
        location.SetPrice(25); location.SetCustomPrice(77); location.SetPrice(100); assert(location.price == 77);
        location.SetExcludedOption(RO_LOCATION_EXCLUDE); assert(location.IsExcluded());
        location.SetVisible(true); location.AddToPool(); location.SetAvailable(true);
        location.SetDelayedItem(static_cast<RandomizerGet>(5)); location.SaveDelayedItem();
        assert(location.RefPlacedItem() == 5 && location.delayedItem == RG_NONE);
        location.ResetVariables();
        assert(!location.IsAddedToPool() && location.placedItem == RG_NONE && !location.IsHintable());
        assert(location.IsVisible() && location.IsExcluded()); // Upstream reset preserves these options.
        assert(location.price == 0 && !location.HasCustomPrice() && !location.IsAvailable());
    }

    TrialInfo trial;
    assert(trial.IsSkipped() && !trial.IsRequired());
    trial.SetAsRequired(); assert(trial.IsRequired());
    trial.SetAsSkipped(); assert(trial.IsSkipped());
    TrialInfo named(static_cast<RandomizerHintTextKey>(1), static_cast<TrialKey>(2));
    assert(named.IsSkipped() && named.GetNameKey() == 1 && named.GetTrialKey() == 2);

    Hint hint;
    assert(hint.ownKey == RH_NONE && hint.hintType == HINT_TYPE_HINT_KEY && hint.distribution.empty());
    assert(hint.hintKeys.empty() && hint.locations.empty() && hint.areas.empty() && hint.trials.empty());
    assert(!hint.yourPocket && hint.num == 0 && hint.messages.empty() && hint.items.empty() && !hint.enabled);
    assert(hint.itemNamesChosen.empty() && hint.hintTextsChosen.empty() && hint.areaNamesChosen.empty());
    std::vector<CustomMessage> messages(2);
    Hint messageHint(static_cast<RandomizerHint>(1), messages);
    assert(messageHint.IsEnabled() && messageHint.GetHintType() == HINT_TYPE_MESSAGE && messageHint.messages.size() == 2);
    messageHint.ResetVariables();
    assert(!messageHint.IsEnabled() && messageHint.messages.empty() && messageHint.ownKey == RH_NONE);

    CustomMessage message;
    assert(message.messages.size() == 3 && message.messages[0].empty());
    assert(message.messages[1] == TODO_TRANSLATE && message.messages[2] == TODO_TRANSLATE);
    assert(message.type == TEXTBOX_TYPE_BLACK && message.position == TEXTBOX_POS_BOTTOM);
    assert(message.colors.empty() && message.capital.empty());
    CustomMessage english("english");
    assert(english.messages[0] == "english" && english.messages[1] == TODO_TRANSLATE);
    CustomMessage translated("english", "german", "french", TEXTBOX_TYPE_BLUE, TEXTBOX_POS_TOP);
    assert(translated.messages[0] == "english" && translated.messages[1] == "german" && translated.messages[2] == "french");
    assert(translated.type == TEXTBOX_TYPE_BLUE && translated.position == TEXTBOX_POS_TOP);
    std::vector<std::string> colors(2, "red"); std::vector<bool> caps(2, true);
    CustomMessage colored("english", colors, caps, TEXTBOX_TYPE_BLUE, TEXTBOX_POS_TOP);
    assert(colored.messages[1] == TODO_TRANSLATE && colored.colors == colors && colored.capital == caps);
    CustomMessage all("english", "german", "french", colors, caps, TEXTBOX_TYPE_BLUE, TEXTBOX_POS_TOP);
    assert(all.messages[2] == "french" && all.colors == colors && all.capital == caps);
    CustomMessage fromText(Text("english", "french", "german"));
    assert(fromText.messages[1] == "german" && fromText.messages[2] == "french");
    SHIPYARD_LAYOUT_PRINTS
    puts("randomizer value/default contracts passed");
}
