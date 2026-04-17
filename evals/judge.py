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
  CAVEMAN_JUDGE_MODEL   model for judging (default: claude-opus-4-6)
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
DEFAULT_JUDGE_MODEL = "claude-opus-4-6"
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]

JUDGE_SYSTEM = """You are an expert technical reviewer scoring a compressed answer against a reference.

The compressed answer intentionally uses terse prose to reduce token count. Do NOT penalize brevity. Score only on whether essential technical substance is preserved.

## Scoring rubric

### completeness (1-5)
- 5: Every key technical concept, step, or recommendation from the reference is present or clearly implied. Nothing a developer would need is missing.
- 4: One minor point omitted (e.g. an edge case, a secondary alternative) but all primary information intact.
- 3: Two or more minor points missing, OR one moderately important point missing. Developer could still mostly solve their problem.
- 2: A significant technical concept is missing that would cause the developer to get stuck or make a mistake.
- 1: Most substantive content is gone. Answer is too skeletal to be useful.

### correctness (1-5)
- 5: Every technical claim is accurate. No errors, no misleading simplifications.
- 4: One minor inaccuracy that would not cause harm (e.g. slightly wrong default value, imprecise terminology).
- 3: One meaningful error OR multiple minor inaccuracies. Developer might waste time debugging.
- 2: A significant technical error that would lead to broken code or wrong architecture decisions.
- 1: Fundamentally wrong answer. Following it would make things worse.

### actionability (1-5)
- 5: A developer can solve their problem using only this answer. Clear next steps, enough detail to implement.
- 4: Developer can solve their problem but may need to look up one minor detail (e.g. exact API syntax).
- 3: Answer points in the right direction but developer needs significant additional research to implement.
- 2: Answer is too vague or abstract to act on without substantial outside help.
- 1: Answer does not help the developer make progress on their problem.

## Rules
- Compare ONLY technical substance, not style or length.
- A short answer that covers all key points scores 5 on completeness.
- Omitted examples, analogies, or verbose explanations are NOT completeness losses.
- The compressed answer may use broken grammar (dropped articles, sentence fragments like "Pool reuse open DB conn"). This is intentional style, not a correctness error.
- Standard abbreviations (DB, auth, config, req, res, fn, impl) are equivalent to their full forms. Do not penalize.
- If the reference answer itself contains errors, do not penalize the compressed answer for omitting them.

Respond with ONLY a valid JSON object, no other text:
{"completeness": N, "correctness": N, "actionability": N}"""


async def run_claude(prompt: str, system: str, semaphore: asyncio.Semaphore) -> str:
    """Call claude CLI with a prompt and system prompt."""
    model = os.environ.get("CAVEMAN_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    cmd = ["claude", "-p", "--model", model, "--system-prompt", system, prompt]

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
    judge_model = os.environ.get("CAVEMAN_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)

    print(
        f"=== Judging {len(skills)} skills × {n_prompts} prompts = {total} calls "
        f"({args.workers} workers, model: {judge_model}) ===",
        flush=True,
    )

    judge_data: dict = {
        "metadata": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "judge_model": judge_model,
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
