from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
# Load the native extension directly: Python convenience imports require Triton.
code = 'import torch, sys, pathlib, importlib.util; assert torch.version.hip; root=pathlib.Path(sys.prefix)/"Lib/site-packages/flex_gemm/kernels"; native=next(root.glob("cuda*.pyd")); spec=importlib.util.spec_from_file_location("cuda", native); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); print("Native extension loaded; Python pipeline and GPU runtime NOT tested")'
run([ctx['python'], '-c', code], env=build_env(ctx))
