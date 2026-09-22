"""Render the two article figures from assets/sensory-data.json only.

From the project root, with matplotlib installed:
    Saved/BrainLab/venv/bin/python Docs/Articles/render_sensory_figures.py

To rebuild the compact data from the recorded runs, then render:
    Saved/BrainLab/venv/bin/python Docs/Articles/render_sensory_figures.py --extract

--source-root accepts another project root containing the same Saved paths.
Extraction never writes to the source logs. It retains every sampled position,
rounding only coordinates to 0.001 m; times and aggregate values stay unrounded.
"""

import argparse
import hashlib
import json
from pathlib import Path

ARTICLE = Path(__file__).resolve().parent
ASSETS = ARTICLE / "assets"
PREFIX = "sensory-visible-v1"
SEEDS = (1701, 2701)
MODES = ("sensory", "planner")
MODE_LABELS = {"sensory": "Сенсорное управление", "planner": "Планировщик"}
MODE_COLORS = {"sensory": "#7549A4", "planner": "#287A5C"}
ENGINE_COLORS = {"siliconfly": "#008EAD", "flybrain": "#BD7C26"}
ENGINE_LABELS = {"siliconfly": "SiliconFly", "flybrain": "FlyBrainEngine"}
SEED_STYLES = {1701: "-", 2701: (0, (5, 3))}


def read_source(root, relative, sources):
    """Record provenance from exactly the bytes used for extraction."""
    raw = (root / relative).read_bytes()
    sources[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
    return raw.decode("utf-8")


def metres(value):
    return round(value / 100, 3)


def compact_geometry(geometry):
    return {
        "half_width_m": metres(geometry["half_width"]),
        "half_height_m": metres(geometry["half_height"]),
        "homes_xy_m": [[metres(x), metres(y)] for x, y in geometry["homes"]],
        "resources_kind_xy_m": [
            [q["kind"], metres(q["x"]), metres(q["y"])]
            for q in geometry["points"]
        ],
        "obstacles_xyr_m": [
            [metres(q["x"]), metres(q["y"]), metres(q["radius"])]
            for q in geometry["obstacles"]
        ],
    }


def compact_run(rows, final, name, mode, seed):
    if not rows or final["elapsed"] < rows[-1]["elapsed"]:
        raise ValueError(f"{name}: missing trace or final precedes trace")
    # Keep the complete snapshot even if its time equals the last trace sample.
    samples = rows + [final]
    times = [row["elapsed"] for row in samples]
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError(f"{name}: non-monotonic game time")
    expected_controller = "sensory-populations-v1" if mode == "sensory" else "planner"
    tracks = {}
    last_seen = {}
    for sample_index, row in enumerate(samples):
        if row["seed"] != seed or row["controller"] != expected_controller:
            raise ValueError(f"{name}: controller or seed changed")
        if row["alive"] != len(row["agents"]):
            raise ValueError(f"{name}: alive count differs from recorded agents")
        keys_in_sample = set()
        for agent in row["agents"]:
            key = (agent["backend"], agent["id"], agent["generation"])
            if key in keys_in_sample:
                raise ValueError(f"{name}: duplicate agent identity")
            keys_in_sample.add(key)
            track = tracks.setdefault(key, {
                "backend": key[0], "id": key[1], "generation": key[2], "segments": [],
            })
            # Never connect across a missing observation, death, or new identity.
            if last_seen.get(key) != sample_index - 1:
                track["segments"].append({"first_sample": sample_index, "xy_m": []})
            track["segments"][-1]["xy_m"].append([metres(agent["x"]), metres(agent["y"])])
            last_seen[key] = sample_index
    return {
        "name": name, "mode": mode, "seed": seed,
        "trace_samples": len(rows), "final_sample": len(rows),
        "elapsed_s": times,
        "alive": [row["alive"] for row in samples],
        "food_delivered": [row["food_delivered"] for row in samples],
        "final": {key: final[key] for key in (
            "elapsed", "alive", "food_delivered", "births", "deaths", "combat_deaths"
        )},
        "tracks": [tracks[key] for key in sorted(tracks)],
    }


def extract(root, output):
    sources = {}
    summary_path = Path("Saved/BrainLab/sensory") / f"{PREFIX}-summary.json"
    summary = json.loads(read_source(root, summary_path, sources))
    summaries = {row["name"]: row for row in summary["runs"]}
    geometries = []
    runs = []
    for seed in SEEDS:
        for mode in MODES:
            name = f"{PREFIX}-{mode}-{seed}"
            folder = Path("Saved/BrainLab/iterations") / name
            rows = [json.loads(line) for line in read_source(
                root, folder / "trace.jsonl", sources
            ).splitlines() if line.strip()]
            final = json.loads(read_source(root, folder / "complete.json", sources))
            geometry = compact_geometry(json.loads(read_source(
                root, folder / "source/Config/BrainBiome.json", sources
            )))
            reference = summaries[name]
            for key in ("alive", "food_delivered", "births", "deaths", "combat_deaths"):
                if reference[key] != final[key]:
                    raise ValueError(f"{name}: summary and complete disagree on {key}")
            if reference["world_seconds"] != final["elapsed"]:
                raise ValueError(f"{name}: summary and complete disagree on time")
            run = compact_run(rows, final, name, mode, seed)
            if geometry not in geometries:
                geometries.append(geometry)
            run["geometry"] = geometries.index(geometry)
            runs.append(run)
    data = {
        "schema": 1,
        "description": "Four recorded runs; two initial states, each with two control modes.",
        "units": {"elapsed_s": "game seconds", "xy_m": "metres, rounded to 0.001",
                  "alive": "living agents, total of both colonies",
                  "food_delivered": "cumulative model food units, total of both colonies"},
        "sampling": "Every trace snapshot plus complete.json; no resampling or smoothing. "
                    "Segment coordinates map to successive samples starting at first_sample.",
        "limitations": "Only two initial states; no statistical superiority claim. Engine identity is tied to colony location. "
                        "Straight path segments join observations; positions between samples are unknown.",
        "sources_sha256": sources,
        "geometries": geometries,
        "runs": runs,
    }
    output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return data


def configure_plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 14, "axes.titleweight": "bold",
        "axes.labelcolor": "#42505A", "text.color": "#23343F",
        "xtick.color": "#596873", "ytick.color": "#596873",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,
        # Preserve all vertices, including small turns and short-lived changes.
        "path.simplify": False,
    })
    return plt


