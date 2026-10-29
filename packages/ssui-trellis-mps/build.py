from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
package = Path(__file__).parent
stage = Path(ctx['source']) / 'ssui-mps-wheel'
stage.mkdir()
for name in ('src', 'setup.py', 'LICENSE'):
    source = package / name
    shutil.copytree(source, stage / name) if source.is_dir() else shutil.copy2(source, stage / name)
env = build_env(ctx)
env['ARCHFLAGS'] = '-arch arm64'
env['MACOSX_DEPLOYMENT_TARGET'] = '12.3'
env['_PYTHON_HOST_PLATFORM'] = 'macosx-12.0-arm64'
run([ctx['python'], '-m', 'build', '--wheel', '--no-isolation', '--outdir', ctx['raw']], cwd=stage, env=env)
