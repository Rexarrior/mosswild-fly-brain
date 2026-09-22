"""Reproducible local build; dependencies, models and binaries stay in Saved/BrainLab."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'Saved/BrainLab'
HERE = Path(__file__).resolve().parent
REPOS = {
    'siliconfly': ('dawsonamf/siliconfly', '8839d84cd24888a4251a2e227792b6f26fbee776'),
    'flyBrain': ('mehrantsi/flyBrain', 'cdd3a127766ec184e19c4988fe12b6fd2cbc64fd'),
}

def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)

def main():
    import numpy as np
    LAB.mkdir(parents=True, exist_ok=True)
    for name, (repo, rev) in REPOS.items():
        dest = LAB / 'upstream' / name
        if not dest.exists():
            run('git', 'clone', 'https://github.com/' + repo + '.git', str(dest))
        current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dest, text=True).strip()
        if current != rev:
            run('git', 'fetch', 'origin', rev, cwd=dest)
            run('git', 'checkout', '--detach', rev, cwd=dest)
    silicon = LAB / 'upstream/siliconfly'
    fly = LAB / 'upstream/flyBrain'
    manifest = json.loads((silicon / 'data/connectome.json').read_text())
    for file, info in manifest['files'].items():
        assert hashlib.sha256((silicon / 'data' / file).read_bytes()).hexdigest() == info['sha256']
    raw = LAB / 'raw'
    raw.mkdir(exist_ok=True)
    provenance = {'repositories': REPOS, 'downloads': {}}
    # Pin the data repository as well as the engines on first setup.
    lock = HERE / 'data-lock.json'
    if lock.exists():
        data_lock = json.loads(lock.read_text())
    else:
        with urllib.request.urlopen('https://api.github.com/repos/eonsystemspbc/fly-brain/commits/main') as f:
            data_lock = {'revision': json.load(f)['sha'], 'sha256': {}}
    for name in ['2025_Completeness_783.csv', '2025_Connectivity_783.parquet']:
        url = f"https://raw.githubusercontent.com/eonsystemspbc/fly-brain/{data_lock['revision']}/data/{name}"
        dest = raw / name
        if not dest.exists():
            print('Downloading', name, flush=True)
            urllib.request.urlretrieve(url, dest.with_suffix(dest.suffix + '.part'))
            dest.with_suffix(dest.suffix + '.part').replace(dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if name in data_lock['sha256']:
            assert digest == data_lock['sha256'][name], f'Hash mismatch: {name}'
        data_lock['sha256'][name] = digest
        provenance['downloads'][name] = {'url': url, 'sha256': digest}
    lock.write_text(json.dumps(data_lock, indent=2) + '\n')
    pack = LAB / 'pack783'
    if not pack.exists():
        spec = importlib.util.spec_from_file_location('pack', fly / 'src/flybrain/pack.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(module.pack_connectome(raw / '2025_Completeness_783.csv', raw / '2025_Connectivity_783.parquet', pack, '783'), flush=True)

    def array(name):
        rec = manifest['arrays'][name]
        return np.fromfile(silicon / 'data' / rec['file'], dtype=rec['dtype'], count=rec['count'], offset=rec['byteOffset'])
    ids, role, side = array('rootId'), array('role'), array('side')
    row, col, weight = array('rowStart'), array('colIdx'), array('weight')
    pre = np.repeat(np.arange(len(ids)), np.diff(row).astype(np.int64))
    outputs = {'left': np.flatnonzero(np.isin(role, [4, 5]) & (side == 1)),
               'right': np.flatnonzero(np.isin(role, [4, 5]) & (side == 2)),
               'forward': np.flatnonzero(role == 6), 'escape': np.flatnonzero(role == 3)}
    pack_ids = np.load(pack / 'neuron_ids.npy')
    mapping = {int(v): i for i, v in enumerate(pack_ids)}
    common = np.array([int(v) in mapping for v in ids])
    scores = {key: np.bincount(pre, weights=np.where(np.isin(col, group) & (weight > 0), weight, 0), minlength=len(ids)) for key, group in outputs.items()}
    inputs = {}
    used = set(np.concatenate(list(outputs.values())).tolist())
    for key in ['left', 'right', 'forward']:
        other = 'right' if key == 'left' else 'left'
        score = scores[key] - (scores[other] if key != 'forward' else 0)
        eligible = common & (role == 0) & (score > 0)
        choices = [int(i) for i in np.argsort(-np.where(eligible, score, -1)) if eligible[i] and int(i) not in used][:24]
        assert len(choices) >= 12, key
        inputs[key] = choices
        used.update(choices)
    inputs['escape'] = np.flatnonzero(np.isin(role, [1, 2]) & common).tolist()
    groups = {}
    for backend in ['siliconfly', 'flybrain']:
        def convert(group):
            return [int(i) if backend == 'siliconfly' else mapping[int(ids[i])] for i in group if common[i]]
        groups[backend] = {'inputs': {k: convert(v) for k, v in inputs.items()}, 'outputs': {k: convert(v) for k, v in outputs.items()}}
    groups['root_ids'] = {'inputs': {k: [str(ids[i]) for i in v] for k, v in inputs.items()}, 'outputs': {k: [str(ids[i]) for i in v] for k, v in outputs.items()}}
    groups['method'] = 'Top 24 positive, side-selective upstream partners of DNa01/02 and DNp09; LC4/LPLC2 threat input. No output neurons receive external stimuli.'
    (LAB / 'groups.json').write_text(json.dumps(groups, indent=2))
    (LAB / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    run('swiftc', '-O', '-swift-version', '5', '-o', str(LAB / 'silicon-adapter'), str(silicon / 'Sim.swift'), str(silicon / 'MetalSim.swift'), str(HERE / 'adapters/SiliconAdapter.swift'), '-framework', 'Metal')
    native = LAB / 'native'
    (native / 'src').mkdir(parents=True, exist_ok=True)
    (native / 'shaders').mkdir(exist_ok=True)
    for file in ['metal_engine.rs', 'pack.rs', 'npy.rs', 'parameters.rs', 'stimulus.rs']:
        shutil.copy2(fly / 'rust/src' / file, native / 'src' / file)
    shutil.copy2(fly / 'rust/shaders/flybrain.metal', native / 'shaders/flybrain.metal')
    shutil.copy2(HERE / 'adapters/flybrain_main.rs', native / 'src/main.rs')
    shutil.copy2(HERE / 'adapters/Cargo.toml', native / 'Cargo.toml')
    if (HERE / 'adapters/Cargo.lock').exists():
        shutil.copy2(HERE / 'adapters/Cargo.lock', native / 'Cargo.lock')
    run(str(Path.home() / '.cargo/bin/cargo'), 'build', '--release', cwd=native)
    shutil.copy2(native / 'Cargo.lock', HERE / 'adapters/Cargo.lock')
    print('Ready:', LAB, flush=True)

if __name__ == '__main__':
    main()
