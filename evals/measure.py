"""
Read eval results and report token compression + quality scores.

Reads results.json (from llm_run.py) for compression stats and
judge.json (from judge.py) for quality scores. Prints a combined
markdown table and saves summary.json alongside the inputs.

Tokenizer note: tiktoken o200k_base is OpenAI's tokenizer and is only an
approximation of Claude's BPE. The ratios are still meaningful for
comparing skills against each other, but the absolute numbers should be
read as "approximate output-length reduction", not "exact Claude tokens".

Run: uv run --with tiktoken python evals/measure.py --tag round-0
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import tiktoken

ENCODING = tiktoken.get_encoding("o200k_base")
EVALS = Path(__file__).parent
RESULTS_DIR = EVALS / "snapshots"


def count(text: str) -> int:
    """Count tokens in a string using tiktoken."""
    return len(ENCODING.encode(text))


def compression_stats(
    savings: list[float],
) -> tuple[float, float, float, float, float]:
    """Return median, mean, min, max, stdev of savings list."""
    return (
        statistics.median(savings),
        statistics.mean(savings),
        min(savings),
        max(savings),
        statistics.stdev(savings) if len(savings) > 1 else 0.0,
    )


def fmt_pct(x: float) -> str:
    """Format a float as a signed percentage string."""
    sign = "−" if x < 0 else "+"
    return f"{sign}{abs(x) * 100:.0f}%"


def resolve_results_path(tag: str) -> Path:
    """Return the path to results.json for a given tag."""
    return RESULTS_DIR / tag / "results.json"


def resolve_judge_path(tag: str) -> Path:
    """Return the path to judge.json for a given tag."""
    return RESULTS_DIR / tag / "judge.json"


def resolve_summary_path(tag: str) -> Path:
    """Return the output path for summary.json."""
    path = RESULTS_DIR / tag / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    """Print compression and quality report from eval results."""
    parser = argparse.ArgumentParser(description="Measure eval results")
    parser.add_argument(
        "--tag",
        required=True,
        help="Run tag (e.g. round-0). Reads from evals/snapshots/<tag>/",
    )
    args = parser.parse_args()

    results_path = resolve_results_path(args.tag)
    if not results_path.exists():
        print(f"No results at {results_path}. Run llm_run.py first.")
        return

    data = json.loads(results_path.read_text())
    arms = data["arms"]
    meta = data.get("metadata", {})

    baseline_tokens = [count(o) for o in arms["__baseline__"]]
    terse_tokens = [count(o) for o in arms["__terse__"]]

    # Load judge scores if available
    judge_path = resolve_judge_path(args.tag)
    judge_scores: dict | None = None
    if judge_path.exists():
        judge_data = json.loads(judge_path.read_text())
        judge_scores = judge_data.get("scores", {})

    # Header
    print(f"_Generated: {meta.get('generated_at', '?')}_")
    print(
        f"_Model: {meta.get('model', '?')} · CLI: {meta.get('claude_cli_version', '?')}_"
    )
    print(f"_Tag: {meta.get('tag', '?')} · Git: {meta.get('git_sha', '?')}_")
    print(f"_Tokenizer: tiktoken o200k_base (approximation of Claude's BPE)_")
    print(
        f"_n = {meta.get('n_prompts', len(baseline_tokens))} prompts, single run per arm_"
    )
    print()
    print("**Reference arms (no skill):**")
    print(f"- baseline (no system prompt): {sum(baseline_tokens)} tokens total")
    print(
        f"- terse control (`Answer concisely.`): {sum(terse_tokens)} tokens total "
        f"({fmt_pct(1 - sum(terse_tokens) / sum(baseline_tokens))} vs baseline)"
    )
    print()

    # Build table header based on whether judge scores exist
    if judge_scores:
        print("| Skill | Median | Mean | Min | Max | Tokens | Comp | Corr | Action |")
        print("|-------|--------|------|-----|-----|--------|------|------|--------|")
    else:
        print(
            "| Skill | Median | Mean | Min | Max | Stdev | Tokens (skill / terse) |"
        )
        print(
            "|-------|--------|------|-----|-----|-------|-------------------------|"
        )

    rows = []
    summary_rows = []
    for skill, outputs in arms.items():
        if skill in ("__baseline__", "__terse__"):
            continue
        skill_tokens = [count(o) for o in outputs]
        savings = [
            1 - (s / t) if t else 0.0 for s, t in zip(skill_tokens, terse_tokens)
        ]
        med, mean, lo, hi, sd = compression_stats(savings)

        row_data = {
            "skill": skill,
            "median": round(med * 100),
            "mean": round(mean * 100),
            "min": round(lo * 100),
            "max": round(hi * 100),
            "stdev": round(sd * 100),
            "skill_tokens": sum(skill_tokens),
            "terse_tokens": sum(terse_tokens),
        }

        # Add judge scores if available
        if judge_scores and skill in judge_scores:
            scores = judge_scores[skill]
            valid = [s for s in scores if "error" not in s]
            if valid:
                row_data["completeness"] = round(
                    statistics.mean(s["completeness"] for s in valid), 1
                )
                row_data["correctness"] = round(
                    statistics.mean(s["correctness"] for s in valid), 1
                )
                row_data["actionability"] = round(
                    statistics.mean(s["actionability"] for s in valid), 1
                )

        rows.append((med, row_data))
        summary_rows.append(row_data)

    for _, row in sorted(rows, key=lambda r: -r[0]):
        if judge_scores:
            comp = row.get("completeness", "–")
            corr = row.get("correctness", "–")
            act = row.get("actionability", "–")
            print(
                f"| **{row['skill']}** | {fmt_pct(row['median'] / 100)} | "
                f"{fmt_pct(row['mean'] / 100)} | {fmt_pct(row['min'] / 100)} | "
                f"{fmt_pct(row['max'] / 100)} | "
                f"{row['skill_tokens']} / {row['terse_tokens']} | "
                f"{comp} | {corr} | {act} |"
            )
        else:
            print(
                f"| **{row['skill']}** | {fmt_pct(row['median'] / 100)} | "
                f"{fmt_pct(row['mean'] / 100)} | {fmt_pct(row['min'] / 100)} | "
                f"{fmt_pct(row['max'] / 100)} | {row['stdev']}% | "
                f"{row['skill_tokens']} / {row['terse_tokens']} |"
            )

    print()
    print("_Savings = `1 - skill_tokens / terse_tokens` per prompt._")
    if judge_scores:
        print("_Quality scores: 1-5 scale (5 = best). Comp=completeness, Corr=correctness, Action=actionability._")
    print(
        f"_Source: {args.tag}. Refresh with `python evals/llm_run.py --tag {args.tag}`._"
    )

    # Save summary
    summary = {
        "metadata": meta,
        "has_quality_scores": judge_scores is not None,
        "skills": summary_rows,
    }
    summary_path = resolve_summary_path(args.tag)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n_Summary written to {summary_path}_")


if __name__ == "__main__":
    main()
