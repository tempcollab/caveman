# Evals

Measures real token compression **and quality** of caveman skills by
running the same prompts through Claude Code under three conditions,
comparing output token counts, and scoring with an LLM judge.

## The three arms

| Arm | System prompt |
|-----|--------------|
| `__baseline__` | none |
| `__terse__` | `Answer concisely.` |
| `<skill>` | `Answer concisely.\n\n{SKILL.md}` |

The honest delta for any skill is **`<skill>` vs `__terse__`** — i.e.
how much the skill itself adds on top of a plain "be terse" instruction.
Comparing a skill to the no-system-prompt baseline conflates the skill
with the generic terseness ask.

## Setup

`llm_run.py` and `judge.py` shell out to the `claude` CLI. Install it
if not already present:

```bash
npm install -g @anthropic-ai/claude-code
```

### Authentication

| Method | How | When to use |
|--------|-----|-------------|
| Interactive login | `claude login` | Local dev — opens browser |
| OAuth token | `export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...` | Docker / CI / headless |

### Benchmarks (SDK-based, separate)

`benchmarks/run.py` uses the Anthropic Python SDK and requires a
standard API key in `.env.local`. It gives exact token counts but costs
real money. Run it occasionally, not every round.

## Results directory

Tagged runs are saved to `evals/snapshots/<tag>/`:

```
evals/snapshots/<tag>/
  ├── results.json    # raw LLM outputs (llm_run.py)
  ├── judge.json      # quality scores (judge.py)
  └── summary.json    # combined stats (measure.py)
```

`--tag` is required for all scripts.

## Workflow

### Full eval with quality scoring

```bash
# 1. Generate outputs
uv run python evals/llm_run.py --tag round-0

# 2. Judge quality (compares skill vs baseline)
uv run python evals/judge.py --tag round-0

# 3. Measure compression + quality
uv run --with tiktoken python evals/measure.py --tag round-0
```

Use a small model for generation, opus for judging:

```bash
CAVEMAN_EVAL_MODEL=claude-sonnet-4-6 uv run python evals/llm_run.py --tag round-0
CAVEMAN_JUDGE_MODEL=claude-opus-4-6 uv run python evals/judge.py --tag round-0
```

Judge defaults to `claude-opus-4-6` for consistent scoring. Generation
model is configurable via `CAVEMAN_EVAL_MODEL`.

### Committed baselines

Run baselines once per model and commit them so every iteration starts
from a fixed reference:

```bash
CAVEMAN_EVAL_MODEL=claude-sonnet-4-6 uv run python evals/llm_run.py --tag baseline-sonnet-4-6
uv run python evals/judge.py --tag baseline-sonnet-4-6
uv run --with tiktoken python evals/measure.py --tag baseline-sonnet-4-6
git add evals/snapshots/baseline-*/ && git commit -m "evals: add baseline for sonnet-4-6"
```

### Compare before/after changes

```bash
# Before changes
uv run python evals/llm_run.py --tag before
uv run python evals/judge.py --tag before
uv run --with tiktoken python evals/measure.py --tag before

# Make changes to skills/caveman/SKILL.md

# After changes
uv run python evals/llm_run.py --tag after
uv run python evals/judge.py --tag after
uv run --with tiktoken python evals/measure.py --tag after

# Compare summary.json files
```

### AutoFyn / CI integration

AutoFyn gives each run a tag (e.g. `round-1`, `round-2`). Results
accumulate in `evals/snapshots/` so you can track improvement over time.

```bash
# AutoFyn round loop
uv run python evals/llm_run.py --tag round-$N
uv run python evals/judge.py --tag round-$N
uv run --with tiktoken python evals/measure.py --tag round-$N

# Success criteria: compression up, quality scores stable
```

## Files

- `prompts/en.txt` — fixed list of dev questions, one per line.
- `llm_run.py` — runs `claude -p --system-prompt …` per (prompt, arm),
  captures real LLM output, writes results.json.
- `judge.py` — pairwise quality judge. For each (prompt, skill), asks
  Claude to score the compressed answer against the baseline on
  completeness (1-50), correctness (1-50), and actionability (1-50).
- `measure.py` — reads results.json + judge.json, counts tokens with
  tiktoken, prints a markdown table with compression and quality stats.
- `snapshots/<tag>/` — run results directory.

## Adding a prompt

Append a line to `prompts/en.txt`, then run a new tagged eval.

## Adding a skill

Drop a `skills/<name>/SKILL.md`. `llm_run.py` picks up every skill
directory automatically.

## Quality scoring

The judge compares each skill output against the baseline on three
dimensions:

| Dimension | What it measures | 50 = best |
|-----------|-----------------|-----------|
| Completeness | All key technical points covered? | Nothing important missing |
| Correctness | Everything stated is accurate? | Fully correct |
| Actionability | Developer can act on this? | Fully actionable |

A good caveman skill should score 40+ on all three while maximizing
token compression. If quality drops below 30, the skill is too aggressive.

## What this does NOT measure

- **Latency or cost** — skills add input tokens, so output savings are
  not the full economic picture.
- **Cross-model behavior** — only the model used to generate the
  snapshot is measured.
- **Exact Claude tokens** — `tiktoken o200k_base` is OpenAI's BPE and
  is only an approximation. Ratios are meaningful; absolute numbers
  approximate.
- **Statistical significance** — single run per (prompt, arm). The
  min/max columns let you eyeball noise, but this is not a powered
  experiment.
