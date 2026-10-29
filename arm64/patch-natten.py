from pathlib import Path
root = Path(__file__).parent / "NATTEN"
setup = root / "setup.py"
text = setup.read_text()
text = text.replace('cmake_args.append("-G Ninja")', 'cmake_args.extend(["-G", "Ninja"])')
text = text.replace('python_path.replace("python.exe", "libs").strip()', 'str(Path(sys.base_prefix) / "libs")')
setup.write_text(text)
cmake = root / "csrc/CMakeLists.txt"
text = cmake.read_text().replace('set(CXX_STD "17"', 'set(CXX_STD "20"')
text = text.replace('-std=c++17', '/std:c++20')
text = text.replace('-Xcompiler -Wall -ldl', '-allow-unsupported-compiler')
text = text.replace('-Xcompiler=-Wconversion', '').replace('-Xcompiler=-fno-strict-aliasing', '')
text = text.replace('-ftemplate-backtrace-limit=0', '')
text = text.replace('CMAKE_CXX_FLAGS_RELEASE} -O3', 'CMAKE_CXX_FLAGS_RELEASE} /O2')
text = text.replace('-Xcompiler -O3', '-Xcompiler /O2')
cmake.write_text(text)
header = root / "third_party/cutlass/include/cutlass/exmy_base.h"
text = header.read_text().replace("cutlass::platform::is_unsigned_v<Storage>", "std::is_unsigned<Storage>::value")
text = text.replace("cutlass::platform::is_unsigned<Storage>::value", "std::is_unsigned<Storage>::value")
if "#include <type_traits>" not in text:
    text = "#include <type_traits>\n" + text
header.write_text(text)
