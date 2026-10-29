"""Load the wheel extension; compilation happens in the package build."""
from functools import lru_cache
import torch

@lru_cache(None)
def extension():
    if torch.__version__.split('+')[0] != '2.4.1':
        raise RuntimeError('ssui-trellis-mps requires PyTorch 2.4.1; install its matching MPS channel')
    from . import _C
    return _C
