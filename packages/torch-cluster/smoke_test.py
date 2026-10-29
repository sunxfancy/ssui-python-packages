from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
run([ctx['python'], '-m', 'pip', 'install', '--no-deps', '--only-binary=:all:',
     '-r', Path(__file__).with_name('smoke.lock')], env=build_env(ctx))
run([ctx['python'], '-c', 'import torch; assert torch.version.hip; import torch_cluster; print("Native import passed; GPU runtime NOT tested")'], env=build_env(ctx))
