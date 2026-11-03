from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
toolchain = '1.99.1-aarch64-pc-windows-msvc'
run(['rustup', 'toolchain', 'install', toolchain, '--profile', 'minimal', '--no-self-update'])
env = build_env(ctx)
env['RUSTUP_TOOLCHAIN'] = toolchain
env['PYO3_PYTHON'] = ctx['python']
vc_tools = env.get('VCToolsInstallDir')
if vc_tools:
    linkers = [Path(vc_tools) / 'bin' / host / 'arm64' / 'link.exe'
               for host in ('Hostarm64', 'Hostx64')]
    linker = next((path for path in linkers if path.is_file()), None)
    if linker is None:
        raise RuntimeError('ARM64 MSVC link.exe not found under VCToolsInstallDir')
    env['PATH'] = str(linker.parent) + os.pathsep + env['PATH']
    env['CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER'] = str(linker)
    env['CARGO_ENCODED_RUSTFLAGS'] = '-Clinker=' + str(linker)
run([ctx['python'], '-m', 'pip', 'wheel', ctx['source'], '--no-deps', '--no-build-isolation',
     '--wheel-dir', ctx['raw']], env=env)
