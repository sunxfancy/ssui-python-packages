"""Build exactly one pinned source/target, then produce a verified release bundle."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from core import ROOT, channel, fingerprint, load_targets, sha256, wheel_version
from runtime import build_env, run
from verify import relabel, verify_wheel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--fingerprint', required=True)
    args = parser.parse_args()
    selected = [item for item in load_targets() if item['package'] == args.package and item['target'] == args.target]
    if len(selected) != 1:
        raise ValueError('Unknown package/target')
    item = selected[0]
    digest = fingerprint(ROOT, item)
    if digest != args.fingerprint:
        raise ValueError('Build inputs differ from the selected plan')
    cfg = item['config']
    host_os = {'win32': 'windows', 'darwin': 'macos', 'linux': 'linux'}[sys.platform]
    host_arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}[platform.machine().lower()]
    if (host_os, host_arch) != (cfg['os'], cfg['arch']):
        raise ValueError(f'Native build required, running on {host_os}/{host_arch}')
    if f'{sys.version_info.major}.{sys.version_info.minor}' != cfg['python']:
        raise ValueError('Wrong Python ABI for target')
    # MSBuild's file tracker still hits MAX_PATH even on long-path-enabled
    # Windows. Keep the native compiler tree short; full identity stays in JSON.
    work = (Path(os.environ['RUNNER_TEMP']) / 'sw' / digest[:16]
            if os.environ.get('RUNNER_TEMP') else ROOT / '.work' / digest[:16])
    work.mkdir(parents=True, exist_ok=True)
    source, venv, raw, out = [work / name for name in ('source', 'venv', 'raw-wheels', 'release')]
    # A reused dirty source tree must not silently change a declared build.
    if source.exists() or venv.exists() or out.exists():
        raise ValueError(f'Build directory already used: {work}; choose a clean workspace')
    raw.mkdir()
    run(['git', 'init', str(source)])
    run(['git', 'remote', 'add', 'origin', 'https://github.com/' + item['recipe']['source']['repository'] + '.git'], cwd=source)
    run(['git', 'fetch', '--depth=1', 'origin', item['recipe']['source']['commit']], cwd=source)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if actual != item['recipe']['source']['commit']:
        raise ValueError('Source checkout SHA mismatch')
    run(['git', 'submodule', 'update', '--init', '--recursive', '--depth=1'], cwd=source)
    patch_dir = ROOT / 'packages' / item['package'] / 'patches'
    for patch in sorted(patch_dir.glob('*.patch')):
        run(['git', 'apply', '--check', patch], cwd=source)
        run(['git', 'apply', patch], cwd=source)
    run([sys.executable, '-m', 'venv', venv])
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    run([python, '-m', 'pip', 'install', '-r', ROOT / item['toolchain']['requirements']])
    if item['toolchain']['bootstrap']:
        run([python, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', *item['toolchain']['bootstrap']])
    if cfg['backend'] == 'rocm':
        run([python, '-m', 'rocm_sdk', 'init'])
    ctx = {'source': str(source), 'venv': str(venv), 'python': str(python),
           'raw': str(raw), 'out': str(out), 'target': cfg, 'recipe': item['recipe'],
           'version': wheel_version(item, digest)}
    context_path = work / 'context.json'
    context_path.write_text(json.dumps(ctx, indent=2), encoding='utf-8')
    package_dir = ROOT / 'packages' / item['package']
    run([sys.executable, package_dir / 'build.py', '--context', context_path])
    wheels = sorted(raw.glob('*.whl'))
    if len(wheels) != 1:
        raise ValueError(f'Expected one package wheel, got {len(wheels)}')
    wheel = relabel(wheels[0], ctx['version'], out, cfg.get('torch'), cfg['python'])
    verify_wheel(wheel, item, ctx['version'])
    run([python, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', wheel])
    run([sys.executable, package_dir / 'smoke_test.py', '--context', context_path])
    freeze = subprocess.check_output([python, '-m', 'pip', 'freeze', '--all'], text=True, env=build_env(ctx))
    (out / 'build-environment.txt').write_text(freeze, encoding='utf-8')
    manifest = {'schema': 1, 'package': item['package'], 'target': item['target'],
                'fingerprint': digest, 'version': ctx['version'], 'channel': channel(item),
                'source': item['recipe']['source'], 'config': cfg,
                'checks': {'wheel_metadata': 'passed', 'smoke': 'passed',
                           'smoke_kind': item['recipe']['tests'], 'gpu_runtime': False},
                'provenance': {'repository_commit': os.environ.get('GITHUB_SHA'),
                               'run_id': os.environ.get('GITHUB_RUN_ID'),
                               'runner_image': os.environ.get('ImageVersion'),
                               'python': sys.version, 'toolchain': item['toolchain']},
                'created_at': datetime.now(timezone.utc).isoformat(),
                'files': [{'name': path.name, 'size': path.stat().st_size, 'sha256': sha256(path)}
                          for path in sorted(out.iterdir()) if path.is_file()]}
    (out / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as stream:
            stream.write(f'release_dir={out}\n')
    print(f'Verified release bundle: {out}')


if __name__ == '__main__':
    main()
