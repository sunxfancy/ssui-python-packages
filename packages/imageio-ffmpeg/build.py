"""Build native FFmpeg/x264 and distribute matching sources and licenses."""
import gzip
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from core import sha256
from runtime import build_env, context, run

ctx = context()
package = Path(__file__).parent
pins = json.loads((package / 'native-sources.json').read_text())
source, python = Path(ctx['source']), ctx['python']
work = source.parent
env = build_env(ctx)
tar = Path(os.environ['SystemRoot']) / 'System32/tar.exe'


def download(name):
    pin = pins[name]
    path = work / pin['url'].rsplit('/', 1)[-1]
    cache = os.environ.get('SSUI_NATIVE_DOWNLOAD_CACHE')
    cached = Path(cache) / path.name if cache else None
    if cached and cached.is_file():
        shutil.copyfile(cached, path)
    else:
        urllib.request.urlretrieve(pin['url'], path)
    if sha256(path) != pin['sha256']:
        raise ValueError('Native tool archive hash mismatch: ' + name)
    return path


def checkout(name):
    pin, dest = pins[name], work / name
    run(['git', 'init', dest])
    run(['git', 'config', 'core.autocrlf', 'false'], cwd=dest)
    run(['git', 'remote', 'add', 'origin', pin['url']], cwd=dest)
    run(['git', 'fetch', '--depth=1', 'origin', pin['commit']], cwd=dest)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=dest)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dest, text=True).strip()
    if actual != pin['commit']:
        raise ValueError('Native source pin mismatch: ' + name)
    return dest


tools = work / 'native-tools'
tools.mkdir()
with zipfile.ZipFile(download('llvm')) as archive:
    archive.extractall(tools)
llvm = next(tools.glob('llvm-mingw-*'))
run([tar, '-xf', download('msys'), '-C', tools])
msys = tools / 'msys64'
for name in ('make', 'pkgconf'):
    run([tar, '-xf', download(name), '-C', msys])
ffmpeg, x264 = checkout('ffmpeg'), checkout('x264')
prefix = work / 'native-install'
prefix.mkdir()
env['PATH'] = str(llvm / 'bin') + os.pathsep + str(msys / 'usr/bin') + os.pathsep + env['PATH']
env['MSYSTEM'] = 'MSYS'
env['CHERE_INVOKING'] = '1'
env.pop('MSYS2_ARG_CONV_EXCL', None)
env.pop('CC', None)
env.pop('CXX', None)


def posix(path):
    text = Path(path).resolve().as_posix()
    return '/' + text[0].lower() + text[2:]


def shell(directory, commands):
    script = directory / 'ssui-build.sh'
    script.write_text('set -eu\ncd ' + shlex.quote(posix(directory)) + '\n'
                      + 'export PATH=' + shlex.quote(posix(llvm / 'bin')) + ':/usr/bin:/bin\n'
                      + 'export CC=aarch64-w64-mingw32-clang AR=llvm-ar RANLIB=llvm-ranlib STRIP=llvm-strip\n'
                      + '\n'.join(commands) + '\n', encoding='utf-8', newline='\n')
    run([msys / 'usr/bin/bash.exe', '--noprofile', '--norc', posix(script)], env=env)


jobs = str(min(8, os.cpu_count() or 4))
p = shlex.quote(posix(prefix))
x264_flags = ['--host=aarch64-w64-mingw32', '--enable-static', '--disable-cli',
              '--disable-asm', '--enable-win32thread', '--prefix=' + posix(prefix)]
shell(x264, ['./configure ' + shlex.join(x264_flags), 'make -j' + jobs, 'make install'])
ffmpeg_flags = ['--arch=aarch64', '--target-os=mingw32', '--cc=aarch64-w64-mingw32-clang',
                '--cxx=aarch64-w64-mingw32-clang++', '--ar=llvm-ar', '--ranlib=llvm-ranlib',
                '--nm=llvm-nm', '--strip=llvm-strip', '--pkg-config=pkgconf',
                '--pkg-config-flags=--static', '--prefix=' + posix(prefix),
                '--extra-cflags=-I' + posix(prefix / 'include'),
                '--extra-ldflags=-L' + posix(prefix / 'lib'),
                '--enable-gpl', '--enable-libx264', '--enable-shared', '--disable-static',
                '--disable-autodetect', '--disable-asm', '--disable-debug', '--disable-doc',
                '--disable-ffplay', '--disable-pthreads', '--enable-w32threads']
