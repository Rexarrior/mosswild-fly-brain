# Simultaneous sensory populations

Mosswild has an optional experimental controller selected with **N** during Play.
Switching resets both colonies and their independent neural states. The default
controller remains the goal planner. The sensory mode does not call `PlanBiome`,
`AssignProvisioners`, `RouteBiome` or `SocialDirection`.

This experiment asks whether continuous, competing ecological stimuli can
produce useful embodied behaviour without selecting a resource or waypoint
before the connectome. There is no symbolic target decoder: the eventual approach
to a resource is an outcome of neural motor activity and body motion.

## Encoding

`InsectSensory.cpp` encodes eight nonnegative channels, in this order:

1. food positive/negative yaw;
2. water positive/negative yaw;
3. nest positive/negative yaw;
4. combined arousal;
5. looming/injury input.

The six lateral channels stimulate separate interleaved subsets of the existing
24 positive upstream partners on each side: ranks `0,3,6,...`, `1,4,7,...` and
`2,5,8,...`. Adapters name the sides left/right according to their motor probes;
game geometry uses signed Unreal yaw. Corresponding cells have the same FlyWire
root IDs in the two engines. These are **engineered input populations**, not an
anatomical identification of food, water or home pathways.

The three subsets each contain eight cells. Their per-cell stimulation gain is
three times the original all-24-cell motor input gain. The two engines retain
their different stimulus mechanisms (current in SiliconFly, seeded events in
FlyBrainEngine). Their responses need not match. Six lateral calls plus forward
and escape also fit SiliconFly's existing eight-stimulus queue without modifying
upstream engine code. Both interfaces request `durationMs = ms + 1`: the upstream
simulation expires a stimulus before the step reaching its end marker, so this
provides exactly `ms` active steps without overlap into the next window.

Hunger, thirst, nest reserve deficit, cargo and injury determine continuous input
gains. All resources inside the sensing radius contribute to their modality;
no resource receives a winning score. Scent uses squared linear falloff `(1-d/R)^2`.
The nest has an idealized longer-range cue. Nearby obstacles and bodies add
contralateral looming signals; collisions still use Unreal physics. There is no
waypoint routing or external flocking in this mode.

The encoder includes authored preferences (e.g. carrying cargo strengthens the
nest cue and weakens the food cue). Thus behaviour is not produced by an
unmodified isolated fly brain. The experiment changes where competing inputs
are combined; it does not establish biological fidelity or an advantage over
a much smaller recurrent policy or conventional controller.

The current gains are explicit and reproducible. Here `clamp` means `[0,1]`,
`E` is energy, `H` hydration, `C` cargo, `HP` health, `S` the nest store, and
`D = 60 + 20 × adults` the configured reserve target:

| Quantity | Formula |
|---|---|
| Hunger `h` | `clamp((120-E)/100)` |
| Thirst `t` | `clamp((100-H)/80)` |
| Reserve deficit `d` | `clamp((D-S)/max(1,D))` |
| Load `l` | `clamp(C/30)` |
| Injury `i` | `clamp((60-HP)/45)` |
| Food gain | `clamp(1.5h + 0.6d) × (1-0.92l)` |
| Water gain | `1.4t²` |
| Nest gain | `clamp(1.3l + 0.7i + 0.15clamp((E-108)/12))` |

Each resource contribution additionally uses availability `clamp(amount/40)`
and lateral response `clamp(abs(bearing)/65 degrees)`. Its signed bearing selects
the receiving hemisphere. Contributions remain separate across modalities and
are saturated only after summation and looming input. Nest reserve is read
directly; communication of that remote information is an idealization.

## Contact ecology and controls

Food and water uptake need physical contact and measured forward neural activity.
Carrying capacity, resource regeneration, energy/water expenditure, delivery,
territory claims and simplified brood rules use the existing economy. Local
feeding, drinking and territorial bites work without a planner goal. Brood and
delivery remain authored physical/economic rules; their mere existence is not
evidence that the network learned reproduction or logistics.

For paired experiments the planner uses the same contact reflexes via
`contact_reflexes: true`. Both modes use `swarm: false`, disabling recruitment
and flocking; the planner retains its local collision separation. This removes the trivial
confound of a sensory agent being unable to eat because it lacks a goal flag.
The control still has route planning and task assignment, so this compares the
two complete controller arrangements, not a single isolated synaptic mechanism.

