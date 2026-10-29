import runpy
import sys
from torch.utils import cpp_extension

# Detached Windows hosts may report OEM code page 1; compiler output is diagnostic.
cpp_extension.SUBPROCESS_DECODE_ARGS = ("utf-8", "replace")
original_cuda_extension = cpp_extension.CUDAExtension
def cuda_extension(*args, **kwargs):
    for kind, flags in kwargs.get("extra_compile_args", {}).items():
        flags[:] = [flag.replace("c++17", "c++20") for flag in flags]
        if kind == "cxx":
            flags[:] = [{"-O3": "/O2", "-std=c++20": "/std:c++20"}.get(flag, flag) for flag in flags]
            flags.extend(["/EHsc", "/bigobj", "/Zc:__cplusplus"])
        elif kind == "nvcc":
            flags.extend(["-allow-unsupported-compiler", "-Xcompiler=/std:c++20", "-Xcompiler=/EHsc"])
    return original_cuda_extension(*args, **kwargs)
cpp_extension.CUDAExtension = cuda_extension
sys.argv = ["setup.py", "bdist_wheel", "--dist-dir", "../wheels"]
runpy.run_path("setup.py", run_name="__main__")
