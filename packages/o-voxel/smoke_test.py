from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
# The full package imports FlexGEMM, nvdiffrast and CuMesh; test its own binary
# independently without installing sibling wheels from floating indexes.
code = 'import torch, sys, pathlib, importlib.util; assert torch.version.hip; root=pathlib.Path(sys.prefix)/"Lib/site-packages/o_voxel"; native=next(root.glob("_C*.pyd")); spec=importlib.util.spec_from_file_location("_C", native); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); print("Native extension loaded; Python pipeline and GPU runtime NOT tested")'
run([ctx['python'], '-c', code], env=build_env(ctx))
