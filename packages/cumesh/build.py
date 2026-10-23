from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
# This fork vendors cubvh but omits its Eigen submodule. Supply pinned headers.
eigen_pin = json.loads(Path(__file__).with_name('eigen.json').read_text())
eigen = Path(ctx['source']) / 'third_party/cubvh/third_party/eigen'
if not (eigen / 'Eigen/Core').is_file():
    eigen.parent.mkdir(parents=True, exist_ok=True)
    run(['git', 'init', eigen])
    run(['git', 'remote', 'add', 'origin', eigen_pin['repository']], cwd=eigen)
    run(['git', 'fetch', '--depth=1', 'origin', eigen_pin['commit']], cwd=eigen)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=eigen)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=eigen, text=True).strip() != eigen_pin['commit']:
        raise RuntimeError('Eigen source SHA mismatch')
env = build_env(ctx)
# Actions has already activated MSVC. PyTorch rejects a second activation.
env['DISTUTILS_USE_SDK'] = '1'
env['MSSdk'] = '1'
# Git Bash prepends its Unix link.exe; setuptools must use the MSVC linker.
compiler_bin = Path(next(value for key, value in env.items() if key.upper() == 'VCTOOLSINSTALLDIR')) / 'bin/Hostx64/x64'
if not (compiler_bin / 'link.exe').is_file():
    raise RuntimeError('MSVC linker not found: ' + str(compiler_bin))
import os
env['PATH'] = str(compiler_bin) + os.pathsep + env['PATH']
run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
     str(Path(ctx['source']) / 'windows-rocm/build_wheel.ps1'),
     '-VenvRoot', ctx['venv'], '-GfxArch', ctx['target']['gpu_arch'], '-Wheelhouse', ctx['raw']],
    cwd=ctx['source'], env=env)
