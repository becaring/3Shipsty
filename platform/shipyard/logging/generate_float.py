"""Project fmt12's exact binary32/64 Dragonbox into the fmt4 compiler boundary."""

from pathlib import Path
import hashlib, json, re, importlib.util

BASE = Path(__file__).parent
ROOT = BASE.parents[2]
UP = ROOT / "scratch/deps/spdlog/include/spdlog/fmt/bundled"


def exact(t, a, b, n=1):
    if t.count(a) != n:
        raise ValueError("float projection match: " + a[:80])
    return t.replace(a, b)


def generate(out):
    src = {}
    for name, sha in json.loads((BASE / "float-source-lock.json").read_text()).items():
        raw = (UP / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("Pinned float source changed: " + name)
        src[name] = raw.decode().replace("\r\n", "\n")
    h = src["format.h"]
    impl = src["format-inl.h"]
    mul = h[h.index("FMT_INLINE auto umul128(") : h.index("namespace dragonbox {")]
    mul = mul[: mul.index("#if FMT_USE_INT128")] + mul[mul.index("#else") + len("#else") : mul.index("#endif")] + "}\n"
    decl = h[h.index("namespace dragonbox {") : h.index("// An 80- or 128-bit floating point number.")]
    # The portable multiplier, rather than desktop intrinsics, is used on both
    # differential host and Xenon builds.
    start = decl.index("#if FMT_USE_INT128")
    end = decl.index("#endif", start)
    decl = decl[:start] + decl[decl.index("#else", start) + len("#else") : end] + decl[end + len("#endif") :]
    decl = decl.replace(
        'static_assert((-1 >> 1) == -1, "right shift is not arithmetic");',
        "typedef char arithmetic_shift_required[((-1 >> 1) == -1) ? 1 : -1];",
    )
    decl += """template <typename T> struct decimal_fp { typedef typename float_info<T>::carrier_uint significand_type; \
significand_type significand; int exponent; };
}
"""
    body = impl[
        impl.index("namespace dragonbox {") : impl.index("}  // namespace dragonbox") + len("}  // namespace dragonbox")
    ]
    # Select the upstream full-cache configuration, avoiding runtime compressed
    # cache reconstruction. The entire authoritative 634-entry table is kept.
    start = body.index("#if FMT_USE_FULL_CACHE_DRAGONBOX")
    end = body.index("#endif", start)
    block = body[start:end]
    body = (
        body[:start]
        + block[len("#if FMT_USE_FULL_CACHE_DRAGONBOX") : block.index("#else")]
        + body[end + len("#endif") :]
    )
    # constexpr construction is unavailable in XDK. Keep cache storage a POD
    # constant table, otherwise 634 constructors and an unsafe local-static
    # first-use guard would be introduced on concurrent formatting paths.
    body = exact(
        body, "static constexpr uint128_fallback pow10_significands[]", "static const uint64_t pow10_significands[][2]"
    )
    body = exact(
        body,
        "return pow10_significands[k - float_info<double>::min_k];",
        "const uint64_t* pair = pow10_significands[k - float_info<double>::min_k];\n    return uint128_fallback(pair[0], pair[1]);",
    )
    start = body.index("#if FMT_USE_FULL_CACHE_DRAGONBOX")
    end = body.index("#endif", start)
    block = body[start:end]
    body = (
        body[:start]
        + block[len("#if FMT_USE_FULL_CACHE_DRAGONBOX") : block.index("#else")]
        + body[end + len("#endif") :]
    )
    t = mul + decl + HELPERS + body
    t = re.sub(r"\busing\s+(\w+)\s*=\s*([^;]+);", r"typedef \2 \1;", t)
    t = t.replace("FMT_INLINE_VARIABLE constexpr", "static const").replace("constexpr", "const").replace("noexcept", "")
    t = t.replace("FMT_API", "inline").replace("FMT_FUNC", "inline").replace("FMT_INLINE", "inline")
    # A syntactic transformation only: move trailing return types in front.
    spec = importlib.util.spec_from_file_location("float_language", BASE / "lowering.py")
    lang = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lang)
    data = t.encode()
    edits = []
    for node in lang.walk(lang.PARSER.parse(data).root_node):
        if node.type != "function_declarator":
            continue
        trailing = next((x for x in node.named_children if x.type == "trailing_return_type"), None)
        if not trailing:
            continue
        parent = node.parent
        typ = parent.child_by_field_name("type")
        if typ is None or typ.text != b"auto":
            raise ValueError("Unrecognized trailing return")
        edits.append((typ.start_byte, typ.end_byte, trailing.text[2:].strip()))
        edits.append((trailing.start_byte, trailing.end_byte, b""))
    for a, b, v in sorted(edits, reverse=True):
        data = data[:a] + v + data[b:]
    # Return-list expressions are POD initializations on this compiler.
    edits = []
    for node in lang.walk(lang.PARSER.parse(data).root_node):
        if node.type != "return_statement":
            continue
        val = next((x for x in node.named_children if x.type == "initializer_list"), None)
        if not val:
            continue
        fn = node.parent
        while fn and fn.type != "function_definition":
            fn = fn.parent
        typ = fn.child_by_field_name("type").text.decode()
        if typ == "uint128_fallback":
            v = ("return uint128_fallback(" + val.text.decode()[1:-1] + ");").encode()
        else:
            v = ("{ " + typ + " result = " + val.text.decode() + "; return result; }").encode()
        edits.append((node.start_byte, node.end_byte, v))
    for a, b, v in sorted(edits, reverse=True):
        data = data[:a] + v + data[b:]
    t = data.decode()
    license = h[: h.index("*/") + 2]
    text = (
        license
        + "\n#pragma once\n// Generated from pinned fmt12.\n#include <limits>\n#include <cstring>\n#include <cassert>\nnamespace shipyard_fmt_float {\n"
        + SUPPORT
        + t
        + "\n}\n"
    )
    target = out / "shipyard_fmt_float.h"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_text() != text:
        target.write_text(text)
    source = (ROOT / "scratch/deps/fmt-xdk/fmt/format.h").read_text()
    source = exact(source, "    double double_value;", "    float float_value;\n    double double_value;")
    source = exact(
        source,
        "    DOUBLE, LONG_DOUBLE, LAST_NUMERIC_TYPE = LONG_DOUBLE,",
        "    FLOAT, DOUBLE, LONG_DOUBLE, LAST_NUMERIC_TYPE = LONG_DOUBLE,",
    )
    source = exact(source, "FMT_MAKE_VALUE(float, double_value, DOUBLE)", "FMT_MAKE_VALUE(float, float_value, FLOAT)")
    source = exact(
        source,
        "  BasicWriter &operator<<(double value) {",
        "  BasicWriter &operator<<(float value) { write_double(value, FormatSpec()); return *this; }\n  BasicWriter &operator<<(double value) {",
    )
    source = exact(
        source,
        "  Result visit_double(double value) {",
        "  Result visit_float(float value) { return FMT_DISPATCH(visit_any_double(value)); }\n  Result visit_double(double value) {",
    )
    source = exact(
        source,
        "    case Arg::DOUBLE:",
        "    case Arg::FLOAT:\n      return FMT_DISPATCH(visit_float(arg.float_value));\n    case Arg::DOUBLE:",
    )
    source = exact(
        source,
        "void BasicWriter<Char>::write_double(T value, const Spec &spec) {",
        "void BasicWriter<Char>::write_double(T value, const Spec &spec) {\n"
        + (BASE / "format/default_float_writer.inc").read_text(),
    )
    source = "#include <shipyard_fmt_float.h>\n" + source
    source = exact(source, '# include "format.cc"', "# include <fmt/format.cc>")
    target = out / "fmt/format.h"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_text() != source:
        target.write_text(source)
    (out / "float-manifest.json").write_text(
        json.dumps(
            {
                "sources": json.loads((BASE / "float-source-lock.json").read_text()),
                "algorithm": "fmt12 Dragonbox full cache; portable integer multiplication; distinct binary32/64 arguments",
                "generated_sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )


SUPPORT = """
typedef unsigned int uint32_t;
typedef unsigned __int64 uint64_t;
typedef char ieee_binary32_required[(sizeof(float)==4 && std::numeric_limits<float>::digits==24)?1:-1];
typedef char ieee_binary64_required[(sizeof(double)==8 && std::numeric_limits<double>::digits==53)?1:-1];
typedef char windows_long_double_required[(sizeof(long double)==sizeof(double) && std::numeric_limits<long \
double>::digits==53)?1:-1];
template<class T> struct select_float { typedef double type; };
template<> struct select_float<float> { typedef float type; };
template<class T> inline T max_value() { return (std::numeric_limits<T>::max)(); }
template<class T> inline T rotr(T x, int n) { return (x >> n) | (x << (sizeof(T)*8-n)); }
template<class To,class From> inline To bit_cast(const From& x) { typedef char \
same_size[sizeof(To)==sizeof(From)?1:-1]; To v; std::memcpy(&v,&x,sizeof(v)); return v; }
class uint128_fallback {
    uint64_t lo_,hi_;
public:
    uint128_fallback(uint64_t hi,uint64_t lo):lo_(lo),hi_(hi){}
    uint128_fallback(uint64_t value=0):lo_(value),hi_(0){}
    uint64_t high() const { return hi_; }
    uint64_t low() const { return lo_; }
    uint128_fallback& operator+=(uint64_t n) { lo_+=n; hi_+=(lo_<n?1:0); return *this; }
};
#ifndef FMT_ASSERT
#define FMT_ASSERT(condition,message) assert(condition)
#endif
"""
HELPERS = """
template<class T> inline int num_significand_bits() { return std::numeric_limits<T>::digits-1; }
template<class T> inline int exponent_bias() { return std::numeric_limits<T>::max_exponent-1; }
template<class T> inline typename dragonbox::float_info<T>::carrier_uint exponent_mask() {
    typedef typename dragonbox::float_info<T>::carrier_uint U;
    return ((U(1)<<dragonbox::float_info<T>::exponent_bits)-1)<<num_significand_bits<T>();
}
"""
