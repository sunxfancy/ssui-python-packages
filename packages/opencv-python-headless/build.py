from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import json
from runtime import build_env, context, run

ctx = context()
env = build_env(ctx)
env.update(json.loads(Path(__file__).with_name('build.json').read_text())['env'])
# scikit-build supplies -A ARM64 itself; Ninja cannot accept that platform flag.
env['CMAKE_GENERATOR'] = 'Visual Studio 17 2022'
env['CMAKE_BUILD_PARALLEL_LEVEL'] = '4'
run([ctx['python'], '-m', 'pip', 'wheel', ctx['source'], '--no-deps', '--no-build-isolation', '--wheel-dir', ctx['raw']], env=env)
