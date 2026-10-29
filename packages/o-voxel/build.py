from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source = Path(ctx['source'])
env = build_env(ctx)
env['DISTUTILS_USE_SDK'] = env['MSSdk'] = '1'
env['GPU_ARCHS'] = env['PYTORCH_ROCM_ARCH'] = ctx['target']['gpu_arch']
env['FORCE_CUDA'] = '1'
compiler = Path(next(v for k, v in env.items() if k.upper() == 'VCTOOLSINSTALLDIR')) / 'bin/Hostx64/x64'
if not (compiler / 'link.exe').is_file():
    raise RuntimeError('MSVC linker not found: ' + str(compiler))
env['PATH'] = str(compiler) + os.pathsep + env['PATH']
run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
     source / 'windows-rocm/build_wheel.ps1', '-VenvRoot', ctx['venv'],
     '-GfxArch', ctx['target']['gpu_arch'], '-Wheelhouse', ctx['raw']], cwd=source, env=env)
