Reduce caveman's token usage while keeping quality scores <= 0.2 points of baseline on every dimensions (completeness, correctness, actionability). 

The `evals` directory contains the evaluation suite. Committed baselines exist at `evals/snapshots/baseline-sonnet-4-6/` and `evals/snapshots/baseline-opus-4-6/`. Understand the opus baseline results (scores, what works and what can be improved). Compare your improvements against the opus baseline, NOT BOTH.

Then, think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language.

DO NOT make multiple changes in a single round. Do targeted, iterative improvement. Record what worked and what did not so the next round can build on it. Stop if changes regress performance or fail to improve compression.

Do not do all the work yourself or run long tool calls yourself. Use subagents. Let code-reviewer run eval so you, or the dev subagent don't have to.

Do not get stuck in a local optimum. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.