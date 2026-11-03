from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
if ctx['target']['backend'] == 'cuda':
    code = ('import importlib.metadata, pathlib, struct, sys; '
            'assert importlib.metadata.version("bitsandbytes") == ' + repr(ctx['version']) + '; '
            'root=pathlib.Path(sys.prefix)/"Lib/site-packages/bitsandbytes"; '
            'dlls=list(root.glob("libbitsandbytes_cuda134.dll")); assert len(dlls)==1; '
            'p=dlls[0].read_bytes(); o=struct.unpack_from("<I",p,60)[0]; '
            'assert p[o:o+4]==b"PE\\0\\0" and struct.unpack_from("<H",p,o+4)[0]==0xaa64; '
            'print("ARM64 CUDA DLL verified; GPU runtime tested separately")')
    run([ctx['python'], '-c', code], env=build_env(ctx))
    sys.exit(0)
code = 'import torch, ctypes, pathlib, importlib.metadata, sys; assert torch.version.hip; assert importlib.metadata.version("bitsandbytes") == ' + repr(ctx['version']) + '; dlls=list((pathlib.Path(sys.prefix)/"Lib/site-packages/bitsandbytes").glob("libbitsandbytes_rocm*.dll")); assert dlls; ctypes.WinDLL(str(dlls[0])); print("ROCm DLL load passed; GPU runtime not tested")'
run([ctx['python'], '-c', code], env=build_env(ctx))
