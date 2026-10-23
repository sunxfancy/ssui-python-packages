from pathlib import Path
import sys
import os
import shutil
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
header = Path(ctx['source']) / 'cpp/src/arrow/vendored/pcg/pcg_uint128.hpp'
text = header.read_text()
anchor = '#ifndef PCG_LITTLE_ENDIAN'
if text.count(anchor) != 1:
    raise RuntimeError('Unexpected Arrow PCG endianness detection')
# Windows ARM64 is little-endian. PCG's MSVC 128-bit multiply specialization
# uses the x64-only _umul128 intrinsic, so retain its portable arithmetic here.
defines = '#if defined(_MSC_VER) && defined(_M_ARM64)\n#define PCG_LITTLE_ENDIAN 1\n#define PCG_64BIT_SPECIALIZATIONS 0\n#endif\n\n'
header.write_text(text.replace(anchor, defines + anchor), newline='\n')

source, python = Path(ctx['source']), ctx['python']
env = build_env(ctx)
compiler = shutil.which('cl.exe', path=env['PATH'])
if not compiler:
    raise RuntimeError('ARM64 MSVC developer environment is not active')
env['PATH'] = str(Path(compiler).parent) + os.pathsep + env['PATH']
env['DISTUTILS_USE_SDK'] = env['MSSdk'] = '1'
env['CMAKE_BUILD_PARALLEL_LEVEL'] = '4'
prefix, build_dir = source.parent / 'arrow-install', source.parent / 'arrow-build'
run(['cmake', '-S', source / 'cpp', '-B', build_dir, '-G', 'Ninja',
     '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={prefix}',
     '-DARROW_DEPENDENCY_SOURCE=BUNDLED', '-DARROW_SIMD_LEVEL=NONE',
     '-DARROW_BUILD_SHARED=ON', '-DARROW_BUILD_STATIC=OFF', '-DARROW_PYTHON=ON',
     '-DARROW_PARQUET=ON', '-DARROW_DATASET=ON', '-DARROW_COMPUTE=ON',
     '-DARROW_CSV=ON', '-DARROW_JSON=ON', '-DARROW_WITH_SNAPPY=ON',
     '-DARROW_S3=OFF', '-DARROW_GCS=OFF', '-DARROW_FLIGHT=OFF', '-DARROW_BUILD_TESTS=OFF'], env=env)
run(['cmake', '--build', build_dir, '--parallel', '4'], env=env)
run(['cmake', '--install', build_dir], env=env)
env['ARROW_HOME'] = env['CMAKE_PREFIX_PATH'] = str(prefix)
env['PATH'] = str(prefix / 'bin') + os.pathsep + env['PATH']
# setup.py has its own legacy VS2017 default and ignores CMAKE_GENERATOR.
env['PYARROW_CMAKE_GENERATOR'] = 'Ninja'
env['PYARROW_BUNDLE_ARROW_CPP'] = '1'
env['PYARROW_WITH_PARQUET'] = env['PYARROW_WITH_DATASET'] = '1'
run([python, '-m', 'pip', 'wheel', source / 'python', '--no-deps', '--no-build-isolation', '--wheel-dir', ctx['raw']], env=env)
