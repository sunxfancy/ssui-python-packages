from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
package = Path(__file__).parent
env = build_env(ctx)
run([ctx['python'], '-m', 'pip', 'install', '--only-binary=:all:', '-r', package / 'runtime-check.lock'], env=env)
run([ctx['python'], package / 'check_runtime.py'], cwd=Path(ctx['source']).parent, env=env)
