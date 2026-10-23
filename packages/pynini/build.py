from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source, python = Path(ctx['source']), ctx['python']
build = source / 'third_party/build'
prefix = source / 'third_party/openfst_install'
env = build_env(ctx)
if ctx['target']['os'] == 'macos':
    env['ARCHFLAGS'] = '-arch arm64'
    env['_PYTHON_HOST_PLATFORM'] = 'macosx-11.0-arm64'
args = ['cmake', '-S', source / 'third_party/openfst-1.8.3', '-B', build, f'-DCMAKE_INSTALL_PREFIX={prefix}']
args += ['-A', 'x64'] if ctx['target']['os'] == 'windows' else ['-G', 'Ninja']
if ctx['target']['os'] == 'macos':
    args += ['-DCMAKE_OSX_ARCHITECTURES=arm64']
run(args, env=env)
run(['cmake', '--build', build, '--config', 'Release', '--parallel', '4'], env=env)
run(['cmake', '--install', build, '--config', 'Release'], env=env)
run([python, '-m', 'build', '--wheel', '--no-isolation', '--outdir', ctx['raw']], cwd=source, env=env)
if ctx['target']['os'] == 'macos':
    fixed = Path(ctx['raw']).parent / 'fixed-wheels'
    fixed.mkdir()
    wheel = next(Path(ctx['raw']).glob('*.whl'))
    run([Path(ctx['venv']) / 'bin/delocate-wheel', '--require-archs', 'arm64', '-w', fixed, '-v', wheel], env=env)
    wheel.unlink()
    for result in fixed.glob('*.whl'):
        result.replace(Path(ctx['raw']) / result.name)
else:
    fixed = Path(ctx['raw']).parent / 'fixed-wheels'
    fixed.mkdir()
    wheel = next(Path(ctx['raw']).glob('*.whl'))
    run([python, '-m', 'delvewheel', 'repair', '--add-path', str(prefix / 'bin') + ';' + str(prefix / 'lib'), '-w', fixed, wheel], env=env)
    wheel.unlink()
    for result in fixed.glob('*.whl'):
        result.replace(Path(ctx['raw']) / result.name)
