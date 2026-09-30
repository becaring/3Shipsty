#include <cassert>
#include <cstdio>
#include <cstring>
namespace Rando {
struct Contract {
    static void Zeroed(const Option &o) {
        assert(o.key == 0 && o.widgetType == 0 && o.widgetInfo.cVar == nullptr && o.widgetInfo.type == 0);
        assert(o.contextSelection == 0 && o.delayedSelection == 0 && !o.hidden);
        assert(o.category == OptionCategory::Setting && o.defaultOption == 0 && !o.defaultHidden);
        assert(o.imFlags == IMFLAG_NONE && !o.disabled && o.disabledText.empty());
        assert(o.name.empty() && o.options.empty() && o.cvarName.empty() && o.description.empty());
        assert(o.optionsTextToVar.empty() && o.optionsMap.empty() && !o.widgetOptions && !o.callback);
    }
    static void Dump(const std::vector<std::string> &values) {
        printf("S %zu", values.size());
        for (const auto &value : values) {
            printf(" :");
            for (unsigned char c : value)
                printf("%02x", c);
        }
        printf("\n");
    }
    static void Dump(const std::set<Tricks::Tag> &values) {
        printf("T %zu", values.size());
        for (const auto &value : values) {
#ifdef SHIPYARD_SETTINGS_PROJECTED
            printf(" %d", value.GetValue());
#else
            printf(" %d", int(value));
#endif
        }
        printf("\n");
    }
    template <class T> static void DumpPointers(const std::vector<T *> &values, T *base, size_t count) {
        printf("P %zu", values.size());
        for (auto *value : values) {
            auto index = value - base;
            assert(index >= 0 && size_t(index) < count);
            printf(" %zu", size_t(index));
        }
        printf("\n");
    }
    static int Run() {
        Settings *s = new Settings;
        assert(!s->mContext && s->mTricksByArea.empty() && s->mTrickNameToEnum.empty());
        assert(s->mExcludeLocationsOptionsAreas.size() == RCAREA_INVALID);
        for (const auto &o : s->mOptions)
            Zeroed(o);
        for (const auto &t : s->mTrickSettings) {
            Zeroed(t);
            assert(t.mQuest == 0 && t.mArea == 0);
        }
        for (const auto &g : s->mOptionGroups)
            assert(g.mName.empty() && g.mOptions.empty() && g.mSubGroups.empty() && !g.mDisabled &&
                   g.mContainerType == WidgetContainerType::BASIC);
        for (const auto &d : s->mOptionDescriptions)
            assert(d.empty());
        auto &mOptions = s->mOptions;
        auto &mOptionGroups = s->mOptionGroups;
        /* LIST_EXPRESSIONS */
        auto full = NumOpts(0, 999);
        assert(full.size() == 1000 && full.front() == "0" && full.back() == "999");
        auto values = NumOpts(-8, 9, 3, "pre", "post");
        assert(values.size() == 6 && values[0] == "pre-8post" && values[5] == "pre7post");
        std::vector<std::vector<std::string>> lists;
        lists.push_back(values);
        lists.push_back(std::vector<std::string>());
        lists.push_back(values);
        auto flat = MultiVecOpts(lists);
        assert(flat.size() == 12);
        for (size_t i = 0; i < 12; ++i)
            assert(flat[i] == values[i % 6]);
        // Typed builders preserve list evaluation order, repeated values, and
        // owned strings independently of the temporary container builder.
        int order = 0;
        auto ordered = Shipyard::RandomizerSettings::Vector<int>(3).Add(order++).Add(order++).Add(order++).Take();
        assert(ordered[0] == 0 && ordered[1] == 1 && ordered[2] == 2);
        auto unique = Shipyard::RandomizerSettings::Set<int>().Add(3).Add(1).Add(3).Take();
        assert(unique.size() == 2 && *unique.begin() == 1);
        delete s;
        return 0;
    }
};
}
int main() { return Rando::Contract::Run(); }
