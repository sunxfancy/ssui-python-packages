from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
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
