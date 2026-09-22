"""Render an observed early failure, without running Unreal or either brain.

Usage: Saved/BrainLab/venv/bin/python Docs/Articles/render_circling.py
To rebuild the compact source excerpt, add --extract from the project root.

The source records positions about every 1.20 world seconds. Frames linearly
interpolate x/y and energy; yaw interpolates along the shortest angular arc.
The trail joins original recorded positions with straight segments. No path
smoothing or newly simulated movement is used. The bug's legs are a static
schematic, not a reconstruction of unrecorded joint animation. Axes translate
the source coordinates to the food position and convert centimetres to metres.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mosswild-circling-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Ellipse
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = HERE / "assets"
SOURCE = ROOT / "Saved/BrainLab/iterations/09-readout/trace.jsonl"
CONFIG = ROOT / "Saved/BrainLab/iterations/09-readout/source/Config/BrainBiome.json"
DATA = ASSETS / "circling-data.json"
OUTPUT = ASSETS / "mosswild-circling.gif"


def extract():
    records = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    columns = ["elapsed", "x", "y", "yaw", "energy", "health", "consumed"]
    samples = []
    for record in records:
        if not 455 <= record["elapsed"] <= 517:
            continue
        for agent in record["agents"]:
            if agent["id"] == 2:
                assert agent["backend"] == "siliconfly"
                assert agent["intent"] == "Forage" and agent["resource"] == 5
                assert (agent["target_x"], agent["target_y"]) == (450, -1400)
                assert record["resources"][5]["amount"] == 280
                samples.append([record["elapsed"]] + [agent[key] for key in columns[1:]])
    assert len(samples) >= 40
    assert len({sample[-1] for sample in samples}) == 1
    point = json.loads(CONFIG.read_text())["points"][5]
    document = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "config_source": str(CONFIG.relative_to(ROOT)),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "run": "09-readout", "agent_id": 2, "backend": "siliconfly",
        "motor_smoothing_seconds": 0.35,
        "source_coordinate_unit": "cm", "source_yaw_unit": "degrees",
        "source_time_unit": "world_seconds", "columns": columns,
        "median_sample_interval_seconds": float(np.median(np.diff([s[0] for s in samples]))),
        "food": {"name": point["name"], "x": point["x"], "y": point["y"],
                 "recorded_amount": 280, "contact_radius_cm": 155},
        "display": {"speed": 5, "fps": 12,
                    "position_interpolation": "linear between recorded samples",
                    "yaw_interpolation": "shortest angular arc between recorded samples",
                    "energy_interpolation": "linear between recorded samples",
                    "trail": "straight segments through original samples, last 12 world seconds",
                    "body": "static schematic; joint motion was not recorded",
                    "gif_timing": "frame timestamps rounded to 10 ms; last frame held for one nominal frame",
                    "axes": "source x/y translated to food and divided by 100"},
        "limits": "This is a telemetry reconstruction, not recorded gameplay. The last frame is the last selected live sample. No death time is reconstructed.",
        "samples": samples,
    }
    ASSETS.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def render(preview_dir):
    document = json.loads(DATA.read_text())
    data = np.asarray(document["samples"], dtype=float)
    times = data[:, 0]
    x = (data[:, 1] - document["food"]["x"]) / 100
    y = (data[:, 2] - document["food"]["y"]) / 100
    yaw = np.unwrap(np.radians(data[:, 3]))
    speed, fps = document["display"]["speed"], document["display"]["fps"]
    frame_times = np.linspace(times[0], times[-1], math.ceil((times[-1] - times[0]) / speed * fps) + 1)
    background, ink, blue, muted = "#f7f6f1", "#24343d", "#168fb6", "#63737b"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(8.6, 5.3), dpi=100, facecolor=background)
    ax = fig.add_axes([0.075, 0.17, 0.55, 0.66], facecolor=background)
    ax.set(xlim=(-3.8, 3.8), ylim=(-2.0, 5.5), aspect="equal",
           xlabel="X от кормушки, м", ylabel="Y от кормушки, м")
    ax.grid(color="#dce0df", linewidth=0.7, zorder=0)
    ax.tick_params(colors=muted, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#c6cecc")
    ax.add_patch(Circle((0, 0), 1.55, facecolor="#73915e", alpha=0.10, edgecolor="none"))
    ax.add_patch(Circle((0, 0), 1.55, fill=False, edgecolor="#8b9b7c", linestyle="--", linewidth=1))
    ax.scatter([0], [0], s=130, marker="*", color="#638447", zorder=4)
    ax.text(0, -0.47, "Еда", ha="center", color="#516f39", fontsize=11)
    ax.text(0, -1.83, "Контакт с едой: < 1,55 м", ha="center", color=muted, fontsize=8)
    trail, = ax.plot([], [], color=blue, alpha=0.48, linewidth=2, zorder=3)
    recorded, = ax.plot([], [], ".", color=blue, alpha=0.55, markersize=3, zorder=3)
    body = Ellipse((0, 0), 0.62, 0.30, facecolor=blue, edgecolor="#124e66", linewidth=1, zorder=6)
    head = Circle((0, 0), 0.13, facecolor="#124e66", zorder=7)
    legs = LineCollection([], colors="#124e66", linewidths=1.6, zorder=5)
    ax.add_patch(body); ax.add_patch(head); ax.add_collection(legs)
    fig.text(0.075, 0.942, "Траектория из лога · ранний цикл 9 · ×5", fontsize=15, weight="bold", color=ink)
    fig.text(0.075, 0.887, "SiliconFly · особь №2 · реконструкция по телеметрии", fontsize=11, color=muted)
    fig.text(0.68, 0.77, "Время мира", color=muted)
    time_text = fig.text(0.68, 0.708, "", fontsize=22, color=ink)
    fig.text(0.68, 0.60, "Энергия", color=muted)
    energy_text = fig.text(0.68, 0.535, "", fontsize=25, weight="bold", color="#ab6125")
    fig.text(0.68, 0.40, "Съедено за отрезок", color=muted)
    fig.text(0.68, 0.347, "0 единиц", fontsize=17, color=ink)
    fig.text(0.68, 0.252, "Еды в источнике: 280", fontsize=10, color=muted)
    fig.text(0.075, 0.053, "Замеры каждые ≈1,20 с; между ними положение интерполировано.", fontsize=9, color=muted)
    fig.text(0.075, 0.018, "Форма жука схематичная. Координаты и направление взяты из журнала.", fontsize=8, color=muted)
    local_legs = []
    for side in (-1, 1):
        for along, tip in ((0.20, 0.39), (0.0, -0.03), (-0.20, -0.40)):
            local_legs.append([(along, side * .08), (tip, side * .30), (tip-.1, side * .43)])
    local_legs = np.asarray(local_legs)

    def frame(t):
        px, py = np.interp(t, times, x), np.interp(t, times, y)
        angle = np.interp(t, times, yaw)
        energy = np.interp(t, times, data[:, 4])
        eligible = (times >= t - 12) & (times <= t)
        trail.set_data(np.r_[x[eligible], px], np.r_[y[eligible], py])
        recorded.set_data(x[eligible], y[eligible])
        body.center = (px, py); body.angle = np.degrees(angle)
        head.center = (px + .32*np.cos(angle), py + .32*np.sin(angle))
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        legs.set_segments(local_legs @ rotation.T + [px, py])
        time_text.set_text(f"{t:.1f} с")
        energy_text.set_text(f"{energy:.1f}")
        return trail, recorded, body, head, legs, time_text, energy_text

    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)
        for i, index in enumerate((0, len(frame_times)//3, 2*len(frame_times)//3, len(frame_times)-1)):
            frame(frame_times[index])
            fig.savefig(preview_dir / f"circling-{i}.png", dpi=100)
    animation = FuncAnimation(fig, frame, frames=frame_times, interval=1000/fps, blit=False)
    animation.save(OUTPUT, writer=PillowWriter(fps=fps))
    # GIF stores delays in 10 ms units. A fixed 12 fps delay otherwise truncates
    # every frame to 80 ms and unintentionally speeds up the recorded movement.
    boundaries = np.rint((frame_times-times[0])/speed*100).astype(int)*10
    delays = np.diff(boundaries).astype(int).tolist() + [round(100/fps)*10]
    with Image.open(OUTPUT) as gif:
        frames = []
        for i in range(gif.n_frames):
            gif.seek(i)
            frames.append(gif.convert("RGB"))
    assert len(frames) == len(delays)
    frames[0].save(OUTPUT, save_all=True, append_images=frames[1:],
                   duration=delays, loop=0, optimize=True)
    plt.close(fig)
    print(json.dumps({"gif": str(OUTPUT), "bytes": OUTPUT.stat().st_size,
                      "frames": len(frame_times), "nominal_fps": fps,
                      "gif_duration_ms": sum(delays),
                      "world_seconds": float(times[-1]-times[0]),
                      "requested_speed": speed, "source_samples": len(times)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true", help="Rebuild compact data from the preserved cycle-9 log.")
    parser.add_argument("--preview-dir", type=Path, help="Write four inspection frames outside the publication assets.")
    args = parser.parse_args()
    if args.extract:
        extract()
    render(args.preview_dir)
