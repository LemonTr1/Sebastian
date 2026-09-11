from pathlib import Path


def _resolve(workdir: Path, rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    return workdir / rel


def run_checkers(workdir: Path, expects: list, metrics: dict, reply: str) -> list[dict]:
    results = []
    for spec in expects:
        kind = spec.get("type")
        ok, detail = False, f"unknown checker: {kind}"
        try:
            if kind == "file_exists":
                path = _resolve(workdir, spec["path"])
                ok = path.is_file()
                detail = f"{path} exists={ok}"
            elif kind == "file_absent":
                path = _resolve(workdir, spec["path"])
                ok = not path.exists()
                detail = f"{path} absent={ok}"
            elif kind == "file_contains":
                path = _resolve(workdir, spec["path"])
                text = path.read_text(encoding="utf-8") if path.is_file() else ""
                needle = spec["text"]
                ok = needle in text
                detail = f"{path} contains {needle!r}: {ok}"
            elif kind == "file_not_contains":
                path = _resolve(workdir, spec["path"])
                text = path.read_text(encoding="utf-8") if path.is_file() else ""
                needle = spec["text"]
                ok = needle not in text
                detail = f"{path} not contains {needle!r}: {ok}"
            elif kind == "file_equals":
                path = _resolve(workdir, spec["path"])
                actual = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
                expected = spec["text"].strip()
                ok = actual == expected
                detail = f"{path} equals expected: {ok}"
            elif kind == "tool_called":
                name = spec["name"]
                ok = name in metrics.get("tools_called", [])
                detail = f"tool {name} called={ok}"
            elif kind == "tool_not_called":
                name = spec["name"]
                ok = name not in metrics.get("tools_called", [])
                detail = f"tool {name} not called={ok}"
            elif kind == "tool_calls_eq":
                n = int(spec["value"])
                actual = int(metrics.get("tool_calls", 0))
                ok = actual == n
                detail = f"tool_calls={actual} expected={n}"
            elif kind == "assistant_contains":
                needle = spec["text"]
                ok = needle in (reply or "")
                detail = f"reply contains {needle!r}: {ok}"
            elif kind == "only_files":
                allowed = {str(Path(p)) for p in spec["files"]}
                actual = set()
                for p in workdir.rglob("*"):
                    if p.is_file() or p.is_symlink():
                        actual.add(str(p.relative_to(workdir)))
                extra = sorted(actual - allowed)
                ok = not extra
                detail = f"extra files={extra}" if extra else f"files={sorted(actual)}"
            else:
                ok = False
                detail = f"unknown checker: {kind}"
        except Exception as e:
            ok = False
            detail = f"{kind} error: {e}"
        results.append({"type": kind, "ok": ok, "detail": detail})
    return results
