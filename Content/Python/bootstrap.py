"""Create the insect laboratory and biome if missing; preserve existing assets."""
from pathlib import Path
import runpy
import unreal
root = Path(unreal.Paths.project_content_dir()) / 'Python'
for script in ('build_insectarium.py', 'build_mosswild.py'):
    runpy.run_path(str(root / script), run_name='__main__')
