from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from arm_build import build
from runtime import context
from core import sha256
import shutil

ctx = context()
lock = Path(__file__).with_name('Cargo.lock')
destination = Path(ctx['source']) / 'Cargo.lock'
shutil.copyfile(lock, destination)
build(Path(__file__).parent)
if sha256(destination) != sha256(lock):
    raise RuntimeError('Cargo changed the pinned tiktoken dependency lock')
