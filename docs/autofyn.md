## Goal

Optimize `skills/caveman/SKILL.md` to maximize token compression while keeping quality scores <= 0.2 points of baseline on all three dimensions (completeness, correctness, actionability). If any dimension regresses by 0.2 from baseline, revert.

## Environment

Read `CLAUDE.md`, `README.md`. You have `CLAUDE_CODE_OAUTH_TOKEN`, `CAVEMAN_EVAL_MODEL`, and `CAVEMAN_JUDGE_MODEL` (defaults to claude-opus-4-6) available. The `evals` directory contains the evaluation suite.

Committed baselines exist at `evals/snapshots/baseline-sonnet-4-6/` and `evals/snapshots/baseline-opus-4-6/`. Read and inspect the results (scores, what works and what can be improved). Compare your improvements against the baseline that corresponds to `CAVEMAN_EVAL_MODEL`, NOT BOTH.


## Rules

Think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language.

DO NOT make massive changes in a single round. Do targeted, iterative improvement. Record what worked and what did not so the next round can build on it. Stop if changes regress performance or fail to improve compression.

Do not run long tool calls yourself. Use subagents. After each change to SKILL.md, let code-reviewer run eval so you, or the dev subagent don't have to.

Do not get stuck in a local optimum. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.