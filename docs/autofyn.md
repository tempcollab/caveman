## Goal

Optimize `skills/caveman/SKILL.md` to maximize token compression (>= 10% median savings vs terse control) while keeping quality scores <= 0.2 points of baseline on all three dimensions (completeness, correctness, actionability). If any dimension regresses by 0.2 from baseline, revert.

## Environment

You have `CLAUDE_CODE_OAUTH_TOKEN`, `CAVEMAN_EVAL_MODEL`, and `CAVEMAN_JUDGE_MODEL` (defaults to claude-opus-4-6) available. The `evals` directory contains the evaluation suite.

Committed baselines exist at `evals/snapshots/baseline-sonnet-4-6/` and `evals/snapshots/baseline-opus-4-6/`. Read their `summary.json` for current scores. Do not regenerate baselines.


## Rules

Think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language. Do iterative improvement in each round.

Do not make massive changes in a single round. Record what worked and what did not so the next round can build on it. Stop if changes regress performance or fail to improve compression.

Do not run long tool calls yourself. After each change to SKILL.md, let code-reviewer run eval so you don't have to:

```bash
uv run python evals/llm_run.py --tag round-N
uv run python evals/judge.py --tag round-N
uv run --with tiktoken python evals/measure.py --tag round-N
```

Compare `summary.json` against the baseline. Results save to `evals/snapshots/<tag>/`.

Do not get stuck in a local optimum. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.