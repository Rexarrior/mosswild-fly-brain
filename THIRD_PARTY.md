# External engines and data

The setup script downloads external sources into ignored `Saved/BrainLab/upstream/`.
They are not vendored in this repository. Keep their notices when redistributing
built adapters or downloaded data.

- [SiliconFly](https://github.com/dawsonamf/siliconfly), revision
  `8839d84cd24888a4251a2e227792b6f26fbee776`: MIT, copyright Denis Shiryaev and
  Dawson Metzger-Fleetwood (2026). See upstream `LICENSE`.
- [FlyBrainEngine](https://github.com/mehrantsi/flyBrain), revision
  `cdd3a127766ec184e19c4988fe12b6fd2cbc64fd`: MIT, copyright FlyBrain Engine
  contributors (2026). See upstream `LICENSE`.
- FlyWire FAFB v783 data: downloaded separately. SiliconFly's
  [`data/DATA_LICENSE.md`](https://github.com/dawsonamf/siliconfly/blob/8839d84cd24888a4251a2e227792b6f26fbee776/data/DATA_LICENSE.md)
  identifies CC BY-NC 4.0 terms for the underlying data. Engine code licenses do
  not grant commercial rights to the connectome data. Source revisions and
  checksums are pinned in `Scripts/BrainLab/setup.py` and `data-lock.json`.
- Unreal Engine is installed separately under Epic's terms; no engine binaries
  or starter content are redistributed. Scene geometry uses installed engine
  basic shapes and project-created materials.

See `Docs/BrainLab.md` for counts, adapters and scientific limitations.
