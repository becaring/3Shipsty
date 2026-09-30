"""Measure one renderer lookup via local MCP tools and scoped shell operations."""
import asyncio
import json
from pathlib import Path
import subprocess
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(r"D:\Projects\3Shipsty9.x")
SMASH = Path(r"D:\Projects\Smash360")
SHIPYARD = Path(r"D:\Projects\becaring\shipyard")
PYTHON = ROOT / "scratch/code-nav/venv/Scripts/python.exe"


def shell_round():
    t0 = time.perf_counter()
    outputs = []
    commands = [
        ["rg", "-n", "Shipyard_BuildFast3DShader|Shipyard_DecodeFast3DFeatures",
         str(SHIPYARD / "sources/graphics"), str(ROOT / "platform/shipyard/xenos"),
         str(SMASH / "platform/xbox360/graphics")],
        ["rg", "-n", "shader_provider.cpp", str(ROOT / "scratch/project-xdk/manifest.json")],
        ["rg", "-n", "shader_provider.cpp", str(SMASH / "scratch/application-xdk/native/project-items.json")],
    ]
    for command in commands:
        result = subprocess.run(command, capture_output=True, check=True)
        outputs.append(result.stdout)
    for path, first, last in (
        (SHIPYARD / "sources/graphics/shader_provider.cpp", 9, 23),
        (ROOT / "platform/shipyard/xenos/shader_provider.cpp", 1, 5),
        (SMASH / "platform/xbox360/graphics/shader_provider.cpp", 1, 6),
    ):
        lines = path.read_text(encoding="utf-8").splitlines()
        outputs.append("\n".join(f"{path}:{n}:{lines[n-1]}" for n in range(first, last + 1)).encode())
    combined = b"\n".join(outputs)
    assert b"Shipyard_BuildFast3DShader" in combined
    assert b"Shipyard_DecodeFast3DFeatures" in combined
    return {"seconds": round(time.perf_counter() - t0, 3), "output_bytes": len(combined),
            "operations": len(commands) + 3}


def payload_bytes(result):
    return sum(len(item.text.encode("utf-8")) for item in result.content if hasattr(item, "text"))


async def mcp_round(project, calls):
    if project == "metadata":
        args = [str(ROOT / "tools/code_nav/mcp_server.py")]
    else:
        args = [str(ROOT / "tools/code_nav/launch_serena.py"), project]
    params = StdioServerParameters(command=str(PYTHON), args=args)
    t0 = time.perf_counter()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            first = time.perf_counter()
            bytes_cold = 0
            for name, arg in calls:
                result = await client.call_tool(name, arg)
                if result.isError:
                    raise RuntimeError(f"{project}:{name}: {result.content}")
                bytes_cold += payload_bytes(result)
            cold = time.perf_counter() - t0
            t1 = time.perf_counter()
            bytes_warm = 0
            for name, arg in calls:
                result = await client.call_tool(name, arg)
                if result.isError:
                    raise RuntimeError(f"{project}:{name}: {result.content}")
                bytes_warm += payload_bytes(result)
            warm = time.perf_counter() - t1
    return {"cold_seconds": round(cold, 3), "warm_seconds": round(warm, 3),
            "cold_bytes": bytes_cold, "warm_bytes": bytes_warm,
            "calls": len(calls), "startup_seconds": round(first-t0, 3)}


async def main():
    canonical = str(SHIPYARD / "sources/graphics/shader_provider.cpp")
    jobs = [
        ("modern", [
            ("find_symbol", {"name_path_pattern": "Shipyard_BuildFast3DShader",
                             "relative_path": canonical, "include_body": False, "max_matches": 1}),
            ("find_symbol", {"name_path_pattern": "Shipyard_DecodeFast3DFeatures",
                             "relative_path": "platform/shipyard/xenos/shader_provider.cpp", "include_body": False, "max_matches": 1}),
            ("read_file", {"relative_path": "platform/shipyard/xenos/shader_provider.cpp",
                           "start_line": 0, "end_line": 5})]),
        ("smash", [
            ("find_symbol", {"name_path_pattern": "Shipyard_DecodeFast3DFeatures",
                             "relative_path": "platform/xbox360/graphics/shader_provider.cpp", "include_body": False, "max_matches": 1}),
            ("read_file", {"relative_path": "platform/xbox360/graphics/shader_provider.cpp",
                           "start_line": 0, "end_line": 6})]),
        ("shipyard", [
            ("read_file", {"relative_path": "sources/graphics/shader_provider.cpp",
                           "start_line": 8, "end_line": 23})]),
        ("metadata", [
            ("consumers_for_source", {"source_path": canonical})]),
    ]
    ordinary = {"cold": shell_round(), "warm": shell_round()}
    retrieval = {name: await mcp_round(name, calls) for name, calls in jobs}
    summary = {
        "ordinary_scoped_search_read": ordinary,
        "mcp_by_server": retrieval,
        "mcp_total": {"cold_seconds": round(sum(r["cold_seconds"] for r in retrieval.values()), 3),
                      "warm_seconds": round(sum(r["warm_seconds"] for r in retrieval.values()), 3),
                      "cold_bytes": sum(r["cold_bytes"] for r in retrieval.values()),
                      "warm_bytes": sum(r["warm_bytes"] for r in retrieval.values()),
                      "calls": sum(r["calls"] for r in retrieval.values())},
        "metric_note": "Output bytes are a proxy for model context. Actual Codex token usage is unavailable.",
    }
    target = ROOT / "scratch/code-nav/benchmark.json"
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
