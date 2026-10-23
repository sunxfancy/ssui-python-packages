import os
import subprocess
from pathlib import Path

import argparse

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--arm64', action='store_true')
args = parser.parse_args()
stem = 'windows-arm64-cpu' if args.arm64 else 'common'
subprocess.run([os.environ.get('SSUI_UV_PATH', 'uv'), 'pip', 'compile',
                f'toolchains/{stem}.in', '--python-version', '3.12',
                *(['--python-platform', 'aarch64-pc-windows-msvc'] if args.arm64 else ['--universal']),
                '-o', f'toolchains/{stem}.lock'], cwd=root, check=True)
