from pathlib import Path
import os
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source, python = Path(ctx['source']), ctx['python']
env = build_env(ctx)
compiler = shutil.which('cl.exe', path=env['PATH'])
if not compiler:
    raise RuntimeError('ARM64 MSVC developer environment is not active')
env['PATH'] = str(Path(compiler).parent) + os.pathsep + env['PATH']
env['PYTHON_PREFIX'] = ctx['venv']
env['CMAKE_CONFIGURATION'] = 'windows312_arm64'
build_dir = source.parent / 'vtk-build'
run(['cmake', '-S', source, '-B', build_dir, '-G', 'Ninja',
     '-C', source / '.gitlab/ci/configure_wheel.cmake', '-DCMAKE_BUILD_TYPE=Release',
     '-DVTK_WRAP_PYTHON=ON', '-DVTK_WHEEL_BUILD=ON', '-DVTK_BUILD_TESTING=OFF',
     '-DVTK_BUILD_EXAMPLES=OFF', '-DVTK_VERSION_SUFFIX=', f'-DPython3_EXECUTABLE={python}',
     # The upstream CI preset assumes Kitware's sccache installation.
     '-DCMAKE_C_COMPILER_LAUNCHER=', '-DCMAKE_CXX_COMPILER_LAUNCHER=',
     '-DCMAKE_CUDA_COMPILER_LAUNCHER='], env=env)
run(['cmake', '--build', build_dir, '--parallel', '4'], env=env)
run([python, 'setup.py', 'bdist_wheel', '--dist-dir', ctx['raw']], cwd=build_dir, env=env)
