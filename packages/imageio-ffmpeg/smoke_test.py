from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
run([ctx['python'], Path(__file__).with_name('check_runtime.py')],
    cwd=Path(ctx['source']).parent, env=build_env(ctx))
