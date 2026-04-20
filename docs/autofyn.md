You have `CLAUDE_CODE_OAUTH_TOKEN`, `CAVEMAN_JUDGE_MODEL` and `CAVEMAN_EVAL_MODEL` available in the environment variables. The `evals` directory contains the evaluation suite for this Caveman skill.

First, inspect the baseline results for sonnet in `evals/snapshots` and understand them (scores, what works, what can be improved). Then think like a prompt engineer: make surgical, precise changes that agents must follow. Be specific. Use strong language. Your goal is to maximize Caveman’s compression while preserving bottom3 performance >= 35 points in every evaluation category. Performance scores range from 1 to 50.

Do not make massive changes in a single round. Record what worked and what did not in lessons so the next round can build on it. Stop if changes begin to regress performance or fail to improve efficiency.

Use subagents. Do not run long tool calls yourself.

Do not get stuck in a local optimum. The goal is to reduce token usage while preserving bottom 3 scores >= 35 points in each category. Caveman is only an approach, not a constraint. If the evals suggest a better pattern or strategy, follow that instead.

Do iterative refinement each round. Have the code reviewer run the evals for subsequent changes so you do not have to. Think of fresh ideas or angles.