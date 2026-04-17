Reduce caveman's token usage while keeping quality scores <= 0.2 points of baseline on every dimensions (completeness, correctness, actionability). 

The `evals` directory contains the evaluation suite. Committed baselines exist at `evals/snapshots/baseline-sonnet-4-6/` and `evals/snapshots/baseline-opus-4-6/`. Understand the opus baseline results (scores, what works and what can be improved). Compare your improvements against the opus baseline, NOT BOTH.

Then, think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language.

DO NOT make multiple changes in a single round. Do targeted, iterative improvement. Record what worked and what did not so the next round can build on it. Stop if changes regress performance or fail to improve compression.

Do not do all the work yourself or run long tool calls yourself. Use subagents. Let code-reviewer run eval so you, or the dev subagent don't have to.

Do not get stuck in a local optimum. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.


# prompt v2


You have `CLAUDE_CODE_OAUTH_TOKEN`, `CAVEMAN_JUDGE_MODEL` and `CAVEMAN_EVAL_MODEL` available in the environment variables. The `evals` directory contains the evaluation suite for this Caveman skill.

First, inspect the baseline results for opus in `evals/snapshots` and understand them (scores, what works, what can be improved). Then think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language. Your goal is to maximize Caveman’s compression while preserving performance within 0.2 points in every evaluation category. Performance scores range from 1 to 5.

Do not make massive changes in a single round. Record what worked and what did not in lessons so the next round can build on it. Stop if changes begin to regress performance or fail to improve efficiency.

Use subagents. Do not run long tool calls yourself.

Do not get stuck in a local optimum. The goal is to reduce token usage while preserving scores within 0.2 points in each category. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.

Do iterative refinement each round. Have the code reviewer run the evals for subsequent changes so you do not have to.