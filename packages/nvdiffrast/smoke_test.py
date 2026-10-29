from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
run([ctx['python'], '-c', 'import torch; assert torch.version.hip; import nvdiffrast.torch, _nvdiffrast_c; print("Native import passed; GPU runtime NOT tested")'], env=build_env(ctx))
