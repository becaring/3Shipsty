#include <nlohmann/json.hpp>
struct Point {float x,y,z;};
NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE(Point,x,y,z)
void probe(){Point p; nlohmann::json j=p; p=j.get<Point>();}
