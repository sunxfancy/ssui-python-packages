from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
code = 'import torch, ctypes, pathlib, importlib.metadata, sys; assert torch.version.hip; assert importlib.metadata.version("bitsandbytes") == ' + repr(ctx['version']) + '; dlls=list((pathlib.Path(sys.prefix)/"Lib/site-packages/bitsandbytes").glob("libbitsandbytes_rocm*.dll")); assert dlls; ctypes.WinDLL(str(dlls[0])); print("ROCm DLL load passed; GPU runtime not tested")'
run([ctx['python'], '-c', code], env=build_env(ctx))
