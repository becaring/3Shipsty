#include <nlohmann/json.hpp>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <locale>
#include <limits>
#include <fstream>
#include <exception>
#include <cstdlib>
using nlohmann::json;
static std::string index_string(size_t n) {
    std::ostringstream s;
    s << n;
    return s.str();
}
static std::string hex(const std::string &s) {
    std::string r;
    const char *h = "0123456789abcdef";
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = s[i];
        r += h[c >> 4];
        r += h[c & 15];
    }
    return r;
}
static void input(const std::string &text, int mode, int initial = 0, bool comments = false) {
    std::istringstream in(text);
    in.unsetf(std::ios::skipws);
    in.setstate(static_cast<std::ios::iostate>(initial));
    json j = "old";
    std::string error = "ok";
    try {
        if (mode == 0) {
            std::istream &r = (in >> j);
            if (&r != &in)
                error = "reference";
        } else
            j = json::parse(in, nullptr, mode == 1, comments);
    } catch (const json::parse_error &e) {
        error = std::string(e.what()) + "/byte=" + index_string(e.byte);
    } catch (const json::exception &e) {
        error = e.what();
    } catch (const std::exception &e) {
        error = std::string("std:") + e.what();
    }
    std::cout << mode << ":" << initial << ":" << comments << ":" << hex(text) << ":" << hex(error) << ":"
              << hex(j.dump()) << ":" << in.rdstate() << ":"
              << hex(std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>())) << "\n";
}
struct BrokenOutput : std::streambuf {
    std::string data;
    size_t limit;
    bool throws;
    BrokenOutput(size_t n, bool t) : limit(n), throws(t) {}
    int_type overflow(int_type c) {
        if (data.size() == limit) {
            if (throws)
                throw std::runtime_error("buffer failure");
            return traits_type::eof();
        }
        data += traits_type::to_char_type(c);
        return c;
    }
    std::streamsize xsputn(const char *p, std::streamsize n) {
        std::streamsize i = 0;
        for (; i < n; ++i)
            if (traits_type::eq_int_type(overflow(traits_type::to_int_type(p[i])), traits_type::eof()))
                break;
        return i;
    }
};
static void output(const json &j, int width, char fill, int initial = 0) {
    std::ostringstream out;
    out << std::hex << std::showbase << std::boolalpha << std::setprecision(2);
    out.fill(fill);
    out.width(width);
    out.setstate(static_cast<std::ios::iostate>(initial));
    std::string error = "ok";
    try {
        std::ostream &r = (out << j);
        if (&r != &out)
            error = "reference";
    } catch (const json::exception &e) {
        error = e.what();
    }
    std::cout << "out:" << width << ":" << int(fill) << ":" << initial << ":" << error << ":" << hex(out.str()) << ":"
              << out.width() << ":" << out.rdstate() << "\n";
}
struct UnbufferedInput : std::streambuf {
    std::string data;
    size_t pos;
    size_t failure;
    UnbufferedInput(const std::string &text, size_t fail) : data(text), pos(0), failure(fail) {}
    int_type underflow() {
        if (pos == failure)
            throw std::runtime_error("input failure");
        return pos == data.size() ? traits_type::eof() : traits_type::to_int_type(data[pos]);
    }
    int_type uflow() {
        int_type c = underflow();
        if (!traits_type::eq_int_type(c, traits_type::eof()))
            ++pos;
        return c;
    }
};
static void exception_input() {
    for (int mask = 0; mask < 2; ++mask)
        for (int mode = 0; mode < 3; ++mode)
            for (size_t fail = 0; fail < 14; ++fail) {
                UnbufferedInput buf("[1,2] trailing", fail);
                std::istream in(&buf);
                if (mask)
                    in.exceptions(std::ios::failbit | std::ios::badbit);
                json j = "old";
                std::string error = "ok";
                try {
                    if (mode == 0)
                        in >> j;
                    else
                        j = json::parse(in, nullptr, mode == 1);
                } catch (const json::exception &e) {
                    error = e.what();
                } catch (const std::exception &e) {
                    error = e.what();
                }
                std::cout << "in-failure:" << mask << ":" << mode << ":" << fail << ":" << hex(error) << ":"
                          << hex(j.dump()) << ":" << in.rdstate() << ":" << buf.pos << "\n";
            }
}
static void file_consumers() {
    // Exact reached statements from the hash-locked modern consumer files.
    const char *tempFile = "stream-save.json";
    json saveBlock = json::parse("{\"version\":1,\"sections\":{\"base\":{\"rupees\":42,\"name\":\"Link\"}}}");
    std::ofstream output(tempFile);
    output << std::setw(1) << saveBlock << std::endl;
    output.close();
    std::ifstream input(tempFile);
    json metaSaveBlock;
    input >> metaSaveBlock;
    std::cout << "save-file:" << metaSaveBlock.dump() << ":" << input.rdstate() << "\n";
    input.close();
    std::ifstream ifs(tempFile);
    json mNestedJson;
    mNestedJson = nlohmann::json::parse(ifs);
    std::cout << "config-file:" << mNestedJson.dump() << ":" << ifs.rdstate() << "\n";
    ifs.close();
    std::ifstream inputFile(tempFile);
    json saveFile;
    inputFile >> saveFile;
    std::cout << "timesplit-stream:" << saveFile.dump() << "\n";
    inputFile.close();
    std::ifstream spoilerFileStream(tempFile);
    nlohmann::json spoilerFileJson;
    spoilerFileStream >> spoilerFileJson;
    std::cout << "seed-stream:" << spoilerFileJson.dump() << "\n";
    spoilerFileStream.close();
}
static void terminated() { std::exit(73); }
struct SyncCounter : std::stringbuf {
    int count;
    SyncCounter() : count(0) {}
    int sync() {
        ++count;
        return 0;
    }
};
static void sentry_contract() {
    SyncCounter tied, written;
    std::ostream tie(&tied), out(&written);
    out.tie(&tie);
    out << std::unitbuf;
    json j = json::parse("[0,-1,1.5,true,null,\"text\",{}]");
    out << std::setw(2) << j;
    std::cout << "output-sentry:" << tied.count << ":" << written.count << ":" << hex(written.str()) << "\n";
    std::istringstream in("x [1] rest");
    in.tie(&tie);
    in.get();
    int before = tied.count;
    json v;
    in >> v;
    std::cout << "input-sentry:" << tied.count - before << ":" << in.gcount() << ":" << v.dump() << ":" << in.rdstate()
              << "\n";
}
int main(int argc, char **argv) {
    if (argc > 1) {
        std::set_terminate(terminated);
        std::istringstream in("123");
        in.exceptions(std::ios::eofbit);
        json j;
        if (argv[1][0] == 'e')
            in >> j;
        else
            j = json::parse(in);
        return 90;
    }
    exception_input();
    file_consumers();
    sentry_contract();
    const char *cases[] = {"",
                           " ",
                           "\n\t\r",
                           "{}",
                           "[]",
                           "null",
                           "true",
                           "false",
                           "123",
                           "1.25",
                           "-1",
                           "{} trailing",
                           "[1] 2",
                           "truefalse",
                           "123x",
                           "12 34",
                           "01",
                           "[1,]tail",
                           "{\"x\":} tail",
                           "{\"x\"!123}tail",
                           "{\"x\":1,\"y\":2e999}tail",
                           "[1,2e999]tail",
                           "[1,truX]tail",
                           "\"text\"rest",
                           "[1,2",
                           "/*a*/[1]/*b*/",
                           "[1]// end"};
    for (size_t n = 0; n < sizeof(cases) / sizeof(*cases); ++n)
        for (int mode = 0; mode < 3; ++mode)
            input(cases[n], mode);
    for (int mode = 0; mode < 3; ++mode) {
        input("/*a*/[1]/*b*/", mode, 0, true);
        input(std::string("\xEF\xBB\xBF") + "{\"x\":1} tail", mode);
        input(std::string("\"a\xFF\"tail"), mode);
        input(std::string("12\0tail", 7), mode);
        input("[1]", mode, std::ios::failbit);
        input("[1]", mode, std::ios::badbit);
        input("[1]", mode, std::ios::eofbit);
    }
    json j = json::parse("{\"a\":[1,true,null,1.23456789],\"empty\":{},\"text\":\"a\\nb\"}");
    for (int w = -1; w < 5; ++w) {
        output(j, w, ' ');
        output(j, w, '\t');
    }
    output(j, 2, '.', std::ios::failbit);
    output(json(std::string("\xC3\xA9\xF0\x9F\x98\x80")), 2, '.');
    for (size_t n = 0; n < 1030; n += 499) {
        output(json(std::string(n, 'x') + "\xFF"), 2, ' ');
        output(json(std::string(n, 'x') + "\xE2\x82"), 2, ' ');
    }
    for (unsigned int c = 0; c < 256; ++c) {
        output(json(std::string(501, 'x') + char(c)), 0, ' ');
        input(std::string("\"") + char(c) + "\"tail", 0);
    }
    json bad = json::object();
    bad["ok"] = 1;
    bad["zz"] = std::string("\xFF");
    output(bad, 1, ' ');
    for (int mask = 0; mask < 2; ++mask)
        for (int t = 0; t < 2; ++t)
            for (size_t limit = 0; limit < 65; ++limit) {
                BrokenOutput buf(limit, t != 0);
                std::ostream out(&buf);
                if (mask)
                    out.exceptions(std::ios::badbit);
                std::string error = "ok";
                try {
                    out << std::setw(1) << j;
                } catch (const std::ios_base::failure &) {
                    error = "io";
                } catch (const std::exception &e) {
                    error = e.what();
                }
                std::cout << "broken:" << mask << ":" << t << ":" << limit << ":" << error << ":" << out.rdstate()
                          << ":" << out.width() << ":" << hex(buf.data) << "\n";
            }
    std::istringstream chain("{}[]true false 12 34");
    for (int n = 0; n < 6; ++n) {
        json v;
        chain >> v;
        std::cout << "chain:" << v.dump() << ":" << chain.rdstate() << "\n";
    }
}
