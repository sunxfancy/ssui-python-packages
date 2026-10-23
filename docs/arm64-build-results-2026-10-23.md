# Windows ARM64 build follow-up (2026-10-23)

Scope: the five remaining native Windows ARM64 / CPython 3.12 / CPU packages.
Published wheels retain their package names and use independent immutable release
tags. Their `release.json` assets contain source pins, build fingerprints, wheel
hashes and validation results.

| Package | Published version | Evidence |
| --- | --- | --- |
| Pynini | `2.1.6.post1+ssui.cpu.r1.b9c91f73d4a44` | [Release](https://github.com/sunxfancy/ssui-python-packages/releases/tag/pynini-2.1.6.post1-r1--windows-arm64-cp312-cpu--9c91f73d4a4468941b61) |
| opencv-python-headless | `4.11.0.86+ssui.cpu.r1.b05e8c6d74ea4` | [Release](https://github.com/sunxfancy/ssui-python-packages/releases/tag/opencv-python-headless-4.11.0.86-r1--windows-arm64-cp312-cpu--05e8c6d74ea4ab03ac7d) |
| opencv-contrib-python | `4.11.0.86+ssui.cpu.r1.bb0121761458f` | [Release](https://github.com/sunxfancy/ssui-python-packages/releases/tag/opencv-contrib-python-4.11.0.86-r1--windows-arm64-cp312-cpu--b0121761458f9f28e2e8) |
| pyarrow | `20.0.0+ssui.cpu.r1.b9bfc03949403` | [Release](https://github.com/sunxfancy/ssui-python-packages/releases/tag/pyarrow-20.0.0-r1--windows-arm64-cp312-cpu--9bfc03949403fb3d7e1e) |
| VTK | `9.4.2+ssui.cpu.r1.b62943278488d` | [Release](https://github.com/sunxfancy/ssui-python-packages/releases/tag/vtk-9.4.2-r1--windows-arm64-cp312-cpu--62943278488d9773e9dc) |

## Verified fixes

- OpenCV: use native ARM64 MSVC with Ninja despite the older scikit-build Visual
  Studio generator detection. Build the NEON FP32 baseline without optional FP16
  CPU dispatch. Remove upstream's unconditional FFmpeg DLL packaging requirement
  when FFmpeg is disabled. Keep both package flavors separately selectable.
- Arrow: select Ninja for both Arrow C++ and the PyArrow setup invocation. Adapt
  vendored PCG to ARM64's portable multiplication path and little-endian layout;
  enable bundled Snappy for the default Parquet codec.
- VTK: clear Kitware CI's assumed sccache launchers, use the existing portable
  pointer fallback in vendored DIY/fmt with MSVC 19.50+, and disable optional MFC
  integration. A small compile probe checks the fmt header before the full build.
  Apply upstream's Windows `delvewheel repair` step after `setup.py`, preserving
  VTK DLL names while bundling runtime libraries and adding the loader bootstrap.
  Pinned delvewheel's API-set handling is extended to `ext-ms-win-*` contracts;
  these are resolved by the [Windows loader](https://learn.microsoft.com/windows/win32/apiindex/windows-apisets)
  and must not be copied from the operating system into the wheel.

## Independent runtime checks

The published wheels were installed in separate native ARM64 CPython 3.12.15
environments and tested outside their build trees. NumPy-dependent checks used
NumPy 2.3.3.

- Pynini: all 146 tests in pinned upstream `pynini_test.py` passed.
- Each OpenCV flavor: native import, image conversion, and ONNX CPU DNN forward
  execution passed; the contrib flavor also exposes `aruco`.
- Arrow: Snappy Parquet round trip and seeded random compute execution passed.
- VTK: native `vtkPoints`, PyVista 0.46.3 sphere generation and PyMeshFix 0.17.1
  mesh repair passed. The final native build used ARM64 MSVC 14.51.36231 on a
  local Windows ARM64 host. Its release records that provenance and includes a
  sanitized compressed build log plus `runtime-checks.json`.

The orchestration/publication test suite passes all 43 tests; `yarn validate`
accepts recipes, immutable pins and target/toolchain bindings.

## Remaining limits

OpenCV excludes Media Foundation, bundled FFmpeg and optional FP16 CPU dispatch.
The two OpenCV flavors share `cv2` and must be installed in separate environments.
Arrow excludes S3, GCS and Flight. These CPU checks do not validate GPU execution,
OpenGL rendering or every downstream SSUI workflow. Existing explicit blockers
for numba, llvmlite and imageio-ffmpeg are outside these five packages and remain
disabled; see [the ARM64 inventory](windows-arm64.md).
