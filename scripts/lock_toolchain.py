import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([os.environ.get('SSUI_UV_PATH', 'uv'), 'pip', 'compile',
                'toolchains/common.in', '--python-version', '3.12', '--universal',
                '-o', 'toolchains/common.lock'], cwd=root, check=True)
