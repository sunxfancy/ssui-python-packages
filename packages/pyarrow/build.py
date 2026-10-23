from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from arm_build import build
from runtime import context

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
build(Path(__file__).parent)
