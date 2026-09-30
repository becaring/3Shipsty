"""Behavior checks for stale/deleted evidence over the actual MCP interface."""

import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nav


class MajoraVendorProjectionTest(unittest.TestCase):
    def test_selected_png_and_gfxd_headers_stay_within_locked_roots(self):
        manifest = nav.data(nav.MAJORA / "scratch/project-xdk/manifest.json")
        locks = {"platform/xbox360/png-source-lock.json", "platform/xbox360/gfxd-source-lock.json"}
        rows = [row for row in manifest["projections"] if row.get("lock") in locks]
        self.assertEqual(len(rows), 10)
        for row in rows:
            with self.subTest(output=row["output"]):
                output = (nav.MAJORA / row["output"]).resolve()
                upstream = (nav.MAJORA / row["upstream_source"]).resolve()
                projector = (nav.MAJORA / row["projector"]).resolve()
                self.assertEqual(sum(nav.majora_vendor_headers(row, output, upstream, projector)), 1)
                escaped = nav.MAJORA.parent / "escaped.h"
                self.assertEqual(nav.majora_vendor_headers(row, escaped, upstream, projector), (False, False))

    def test_projected_interpreter_uses_exact_selected_roots(self):
        manifest = nav.data(nav.MAJORA / "scratch/project-xdk/manifest.json")
        rows = [
            row for row in manifest["projections"] if row.get("projector") == "platform/xbox360/project_interpreter.py"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        output = (nav.MAJORA / row["output"]).resolve()
        upstream = (nav.MAJORA / row["upstream_source"]).resolve()
        projector = (nav.MAJORA / row["projector"]).resolve()
        self.assertTrue(nav.majora_interpreter_projection(row, output, upstream, projector))
        escaped = nav.MAJORA.parent / "escaped.cpp"
        self.assertFalse(nav.majora_interpreter_projection(row, escaped, upstream, projector))
        self.assertFalse(nav.majora_interpreter_projection(row, output, escaped, projector))
        self.assertFalse(nav.majora_interpreter_projection(row, output, upstream, escaped))
        self.assertFalse(nav.majora_interpreter_projection({**row, "lock": "other"}, output, upstream, projector))


class ShipyardIdentityTest(unittest.TestCase):
    def test_linked_branch_relations_require_common_history(self):
        with tempfile.TemporaryDirectory(dir=nav.STATE) as folder:
            canonical = Path(folder) / "canonical"
            selected = Path(folder) / "selected"
            canonical.mkdir()
            nav.git_output(canonical, "init")
            nav.git_output(canonical, "config", "user.name", "Navigation fixture")
            nav.git_output(canonical, "config", "user.email", "fixture@example.invalid")
            nav.git_output(canonical, "commit", "--allow-empty", "-m", "root")
            initial = nav.head(canonical)
            nav.git_output(canonical, "worktree", "add", "--detach", str(selected))
            with patch.object(nav, "SHIPYARD", canonical):
                nav.git_output(selected, "commit", "--allow-empty", "-m", "selected")
                self.assertEqual(
                    nav.shipyard_identity(selected)["history_relation"], "selected-descendant-of-maintained"
                )
                nav.git_output(canonical, "commit", "--allow-empty", "-m", "maintained")
                self.assertEqual(nav.shipyard_identity(selected)["history_relation"], "diverged-branch-of-maintained")
                nav.git_output(selected, "checkout", "--detach", initial)
                self.assertEqual(nav.shipyard_identity(selected)["history_relation"], "selected-ancestor-of-maintained")
                nav.git_output(selected, "checkout", "--orphan", "unrelated")
                nav.git_output(selected, "commit", "--allow-empty", "-m", "orphan")
                with self.assertRaises(ValueError):
                    nav.shipyard_identity(selected)


class NavigationFixtureTest(unittest.IsolatedAsyncioTestCase):
    async def test_changed_and_removed_symbol_invalidates_selected_source(self):
        with tempfile.TemporaryDirectory(dir=nav.STATE) as folder:
            root = Path(folder)
            (root / ".git").mkdir()
            (root / ".git/HEAD").write_text("a" * 40 + "\n", encoding="ascii")
            source = root / "fixture.cpp"
            source.write_text("void OriginalSymbol() {}\n", encoding="utf-8")
            baseline = root / "baseline.json"
            baseline.write_text("{}\n", encoding="utf-8")
            lock = root / "platform-base.lock.json"
            manifest = root / "manifest.json"
            lock.write_text(
                json.dumps({"base": ".", "git_revision": "a" * 40, "baseline_sha256": nav.sha(baseline)}) + "\n",
                encoding="utf-8",
            )
            manifest.write_text("{}\n", encoding="utf-8")
            database = root / "fixture.sqlite"
            conn = sqlite3.connect(database)
            conn.executescript(nav.SCHEMA)
            conn.execute(
                """INSERT INTO snapshot (consumer,root,root_head,base,base_head,lock_path,lock_sha,manifest_path,manifest_sha,\
compile_sha,serena_sha,indexer,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "fixture",
                    str(root),
                    "a" * 40,
                    str(root),
                    "a" * 40,
                    str(lock),
                    nav.sha(lock),
                    str(manifest),
                    nav.sha(manifest),
                    None,
                    None,
                    nav.VERSION,
                    0,
                ),
            )
            conn.execute(
                "INSERT INTO selection (consumer,config,source,source_sha,kind,manifest_path,receipt,options_json,receipt_sha) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "fixture",
                    "probe",
                    str(source),
                    nav.sha(source),
                    "consumer",
                    str(manifest),
                    str(manifest),
                    "[]",
                    nav.sha(manifest),
                ),
            )
            conn.execute(
                "INSERT INTO selection (consumer,config,source,source_sha,kind,manifest_path,receipt,options_json,receipt_sha) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "fixture",
                    "probe-alt",
                    str(source),
                    nav.sha(source),
                    "consumer",
                    str(manifest),
                    str(manifest),
                    "[]",
                    nav.sha(manifest),
                ),
            )
            conn.commit()
            conn.close()
            env = dict(os.environ, CODE_NAV_DB=str(database))
            params = StdioServerParameters(
                command=str(nav.STATE / "venv/Scripts/python.exe"),
                args=[str(nav.NAV_ROOT / "tools/code_nav/mcp_server.py")],
                env=env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()

                    async def status():
                        result = await client.call_tool("consumers_for_source", {"source_path": str(source)})
                        payload = json.loads(result.content[0].text)
                        return payload["results"][0]["status"]

                    self.assertEqual(await status(), "current")
                    first = await client.call_tool("consumers_for_source", {"source_path": str(source), "limit": 1})
                    page = json.loads(first.content[0].text)
                    self.assertTrue(page["truncated"])
                    second = await client.call_tool(
                        "consumers_for_source", {"source_path": str(source), "limit": 1, "offset": 1}
                    )
                    self.assertFalse(json.loads(second.content[0].text)["truncated"])
                    source.write_text("void ReplacementSymbol() {}\n", encoding="utf-8")
                    self.assertEqual(await status(), "stale")
                    source.unlink()
                    self.assertEqual(await status(), "deleted")
                    (root / ".git/HEAD").write_text("b" * 40 + "\n", encoding="ascii")
                    self.assertEqual(await status(), "stale-configuration")


if __name__ == "__main__":
    unittest.main()
