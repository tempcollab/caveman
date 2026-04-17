"""
Pairwise quality judge for caveman eval results.

For each (prompt, skill) pair, asks Claude to compare the skill output
against the baseline and score on three dimensions:

  - completeness: did it cover all key points? (1-5)
  - correctness: any wrong or misleading claims? (1-5)
  - actionability: could a developer act on this answer? (1-5)

Reads results.json (from llm_run.py), writes judge.json alongside it.

Requires:
  - `claude` CLI on PATH (Claude Code), authenticated

Run: uv run python evals/judge.py --tag round-0

Environment:
  CAVEMAN_EVAL_MODEL  optional --model flag value passed through to claude
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

EVALS = Path(__file__).parent
RESULTS_DIR = EVALS / "snapshots"

JUDGE_SYSTEM = """You are an expert technical reviewer. You will be given a reference answer and a compressed answer to the same programming question.

The compressed answer is intentionally brief — it uses a terse writing style to reduce token count. Do NOT penalize brevity itself. Score based on whether all the essential technical content is preserved, not on length or detail parity. Dropped filler, examples, and verbose explanations are fine as long as the core information a developer needs is still there.

You must score the compressed answer on three dimensions (1-5 each):

- completeness: Are the essential technical points preserved? 5 = all key information a developer needs is present, 1 = critical information missing that would leave a developer stuck.
- correctness: Is everything stated technically accurate? 5 = fully correct, 1 = contains serious errors or misleading claims.
- actionability: Could a developer solve their problem with this answer alone? 5 = fully actionable, 1 = useless without additional research.

Respond with ONLY a valid JSON object, no other text:
{"completeness": N, "correctness": N, "actionability": N}"""


def run_claude(prompt: str, system: str) -> str:
    """Call claude CLI with a prompt and system prompt."""
    cmd = ["claude", "-p", "--system-prompt", system]
    if model := os.environ.get("CAVEMAN_EVAL_MODEL"):
        cmd += ["--model", model]
    cmd.append(prompt)
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def parse_scores(raw: str) -> dict:
    """Extract the JSON scores from judge output."""
    # Find the JSON object in the response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {"completeness": 0, "correctness": 0, "actionability": 0, "error": raw}
    try:
        scores = json.loads(raw[start:end])
        for key in ("completeness", "correctness", "actionability"):
            if key not in scores or not isinstance(scores[key], (int, float)):
                scores[key] = 0
        return scores
    except json.JSONDecodeError:
        return {"completeness": 0, "correctness": 0, "actionability": 0, "error": raw}


def resolve_results_path(tag: str) -> Path:
    """Return the path to results.json for a given tag."""
    return RESULTS_DIR / tag / "results.json"


def resolve_judge_path(tag: str) -> Path:
    """Return the output path for judge.json."""
    path = RESULTS_DIR / tag / "judge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    """Run pairwise quality judging on eval results."""
    parser = argparse.ArgumentParser(description="Judge eval quality")
    parser.add_argument(
        "--tag",
        required=True,
        help="Run tag to judge (e.g. round-0). Reads from evals/snapshots/<tag>/",
    )
    args = parser.parse_args()

    results_path = resolve_results_path(args.tag)
    if not results_path.exists():
        print(f"No results at {results_path}. Run llm_run.py first.")
        return

    data = json.loads(results_path.read_text())
    prompts = data["prompts"]
    arms = data["arms"]
    baseline_outputs = arms["__baseline__"]

    skills = [k for k in arms if not k.startswith("__")]
    n_prompts = len(prompts)
    total = len(skills) * n_prompts

    print(f"=== Judging {len(skills)} skills × {n_prompts} prompts = {total} calls ===")

    judge_data: dict = {
        "metadata": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "model": os.environ.get("CAVEMAN_EVAL_MODEL", "default"),
            "source_results": str(results_path),
            "tag": args.tag,
        },
        "scores": {},
    }

    done = 0
    for skill in skills:
        skill_outputs = arms[skill]
        skill_scores = []

        for i, (prompt, baseline, compressed) in enumerate(
            zip(prompts, baseline_outputs, skill_outputs)
        ):
            done += 1
            print(f"  [{done}/{total}] {skill} | prompt {i + 1}", flush=True)

            judge_prompt = (
                f"## Question\n{prompt}\n\n"
                f"## Reference Answer\n{baseline}\n\n"
                f"## Compressed Answer\n{compressed}"
            )
            raw = run_claude(judge_prompt, system=JUDGE_SYSTEM)
            scores = parse_scores(raw)
            scores["prompt_index"] = i
            skill_scores.append(scores)

        judge_data["scores"][skill] = skill_scores

    judge_path = resolve_judge_path(args.tag)
    judge_path.write_text(json.dumps(judge_data, ensure_ascii=False, indent=2))
    print(f"\nWrote {judge_path}")


if __name__ == "__main__":
    main()
