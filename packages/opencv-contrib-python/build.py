from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source = Path(ctx['source'])
env = build_env(ctx)
env.update(json.loads(Path(__file__).with_name('build.json').read_text())['env'])
env['CMAKE_GENERATOR'] = 'Ninja'
env['CMAKE_BUILD_PARALLEL_LEVEL'] = '4'
compiler = shutil.which('cl.exe', path=env['PATH'])
if not compiler:
    raise RuntimeError('ARM64 MSVC developer environment is not active')
env['PATH'] = str(Path(compiler).parent) + ';' + env['PATH']
# OpenCV and scikit-build 0.18 assume VS2022. Use the already activated native
# compiler with Ninja, removing the VS-only platform flag from pinned setup.py.
setup = source / 'setup.py'
text = setup.read_text()
flag = '"-DCMAKE_GENERATOR_PLATFORM=ARM64",'
if text.count(flag) != 1:
    raise RuntimeError('Unexpected OpenCV ARM64 generator configuration')
setup.write_text(text.replace(flag, '"-DCMAKE_SYSTEM_PROCESSOR=ARM64",'), newline='\n')
bootstrap = """
import os, runpy, sys
from skbuild import platform_specifics
from skbuild.platform_specifics.abstract import CMakePlatform, CMakeGenerator
class ActivatedPlatform(CMakePlatform):
    def __init__(self):
        super().__init__()
        self.default_generators = [CMakeGenerator('Ninja', env=dict(os.environ))]
    @property
    def generator_installation_help(self):
        return 'The pre-activated ARM64 MSVC compiler and Ninja are required.'
platform_specifics.get_platform = ActivatedPlatform
sys.argv = ['setup.py', 'bdist_wheel', '--dist-dir', sys.argv[1]]
runpy.run_path('setup.py', run_name='__main__')
"""
run([ctx['python'], '-c', bootstrap, ctx['raw']], cwd=source, env=env)
