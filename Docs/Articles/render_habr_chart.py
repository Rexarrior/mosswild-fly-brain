"""Render the article chart from a compact extract of the recorded session.

From the project root:
MPLCONFIGDIR=Saved/BrainLab/mpl-cache Saved/BrainLab/venv/bin/python \
    Docs/Articles/render_habr_chart.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def main():
    assets = Path(__file__).resolve().parent / "assets"
    data = json.loads((assets / "mosswild-night-data.json").read_text())
    population = data["population"]
    windows = data["delivery_windows"]
    colors = ["#008EAD", "#BD7C26"]
    labels = ["SiliconFly · голубые", "FlyBrainEngine · янтарные"]

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelcolor": "#42505A",
        "text.color": "#23343F",
        "xtick.color": "#596873",
        "ytick.color": "#596873",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": False,
    })
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.9))
    fig.subplots_adjust(left=0.065, right=0.98, bottom=0.19, top=0.68, wspace=0.21)
    fig.text(0.065, 0.94, "Ночь в Mosswild", fontsize=21, weight="bold")
    fig.text(0.065, 0.875, "5 ч 25 мин игрового мира · 683 доставки · 16 рождений · 10 смертей", fontsize=11)
    fig.legend(
        handles=[Patch(facecolor=color, label=label) for color, label in zip(colors, labels)],
        loc="upper left", bbox_to_anchor=(0.057, 0.84), ncol=2,
        frameon=False, handlelength=1.1, columnspacing=2.0,
    )

    hours = [row["world_seconds"] / 3600 for row in population]
    for colony in range(2):
        axes[0].step(
            hours, [row["counts"][colony] for row in population],
            where="post", color=colors[colony], linewidth=2.0,
            linestyle="-" if colony == 0 else (0, (4, 3)),
            zorder=3 + colony,
        )
    axes[0].set_title("Численность восстанавливалась", loc="left", pad=16)
    axes[0].set_ylabel("Живых особей")
    axes[0].set_ylim(0, 6.6)
    axes[0].set_yticks(range(7))

    for window in windows:
        duration = window["end"] - window["start"]
        center = (window["start"] + window["end"]) / 7200
        width = duration / 3600 * 0.35
        for colony in range(2):
            axes[1].bar(
                center + (colony - 0.5) * width,
                window["deliveries"][colony] / (duration / 60),
                width=width * 0.9, color=colors[colony], zorder=3,
            )
    axes[1].set_title("Доставка продолжалась", loc="left", pad=16)
    axes[1].set_ylabel("Единиц еды за игровую минуту")
    axes[1].set_ylim(0, 35)

    for ax in axes:
        ax.set_xlim(0, hours[-1])
        ax.set_xticks(range(6))
        ax.set_xlabel("Время в игровом мире, ч", labelpad=10)
        ax.tick_params(length=0, pad=6)
        ax.grid(axis="y", color="#E5E9EC", linewidth=0.8, zorder=0)
    fig.text(
        0.065, 0.045,
        "Доставка усреднена по 30 минутам; последний интервал — 25,5 минуты. Численность без сглаживания.",
        fontsize=9, color="#596873",
    )
    output = assets / "mosswild-night.png"
    fig.savefig(output, dpi=170, facecolor="white")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
