from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
     str(Path(ctx['source']) / 'windows-rocm/build_wheel.ps1'),
     '-VenvRoot', ctx['venv'], '-GfxArch', ctx['target']['gpu_arch'], '-Wheelhouse', ctx['raw']],
    cwd=ctx['source'], env=build_env(ctx))
