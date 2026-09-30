"""Bounded build, projection, and checkout relationships beside Serena."""
from __future__ import annotations

import json
from pathlib import Path
import re

from mcp.server.fastmcp import FastMCP

import nav

server = FastMCP("shipyard-navigation", instructions=(
    "Use Serena for symbol definitions, references and bounded reads. "
    "These tools only report selected builds and source/projector provenance. "
    "A missing semantic reference with partial coverage is not proof of no callers."
))


@server.tool()
def consumers_for_source(source_path: str, limit: int = 10, offset: int = 0) -> dict:
    """Which selected Modern/Smash/Majora builds consume an exact source path? No bodies."""
    if not 1 <= limit <= 50 or offset < 0:
        raise ValueError("limit must be 1..50 and offset nonnegative")
    requested = Path(source_path).resolve()
    if requested.is_relative_to(nav.SHIPYARD):
        relative = requested.relative_to(nav.SHIPYARD)
        aliases = {nav.selected_base(root)[0] / relative for root in (nav.MODERN, nav.SMASH, nav.MAJORA)}
        matches = []
        for alias in sorted(aliases):
            report = nav.query("consumers", str(alias), limit=50)
            for row in report["results"]:
                maintained_sha, selected_sha = nav.sha(requested), nav.sha(alias)
                same_bytes = maintained_sha == selected_sha
                matches.append({**row, "maintained_source": str(requested),
                                "maintained_sha": maintained_sha,
                                "maintained_matches_selected": same_bytes,
                                "source_content_relation": ("same-bytes" if same_bytes else
                                    "different-revisions-of-same-history" if
                                    row.get("history_relation") == "selected-ancestor-of-maintained"
                                    else "unverified")})
        return {"query": "consumers", "path": str(requested), "indexer": nav.VERSION,
                "results": matches[offset:offset + limit], "offset": offset, "limit": limit,
                "truncated": len(matches) > offset + limit,
                "next_offset": offset + limit if len(matches) > offset + limit else None}
    return nav.query("consumers", str(requested), limit=limit, offset=offset)


@server.tool()
def shipyard_topology() -> dict:
    """Canonical and selected Shipyard revisions, local Git relationship, and freshness."""
    return nav.topology()


@server.tool()
def origin_for_generated(generated_path: str, line: int | None = None,
                         limit: int = 10, offset: int = 0) -> dict:
    """Find maintained adapter, shared projector and pinned input for generated code.

    A line supplied for a #line-mapped output returns its source line. If no
    exact mapping exists, the result explicitly reports projector/lock scope.
    """
    return nav.query("origin", generated_path, line=line, limit=limit, offset=offset)


@server.tool()
def affected_by_diff(repository: str, diff: str, limit: int = 10, offset: int = 0) -> dict:
    """Selected relationships affected by paths in a unified diff; no body text.

    repository is modern, smash, majora, or shipyard. A Shipyard path is also checked
    against the pinned dependency checkout, with identity shown in each row.
    """
    roots = {"modern": nav.MODERN, "smash": nav.SMASH,
             "majora": nav.MAJORA, "shipyard": nav.SHIPYARD}
    if repository not in roots:
        raise ValueError("repository must be modern, smash, majora, or shipyard")
    if not 1 <= limit <= 50 or offset < 0:
        raise ValueError("limit must be 1..50 and offset nonnegative")
    if len(diff) > 500_000:
        raise ValueError("diff exceeds 500000 characters")
    names = []
    for match in re.finditer(r"^diff --git a/(.+?) b/(.+)$", diff, re.MULTILINE):
        name = match.group(2)
        path = (roots[repository] / name).resolve()
        if not path.is_relative_to(roots[repository]):
            raise ValueError("diff path outside repository")
        names.append(path)
    names = list(dict.fromkeys(names))
    if len(names) > 100:
        raise ValueError("diff contains more than 100 paths")
    matches = []
    capped = False
    for path in names:
        aliases = [path]
        if repository == "shipyard":
            relative = path.relative_to(nav.SHIPYARD)
            for consumer_root in (nav.MODERN, nav.SMASH, nav.MAJORA):
                base, _ = nav.selected_base(consumer_root)
                aliases.append(base / relative)
        elif repository == "smash":
            aliases.append(nav.SMASH / "scratch/application-xdk/native/source" / path.relative_to(nav.SMASH))
        for alias in dict.fromkeys(aliases):
            same_bytes = nav.sha(path) == nav.sha(alias)
            page = 0
            while True:
                report = nav.query("affected", str(alias), limit=50, offset=page)
                for row in report["results"]:
                    matches.append({"changed_path": str(path), "indexed_path": str(alias),
                                    "source_identity_matches": same_bytes, **row})
                if report["next_offset"] is None:
                    break
                page = report["next_offset"]
                if page >= 1000:
                    capped = True
                    break
    result = matches[offset:offset + limit]
    return {"repository": repository, "changed_paths": [str(p) for p in names],
            "results": result, "offset": offset, "limit": limit,
            "truncated": capped or len(matches) > offset + limit,
            "next_offset": offset + limit if len(matches) > offset + limit else None,
            "internal_cap_reached": capped,
            "coverage": "selected manifest/projection relationships; no inferred call graph"}


@server.tool()
def refresh_navigation_index() -> dict:
    """Rebuild analysis maps and relationships under a single writer lock."""
    nav.refresh_all(verbose=False)
    return {"status": "refreshed", "indexer": nav.VERSION, "database": str(nav.DB),
            "semantic_restart_required": True}


if __name__ == "__main__":
    server.run(transport="stdio")
