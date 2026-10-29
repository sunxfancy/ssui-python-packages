from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
source = Path(ctx['source'])
env = build_env(ctx)
env['DISTUTILS_USE_SDK'] = env['MSSdk'] = '1'
env['GPU_ARCHS'] = env['PYTORCH_ROCM_ARCH'] = ctx['target']['gpu_arch']
env['FORCE_CUDA'] = '1'
compiler = Path(next(v for k, v in env.items() if k.upper() == 'VCTOOLSINSTALLDIR')) / 'bin/Hostx64/x64'
if not (compiler / 'link.exe').is_file():
    raise RuntimeError('MSVC linker not found: ' + str(compiler))
env['PATH'] = str(compiler) + os.pathsep + env['PATH']
sources = [source / "csrc/natten.cpp"]
for pattern in ("csrc/src/*.cpp", "csrc/src/pytorch/*.cpp", "csrc/src/pytorch/cpu/*.cpp",
                "csrc/src/pytorch/cuda/*.cu", "csrc/autogen/src/cpu/naive/*.cpp",
                "csrc/autogen/src/cuda/naive/*.cu"):
    sources.extend(sorted(source.glob(pattern)))
converted = []
for path in sources:
    if path.suffix == ".cpp":
        target = path.with_name(path.stem + "_win.cu")
        target.write_text(path.read_text())
        path = target
    converted.append(path.relative_to(source).as_posix())
(source / "setup.py").write_text('''import os
from setuptools import setup, find_packages
from torch.utils.cpp_extension import BuildExtension, CUDAExtension
setup(
    name="natten", version="0.17.4+ssui.rocm72",
    packages=find_packages("src"), package_dir={"": "src"},
    ext_modules=[CUDAExtension(
        "natten.libnatten", sources=''' + repr(converted) + ''',
        include_dirs=[os.path.abspath("csrc/include"), os.path.abspath("csrc/autogen/include"),
                      os.environ["ROCM_DEVEL_INCLUDE"]],
        extra_compile_args={"nvcc": ["-O2", "-std=c++17", "-DSSUI_HIP_BUILD=1",
            "-DNATTEN_WITH_CUDA", "-DWITH_CUDA", "--offload-arch=gfx1201",
            "--rocm-device-lib-path=" + os.path.join(os.environ["ROCM_PATH"], "lib/llvm/amdgcn/bitcode")]},
    )], cmdclass={"build_ext": BuildExtension},
)
''')
run([ctx['python'], '-m', 'pip', 'wheel', source, '--wheel-dir', ctx['raw'], '--no-build-isolation', '--no-deps', '--no-cache-dir'], cwd=source, env=env)
