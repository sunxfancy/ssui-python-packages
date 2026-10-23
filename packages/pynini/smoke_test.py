from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
run([ctx['python'], '-c', 'import pynini; assert (pynini.accep("SSUI") @ pynini.cross("SSUI", "ok")).string() == "ok"'], env=build_env(ctx))
run([ctx['python'], str(Path(ctx['source']) / 'tests/pynini_test.py')], env=build_env(ctx))
