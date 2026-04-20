# Improving Caveman with AutoFyn

Caveman is a skill that makes AI coding agents respond in compressed caveman-style prose — dropping articles, filler, and pleasantries while keeping technical accuracy. It ships as a plugin for Claude Code, Codex, Cursor, and 40+ other agents.

But how do you measure whether a compression skill is actually good? And how do you improve it without breaking things?

## The original eval: 10 tasks, compression only

The original eval harness ran 10 developer questions through Claude with and without the caveman skill, then counted output tokens. The tasks were generic dev questions:

- "Why does my React component re-render every time the parent updates?"
- "Explain database connection pooling."
- "What's the difference between TCP and UDP?"
- "How do I fix a memory leak in a long-running Node.js process?"

Each prompt was run under three conditions: *no system prompt* (baseline), *"Answer concisely."* (terse control), and *"Answer concisely." plus the caveman SKILL.md*. Compression was measured as `1 - skill_tokens / terse_tokens` — how much shorter caveman makes answers compared to just asking the model to be concise.

We first discovered that 10 tasks is not enough. One outlier prompt swings the median. We saw the same SKILL.md produce anywhere from 27% to 54% compression across runs — noise exceeding the signal.

## Adding 10 more tasks

We added 10 more prompts covering broader territory:

- "What's the difference between a mutex and a semaphore?"
- "Why is my Docker container exiting immediately after starting?"
- "What are the tradeoffs between REST and GraphQL?"
- "How does JavaScript's event loop handle async operations?"
- "What happens during a TLS handshake?"

With 20 prompts, the variance dropped and measurements became reproducible. The median and mean started converging, and run-to-run noise shrank to a few percentage points rather than swinging wildly.

## Adding quality scoring

Compression alone is a dangerous metric. A skill that replies "k" to everything would score 99% compression and "win." The original eval had no way to detect this — it only counted tokens.

We added an LLM-as-judge step. After generating outputs, each skill answer is scored against the baseline on three dimensions (1-50 scale):

- **Completeness**: Are the essential technical points preserved? Does the answer cover what a developer needs?
- **Correctness**: Is everything stated technically accurate? No errors or misleading simplifications?
- **Actionability**: Could a developer solve their problem using only this answer?

The judge uses Claude Opus for consistency, with a detailed rubric and anchor points at each level. It's explicitly told not to penalize brevity — a short answer that covers all key points scores 50 on completeness. It also tolerates caveman grammar (dropped articles, sentence fragments) and standard abbreviations (DB, auth, config).

## Baseline: where caveman starts

Running the eval on Claude Sonnet 4.6 with the original SKILL.md:

| Metric | Value |
|--------|-------|
| Median compression | +45% |
| Mean compression | +44% |
| Min | +8% |
| Max | +71% |
| Completeness | 39.1 / 50 |
| Correctness | 48.0 / 50 |
| Actionability | 41.6 / 50 |

Caveman cuts nearly half the tokens compared to just saying "Answer concisely." Correctness is near-perfect — caveman doesn't introduce errors, it just compresses the delivery. Completeness and actionability take a modest hit as some detail gets dropped.

## AutoFyn's approach

[AutoFyn](https://github.com/SignalPilot-Labs/AutoFyn) is an autonomous AI agent that works on codebases in iterative rounds inside isolated Docker containers. We pointed it at the caveman repo with a simple directive: maximize compression while keeping quality scores stable.

AutoFyn's strategy:

1. **Read the baseline results** to understand current compression and quality scores
2. **Read the SKILL.md** to understand what rules drive the compression
3. **Make one surgical change** per round — add a rule, tighten a constraint, adjust an example
4. **Run the full eval pipeline** (generate outputs → judge quality → measure tokens) after each change
5. **Record what worked and what didn't**, so the next round builds on findings rather than repeating mistakes
6. **Revert if quality regresses** — compression gains aren't worth it if answers become useless

## The winning change

After exploring several approaches, the most effective change was adding structural compression rules:

- No markdown headers in answers — forces inline prose over formatted sections
- No numbered lists unless order matters — use semicolons or `→` chains instead
- Target line counts: 3-5 lines for simple questions, 6-10 for complex ones
- Merge related points into single lines

These rules attack the structure of the output, not just word choice. The original caveman skill already dropped articles and filler — the low-hanging fruit was gone. What remained was structural bloat: headers, numbered lists, and excessive line breaks that pad token counts without adding information.

## Results

| Metric | Baseline | AutoFyn | Delta |
|--------|----------|---------|-------|
| Median compression | +45% | +53% | **+8%** |
| Mean compression | +44% | +54% | **+10%** |
| Min | +8% | +17% | +9% |
| Max | +71% | +86% | +15% |
| Completeness | 39.1 | 37.5 | −1.6 |
| Correctness | 48.0 | 47.1 | −0.9 |
| Actionability | 41.6 | 39.6 | −2.0 |

Compression improved by 8-10 percentage points across the board. The minimum improved from +8% to +17% — meaning even the worst-case prompt now compresses meaningfully. The maximum hit +86%, nearly cutting token count by 7x on the best prompt.

Quality drops are modest: ~1-2 points on a 50-point scale. Correctness barely moved — the skill still doesn't introduce errors. Completeness and actionability take a small hit as the structural rules force denser output, but answers remain functional.

## What we learned

**Eval design matters more than you think.** With 10 prompts we couldn't tell signal from noise. With 20 prompts and a quality judge, we could finally make confident decisions about SKILL.md changes.

**Compression has two phases.** Phase 1 is word-level: drop articles, filler, hedging. The original caveman skill already did this well. Phase 2 is structural: eliminate headers, collapse lists, merge lines. AutoFyn found gains in phase 2 because phase 1 was already saturated.

**Quality-compression is a real tradeoff.** Every structural rule that increases compression slightly reduces completeness and actionability. The question isn't "can we compress more?" — it's always possible. The question is "how much quality are we willing to trade?"

**Autonomous agents can do prompt engineering.** AutoFyn treated SKILL.md like code — read it, change one thing, measure the effect, iterate. The same loop a human prompt engineer would follow, just faster and with less bias toward changes that "feel right."
