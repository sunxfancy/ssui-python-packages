"""Package adapters for the Windows ARM64 CPU supplement channel."""
import json
import os
import shutil
from pathlib import Path
import sys

from runtime import build_env, context, run


def build(package_dir):
    ctx = context()
    cfg = json.loads((Path(package_dir) / 'build.json').read_text())
    source, python = Path(ctx['source']), ctx['python']
    env = build_env(ctx)
    env.update(cfg.get('env', {}))
    env['DISTUTILS_USE_SDK'] = env['MSSdk'] = '1'
    env['CMAKE_BUILD_PARALLEL_LEVEL'] = '4'
    env['CMAKE_GENERATOR'] = 'Ninja'
    compiler = shutil.which('cl.exe', path=env['PATH'])
    if not compiler:
        raise RuntimeError('Activate the ARM64 MSVC developer environment before building')
    env['PATH'] = str(Path(compiler).parent) + os.pathsep + env['PATH']
    if cfg.get('rust'):
        toolchain = '1.90.0-aarch64-pc-windows-msvc'
        run(['rustup', 'toolchain', 'install', toolchain, '--profile', 'minimal', '--no-self-update'])
        env['RUSTUP_TOOLCHAIN'] = toolchain
        env['CARGO_BUILD_TARGET'] = 'aarch64-pc-windows-msvc'
        env['PYO3_PYTHON'] = python
    if cfg['kind'] == 'arrow':
        prefix, build_dir = source.parent / 'arrow-install', source.parent / 'arrow-build'
        run(['cmake', '-S', source / 'cpp', '-B', build_dir, '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={prefix}',
             '-DARROW_DEPENDENCY_SOURCE=BUNDLED', '-DARROW_SIMD_LEVEL=NONE',
             '-DARROW_BUILD_SHARED=ON', '-DARROW_BUILD_STATIC=OFF', '-DARROW_PYTHON=ON',
             '-DARROW_PARQUET=ON', '-DARROW_DATASET=ON', '-DARROW_COMPUTE=ON',
             '-DARROW_CSV=ON', '-DARROW_JSON=ON', '-DARROW_S3=OFF', '-DARROW_GCS=OFF',
             '-DARROW_FLIGHT=OFF', '-DARROW_BUILD_TESTS=OFF'], env=env)
        run(['cmake', '--build', build_dir, '--parallel', '4'], env=env)
        run(['cmake', '--install', build_dir], env=env)
        env['ARROW_HOME'] = str(prefix)
        env['CMAKE_PREFIX_PATH'] = str(prefix)
        env['PATH'] = str(prefix / 'bin') + os.pathsep + env['PATH']
        env['PYARROW_BUNDLE_ARROW_CPP'] = '1'
        env['PYARROW_WITH_PARQUET'] = env['PYARROW_WITH_DATASET'] = '1'
        source = source / 'python'
    elif cfg['kind'] == 'vtk':
        build_dir = source.parent / 'vtk-build'
        env['PYTHON_PREFIX'] = ctx['venv']
        env['CMAKE_CONFIGURATION'] = 'windows312_arm64'
        run(['cmake', '-S', source, '-B', build_dir, '-G', 'Ninja',
             '-C', source / '.gitlab/ci/configure_wheel.cmake', '-DCMAKE_BUILD_TYPE=Release',
             '-DVTK_WRAP_PYTHON=ON', '-DVTK_WHEEL_BUILD=ON', '-DVTK_BUILD_TESTING=OFF',
             '-DVTK_VERSION_SUFFIX=', f'-DPython3_EXECUTABLE={python}'], env=env)
        run(['cmake', '--build', build_dir, '--parallel', '4'], env=env)
        run([python, 'setup.py', 'bdist_wheel', '--dist-dir', ctx['raw']], cwd=build_dir, env=env)
        return
    run([python, '-m', 'pip', 'wheel', source, '--no-deps', '--no-build-isolation', '--wheel-dir', ctx['raw']], env=env)


def smoke(package_dir):
    ctx = context()
    cfg = json.loads((Path(package_dir) / 'build.json').read_text())
    # Use the installed wheel, never a source-tree import.
    run([ctx['python'], '-c', cfg['smoke']], cwd=Path(ctx['source']).parent, env=build_env(ctx))
