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
  CAVEMAN_EVAL_MODEL    optional --model flag value passed through to claude
  CAVEMAN_EVAL_WORKERS  parallel workers (default: 2)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path

EVALS = Path(__file__).parent
RESULTS_DIR = EVALS / "snapshots"
DEFAULT_WORKERS = 2
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]

JUDGE_SYSTEM = """You are an expert technical reviewer. You will be given a reference answer and a compressed answer to the same programming question.

The compressed answer is intentionally brief — it uses a terse writing style to reduce token count. Do NOT penalize brevity itself. Score based on whether all the essential technical content is preserved, not on length or detail parity. Dropped filler, examples, and verbose explanations are fine as long as the core information a developer needs is still there.

You must score the compressed answer on three dimensions (1-5 each):

- completeness: Are the essential technical points preserved? 5 = all key information a developer needs is present, 1 = critical information missing that would leave a developer stuck.
- correctness: Is everything stated technically accurate? 5 = fully correct, 1 = contains serious errors or misleading claims.
- actionability: Could a developer solve their problem with this answer alone? 5 = fully actionable, 1 = useless without additional research.

Respond with ONLY a valid JSON object, no other text:
{"completeness": N, "correctness": N, "actionability": N}"""


async def run_claude(prompt: str, system: str, semaphore: asyncio.Semaphore) -> str:
    """Call claude CLI with a prompt and system prompt."""
    cmd = ["claude", "-p", "--system-prompt", system]
    if model := os.environ.get("CAVEMAN_EVAL_MODEL"):
        cmd += ["--model", model]
    cmd.append(prompt)

    last_err = ""
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return stdout.decode().strip()

            last_err = stderr.decode().strip()
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print(
                    f"    retry {attempt + 1}/{MAX_RETRIES} in {delay}s: {last_err[:80]}",
                    flush=True,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"claude CLI failed after {MAX_RETRIES} attempts: {last_err[:200]}"
        )


def parse_scores(raw: str) -> dict:
    """Extract the JSON scores from judge output."""
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


async def judge_one(
    skill: str,
    idx: int,
    prompt: str,
    baseline: str,
    compressed: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, int, dict]:
    """Judge a single prompt/skill pair. Returns (skill, index, scores)."""
    judge_prompt = (
        f"## Question\n{prompt}\n\n"
        f"## Reference Answer\n{baseline}\n\n"
        f"## Compressed Answer\n{compressed}"
    )
    try:
        raw = await run_claude(judge_prompt, system=JUDGE_SYSTEM, semaphore=semaphore)
        scores = parse_scores(raw)
    except RuntimeError as e:
        scores = {
            "completeness": 0,
            "correctness": 0,
            "actionability": 0,
            "error": str(e),
        }
    scores["prompt_index"] = idx
    return skill, idx, scores


def resolve_results_path(tag: str) -> Path:
    """Return the path to results.json for a given tag."""
    return RESULTS_DIR / tag / "results.json"


def resolve_judge_path(tag: str) -> Path:
    """Return the output path for judge.json."""
    path = RESULTS_DIR / tag / "judge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def async_main(args: argparse.Namespace) -> None:
    """Run pairwise quality judging on eval results."""
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
    semaphore = asyncio.Semaphore(args.workers)

    print(
        f"=== Judging {len(skills)} skills × {n_prompts} prompts = {total} calls "
        f"({args.workers} workers) ===",
        flush=True,
    )

    judge_data: dict = {
        "metadata": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "model": os.environ.get("CAVEMAN_EVAL_MODEL", "default"),
            "source_results": str(results_path),
            "tag": args.tag,
        },
        "scores": {},
    }

    # Build all tasks
    tasks = []
    for skill in skills:
        skill_outputs = arms[skill]
        for i, (prompt, baseline, compressed) in enumerate(
            zip(prompts, baseline_outputs, skill_outputs)
        ):
            tasks.append(
                judge_one(skill, i, prompt, baseline, compressed, semaphore)
            )

    # Run all concurrently, semaphore limits parallelism
    done = 0
    results_map: dict[tuple[str, int], dict] = {}
    for coro in asyncio.as_completed(tasks):
        skill, idx, scores = await coro
        results_map[(skill, idx)] = scores
        done += 1
        status = "ok" if "error" not in scores else "FAILED"
        print(f"  [{done}/{total}] {skill} | prompt {idx + 1} [{status}]", flush=True)

    # Reassemble in order
    for skill in skills:
        judge_data["scores"][skill] = [
            results_map[(skill, i)] for i in range(n_prompts)
        ]

    # Report failures
    failures = sum(1 for s in results_map.values() if "error" in s)
    if failures:
        print(f"\n  {failures}/{total} judgments failed (scored as 0)")

    judge_path = resolve_judge_path(args.tag)
    judge_path.write_text(json.dumps(judge_data, ensure_ascii=False, indent=2))
    print(f"\nWrote {judge_path}")


def main() -> None:
    """Entry point — parse args and run async main."""
    parser = argparse.ArgumentParser(description="Judge eval quality")
    parser.add_argument(
        "--tag",
        required=True,
        help="Run tag to judge (e.g. round-0). Reads from evals/snapshots/<tag>/",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("CAVEMAN_EVAL_WORKERS", DEFAULT_WORKERS)),
        help=f"Parallel workers (default: {DEFAULT_WORKERS})",
    )
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
