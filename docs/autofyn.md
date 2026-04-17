## Goal

Optimize `skills/caveman/SKILL.md` to maximize token compression (>= 10% median savings vs terse control) while keeping quality scores <= 2 points of baseline on all three dimensions (completeness, correctness, actionability). If any dimension drops below 0.2, revert.

## Environment

You have `CLAUDE_CODE_OAUTH_TOKEN`, `CAVEMAN_EVAL_MODEL`, and `CAVEMAN_JUDGE_MODEL` (defaults to claude-opus-4-6) available. The `evals` directory contains the evaluation suite.

Committed baselines exist at `evals/snapshots/baseline-sonnet-4-6/` and `evals/snapshots/baseline-opus-4-6/`. Read their `summary.json` for current scores. Do not regenerate baselines.

Think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language.

Do not make massive changes in a single round. Record what worked and what did not so the next round can build on it. Stop if changes begin to regress performance or fail to improve efficiency.

Use subagents. Do not run long tool calls yourself.

Do not get stuck in a local optimum. The goal is to reduce token usage while preserving scores within 0.2 points in each category. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.

Do iterative refinement each round. After the first baseline, have the code reviewer run the evals for subsequent changes so you do not have to.