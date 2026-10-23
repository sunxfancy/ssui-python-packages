from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run
ctx = context()
source = Path(ctx['source'])
matches = list(source.rglob('mediapipe_face_common.py'))
if len(matches) != 1:
    raise ValueError('Unexpected upstream MediaPipe adapter layout')
original = matches[0]
shutil.copy2(original, original.with_name('legacy.py'))
shutil.copy2(Path(__file__).with_name('tasks.py'), original.with_name('modern_tasks.py'))
original.write_text('''try:
    import mediapipe as mp
except ImportError:
    from .legacy import generate_annotation
else:
    if hasattr(mp, 'solutions'):
        from .legacy import generate_annotation
    else:
        from .modern_tasks import generate_annotation
''', encoding='utf-8', newline='\n')
run([ctx['python'], '-m', 'pip', 'wheel', source, '--no-deps', '--no-build-isolation',
     '--wheel-dir', ctx['raw']], env=build_env(ctx))
