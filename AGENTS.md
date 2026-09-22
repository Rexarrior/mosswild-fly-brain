# Mosswild

Unreal Engine 5.8.2 on Apple Silicon. Read the parent AGENTS.md when present.

- This is the insect connectome experiment. Default map: `/Game/Maps/Mosswild`.
  `/Game/Maps/Insectarium` retains the first laboratory. Elderglen was removed.
- Keep the `RPGPrototype` module/project identifier compatible with saved assets.
- Run `python3 Scripts/ue.py build`, `open`, `status` from this directory.
- Close this project's editor before native builds; preserve dirty packages.
- `bootstrap` creates missing insect maps; `smoke` runs biome checks in PIE.
- Asset edits must use Unreal APIs, never binary/text editing of uasset/umap.
- Keep caches, models and raw reports in ignored Saved/. Never commit credentials.
- Editor automation uses loopback UDP 6776 / TCP 6777; BrainLab uses 18765.
- Keep historical experiment reports intact. Do not claim archived measurements
  came from later cleanup builds, and do not silently repeat evaluation runs.
