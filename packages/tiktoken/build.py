from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from arm_build import build
from runtime import build_env, context, run
from core import sha256
import shutil

ctx = context()
lock_name = 'Cargo.lock' if ctx['recipe']['version'] == '0.9.0' else 'Cargo-0.14.lock'
lock = Path(__file__).with_name(lock_name)
destination = Path(ctx['source']) / 'Cargo.lock'
shutil.copyfile(lock, destination)
before = sha256(destination)
if ctx['recipe']['version'] == '0.14.0':
    toolchain = '1.99.1-aarch64-pc-windows-msvc'
    run(['rustup', 'toolchain', 'install', toolchain, '--profile', 'minimal', '--no-self-update'])
    env = build_env(ctx)
    env['RUSTUP_TOOLCHAIN'] = toolchain
    env['CARGO_BUILD_TARGET'] = 'aarch64-pc-windows-msvc'
    env['PYO3_PYTHON'] = ctx['python']
    run([ctx['python'], '-m', 'pip', 'wheel', ctx['source'], '--no-deps', '--no-build-isolation',
         '--wheel-dir', ctx['raw']], env=env)
else:
    build(Path(__file__).parent)
if sha256(destination) != before:
    raise RuntimeError('Cargo changed the pinned tiktoken dependency lock')
