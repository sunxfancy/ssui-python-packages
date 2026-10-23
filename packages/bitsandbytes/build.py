import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source, python = Path(ctx['source']), ctx['python']
env = build_env(ctx)
wheelhouse = Path(ctx['raw']).parent / 'official-wheel'
run([python, '-m', 'pip', 'download', 'bitsandbytes==' + ctx['recipe']['version'], '--no-deps', '--only-binary=:all:', '-d', wheelhouse], env=env)
official = next(wheelhouse.glob('bitsandbytes-*.whl'))
run([python, '-m', 'pip', 'install', '--no-deps', official], env=env)
vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
vsroot = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
if not vsroot:
    raise RuntimeError('Visual Studio C++ tools not found')
vcvars = Path(vsroot) / 'VC/Auxiliary/Build/vcvars64.bat'
run(['cmd', '/d', '/c', source / 'windows-rocm/build_rocm_windows.cmd', ctx['venv'], ctx['target']['gpu_arch'], vcvars], cwd=source, env=env)
dll = next((source / 'windows-rocm/build').glob('libbitsandbytes_rocm*.dll'))
run([python, source / 'windows-rocm/package_wheel.py', '--official-wheel', official, '--dll', dll, '--out', ctx['raw']], env=env)
