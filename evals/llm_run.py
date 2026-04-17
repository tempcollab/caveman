"""
Run each prompt through Claude Code in three conditions and snapshot the
real LLM outputs:

  1. baseline      — no extra system prompt at all
  2. terse         — system prompt: "Answer concisely."
  3. terse+skill   — system prompt: "Answer concisely.\n\n{SKILL.md}"

The honest delta is (3) vs (2): how much does the SKILL itself add on top
of a plain "be terse" instruction? Comparing (3) vs (1) conflates the
skill with the generic terseness ask.

Results are saved to evals/snapshots/<tag>/results.json.

Requires:
  - `claude` CLI on PATH (Claude Code), authenticated

Run: uv run python evals/llm_run.py --tag round-0

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
import subprocess
from pathlib import Path

EVALS = Path(__file__).parent
SKILLS = EVALS.parent / "skills"
PROMPTS = EVALS / "prompts" / "en.txt"
RESULTS_DIR = EVALS / "snapshots"

TERSE_PREFIX = "Answer concisely."
DEFAULT_WORKERS = 2
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]


async def run_claude(
    prompt: str, system: str | None, semaphore: asyncio.Semaphore
) -> str:
    """Call claude CLI with a prompt and optional system prompt."""
    cmd = ["claude", "-p"]
    if system:
        cmd += ["--system-prompt", system]
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


async def run_arm(
    prompts: list[str], system: str | None, semaphore: asyncio.Semaphore
) -> list[str]:
    """Run all prompts for one arm concurrently, preserving order."""
    tasks = [run_claude(p, system, semaphore) for p in prompts]
    return list(await asyncio.gather(*tasks))


def claude_version() -> str:
    """Return the installed claude CLI version string."""
    try:
        out = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def git_sha() -> str:
    """Return the current git HEAD sha."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()[:12]
    except Exception:
        return "unknown"


def resolve_output_path(tag: str) -> Path:
    """Return the output path for results.json."""
    path = RESULTS_DIR / tag / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def async_main(args: argparse.Namespace) -> None:
    """Generate eval snapshot by running prompts through claude CLI."""
    prompts = [p.strip() for p in PROMPTS.read_text().splitlines() if p.strip()]
    skills = sorted(p.name for p in SKILLS.iterdir() if (p / "SKILL.md").exists())
    n_arms = len(skills) + 2
    total = len(prompts) * n_arms
    semaphore = asyncio.Semaphore(args.workers)

    print(
        f"=== {len(prompts)} prompts × {n_arms} arms = {total} calls "
        f"({args.workers} workers) ===",
        flush=True,
    )

    snapshot: dict = {
        "metadata": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "claude_cli_version": claude_version(),
            "model": os.environ.get("CAVEMAN_EVAL_MODEL", "default"),
            "n_prompts": len(prompts),
            "terse_prefix": TERSE_PREFIX,
            "git_sha": git_sha(),
            "tag": args.tag,
        },
        "prompts": prompts,
        "arms": {},
    }

    print("  baseline (no system prompt)", flush=True)
    snapshot["arms"]["__baseline__"] = await run_arm(prompts, None, semaphore)

    print("  terse (control)", flush=True)
    snapshot["arms"]["__terse__"] = await run_arm(prompts, TERSE_PREFIX, semaphore)

    for skill in skills:
        skill_md = (SKILLS / skill / "SKILL.md").read_text()
        system = f"{TERSE_PREFIX}\n\n{skill_md}"
        print(f"  {skill}", flush=True)
        snapshot["arms"][skill] = await run_arm(prompts, system, semaphore)

    out_path = resolve_output_path(args.tag)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_path}")


def main() -> None:
    """Entry point — parse args and run async main."""
    parser = argparse.ArgumentParser(description="Generate eval snapshot")
    parser.add_argument(
        "--tag",
        required=True,
        help="Run tag (e.g. round-0). Saves to evals/snapshots/<tag>/",
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