def render_comparison(data, plt, output):
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 6.5))
    fig.subplots_adjust(left=0.075, right=0.98, bottom=0.20, top=0.66, wspace=0.23)
    fig.text(0.075, 0.95, "Mosswild: два режима управления", fontsize=22, weight="bold")
    fig.text(0.075, 0.892, "Четыре прогона · два начальных состояния · около 10 игровых минут", fontsize=11)
    fig.legend(handles=[Line2D([], [], color=MODE_COLORS[mode], lw=2.5, label=MODE_LABELS[mode])
                        for mode in MODES], loc="upper left", bbox_to_anchor=(0.068, 0.855),
               ncol=2, frameon=False, handlelength=2.7, columnspacing=2.5)
    fig.legend(handles=[Line2D([], [], color="#596873", lw=1.6, ls=SEED_STYLES[seed],
                              label=f"Начальное состояние {seed}") for seed in SEEDS],
               loc="upper left", bbox_to_anchor=(0.068, 0.800), ncol=2, frameon=False,
               handlelength=2.7, columnspacing=2.5)
    for run in data["runs"]:
        minutes = [value / 60 for value in run["elapsed_s"]]
        kwargs = {"color": MODE_COLORS[run["mode"]], "linestyle": SEED_STYLES[run["seed"]],
                  "linewidth": 1.8, "zorder": 3}
        axes[0].plot(minutes, run["alive"], drawstyle="steps-post", **kwargs)
        axes[1].plot(minutes, run["food_delivered"], drawstyle="steps-post", **kwargs)
    axes[0].set_title("Численность", loc="left", pad=16)
    axes[0].set_ylabel("Живых особей")
    axes[0].set_ylim(0, 13)
    axes[0].set_yticks(range(0, 13, 2))
    axes[1].set_title("Накопленная доставка еды", loc="left", pad=16)
    axes[1].set_ylabel("Единиц еды")
    axes[1].set_ylim(0, 1000)
    for ax in axes:
        ax.set_xlim(0, max(run["elapsed_s"][-1] for run in data["runs"]) / 60)
        ax.set_xticks(range(0, 11, 2))
        ax.set_xlabel("Игровое время, мин", labelpad=10)
        ax.tick_params(length=0, pad=6)
        ax.grid(axis="y", color="#E5E9EC", linewidth=0.8, zorder=0)
    fig.text(0.075, 0.070, "Все количества — сумма по двум колониям. Цвет обозначает режим управления, а не движок.",
             fontsize=9.5, color="#596873")
    fig.text(0.075, 0.035, "Ступени показывают записанные значения; время изменений известно с точностью до интервала записи.",
             fontsize=9.5, color="#596873")
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


