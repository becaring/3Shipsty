"""Check Xbox logger path ownership against the pinned Context projection."""
from prepare_context import prepare, OUT

prepare()
source=(OUT/'generated/src/ship/Context.cpp').read_text()
begin=source.index('bool Context::InitLogging(')
end=source.index('bool Context::InitConfiguration()',begin)
logging=source[begin:end]
directory='xbox_compat::filesystem::create_directories(nativeLogPath.parent_path(), logDirectoryError);'
native='logPath = nativeLogPath.make_preferred().string();'
sink='std::make_shared<spdlog::sinks::rotating_file_sink_mt>(logPath'
assert logging.index(directory)<logging.index(native)<logging.index(sink)
assert 'if (logDirectoryError) return false;' in logging
assert 'catch (const spdlog::spdlog_ex& ex)' in logging
print('PASS: native mounted logs directory and preferred CRT path precede real spdlog sink')