The frozen motor readout uses only recorded descending-neuron rates; no input
channel or selected resource enters it directly. Its earlier training used
motor-intent stimuli. Concurrent bilateral activity is therefore a distribution
shift and must be checked separately before interpreting decisions as useful
goal selection. No connectome weights are trained in this experiment.

## Running and evidence

Build with the RPGPrototype editor closed, then open this project:

```sh
python3 Scripts/BrainLab/lab.py setup
python3 Scripts/ue.py build
python3 Scripts/BrainLab/lab.py stop
python3 Scripts/BrainLab/lab.py start
python3 Scripts/ue.py open
```

If a different Unreal project is already open, launch a separate editor instance;
macOS `open` may otherwise only activate the existing one. Do not close or save
another project as part of this experiment.

The native probe suite runs 11 stimulus cases × 3 seeds × 2 engines, each with
32 windows of 20 ms; the first 12 windows are discarded from summary means.
Use a fresh output directory for another probe suite.

```sh
Saved/BrainLab/venv/bin/python Scripts/BrainLab/sensory_probe.py
python3 Scripts/ue.py script Content/Python/sensory_smoke.py
Saved/BrainLab/venv/bin/python Scripts/BrainLab/sensory_experiment.py \
  --launch --duration 600 --seeds 1701 2701 --prefix sensory-visible-v1
Saved/BrainLab/venv/bin/python Scripts/BrainLab/summarize_sensory.py --prefix sensory-visible-v1
Saved/BrainLab/venv/bin/python Scripts/BrainLab/plot_sensory.py --prefix sensory-visible-v1
```

The smoke report is `Saved/BrainLab/sensory/smoke.json`. It checks both engines'
contact feeding/drinking/delivery, player interaction, ablation and restoration
of the planner in rendered PIE. Fixtures teleport actors to test contact rules;
they must not be mistaken for successful autonomous navigation.

For a fresh interactive sensory experiment without a stop timer, run this with
PIE stopped and the brain service running:

```sh
python3 Scripts/ue.py script Content/Python/start_sensory_live.py
```

It reports readiness in `Saved/BrainLab/live-launch.json`; the game runs until
the user presses Stop or Esc. Ordinary Play still starts the planner, and **N**
switches mode while resetting the colonies.

Paired runs default to actual rendered gameplay with asynchronous body updates.
Each 20 ms neural window grants at most 0.4 seconds of body motion, integrated
across display frames with sensory lookahead. This is a time-scaled experiment,
not biological real time. `--synchronous` instead integrates 0.4 seconds in 50 ms
steps at each brain response; motion then visibly advances in chunks.
Rendering stays enabled in both modes. Disabling it in the early pilot caused
HUD labels and health bars to accumulate in the viewport; that mode is removed.
Seeds use alternating mode order.
Seeds fix initialization and neural randomness; asynchronous frame integration
does not guarantee bit-for-bit identical trajectories on a repeated run.
The run stops at its requested duration even if the colony does poorly.

The two seeds are descriptive replications, not a statistical comparison. Engine
identity is fixed to colony location. A ten-minute run with a 12-adult cap cannot
establish long-term carrying capacity. The historical `stuck_fraction` also has
different eligibility rules for targetless and planner agents; do not use it as
a common performance score. The paired report instead includes a common motion
diagnostic based on path length during non-contact intervals.

`competing_modalities_fraction` counts intervals with at least two lateral
population pairs above 0.05 combined input. Looming can excite all three pairs,
so this is simultaneous population activity, not a count of conflicting economic
decisions. The isolated hungry/thirsty probes supply economic competition directly.

Traces, complete snapshots, analysis and source/binary hashes are retained in
`Saved/BrainLab/iterations/<prefix>-<mode>-<seed>/`. Inputs and outputs are also
logged by neural session in `Saved/BrainLab/batches.jsonl`. Session telemetry
adds `controller`, `contact_reflexes`, `social_steering`, per-agent
`sensory_channels`, `sensory_needs` (hunger, thirst, reserve deficit, load, injury)
and `contact_resource`. In sensory mode active agents have no goal/resource
target; a hatchling may be recorded before its first brain response.

Do not overwrite a completed or interrupted run. Results and plots belong in
`Saved/BrainLab/sensory/`; retain negative results alongside successful ones.
