# Same-input motor replacement control

This follow-up isolates the motor block more closely than the earlier sensory/planner comparison. It compares the two full connectomes plus their frozen readouts against a small stateless controller. Both arms receive the same **kind** of eight-channel sensor vector; values diverge naturally when bodies take different paths.

## Frozen protocol (before evaluation)

- Four new initialization seeds: 4101, 5101, 6101, 7101.
- Two arms per seed, alternating order; 1,800 seconds of world time per run.
- Both colonies begin with three insects and have the same cap of six. Geometry, needs, sensor gains, bodies, contact radii, economic parameters and procedural animation are unchanged.
- Sensory mode only: no planner goals, provisioners, routes, social recruitment or flocking.
- Each response advances the world by 0.4 seconds, in eight 0.05-second physics/ecology substeps. No predictive sensing. Faster computation cannot buy a higher update frequency in world time.
- Food, water, emergency cargo eating and bites have their neural-frequency gate removed in **both** arms. Contact, cooldown, territorial and other ecological conditions still apply. This is an explicit change from the earlier article experiments. No fictitious neural rates are supplied by the control.
- Primary observations: hunger/thirst deaths, persistence of both colonies, delivered food. Secondary: combat deaths, low-energy exposure, explored cells/resource sites, computation cost. No composite ranking score is used for conclusions.
- The policy is frozen before outcomes are known. A separate short pilot checks wiring; it is excluded from the long comparison. All negative and interrupted runs remain on disk.

## Reactive policy

`Scripts/BrainLab/reactive_control.py` uses equal weights for the three modalities. For channels `c[0:8]`:

```
lateral = (c0-c1) + (c2-c3) + (c4-c5)
turn = clamp(4*lateral, -1, 1)
drive = min(1, 2*c6) * (1-0.5*c7) / (1+abs(turn))
```

The sensor already weights food, water and home by authored needs and distance. The control sums their signed contributions, turns toward the larger input, moves faster with arousal and slows during turns/looming. It has no coordinates, resource identity, symbolic goal, memory, random exploration, neural weights or fitted decoder. Common body smoothing still applies.

The `reactive-v1` arm uses that same policy for both colonies. Historic backend labels in telemetry identify body/colony slots there; they do **not** indicate running SiliconFly/FlyBrainEngine processes. The service releases native workers in reactive sessions. In the connectome arm those engines still occupy fixed map sides. Paired results are therefore compared within the same side or pooled across both, without claiming one engine is superior to the other.

## Reproduction

With the Editor closed, build the project and restart its local service, then open it. The runner requires stopped PIE and no dirty map packages:

```sh
python3 Scripts/ue.py build
python3 Scripts/BrainLab/lab.py stop
python3 Scripts/BrainLab/lab.py start
python3 Scripts/ue.py open
Saved/BrainLab/venv/bin/python Scripts/BrainLab/controller_experiment.py --launch
```

A new run requires a new `--prefix`. Sources/configs/native binary hashes and traces are archived under `Saved/BrainLab/iterations/`; the preregistered plan and results live under `Saved/BrainLab/controller-control/<prefix>/`. The runner stops PIE after completion or failure. Ordinary Play and the `N` key retain the neural modes and original frequency gating.

## Interpretation limits

This is a descriptive test of one frozen reactive policy in one small authored world, not a benchmark of every classical AI method or a test of biological realism. A neural win would not establish that all 139k neurons are needed; a control win would show that this task can be solved without them. Delivery is partly limited by the prescribed reserve target and expenses. Engine placement is not randomized across map sides. Synchronous stepping controls command age but differs from previous live, asynchronous runs. Per-batch wall time excludes rendering/HTTP and is not a game FPS comparison.

## Completed results (22 September 2026)

All eight planned runs completed, each at 1800.180786 seconds of world time. No retries or excluded evaluation runs. Each ended with 6 + 6 living insects. The archived runtime source, configuration and model/binary hashes match across all runs.

| Seed | Neural delivery | Reactive delivery | Reactive difference | Deaths, neural / reactive |
|---|---:|---:|---:|---|
| 4101 | 1878.2 | 1873.6 | −0.25% | 0 / 1 combat |
| 5101 | 1886.4 | 1834.4 | −2.76% | 1 hunger / 0 |
| 6101 | 1906.0 | 1837.5 | −3.59% | 1 combat / 0 |
| 7101 | 1903.8 | 1848.1 | −2.93% | 0 / 0 |

Delivery totals combine both colonies and include the final snapshot. Differences use the paired neural run as denominator. Mean delivery is 1893.61 neural and 1848.40 reactive. These small deficits do not establish practical equivalence: demand and reserve targets constrain throughput, and movement differs substantially.

No reactive agent died from hunger or thirst; all sampled energy/hydration values stayed above 25. There were no dehydration deaths in either arm. The neural hunger death in seed 5101 was Cyan/SiliconFly #3 at about 1049.1 seconds. It remained nearly stationary for roughly 286 seconds despite nonzero motor commands; the trace suggests a blocked body but does not identify the exact collision. Do not interpret it as a deliberate refusal to eat.

Per-run total recorded path was about 23.0–23.1 km reactive versus 12.0–12.5 km neural. Similar delivery therefore did not mean identical locomotion or foraging efficiency. This test contains no blinded assessment of which behaviour looks more natural.

Median service batch time was 0.0731–0.0738 ms reactive and 535.4–544.9 ms neural, excluding HTTP and rendering. These are group-request costs, not frame times or per-neuron timings. Full wall durations were 113–116 seconds reactive and 2383–2523 seconds neural. Same simulated update interval isolates decision frequency; remaining Unreal/HTTP overhead limits overall wall-speed gains.

Conclusion: this authored sensor/economy arrangement supports colony provisioning with a small stateless policy, so the full connectome is not necessary for that demonstrated outcome. The neural arrangement delivered slightly more with less travel. Neither observation establishes superiority over other classical controllers, biological fidelity, or usefulness in a larger world.

Rebuild the complete summary and article figure from the project root:

```sh
Saved/BrainLab/venv/bin/python Scripts/BrainLab/summarize_controller_control.py --prefix motor-control-v1
Saved/BrainLab/venv/bin/python Docs/Articles/render_controller_control.py --extract
```

The detailed local report is `Saved/BrainLab/controller-control/motor-control-v1/report.md`; the article's `assets/controller-control-data.json` retains shareable compact results and input hashes. Normal rendering of `render_controller_control.py` uses that JSON without the Saved directory.
