"""Import hash-pinned ARM64 binaries, test the relabeled wheels, publish immutably.

This is a binary migration, not a claim that the original local builds were
produced by the hosted recipe pipeline. It leaves that pipeline untouched.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from core import canonical, sha256
from verify import relabel, verify_wheel
from release_store import find_release, gh, release_is_valid

TORCH = '2.16.0.dev20261026+cu134'
WORK = ROOT / '.work/arm64-import'


def entries():
    values = json.loads((HERE / 'registry.json').read_text())
    names = set()
    for value in values:
        name = value['package']
        if name in names or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
            raise ValueError('Duplicate or unsafe package')
        names.add(name)
        if value['backend'] not in ('cpu', 'cuda') or value['python'] not in ('3.12', '3.13'):
            raise ValueError('Unsupported ARM import target')
        if Path(value['input']['name']).name != value['input']['name'] or not re.fullmatch(r'[0-9a-f]{64}', value['input']['sha256']):
            raise ValueError('Unsafe or unpinned import')
    return values


def identity(entry):
    # Per-package source evidence plus the ARM-only migration/verification code.
    files = [HERE / n for n in ('migrate.py', 'rigging_checks.py', 'pixal_checks.py',
                               'rigging-build.py', 'sitecustomize.py', 'pixal-run-setup.py', 'patch-natten.py')]
    files += [ROOT / 'scripts/verify.py']
    files += sorted((HERE / 'provenance' / entry['package']).rglob('*'))
    digest = hashlib.sha256(canonical({'entry': entry, 'dependency_inputs': json.loads((HERE/'registry.json').read_text()), 'inputs': {
        p.relative_to(ROOT).as_posix(): sha256(p) for p in files if p.is_file()}})).hexdigest()
    cfg = dict(os='windows', arch='arm64', backend=entry['backend'], python=entry['python'])
    channel = 'windows/arm64/' + entry['backend']
    if entry['backend'] == 'cuda':
        cfg.update(sdk='13.4', torch=TORCH, gpu_arch='sm121')
        channel += '/13.4/' + TORCH.replace('+', '-') + '/sm121'
    target = 'windows-arm64-cp' + entry['python'].replace('.', '') + '-' + entry['backend']
    if entry['backend'] == 'cuda': target += '134-torch216dev20261026-sm121'
    version = entry['version'] + '+ssui.' + entry['backend'] + '.import1.b' + digest[:12]
    return dict(schema=1, package=entry['package'], target=target, fingerprint=digest,
                version=version, channel=channel, source=entry['source'], config=cfg)


def item(entry):
    return dict(package=entry['package'], recipe={'pure_python': entry['pure_python']}, config=identity(entry)['config'])


def prepare(raw):
    values = entries()
    versions = {e['package']: identity(e)['version'] for e in values}
    for entry in values:
        original = Path(raw) / entry['input']['name']
        if sha256(original) != entry['input']['sha256']:
            raise ValueError('Input wheel digest mismatch: ' + entry['package'])
        meta = identity(entry)
        out = WORK / entry['package'] / 'release'
        if out.exists(): raise ValueError('Bundle already exists: ' + str(out))
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            intermediate = Path(tmp) / original.name
            with zipfile.ZipFile(original) as zin, zipfile.ZipFile(intermediate, 'w', zipfile.ZIP_DEFLATED) as zout:
                for member in zin.infolist():
                    data = zin.read(member.filename)
                    if member.filename.endswith('.dist-info/METADATA'):
                        text = data.decode('utf-8')
                        lines = []
                        in_headers = True
                        for line in text.splitlines():
                            if not line: in_headers = False
                            match = re.match(r'Requires-Dist: ([A-Za-z0-9_.-]+)(.*)', line) if in_headers else None
                            if match:
                                name = re.sub(r'[-_.]+', '-', match[1]).lower()
                                # Torch is added by relabel below. Replace source URL dependencies
                                # with the exact migrated builds so pip cannot compile upstream.
                                if name == 'torch' and entry['backend'] == 'cuda': continue
                                if name in versions and entry['backend'] == 'cuda':
                                    marker = ';' + match[2].split(';', 1)[1] if ';' in match[2] else ''
                                    line = 'Requires-Dist: ' + name + '==' + versions[name] + marker
                            lines.append(line)
                        data = ('\n'.join(lines) + '\n').encode()
                    zout.writestr(member, data)
            wheel = relabel(intermediate, meta['version'], out,
                            TORCH if entry['backend'] == 'cuda' else None, entry['python'])
        verify_wheel(wheel, item(entry), meta['version'])
        print('Prepared', wheel.name, flush=True)


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def check_group(python, abi):
    selected = [e for e in entries() if e['python'] == abi]
    stage = WORK / ('installed-cp' + abi.replace('.', ''))
    if stage.exists(): raise ValueError('Use a fresh verification directory: ' + str(stage))
    wheels = [next((WORK/e['package']/'release').glob('*.whl')) for e in selected]
    env = os.environ.copy()
    temporary = WORK/'temp'
    temporary.mkdir(exist_ok=True)
    env['TEMP'] = env['TMP'] = str(temporary)
    run([python, '-m', 'pip', 'install', '--no-deps', '--no-index', '--target', stage, *wheels], env=env)
    env['PYTHONPATH'] = str(stage)
    env['PYTHONUTF8'] = '1'
    env['FLEX_GEMM_AUTOSAVE_AUTOTUNE_CACHE'] = '0'
    env['FLEX_GEMM_USE_AUTOTUNE_CACHE'] = '0'
    env['TRITON_CACHE_DIR'] = str(WORK/'triton-cache')
    env['TORCHINDUCTOR_CACHE_DIR'] = str(WORK/'inductor-cache')
    evidence = WORK / ('evidence-cp' + abi.replace('.', ''))
    evidence.mkdir(exist_ok=True)
    # Confirm distribution metadata comes from the just-installed artifacts.
    versions = {e['package']: identity(e)['version'] for e in selected}
    code = "import importlib.metadata as m,sys,platform; " + \
        f"assert '.'.join(map(str,sys.version_info[:2]))=={abi!r}; assert platform.machine().lower()=='arm64'; " + \
        f"expected={versions!r}; assert all(m.version(k)==v for k,v in expected.items())"
    run([python, '-c', code], env=env, cwd=WORK)
    if abi == '3.13':
        run([python, '-c', f"import torch; assert torch.__version__=={TORCH!r}; assert torch.version.cuda=='13.4'; assert torch.cuda.get_device_capability()==(12,1)"], env=env, cwd=WORK)
        run([python, HERE/'pixal_checks.py', '--output', evidence/'pixal.json',
             *[a for name in ('cuda_tensor','flex_gemm','sparse_convolution','cumesh','nvdiffrast','natten','o_voxel','opencv') for a in ('--check',name)]], env=env, cwd=WORK)
        run([python, HERE/'rigging_checks.py', '--worker', '--ops', 'pyg','pytorch3d','flash-attn','spconv',
             '--report',evidence/'rigging.json'], env=env, cwd=WORK)
        run([python, '-c', "import freetype; assert freetype.version()==(2,13,3); f=freetype.Face('C:/Windows/Fonts/arial.ttf'); f.set_pixel_sizes(0,24); f.load_char('A'); assert f.glyph.bitmap.width>0; print(freetype.version())"], env=env, cwd=WORK)
    else:
        run([python, '-c', "from tn.chinese.normalizer import Normalizer; n=Normalizer(); result=n.normalize('今天是2026年10月29日'); assert '2026' not in result; print(result)"], env=env, cwd=WORK)
    freeze = subprocess.check_output([python,'-m','pip','freeze','--all'], env=env, text=True, encoding='utf-8')
    host = subprocess.check_output([python,'-c',"import json,sys,platform; print(json.dumps(dict(python=sys.version,architecture=platform.machine())))"], text=True)
    for entry,wheel in zip(selected,wheels):
        meta = identity(entry)
        out = wheel.parent
        meta.update(checks=dict(wheel_metadata='passed',smoke='passed',
                                smoke_kind='installed-arm64-gpu-operators' if entry['backend']=='cuda' else 'installed-arm64-operation',
                                gpu_runtime=entry['backend']=='cuda'),
                    limitations=['Migration of hash-pinned local binaries, not a fresh source rebuild.',
                                 'Validated on Windows ARM64 only; GPU variants require the exact PyTorch/CUDA ABI and SM 12.1.',
                                 'Forward/operator checks do not establish full training or every model workflow compatibility.'],
                    provenance=dict(kind='verified-binary-migration', original_wheel=entry['input'],
                                    host=json.loads(host), validation_time=datetime.now(timezone.utc).isoformat()),
                    created_at=datetime.now(timezone.utc).isoformat())
        if abi=='3.13':
            for p in evidence.glob('*.json'): (out/p.name).write_bytes(p.read_bytes())
        (out/'build-environment.txt').write_text(freeze,encoding='utf-8')
        (out/'source-provenance.json').write_text(json.dumps(entry,indent=2)+'\n')
        meta['files']=[dict(name=p.name,size=p.stat().st_size,sha256=sha256(p)) for p in sorted(out.iterdir()) if p.name!='release.json']
        (out/'release.json').write_text(json.dumps(meta,indent=2)+'\n')
        print('Verified',entry['package'],flush=True)


def validate_bundle(entry):
    expected = identity(entry)
    out = WORK / entry['package'] / 'release'
    manifest = json.loads((out/'release.json').read_text())
    for key,value in expected.items():
        if manifest.get(key)!=value: raise ValueError('Stale bundle: '+key)
    if manifest.get('checks',{}).get('smoke')!='passed': raise ValueError('Missing runtime check')
    if manifest['provenance']['original_wheel']!=entry['input']: raise ValueError('Wrong input provenance')
    files=manifest['files']
    if len({f['name'] for f in files})!=len(files): raise ValueError('Duplicate assets')
    if {p.name for p in out.iterdir()}!={'release.json',*(f['name'] for f in files)}: raise ValueError('Unexpected assets')
    for f in files:
        if Path(f['name']).name!=f['name'] or sha256(out/f['name'])!=f['sha256'] or (out/f['name']).stat().st_size!=f['size']:
            raise ValueError('Bundle digest mismatch')
    wheels=list(out.glob('*.whl'))
    if len(wheels)!=1: raise ValueError('Expected one wheel')
    verify_wheel(wheels[0],item(entry),expected['version'])
    return out,manifest


def publish(repo, commit):
    if repo!='sunxfancy/ssui-python-packages' or not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Explicit repository and source commit required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--','arm64'],cwd=ROOT,text=True)
    if head!=commit or dirty: raise ValueError('Commit the exact ARM migration inputs before publishing')
    gh('api',f'repos/{repo}/commits/{commit}','--jq','.sha')
    # Verify all bundles before the first remote mutation.
    bundles=[(e,*validate_bundle(e)) for e in entries()]
    for entry,out,manifest in bundles:
        tag=entry['package']+'-'+entry['version']+'-arm64-import1--'+manifest['target']+'--'+manifest['fingerprint'][:20]
        existing=find_release(repo,tag)
        if existing:
            if not release_is_valid(existing,manifest) or existing['manifest']['files']!=manifest['files']:
                raise ValueError('Existing release differs; never overwrite: '+tag)
            print('Already verified',tag,flush=True)
            continue
        notes=out.parent/'notes.md'
        notes.write_text(f"ARM64 binary migration: {entry['package']} {manifest['version']}\n\n"
                         f"Channel: `{manifest['channel']}`\n\n"
                         f"GPU runtime checked: {manifest['checks']['gpu_runtime']}. Source was not rebuilt during migration. "
                         'See release.json, source-provenance.json and operator reports for exact ABI, checksums and limits.\n')
        gh('release','create',tag,'--repo',repo,'--draft','--target',commit,'--title',f"{entry['package']} {manifest['version']} (Windows ARM64)",'--notes-file',str(notes))
        gh('release','upload',tag,'--repo',repo,*[str(p) for p in sorted(out.iterdir())])
        gh('release','edit',tag,'--repo',repo,'--draft=false','--latest=false')
        if not release_is_valid(find_release(repo,tag),manifest): raise RuntimeError('Remote digest verification failed: '+tag)
        print('Published and verified',tag,flush=True)
    gh('api','--method','POST',f'repos/{repo}/dispatches','-f','event_type=wheel-published')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','check','publish','validate'])
    parser.add_argument('--raw',type=Path,default=WORK/'raw')
    parser.add_argument('--python',type=Path)
    parser.add_argument('--abi',choices=['3.12','3.13'])
    parser.add_argument('--repo',default='sunxfancy/ssui-python-packages')
    parser.add_argument('--commit')
    args=parser.parse_args()
    if args.action=='prepare': prepare(args.raw)
    elif args.action=='check':
        if not args.python or not args.abi: parser.error('--python and --abi required')
        check_group(args.python.resolve(),args.abi)
    elif args.action=='publish': publish(args.repo,args.commit or '')
    else:
        for e in entries(): validate_bundle(e)
        print('All ARM bundles verified')


if __name__=='__main__': main()