shell(ffmpeg, ['export PKG_CONFIG_PATH=' + p + '/lib/pkgconfig',
               './configure ' + shlex.join(ffmpeg_flags), 'make -j' + jobs, 'make install'])

binaries = source / 'imageio_ffmpeg/binaries'
for path in (prefix / 'bin').iterdir():
    if path.suffix.lower() in ('.exe', '.dll'):
        shutil.copy2(path, binaries / path.name)
if not (binaries / 'ffmpeg.exe').is_file() or not list(binaries.glob('*.dll')):
    raise RuntimeError('Expected native FFmpeg executable and shared libraries')
definitions = source / 'imageio_ffmpeg/_definitions.py'
text = definitions.read_text().replace('machine = platform.machine()', 'machine = platform.machine().lower()')
text = text.replace('FNAME_PER_PLATFORM = {', 'FNAME_PER_PLATFORM = {\n    "windows-aarch64": "ffmpeg.exe",')
definitions.write_text(text, encoding='utf-8', newline='\n')
setup_file = source / 'setup.py'
setup_file.write_text(setup_file.read_text().replace('license="BSD-2-Clause"',
    'license="BSD-2-Clause AND GPL-2.0-or-later"'), encoding='utf-8', newline='\n')
(binaries / 'SSUI-NOTICE.txt').write_text(
    'imageio-ffmpeg wrapper: BSD-2-Clause.\nFFmpeg with x264: GPL-2.0-or-later.\n'
    'Matching ffmpeg-source.tar.gz and x264-source.tar.gz, source pins and build adapter\n'
    'are assets alongside this wheel in the same ssui-python-packages release.\n'
    'https://github.com/sunxfancy/ssui-python-packages/releases\n', encoding='utf-8')

# Include actual corresponding sources, exact build adapter and source pins.
out = Path(ctx['out'])
out.mkdir()
for name, tree in (('ffmpeg', ffmpeg), ('x264', x264)):
    raw_tar = work / (name + '-source.tar')
    run(['git', 'archive', '--format=tar', '--prefix=' + name + '/', '-o', raw_tar, pins[name]['commit']], cwd=tree)
    with raw_tar.open('rb') as src, gzip.open(out / (name + '-source.tar.gz'), 'wb') as dest:
        shutil.copyfileobj(src, dest)
for origin, name in ((ffmpeg / 'COPYING.GPLv2', 'FFMPEG-COPYING.GPLv2'),
                     (x264 / 'COPYING', 'X264-COPYING'), (package / 'build.py', 'SSUI-build.py'),
                     (package / 'native-sources.json', 'SSUI-native-sources.json')):
    shutil.copy2(origin, out / name)
    shutil.copy2(origin, binaries / name)
config = {'sources': pins, 'x264_configure': x264_flags, 'ffmpeg_configure': ffmpeg_flags,
          'compiler': subprocess.check_output([llvm / 'bin/aarch64-w64-mingw32-clang.exe', '--version'], text=True)}
(out / 'native-build.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
shutil.copy2(out / 'native-build.json', binaries / 'native-build.json')
bootstrap = '''
import runpy, setuptools
from setuptools import Distribution
from wheel.bdist_wheel import bdist_wheel
class NativeTools(Distribution):
    def has_ext_modules(self): return True
class NativeWheel(bdist_wheel):
    def get_tag(self): return ('py3', 'none', 'win_arm64')
setup = setuptools.setup
def native_setup(**kwargs):
    kwargs.update(distclass=NativeTools, cmdclass={'bdist_wheel': NativeWheel})
    setup(**kwargs)
setuptools.setup = native_setup
runpy.run_path('setup.py', run_name='__main__')
'''
run([python, '-c', bootstrap, 'bdist_wheel', '--dist-dir', ctx['raw']], cwd=source, env=env)
