# Insect-only project cleanup — 2026-09-22

Removed Elderglen, its 28 materials, its map HUD/location labels, RPG equipment,
and its bootstrap/regression checks. The player remains a simple observer body
for interaction with insects. L now switches Mosswild and Insectarium.
The module identifier remains RPGPrototype for serialized asset compatibility.

Validation on macOS / UE 5.8.2:

- Closed-editor native build: succeeded.
- Biome smoke: 19 checks passed (both neural engines, feeding, drinking,
  delivery, territory, player combat, ablation, extinction, drought and reset).
- Service recovery: 7 checks passed, including both map transitions.
- Both maps: Map Check, 0 errors and 0 warnings; PIE stopped afterward.
- Python compilation, three reactive-controller unit tests and git diff --check passed.
- Source/article local links checked; article images use portable relative paths.

The first updated recovery test used the wrong Python property name and failed
before travel. It was corrected to expanded_biome and rerun; that failure is
retained locally in Saved/BrainLab/cleanup-recovery-property-failure.json.
Original experiment measurements were not rerun or modified by this cleanup.

Build and runtime reports remain under ignored Saved/BrainLab/. The residual
Elderglen package left on disk by Unreal's asset deletion was preserved intact
in Saved/Cleanup/ and removed from Content. No asset binary contents were edited.
