#include <nlohmann/json.hpp>
#include <sstream>
#include <array>
#include <map>
enum Code { A=1 };
struct Record { int n; };
void to_json(nlohmann::json& j,const Record&r){j["n"]=r.n;}
void from_json(const nlohmann::json& j,Record&r){j.at("n").get_to(r.n);}
void probe(){std::map<std::string,int> m; nlohmann::json j=m; m=j.get<std::map<std::string,int>>();}
