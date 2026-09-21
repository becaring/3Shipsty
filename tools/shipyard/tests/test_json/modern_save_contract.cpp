#include <nlohmann/json.hpp>
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
#include <limits>
struct SaveTemplates {
    nlohmann::json* currentJsonContext;
    nlohmann::json::iterator currentJsonArrayContext;
#line 113 "soh/soh/SaveManager.h"
    template <typename T> void SaveData(const std::string& name, const T& data) {
        if (name == "") {
            assert((*currentJsonContext).is_array());
            (*currentJsonContext).push_back(data);
        } else {
            (*currentJsonContext)[name.c_str()] = data;
        }
    }
#line 130 "soh/soh/SaveManager.h"
    template <typename T> void LoadData(const std::string& name, T& data, const T& defaultValue = T{}) {
        if (name == "") {
            if (currentJsonArrayContext == currentJsonContext->end()) {
                // This array member is past the data in the json file. Therefore, default construct it
                data = defaultValue;
            } else {
                currentJsonArrayContext.value().get_to(data);
            }
        } else if (!currentJsonContext->contains(name.c_str())) {
            data = defaultValue;
        } else {
            (*currentJsonContext)[name.c_str()].get_to(data);
        }
    }
};
int main() {
    nlohmann::json save = nlohmann::json::parse("{\"version\":1,\"sections\":{\"base\":{\"version\":4,\"data\":{}},\"randomizer\":{\"version\":3,\"data\":{}}}}");
    SaveTemplates context;
    context.currentJsonContext = &save["sections"]["base"]["data"];
    context.SaveData("healthCapacity", static_cast<short>(80));
    context.SaveData("rupees", static_cast<short>(-3));
    context.SaveData("fileCreatedAt", std::numeric_limits<unsigned long long>::max());
    context.SaveData("filename", std::string("Link"));
    context.SaveData("seed", static_cast<unsigned>(4294967295U));
    std::vector<unsigned> entrances; entrances.push_back(0); entrances.push_back(4294967295U);
    context.SaveData("entrancesDiscovered", entrances);
    nlohmann::json round = nlohmann::json::parse(save.dump(4));
    context.currentJsonContext = &round["sections"]["base"]["data"];
    short health=0, rupees=0; unsigned long long created=0; std::string name;
    context.LoadData("healthCapacity",health); context.LoadData("rupees",rupees);
    context.LoadData("fileCreatedAt",created); context.LoadData("filename",name);
    int defaulted=0;context.LoadData("filenameLanguage",defaulted,2);
    assert(health==80 && rupees==-3 && created==std::numeric_limits<unsigned long long>::max() && name=="Link" && defaulted==2);
    nlohmann::json array=nlohmann::json::array(); context.currentJsonContext=&array;
    context.SaveData("",static_cast<unsigned char>(255));context.SaveData("",std::string("hint"));
    context.currentJsonArrayContext=array.begin(); unsigned char byte=0;context.LoadData("",byte);assert(byte==255);
    ++context.currentJsonArrayContext;context.LoadData("",name);assert(name=="hint");
    ++context.currentJsonArrayContext;context.LoadData("",defaulted,9);assert(defaulted==9);
    std::cout<<round.dump()<<"\n"<<array.dump()<<"\n";
}
