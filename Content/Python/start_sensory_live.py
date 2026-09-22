"""Leave the simultaneous-stimulus experiment playable, with no automatic stop."""
from pathlib import Path
import runpy
import unreal

runpy.run_path(str(Path(unreal.Paths.project_content_dir())/'Python/start_mosswild_live.py'),
              init_globals={'experiment_config': dict(sensory_competition=True,
                           contact_reflexes=True, swarm=False, synchronous=False,
                           continuous_economy=True, seed=1701)})
