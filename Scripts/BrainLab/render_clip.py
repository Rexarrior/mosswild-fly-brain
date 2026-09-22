"""Encode the real timed frames produced by Content/Python/biome_capture.py."""
import argparse
import json
from pathlib import Path
import shutil
import statistics
import subprocess
from runtime import LAB, ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--folder',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'Docs/Mosswild.mp4')
    args=parser.parse_args()
    folder=args.folder or Path(json.loads((LAB/'animation-latest.json').read_text())['folder'])
    capture=json.loads((folder/'frames.json').read_text())
    assert not capture.get('error'),capture.get('error')
    frames=capture['frames'];assert len(frames)>5,'Insufficient captured frames'
    gaps=[b['wall_seconds']-a['wall_seconds'] for a,b in zip(frames,frames[1:])]
    assert all(gap>0 for gap in gaps),'Non-monotonic capture timestamps'
    lines=['ffconcat version 1.0']
    for index,frame in enumerate(frames):
        path=Path(frame['path'])
        assert path.is_file() and path.parent.resolve()==folder.resolve(),path
        assert path.name.startswith('frame-') and path.suffix in ('.png','.jpg'),path
        duration=gaps[index] if index<len(gaps) else statistics.median(gaps)
        lines.extend([f'file {path.name}',f'duration {duration:.6f}'])
    lines.append(f"file {Path(frames[-1]['path']).name}")
    manifest=folder/'clip.ffconcat';manifest.write_text('\n'.join(lines)+'\n')
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg,'Install ffmpeg to encode the clip'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0',
                    '-i',str(manifest),'-an','-c:v','libx264','-preset','medium','-crf','20',
                    '-vf','scale=1600:-2','-pix_fmt','yuv420p','-fps_mode','vfr',
                    '-movflags','+faststart',str(args.output)],check=True)
    print(json.dumps(dict(output=str(args.output),frames=len(frames),
                         capture_seconds=frames[-1]['wall_seconds']-frames[0]['wall_seconds'],
                         median_capture_interval=statistics.median(gaps)),indent=2))


if __name__=='__main__':main()
