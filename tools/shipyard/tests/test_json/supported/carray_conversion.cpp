#include <nlohmann/json.hpp>
#include <sstream>
#include <array>
#include <map>
enum Code { A=1 };
struct Record { int n; };
void to_json(nlohmann::json& j,const Record&r){j["n"]=r.n;}
void from_json(const nlohmann::json& j,Record&r){j.at("n").get_to(r.n);}
void probe(){unsigned char v[3]={1,2,3}; nlohmann::json j=v; j.get_to(v);}
