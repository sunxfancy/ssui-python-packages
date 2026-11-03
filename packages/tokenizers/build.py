from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
toolchain = '1.99.1-aarch64-pc-windows-msvc'
run(['rustup', 'toolchain', 'install', toolchain, '--profile', 'minimal', '--no-self-update'])
env = build_env(ctx)
env['RUSTUP_TOOLCHAIN'] = toolchain
env['CARGO_BUILD_TARGET'] = 'aarch64-pc-windows-msvc'
env['PYO3_PYTHON'] = ctx['python']
run([ctx['python'], '-m', 'pip', 'wheel', ctx['source'], '--no-deps', '--no-build-isolation',
     '--wheel-dir', ctx['raw']], env=env)
