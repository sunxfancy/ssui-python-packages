from pathlib import Path
import os
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source, python = Path(ctx['source']), ctx['python']
env = build_env(ctx)
compiler = shutil.which('cl.exe', path=env['PATH'])
if not compiler:
    raise RuntimeError('ARM64 MSVC developer environment is not active')
env['PATH'] = str(Path(compiler).parent) + os.pathsep + env['PATH']
# DIY's bundled fmt predates removal of checked_array_iterator in MSVC 19.50+.
# Its existing portable pointer fallback is also the upstream fmt solution.
fmt_header = source / 'ThirdParty/diy2/vtkdiy2/include/vtkdiy2/fmt/format.h'
fmt_text = fmt_header.read_text()
guard = '#ifdef _SECURE_SCL'
if fmt_text.count(guard) != 1:
    raise RuntimeError('Unexpected VTK DIY/fmt checked iterator guard')
fmt_header.write_text(fmt_text.replace(guard, '#if defined(_SECURE_SCL) && defined(_MSC_VER) && _MSC_VER < 1950'), newline='\n')
# Catch this STL/compiler compatibility issue before the full VTK build.
probe = source.parent / 'vtk-fmt-probe.cxx'
probe.write_text(f'#include "{fmt_header.as_posix()}"\nint main() {{ return 0; }}\n', newline='\n')
run([compiler, '/nologo', '/EHsc', '/std:c++14', '/c', probe,
     '/Fo' + str(source.parent / 'vtk-fmt-probe.obj')], env=env)
env['PYTHON_PREFIX'] = ctx['venv']
env['CMAKE_CONFIGURATION'] = 'windows312_arm64'
build_dir = source.parent / 'vtk-build'
run(['cmake', '-S', source, '-B', build_dir, '-G', 'Ninja',
     '-C', source / '.gitlab/ci/configure_wheel.cmake', '-DCMAKE_BUILD_TYPE=Release',
     '-DVTK_WRAP_PYTHON=ON', '-DVTK_WHEEL_BUILD=ON', '-DVTK_BUILD_TESTING=OFF',
     '-DVTK_BUILD_EXAMPLES=OFF', '-DVTK_VERSION_SUFFIX=', f'-DPython3_EXECUTABLE={python}',
     '-DVTK_MODULE_ENABLE_VTK_GUISupportMFC=NO',
     # The upstream CI preset assumes Kitware's sccache installation.
     '-DCMAKE_C_COMPILER_LAUNCHER=', '-DCMAKE_CXX_COMPILER_LAUNCHER=',
     '-DCMAKE_CUDA_COMPILER_LAUNCHER='], env=env)
workers = str(min(8, os.cpu_count() or 4))
print('VTK native build workers:', workers, flush=True)
run(['cmake', '--build', build_dir, '--parallel', workers], env=env)
run([python, 'setup.py', 'bdist_wheel', '--dist-dir', ctx['raw']], cwd=build_dir, env=env)
# Match upstream's Windows wheel job: setup.py does not bundle bin/*.dll.
# Keep VTK DLL names stable for its runtime lookups, but let delvewheel handle
# other redistributable dependencies and install the DLL search-path bootstrap.
fixed = source.parent / 'fixed-wheels'
fixed.mkdir()
wheel = next(Path(ctx['raw']).glob('*.whl'))
no_mangle = ';'.join(sorted(path.name for path in (build_dir / 'bin').glob('*.dll')))
# Pinned delvewheel handles api-* contracts but misses ext-ms-win-* contracts.
# Both are Windows loader API sets, not DLLs to copy out of the operating system:
# https://learn.microsoft.com/windows/win32/apiindex/windows-apisets
repair = ('import re; from delvewheel import _dll_list; '
          '_dll_list.ignore_regexes.add(re.compile(r"ext-ms-win-.*\\.dll")); '
          'from delvewheel.__main__ import main; main()')
run([python, '-c', repair, 'repair', '--add-path', build_dir / 'bin',
     '--no-mangle', no_mangle, '-w', fixed, wheel], env=env)
wheel.unlink()
for result in fixed.glob('*.whl'):
    result.replace(Path(ctx['raw']) / result.name)
