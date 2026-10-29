from setuptools import setup, find_packages
from torch.utils.cpp_extension import BuildExtension, CppExtension

setup(name='ssui-trellis-mps', version='0.1.0',
      packages=find_packages('src'), package_dir={'': 'src'},
      python_requires='>=3.12,<3.13', install_requires=['torch==2.4.1'],
      license='MIT', license_files=['LICENSE'],
      ext_modules=[CppExtension('ssui_trellis_mps._C', ['src/ssui_trellis_mps/neighbors.mm'],
          extra_compile_args=['-O2', '-std=c++17', '-Wno-invalid-specialization'],
          extra_link_args=['-framework', 'Foundation', '-framework', 'Metal',
                           '-framework', 'MetalPerformanceShaders',
                           '-Wl,-rpath,@loader_path/../torch/lib'])],
      cmdclass={'build_ext': BuildExtension})
