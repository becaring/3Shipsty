#include "async/native.h"
#include <spdlog/spdlog.h>
#include <spdlog/async.h>
#include <spdlog/sinks/base_sink.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <sstream>

struct Capture : spdlog::sinks::base_sink<Shipyard::Async::mutex> {
    std::vector<std::string> lines;
    unsigned flushes;
    bool blockFirst;
    Shipyard::Async::manual_reset_event entered, release;
    Capture() : flushes(0), blockFirst(false), entered(false), release(false) {}
    void sink_it_(const spdlog::details::log_msg &msg) {
        if (blockFirst) {
            blockFirst = false;
            entered.set();
            release.wait();
        }
        spdlog::memory_buf_t buffer;
        formatter_->format(msg, buffer);
        lines.push_back(std::string(buffer.data(), buffer.size()));
    }
    void flush_() { ++flushes; }
};
static std::string contents(const std::string &p) {
    std::ifstream file(p.c_str(), std::ios::binary);
    std::ostringstream out;
    out << file.rdbuf();
    return out.str();
}
struct CountedInteger {
    int *conversions;
    explicit CountedInteger(int &count) : conversions(&count) {}
    operator int() const {
        ++*conversions;
        return 42;
    }
};
#if ORIGINAL_SPDLOG
template <> struct fmt::formatter<CountedInteger> : fmt::formatter<int> {
    auto format(const CountedInteger &value, fmt::format_context &ctx) const {
        return fmt::formatter<int>::format(static_cast<int>(value), ctx);
    }
};
#endif
int main(int argc, char **argv) {
    assert(argc == 2);
    std::string path = std::string(argv[1]) + "/rotation.log";
    assert(spdlog::default_logger() != nullptr);
    spdlog::default_logger()->set_pattern("%v");
    SPDLOG_INFO("pre-init diagnostic {}", 42);
    std::shared_ptr<Capture> capture(new Capture);
    spdlog::logger sync("sync", capture);
    sync.set_pattern("[%n] [%@] [%l] %v");
    sync.flush_on(spdlog::level::info);
    sync.log(spdlog::source_loc("unit.cpp", 17, "Test"), spdlog::level::info, "{} {:08X}", "owned", 42);
    assert(capture->lines[0] == "[sync] [unit.cpp:17] [info] owned 0000002A\n");
    assert(capture->flushes == 1);
    sync.set_level(spdlog::level::warn);
    sync.info("filtered");
    assert(capture->lines.size() == 1);
    int conversions = 0;
    CountedInteger counted(conversions);
    sync.info("filtered argument {}", counted);
    sync.log(spdlog::source_loc("filter.cpp", 1, "filter"), spdlog::level::info, "filtered argument {}", counted);
    sync.log(spdlog::level::info, "filtered argument {}", counted);
    sync.info("{16}", 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, counted);
    spdlog::default_logger()->set_level(spdlog::level::off);
    spdlog::info("filtered global {}", counted);
    spdlog::log(spdlog::level::info, "filtered global {}", counted);
    spdlog::log(spdlog::source_loc("filter.cpp", 2, "global"), spdlog::level::info, "filtered global {}", counted);
    spdlog::default_logger()->set_level(spdlog::level::info);
    if (conversions != 0) {
        std::fprintf(stderr, "Filtered logs converted arguments %d times\n", conversions);
        return 2;
    }
    {
        std::shared_ptr<Capture> backtraceCapture(new Capture);
        spdlog::logger backtraceLogger("argument-backtrace", backtraceCapture);
        backtraceLogger.set_pattern("%v");
        backtraceLogger.set_level(spdlog::level::warn);
        backtraceLogger.enable_backtrace(1);
        backtraceLogger.info("backtrace argument {}", counted);
        if (conversions == 0) {
            std::fprintf(stderr, "Backtrace dropped a filtered argument\n");
            return 3;
        }
        backtraceLogger.dump_backtrace();
        assert(backtraceCapture->lines.size() == 3 && backtraceCapture->lines[1] == "backtrace argument 42\n");
    }
    sync.enable_backtrace(2);
    sync.info("backtrace1");
    sync.info("backtrace2");
    sync.dump_backtrace();
    assert(capture->lines.size() == 5);
    int errors = 0;
    sync.set_error_handler([&errors](const std::string &) { ++errors; });
    sync.set_level(spdlog::level::info);
#if ORIGINAL_SPDLOG
    sync.info(fmt::runtime("{"), 42);
#else
    sync.info(fmt::CStringRef("{"), 42);
#endif
    assert(errors == 1);
    sync.info("{} {} {} {} {} {} {} {} {} {} {} {} {}", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13);
    assert(capture->lines.back().find("1 2 3 4 5 6 7 8 9 10 11 12 13") != std::string::npos);
    sync.log(spdlog::source_loc("wide.cpp", 39, "Wide"), spdlog::level::info,
             "{} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} "
             "{} {} {} {}",
             1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, "sixteen", 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
             28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, std::string("thirtynine"));
    assert(capture->lines.back() == "[sync] [wide.cpp:39] [info] 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 sixteen 17 18 19 "
                                    "20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 thirtynine\n");
    // Exactly16 selects typed Arg storage; the next index must stop at NONE.
    sync.info("{15}", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, "sixteen");
    assert(capture->lines.back().find("sixteen") != std::string::npos);
#if ORIGINAL_SPDLOG
    sync.info(fmt::runtime("{16}"), 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16);
#else
    sync.info(fmt::CStringRef("{16}"), 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16);
#endif
    assert(errors == 2);
    // Fixed UTC timestamp exercises real current formatter flags and padding.
    spdlog::pattern_formatter pattern(
        "%Y-%m-%d %H:%M:%S.%e|%f|%F|%a|%A|%b|%B|%C|%D|%I|%p|%r|%R|%T|%E|%n|%l|%L|%@|%s|%g|%#|%!|%8l|%-8l|%=8l|%3!l|%v",
        spdlog::pattern_time_type::utc, "\n");
    spdlog::log_clock::time_point timestamp = spdlog::log_clock::from_time_t(1700000000);
#if ORIGINAL_SPDLOG
    timestamp += std::chrono::milliseconds(123);
#else
    timestamp += Shipyard::Logging::chrono::milliseconds(123);
#endif
    spdlog::details::log_msg msg(timestamp, spdlog::source_loc("dir/test.cpp", 123, "Fn"), "name", spdlog::level::warn,
                                 "payload");
    spdlog::memory_buf_t formatted;
    pattern.format(msg, formatted);
    std::string result(formatted.data(), formatted.size());
    std::printf("pattern:%s", result.c_str());
    // Verify actual rotating sink file naming, eviction and callback lifetime.
    int opens = 0, closes = 0;
    spdlog::file_event_handlers events;
    events.after_open = [&opens](const std::string &, FILE *) { ++opens; };
    events.after_close = [&closes](const std::string &) { ++closes; };
    {
        std::shared_ptr<spdlog::sinks::rotating_file_sink_mt> disk(
            new spdlog::sinks::rotating_file_sink_mt(path, 12, 2, false, events));
        spdlog::logger file("file", disk);
        file.set_pattern("%v");
        file.flush_on(spdlog::level::info);
        for (int i = 0; i < 5; ++i)
            file.info("record-{}", i);
    }
    assert(contents(path) == "record-4\n");
    assert(contents(std::string(argv[1]) + "/rotation.1.log") == "record-3\n");
    assert(contents(std::string(argv[1]) + "/rotation.2.log") == "record-2\n");
    assert(opens == 5 && closes == 5);
    bool failed = false;
    try {
        spdlog::sinks::rotating_file_sink_mt invalid(path, 0, 10);
    } catch (const spdlog::spdlog_ex &) {
        failed = true;
    }
    assert(failed);
    spdlog::init_thread_pool(8192, 1);
    capture.reset(new Capture);
    capture->blockFirst = true;
    std::vector<spdlog::sink_ptr> sinks;
    sinks.push_back(capture);
    std::shared_ptr<spdlog::logger> logger(new spdlog::async_logger(
        "async", sinks.begin(), sinks.end(), spdlog::thread_pool(), spdlog::async_overflow_policy::block));
    logger->set_pattern("[%@] %v");
    logger->set_level(spdlog::level::info);
    logger->flush_on(spdlog::level::info);
    spdlog::register_logger(logger);
    spdlog::set_default_logger(logger);
    assert(spdlog::get("async") == logger);
    failed = false;
    try {
        spdlog::register_logger(logger);
    } catch (const spdlog::spdlog_ex &) {
        failed = true;
    }
    assert(failed);
    logger->log(spdlog::source_loc("async.cpp", 7, "Fn"), spdlog::level::info, "first");
    capture->entered.wait();
    std::string owned(1200, 'x');
    logger->log(spdlog::source_loc("async.cpp", 8, "Fn"), spdlog::level::info, "{}", owned);
    owned.assign(1200, 'z');
    for (int i = 0; i < 1000; ++i)
        logger->log(spdlog::source_loc("async.cpp", 9, "Fn"), spdlog::level::info, "item {}", i);
    std::weak_ptr<spdlog::logger> weak(logger);
    logger.reset();
    assert(!weak.expired());
    capture->release.set();
    spdlog::shutdown();
    assert(weak.expired());
    assert(capture->lines.size() == 1002);
    assert(capture->flushes == 1002);
    assert(capture->lines[1] == "[async.cpp:8] " + std::string(1200, 'x') + "\n");
    assert(capture->lines.back() == "[async.cpp:9] item 999\n");
    puts("PASS current logger: default diagnostics, levels/source/pattern/backtrace/error handler, rotation, async "
         "owned bytes, registration, shutdown drain");
}
