"""
Generate a boxplot showing the distribution of token compression per
skill, compared against a plain "Answer concisely." control.

Reads evals/snapshots/<tag>/results.json and writes:
  - evals/snapshots/<tag>/results.html  (interactive plotly)
  - evals/snapshots/<tag>/results.png   (static export for README/PR embed)

Run: uv run --with tiktoken --with plotly --with kaleido python evals/plot.py --tag round-0
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import plotly.graph_objects as go
import tiktoken

ENCODING = tiktoken.get_encoding("o200k_base")
EVALS = Path(__file__).parent
RESULTS_DIR = EVALS / "snapshots"


def count(text: str) -> int:
    """Count tokens in a string using tiktoken."""
    return len(ENCODING.encode(text))


def main() -> None:
    """Generate compression boxplot from eval results."""
    parser = argparse.ArgumentParser(description="Plot eval results")
    parser.add_argument(
        "--tag",
        required=True,
        help="Run tag (e.g. round-0). Reads from evals/snapshots/<tag>/",
    )
    args = parser.parse_args()

    results_path = RESULTS_DIR / args.tag / "results.json"
    if not results_path.exists():
        print(f"No results at {results_path}. Run llm_run.py first.")
        return

    data = json.loads(results_path.read_text())
    arms = data["arms"]
    meta = data.get("metadata", {})

    terse_tokens = [count(o) for o in arms["__terse__"]]

    rows = []
    for skill, outputs in arms.items():
        if skill in ("__baseline__", "__terse__"):
            continue
        skill_tokens = [count(o) for o in outputs]
        savings = [
            (1 - (s / t)) * 100 if t else 0.0
            for s, t in zip(skill_tokens, terse_tokens)
        ]
        rows.append(
            {"skill": skill, "savings": savings, "median": statistics.median(savings)}
        )

    rows.sort(key=lambda r: -r["median"])

    fig = go.Figure()

    for row in rows:
        fig.add_trace(
            go.Box(
                y=row["savings"],
                name=row["skill"],
                boxpoints="all",
                jitter=0.4,
                pointpos=0,
                marker=dict(color="#2ca02c", size=7, opacity=0.7),
                line=dict(color="#2c3e50", width=2),
                fillcolor="rgba(76, 120, 168, 0.25)",
                boxmean=True,
                hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
            )
        )

    fig.add_hline(
        y=0,
        line=dict(color="black", width=1.5, dash="dash"),
        annotation_text="no effect (= same length as control)",
        annotation_position="top right",
        annotation_font=dict(size=11, color="black"),
    )

    for row in rows:
        fig.add_annotation(
            x=row["skill"],
            y=max(row["savings"]),
            text=f"<b>{row['median']:+.0f}%</b>",
            showarrow=False,
            yshift=22,
            font=dict(size=16, color="#2c3e50"),
        )

    fig.update_layout(
        title=dict(
            text=f"<b>How much shorter does each skill make Claude's answers?</b><br>"
            f"<sub>Distribution of per-prompt savings vs system prompt = "
            f"<i>'Answer concisely.'</i><br>"
            f"{meta.get('model', '?')} · n={meta.get('n_prompts', '?')} prompts · "
            f"single run per arm</sub>",
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(title="", automargin=True),
        yaxis=dict(
            title="↑ shorter  ·  vs control  ·  longer ↓",
            ticksuffix="%",
            zeroline=False,
            gridcolor="rgba(0,0,0,0.08)",
            range=[-30, 115],
        ),
        plot_bgcolor="white",
        height=560,
        width=980,
        margin=dict(l=140, r=80, t=120, b=120),
        showlegend=False,
        annotations=[
            dict(
                x=0.5,
                y=-0.22,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=11, color="#555"),
                text=(
                    "<b>box</b> = IQR (middle 50%) · "
                    "<b>line in box</b> = median · "
                    "<b>dashed line</b> = mean · "
                    "<b>green dots</b> = individual prompts"
                ),
            )
        ],
    )

    for row in rows:
        fig.add_annotation(
            x=row["skill"],
            y=max(row["savings"]),
            text=f"<b>{row['median']:+.0f}%</b>",
            showarrow=False,
            yshift=22,
            font=dict(size=16, color="#2c3e50"),
        )

    html_out = RESULTS_DIR / args.tag / "results.html"
    png_out = RESULTS_DIR / args.tag / "results.png"
    fig.write_html(html_out)
    print(f"Wrote {html_out}")
    fig.write_image(png_out, scale=2)
    print(f"Wrote {png_out}")


if __name__ == "__main__":
    main()
