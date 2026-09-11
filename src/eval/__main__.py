"""Run: python -m src.eval [--case ID] [--tag TAG] [--online] [--keep]"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

os.environ["SEBASTIAN_EVAL"] = "1"
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["all_proxy"] = ""

from src.eval.harness import load_cases, run_case


def _print_table(rows: list[dict]):
    header = f"{'id':<22} {'pass':<6} {'rounds':>6} {'calls':>6} {'llm':>5} {'tokens':>8} {'sec':>7} {'note'}"
    print(header)
    print("-" * len(header))
    for r in rows:
        note = ""
        if not r["passed"]:
            note = "FAIL"
        elif r.get("inefficient"):
            note = "inefficient"
        print(
            f"{r['id']:<22} {'Y' if r['passed'] else 'N':<6} "
            f"{r['tool_rounds']:>6} {r['tool_calls']:>6} {r['llm_turns']:>5} "
            f"{r['tokens']:>8} {r['latency_sec']:>7.1f} {note}"
        )


def main():
    parser = argparse.ArgumentParser(description="Sebastian Agent 评测试卷")
    parser.add_argument("--case", help="只跑指定题目 id")
    parser.add_argument("--tag", help="只跑带该标签的题目，如 security")
    parser.add_argument("--online", action="store_true", help="包含联网题")
    parser.add_argument("--keep", action="store_true", help="保留失败题的工作目录")
    args = parser.parse_args()

    cases = load_cases(case_id=args.case, include_online=args.online, tag=args.tag)
    if not cases:
        raise SystemExit("没有匹配的题目")

    rows = []
    for case in cases:
        print(f"\n>>> running {case['id']} ...")
        row = run_case(case, keep=args.keep)
        rows.append(row)
        status = "PASS" if row["passed"] else "FAIL"
        print(f"    {status}  rounds={row['tool_rounds']}  tokens={row['tokens']}")
        if not row["passed"]:
            for c in row["checks"]:
                if not c["ok"]:
                    print(f"    - {c['detail']}")

    attempted = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    rate = passed / attempted if attempted else 0
    avg_rounds = sum(r["tool_rounds"] for r in rows) / attempted
    avg_tokens = sum(r["tokens"] for r in rows) / attempted
    avg_latency = sum(r["latency_sec"] for r in rows) / attempted

    print("\n")
    _print_table(rows)
    print("-" * 72)
    print(f"success_rate  {passed}/{attempted} = {rate:.1%}")
    print(f"avg tool_rounds={avg_rounds:.2f}  avg tokens={avg_tokens:.0f}  avg latency={avg_latency:.1f}s")

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {
        "success_rate": rate,
        "passed": passed,
        "attempted": attempted,
        "avg_tool_rounds": avg_rounds,
        "avg_tokens": avg_tokens,
        "avg_latency_sec": avg_latency,
        "cases": rows,
    }
    out = out_dir / f"{stamp}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
