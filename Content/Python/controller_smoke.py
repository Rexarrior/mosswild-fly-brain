"""Contact mechanics for the reactive control, followed by normal neural Play restoration."""
from pathlib import Path
import runpy
import unreal
runpy.run_path(str(Path(unreal.Paths.project_content_dir())/'Python/sensory_smoke.py'),
              init_globals=dict(motor_controller='reactive-v1',
                                report_name='BrainLab/controller-control/smoke-reactive-v1.json'))
