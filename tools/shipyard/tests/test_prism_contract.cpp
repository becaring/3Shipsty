#include "prism/processor.h"
#include "fast/cc_features.h"
#include "shader_lower.h"
#include "audit.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <spdlog/spdlog.h>
#undef assert
#define assert(condition) do { if(!(condition)) throw std::runtime_error("Assertion: " #condition); } while(0)
#ifdef SHIPYARD_PROJECTED
namespace values=xbox_compat;
#else
namespace values=std;
#endif

std::string AuditTemplate;
values::optional<std::string> AuditInclude(const std::string& path) {
    if(path=="fixture")return std::string("@prism(type='test')\n\nIncluded @{answer}\n");
    return values::nullopt;
}
static void write(const std::string& name,const std::string& value) {
    std::ofstream file(name.c_str(),std::ios::binary);file<<value;
    if(!file.good())throw std::runtime_error("Writing shader fixture failed");
}
static std::string process(const std::string& source) {
    prism::Processor p;prism::ContextItems c;c["answer"]=42;p.populate(c);
    p.bind_include_loader(AuditInclude);p.load(source);return p.process();
}
struct Throwing {
    static int live;static bool fail;int n;
    Throwing(int v=0):n(v){++live;}
    Throwing(const Throwing& o):n(o.n){if(fail)throw std::runtime_error("copy");++live;}
    Throwing(Throwing&& o):n(o.n){if(fail)throw std::runtime_error("move");++live;}
    Throwing& operator=(const Throwing& o){n=o.n;return *this;}
    Throwing& operator=(Throwing&& o){n=o.n;return *this;}
    ~Throwing(){--live;}
};
int Throwing::live=0;bool Throwing::fail=false;
static void valuesTest() {
    prism::ContextTypes c=true;assert(values::get<int>(c)==1);
    c=2.5f;assert(values::get<float>(c)==2.5f);c=std::string("owned");
    prism::ContextTypes copy(c);assert(values::get<std::string>(copy)=="owned");
    prism::ast::ASTTypes ast;assert(values::holds_alternative<prism::ast::VariableNode>(ast));
    prism::ast::QuoteNode quote;quote.value="nineteenth";ast=quote;
    assert(ast.index()==18 && values::get<prism::ast::QuoteNode>(ast).value=="nineteenth");
    bool caught=false;try{values::get<int>(c);}catch(const values::bad_variant_access&){caught=true;}assert(caught);
    values::optional<std::string> opt;assert(!opt.has_value());opt=std::string("shader");
    values::optional<std::string> copied(opt);opt=values::nullopt;assert(!opt.has_value() && copied.value()=="shader");
    {
        values::variant<int,Throwing> source=Throwing(7),dest=9;Throwing::fail=true;caught=false;
        try{dest=std::move(source);}catch(const std::runtime_error&){caught=true;}
        Throwing::fail=false;assert(caught && dest.valueless_by_exception());dest=42;assert(values::get<int>(dest)==42);
    }
    assert(Throwing::live==0);
}
int main(int argc,char**argv) {
    try {
        assert(argc==2);spdlog::set_level(spdlog::level::off);valuesTest();
        std::ifstream file(argv[1],std::ios::binary);std::ostringstream bytes;bytes<<file.rdbuf();AuditTemplate=bytes.str();
        assert(!AuditTemplate.empty());
        const char* scripts[]={"", "plain text\n", "@prism(name='missing type')\nbody\n",
            "@prism(type='test')\n\n@{missing}\n",
            "@prism(type='test')\n\n@if(answer == 42)\nYES\n@else\nNO\n@end\n",
            "@prism(type='test')\n\n@for(i in 0..3)\n@{i}\n@end\n",
            "@prism(type='test')\n\n@include(\"fixture\")\nDONE\n",
            "@prism(type='test')\n\n@include(\"missing\")\n",
            "@prism(type='test')\n\n@{(answer}\n"};
        for(size_t i=0;i<sizeof(scripts)/sizeof(*scripts);++i){
            std::cout<<"script "<<i<<"\n";
            try{std::cout<<process(scripts[i]);}catch(const std::exception&e){std::cout<<"exception "<<e.what()<<"\n";}
        }
        const uint64_t modes[]={0x10001000ULL,0x80008000ULL,0x01080108ULL,0xA1A8A1A8ULL,0xA218A218ULL,
            0x90008000ULL,0xE1EAE1EAULL,0xD1DAD1DA80008000ULL,0xA278A278ULL};
        const uint32_t opts[]={0,1,3,5,9,17,33,65,129,0xF01,0xF001,0xFF1F,0xFFFF};
        unsigned count=0;uint32_t hash=2166136261u;
        for(size_t m=0;m<sizeof(modes)/sizeof(*modes);++m)for(size_t o=0;o<sizeof(opts)/sizeof(*opts);++o)
        for(unsigned flags=0;flags<8;++flags){
            CCFeatures cc={};gfx_cc_get_features(modes[m],opts[o],&cc);size_t floats=0;
            std::string hlsl=Fast::gfx_direct3d_common_build_shader(floats,cc,(flags&1)!=0,(flags&2)!=0,(flags&4)!=0);
            assert(hlsl.find("@{")==std::string::npos && hlsl.find("@if")==std::string::npos);
            size_t expected=4;
            for(int t=0;t<2;++t)if(cc.usedTextures[t])expected+=2+cc.clamp[t][0]+cc.clamp[t][1];
            expected+=cc.opt_fog?4:0;expected+=cc.opt_grayscale?4:0;expected+=cc.numInputs*(cc.opt_alpha?4:3);
            assert(floats==expected);
            for(size_t i=0;i<hlsl.size();++i)hash=(hash^static_cast<unsigned char>(hlsl[i]))*16777619u;
            hash=(hash^static_cast<uint32_t>(floats))*16777619u;
            // Representative actual current templates; Xenos uses no root signature.
            if(!(flags&1) && (o==0 || o==9 || o==11 || o==12)) {
                std::ostringstream name;name<<"shader-"<<count;
                write(name.str()+"-expanded.hlsl",hlsl);
                std::string lowered,error;
                if(!Shipyard_LowerShader(hlsl,lowered,error))throw std::runtime_error(error);
                write(name.str()+"-xenos.hlsl",lowered);
            }
            ++count;
        }
        std::cout<<"Shader cases "<<count<<" hash "<<hash<<"; value ownership and 19-alternative AST pass\n";
        return 0;
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
