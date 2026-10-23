from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
# GitHub-hosted Windows has no AMD GPU. Import every native module; do not
# claim that successful import proves GPU kernel execution.
run([ctx['python'], '-c', 'import torch; assert torch.version.hip; import cumesh, cumesh._C, cumesh._cubvh, cumesh._cumesh_xatlas; print("CuMesh native imports passed; GPU runtime not tested")'], env=build_env(ctx))
