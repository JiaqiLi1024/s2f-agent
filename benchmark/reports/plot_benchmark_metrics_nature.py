#!/usr/bin/env python3
"""Render the manuscript benchmark metrics as a publication-ready figure."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


REPORT_DIR = Path(__file__).resolve().parent
SUMMARY_PATH = (
    REPORT_DIR
    / "manuscript"
    / "benchmark-summary-ttapi_s2f_gpt55_chat_full_20260523_152235.csv"
)
STATS_PATH = (
    REPORT_DIR
    / "manuscript"
    / "benchmark-stats-ttapi_s2f_gpt55_chat_full_20260523_152235.json"
)
SOURCE_DATA_PATH = REPORT_DIR / "benchmark_metrics_source_data.csv"
OUTPUT_STEM = REPORT_DIR / "benchmark_metrics_nature"

SUITE_LABELS = {
    "overall": "Overall",
    "routing": "Routing",
    "groundedness": "Groundedness",
    "task_success": "Task success",
}
PARTICIPANTS = {
    "s2f-agent": "s2f-agent",
    "gpt-5.5-ttapi-chat": "gpt-5.5 (ttapi chat)",
}
COLORS = {
    "s2f-agent": "#0F4D92",
    "gpt-5.5-ttapi-chat": "#767676",
    "delta": "#2A7F88",
    "grid": "#D9D9D9",
    "text": "#202020",
    "muted": "#666666",
}


def load_metrics() -> tuple[dict[tuple[str, str], dict[str, float]], list[dict]]:
    """Load and validate the strict-track manuscript snapshot."""
    with SUMMARY_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    suite_metrics: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        if (
            row["score_track"] == "strict"
            and row["participant_id"] in PARTICIPANTS
            and row["suite"] in {"routing", "groundedness", "task_success"}
        ):
            key = (row["participant_id"], row["suite"])
            suite_metrics[key] = {
                "n": int(row["total"]),
                "estimate": float(row["micro"]),
                "ci_low": float(row["micro_ci_low"]),
                "ci_high": float(row["micro_ci_high"]),
            }

    expected_keys = {
        (participant, suite)
        for participant in PARTICIPANTS
        for suite in ("routing", "groundedness", "task_success")
    }
    if set(suite_metrics) != expected_keys:
        missing = sorted(expected_keys - set(suite_metrics))
        raise ValueError(f"Missing strict suite metrics: {missing}")

    with STATS_PATH.open(encoding="utf-8") as handle:
        stats = json.load(handle)
    comparisons = stats["strict"]["comparisons"]
    comparisons_by_suite = {row["suite"]: row for row in comparisons}
    expected_suites = {"overall", "routing", "groundedness", "task_success"}
    if set(comparisons_by_suite) != expected_suites:
        raise ValueError("Strict paired comparisons are incomplete")

    ordered_comparisons = [comparisons_by_suite[suite] for suite in SUITE_LABELS]
    for comparison in ordered_comparisons:
        if (
            comparison["target"] != "s2f-agent"
            or comparison["baseline"] != "gpt-5.5-ttapi-chat"
        ):
            raise ValueError("Unexpected paired-comparison participants")

    return suite_metrics, ordered_comparisons


def write_source_data(
    suite_metrics: dict[tuple[str, str], dict[str, float]],
    comparisons: list[dict],
) -> None:
    """Write the exact values plotted in both panels."""
    fields = [
        "panel",
        "metric",
        "suite",
        "participant_or_comparison",
        "n",
        "estimate",
        "ci_low",
        "ci_high",
        "exact_mcnemar_p",
        "score_track",
        "source_file",
    ]
    output_rows = []
    for suite in ("routing", "groundedness", "task_success"):
        for participant, label in PARTICIPANTS.items():
            metric = suite_metrics[(participant, suite)]
            output_rows.append(
                {
                    "panel": "a",
                    "metric": "micro_pass_rate",
                    "suite": suite,
                    "participant_or_comparison": label,
                    "n": metric["n"],
                    "estimate": metric["estimate"],
                    "ci_low": metric["ci_low"],
                    "ci_high": metric["ci_high"],
                    "exact_mcnemar_p": "",
                    "score_track": "strict",
                    "source_file": SUMMARY_PATH.name,
                }
            )

    for comparison in comparisons:
        output_rows.append(
            {
                "panel": "b",
                "metric": "paired_micro_pass_rate_difference",
                "suite": comparison["suite"],
                "participant_or_comparison": "s2f-agent minus gpt-5.5 (ttapi chat)",
                "n": comparison["n"],
                "estimate": comparison["delta_micro"],
                "ci_low": comparison["delta_micro_ci"][0],
                "ci_high": comparison["delta_micro_ci"][1],
                "exact_mcnemar_p": comparison["mcnemar"]["p_value"],
                "score_track": "strict",
                "source_file": STATS_PATH.name,
            }
        )

    with SOURCE_DATA_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)


def format_p_value(value: float) -> str:
    if value < 0.001:
        exponent = 0
        coefficient = value
        while coefficient < 1:
            coefficient *= 10
            exponent -= 1
        return rf"$P={coefficient:.2f}\times10^{{{exponent}}}$"
    return rf"$P={value:.4f}$"


def style_axis(axis: plt.Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_visible(False)
    axis.spines["bottom"].set_color("#777777")
    axis.spines["bottom"].set_linewidth(0.6)
    axis.tick_params(axis="x", width=0.6, length=2.5, color="#777777", pad=2)
    axis.tick_params(axis="y", length=0, pad=4)
    axis.xaxis.grid(True, color=COLORS["grid"], linewidth=0.5, zorder=0)
    axis.yaxis.grid(False)


def render_figure(
    suite_metrics: dict[tuple[str, str], dict[str, float]],
    comparisons: list[dict],
) -> None:
    mm = 1 / 25.4
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 7,
            "legend.fontsize": 6.5,
            "text.color": COLORS["text"],
            "axes.labelcolor": COLORS["text"],
            "xtick.color": COLORS["text"],
            "ytick.color": COLORS["text"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, (ax_rate, ax_delta) = plt.subplots(
        1,
        2,
        figsize=(183 * mm, 90 * mm),
        gridspec_kw={"width_ratios": [1.0, 1.13]},
        facecolor="white",
    )
    fig.subplots_adjust(left=0.145, right=0.985, bottom=0.205, top=0.755, wspace=0.42)

    fig.text(
        0.055,
        0.955,
        "Benchmark metrics: legacy strict-track snapshot",
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.895,
        "Pass rates and paired effects across 54 aligned cases",
        ha="left",
        va="top",
        fontsize=7,
        color=COLORS["muted"],
    )

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color=COLORS["s2f-agent"],
            markerfacecolor="white",
            markeredgewidth=1.1,
            linewidth=1.2,
            markersize=4.3,
            label=PARTICIPANTS["s2f-agent"],
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color=COLORS["gpt-5.5-ttapi-chat"],
            markerfacecolor=COLORS["gpt-5.5-ttapi-chat"],
            linewidth=1.2,
            markersize=3.8,
            label=PARTICIPANTS["gpt-5.5-ttapi-chat"],
        ),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper right",
        bbox_to_anchor=(0.975, 0.922),
        frameon=False,
        ncol=2,
        columnspacing=1.2,
        handlelength=1.8,
        handletextpad=0.5,
    )

    # Panel a: suite-level pass rates with their bootstrap intervals.
    rate_suites = ("routing", "groundedness", "task_success")
    y_positions = {suite: 2 - index for index, suite in enumerate(rate_suites)}
    participant_style = {
        "s2f-agent": {"offset": 0.14, "marker": "o", "filled": False},
        "gpt-5.5-ttapi-chat": {"offset": -0.14, "marker": "s", "filled": True},
    }
    for participant in PARTICIPANTS:
        style = participant_style[participant]
        for suite in rate_suites:
            metric = suite_metrics[(participant, suite)]
            y_value = y_positions[suite] + style["offset"]
            facecolor = COLORS[participant] if style["filled"] else "white"
            ax_rate.errorbar(
                metric["estimate"],
                y_value,
                xerr=[
                    [metric["estimate"] - metric["ci_low"]],
                    [metric["ci_high"] - metric["estimate"]],
                ],
                fmt=style["marker"],
                color=COLORS[participant],
                markerfacecolor=facecolor,
                markeredgecolor=COLORS[participant],
                markeredgewidth=1.0,
                markersize=4.2,
                elinewidth=1.1,
                capsize=2.0,
                capthick=0.8,
                zorder=3,
            )
            estimate = metric["estimate"]
            if estimate > 0.90:
                label_x, horizontal_alignment = estimate - 0.035, "right"
            else:
                label_x, horizontal_alignment = estimate + 0.035, "left"
            label_y = y_value
            vertical_alignment = "center"
            if participant == "gpt-5.5-ttapi-chat":
                label_y += 0.07
                vertical_alignment = "bottom"
            ax_rate.text(
                label_x,
                label_y,
                f"{estimate * 100:.1f}%",
                ha=horizontal_alignment,
                va=vertical_alignment,
                fontsize=6.2,
                color=COLORS[participant],
            )

    ax_rate.set_title("Strict micro pass rate", loc="left", fontweight="bold", pad=7)
    ax_rate.set_xlim(-0.04, 1.07)
    ax_rate.set_ylim(-0.55, 2.55)
    ax_rate.set_xticks([0, 0.25, 0.50, 0.75, 1.00])
    ax_rate.set_xticklabels(["0", "25", "50", "75", "100"])
    ax_rate.set_xlabel("Cases passed (%)", labelpad=5)
    ax_rate.set_yticks(
        [y_positions[suite] for suite in rate_suites],
        [f"{SUITE_LABELS[suite]}  (n={suite_metrics[('s2f-agent', suite)]['n']})" for suite in rate_suites],
    )
    style_axis(ax_rate)

    # Panel b: paired micro-rate differences with exact test results.
    delta_y = {comparison["suite"]: 3 - i for i, comparison in enumerate(comparisons)}
    for comparison in comparisons:
        estimate = comparison["delta_micro"]
        low, high = comparison["delta_micro_ci"]
        y_value = delta_y[comparison["suite"]]
        ax_delta.errorbar(
            estimate,
            y_value,
            xerr=[[estimate - low], [high - estimate]],
            fmt="D",
            color=COLORS["delta"],
            markerfacecolor=COLORS["delta"],
            markeredgecolor="white",
            markeredgewidth=0.5,
            markersize=4.4,
            elinewidth=1.2,
            capsize=2.2,
            capthick=0.8,
            zorder=3,
        )
        if estimate > 0.92:
            label_x, horizontal_alignment = estimate - 0.035, "right"
        else:
            label_x, horizontal_alignment = estimate + 0.035, "left"
        ax_delta.text(
            label_x,
            y_value + 0.19,
            f"+{estimate * 100:.1f}%",
            ha=horizontal_alignment,
            va="bottom",
            fontsize=6.2,
            color=COLORS["delta"],
            fontweight="bold",
        )
        ax_delta.text(
            1.075,
            y_value,
            format_p_value(comparison["mcnemar"]["p_value"]),
            ha="left",
            va="center",
            fontsize=5.8,
            color=COLORS["muted"],
        )

    ax_delta.axvline(0, color="#777777", linewidth=0.7, linestyle=(0, (2, 2)), zorder=1)
    ax_delta.text(
        1.075,
        3.48,
        "Exact McNemar",
        ha="left",
        va="bottom",
        fontsize=5.8,
        color=COLORS["muted"],
        fontweight="bold",
    )
    ax_delta.set_title(
        "Paired pass-rate difference",
        loc="left",
        fontweight="bold",
        pad=7,
    )
    ax_delta.set_xlim(-0.04, 1.45)
    ax_delta.set_ylim(-0.55, 3.60)
    ax_delta.set_xticks([0, 0.25, 0.50, 0.75, 1.00])
    ax_delta.set_xticklabels(["0", "25", "50", "75", "100"])
    ax_delta.set_xlabel("s2f-agent advantage (percentage points)", labelpad=5)
    ax_delta.set_yticks(
        [delta_y[comparison["suite"]] for comparison in comparisons],
        [
            f"{SUITE_LABELS[comparison['suite']]}  (n={comparison['n']})"
            for comparison in comparisons
        ],
    )
    style_axis(ax_delta)

    ax_rate.text(
        -0.24,
        1.10,
        "a",
        transform=ax_rate.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax_delta.text(
        -0.24,
        1.10,
        "b",
        transform=ax_delta.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="top",
    )
    fig.text(
        0.055,
        0.055,
        "Legacy comparative snapshot; strict track; complete paired coverage; proxy model endpoint. Not a Benchmark v2 result.",
        ha="left",
        va="bottom",
        fontsize=6.2,
        color=COLORS["muted"],
    )

    fig.savefig(OUTPUT_STEM.with_suffix(".svg"), facecolor="white")
    fig.savefig(
        OUTPUT_STEM.with_suffix(".pdf"),
        facecolor="white",
        metadata={
            "Title": "Benchmark metrics: legacy strict-track snapshot",
            "Creator": "matplotlib",
        },
    )
    fig.savefig(OUTPUT_STEM.with_suffix(".png"), dpi=600, facecolor="white")
    fig.savefig(
        OUTPUT_STEM.with_suffix(".tiff"),
        dpi=600,
        facecolor="white",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)


def main() -> None:
    suite_metrics, comparisons = load_metrics()
    write_source_data(suite_metrics, comparisons)
    render_figure(suite_metrics, comparisons)
    print(f"Wrote source data: {SOURCE_DATA_PATH}")
    for suffix in ("svg", "pdf", "png", "tiff"):
        print(f"Wrote figure: {OUTPUT_STEM.with_suffix('.' + suffix)}")


if __name__ == "__main__":
    main()