def render_paths(data, plt, output):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 12.8))
    fig.subplots_adjust(left=0.080, right=0.980, bottom=0.130, top=0.805, wspace=0.15, hspace=0.28)
    fig.text(0.080, 0.963, "Mosswild: наблюдённые траектории", fontsize=22, weight="bold")
    fig.text(0.080, 0.928, "Строки — два начальных состояния; столбцы — режимы управления", fontsize=11)
    fig.legend(handles=[Line2D([], [], color=ENGINE_COLORS[key], lw=2, label=f"Движок {ENGINE_LABELS[key]}")
                        for key in ENGINE_COLORS], loc="upper left", bbox_to_anchor=(0.073, 0.908),
               ncol=2, frameon=False, handlelength=2.6, columnspacing=2.4)
    fig.legend(handles=[
        Line2D([], [], marker="s", ls="", color="#528647", label="Еда", markersize=6),
        Line2D([], [], marker="s", ls="", color="#406DA6", label="Вода", markersize=6),
        Line2D([], [], marker="*", ls="", color="#23343F", label="Гнездо", markersize=12),
        Line2D([], [], marker="o", ls="", color="#D9DEE2", markeredgecolor="#9CA8AE", label="Препятствие", markersize=8),
    ], loc="upper left", bbox_to_anchor=(0.073, 0.875), ncol=4, frameon=False,
       handlelength=1.2, columnspacing=2.0)
    lookup = {(run["seed"], run["mode"]): run for run in data["runs"]}
    for row_index, seed in enumerate(SEEDS):
        for column_index, mode in enumerate(MODES):
            ax = axes[row_index, column_index]
            run = lookup[seed, mode]
            geometry = data["geometries"][run["geometry"]]
            for x, y, radius in geometry["obstacles_xyr_m"]:
                ax.add_patch(Circle((x, y), radius, facecolor="#E6EAED", edgecolor="#ABB6BD", lw=0.6, zorder=1))
            for track in run["tracks"]:
                for segment in track["segments"]:
                    points = segment["xy_m"]
                    x, y = zip(*points)
                    ax.plot(x, y, color=ENGINE_COLORS[track["backend"]], lw=0.7, alpha=0.60,
                            marker="." if len(points) == 1 else None, markersize=2, zorder=2)
            for kind, x, y in geometry["resources_kind_xy_m"]:
                ax.scatter(x, y, c="#406DA6" if kind == 1 else "#528647", marker="s", s=25,
                           edgecolors="white", linewidths=0.4, zorder=4)
            for x, y in geometry["homes_xy_m"]:
                ax.scatter(x, y, c="#23343F", edgecolors="white", linewidths=0.5, marker="*", s=160, zorder=5)
            ax.set(xlim=(-geometry["half_width_m"], geometry["half_width_m"]),
                   ylim=(-geometry["half_height_m"], geometry["half_height_m"]),
                   aspect="equal", xlabel="X, м", ylabel="Y, м")
            ax.set_title(f"{MODE_LABELS[mode]}\nНачальное состояние {seed}", loc="left", fontsize=12, pad=12)
            ax.set_xticks(range(-40, 41, 20))
            ax.set_yticks(range(-40, 41, 20))
            ax.tick_params(length=0, pad=6)
            ax.grid(color="#E8ECEF", linewidth=0.6, zorder=0)
    fig.text(0.080, 0.077, "Все записанные положения за ≈10 игровых минут; линии соединяют соседние отсчёты одной особи.",
             fontsize=9.5, color="#596873")
    fig.text(0.080, 0.051, "Новые особи начинают отдельные линии. Между отсчётами движение неизвестно; сглаживание не применялось.",
             fontsize=9.5, color="#596873")
    fig.text(0.080, 0.025, "Цвет здесь обозначает движок. Его идентичность связана с расположением колонии.",
             fontsize=9.5, color="#596873")
    fig.savefig(output, dpi=170, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extract", action="store_true", help="rebuild compact JSON from recorded Saved sources")
    parser.add_argument("--source-root", type=Path, default=ARTICLE.parents[1], help="project root for --extract")
    args = parser.parse_args()
    data_path = ASSETS / "sensory-data.json"
    data = extract(args.source_root.resolve(), data_path) if args.extract else json.loads(data_path.read_text(encoding="utf-8"))
    if data["schema"] != 1:
        raise ValueError("Unsupported sensory-data schema")
    plt = configure_plotting()
    for filename, renderer in (("mosswild-sensory-comparison.png", render_comparison),
                               ("mosswild-sensory-paths.png", render_paths)):
        output = ASSETS / filename
        renderer(data, plt, output)
        print(output)


if __name__ == "__main__":
    main()
