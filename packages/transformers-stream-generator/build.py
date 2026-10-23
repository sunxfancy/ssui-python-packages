from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import shutil
from runtime import build_env, context, run

ctx = context()
source = Path(ctx['source'])
shutil.copy2(Path(__file__).with_name('modern_main.py'), source / 'transformers_stream_generator/main.py')
run([ctx['python'], '-m', 'pip', 'wheel', source, '--no-deps', '--no-build-isolation',
     '--wheel-dir', ctx['raw']], env=build_env(ctx))
