# Windows ARM64 CPU supplement

The target is native Windows ARM64, CPython 3.12, CPU. Architecture and compute
backend remain independent configuration fields. Builds use `windows-11-arm`,
ARM64 MSVC, and a separate pinned build-tool lock. Native PE headers must report
ARM64 (`0xAA64`) before a wheel can be published; renaming an x64 wheel is rejected.

This is the missing-wheel inventory from SSUI's 2026-10-23 dependency audit.
Recipe presence is not proof of a successful port: only independently verified
releases appear in the [live catalog](https://sunxfancy.github.io/ssui-python-packages/catalog.json).
The [five-package build follow-up](arm64-build-results-2026-10-23.md) records
published versions, native build fixes and independent runtime checks.

| Package | Version | Validation / limitation |
| --- | --- | --- |
| Pynini | 2.1.6.post1 | FST operation and upstream `pynini_test.py` suite (146 tests); builds OpenFST for ARM64 |
| torchaudio | 2.9.1 | Native import and CPU resampling; matches official ARM64 torch 2.9.1+cpu; no FFmpeg/SoX/CUDA/ROCm |
| opencv-python-headless | 4.11.0.86 | Native import, image conversion and ONNX CPU DNN execution; NEON FP32 baseline, no optional FP16 CPU dispatch, Media Foundation or bundled FFmpeg |
| opencv-contrib-python | 4.11.0.86 | Same conversion/DNN checks plus contrib/aruco presence; same CPU/media limitations |
| glcontext | 3.0.0 | Native backend loading; actual OpenGL rendering requires a suitable driver |
| moderngl | 5.12.0 | Native module loading; actual OpenGL rendering requires a suitable driver |
| pyworld | 0.3.4 | WORLD CPU pitch extraction |
| soxr | 0.5.0.post1 | CPU audio resampling |
| tiktoken | 0.9.0 | Offline BPE encode/decode round trip; pinned native ARM64 Rust toolchain |
| hf-transfer | 0.1.9 | Native import; pinned native ARM64 Rust toolchain |
| pymeshfix | 0.17.1 | Native extension loading and mesh repair with the published VTK wheel and pyvista |
| pyarrow | 20.0.0 | Builds bundled Arrow C++; Snappy Parquet round trip and seeded random compute kernel; S3/GCS/Flight disabled |
| vtk | 9.4.2 | Native vtkPoints, PyVista geometry generation and PyMeshFix repair; no Qt, MFC or external optional modules |
| antlr4-python3-runtime | 4.9.3 | Pure Python wheel and InputStream operation; supplies hydra-core's source-only dependency |
| openai-whisper | 20240930 | Pure Python wheel and bytecode validation only; runtime still needs ARM64 numba/llvmlite |
| transformers-stream-generator | 0.0.4 | Pure Python wheel and bytecode validation only; Transformers integration still needs testing |
| imageio-ffmpeg | 0.6.0 | **Blocked/disabled**: native ARM64 FFmpeg executable/build pipeline missing; publishing the pure wrapper would not resolve this |
| numba | 0.62.1 | **Blocked/disabled**: requires a validated Windows ARM64 llvmlite/LLVM JIT port |
| llvmlite | 0.45.1 | **Blocked/disabled**: native LLVM JIT build and execution tests are not configured for this target |

OpenCV flavors both install `cv2`; select one flavor in an environment. Keeping
separate recipes preserves the dependency names required by different consumers;
it does not make simultaneous installation safe.

Already available official ARM64 wheels (torch, torchvision, upgraded tokenizers
and sentencepiece, etc.) continue to come from their official sources. Pure
consumer packages such as librosa, WeTextProcessing, hydra-core, pyvista, rembg,
controlnet-aux and mediapipe do not need redundant rebuilds merely because a
native dependency is missing. Their complete workflows still need integration
tests once those dependencies are available.

Numba/llvmlite are additional runtime blockers for both Whisper and librosa;
this migration does not claim to port the LLVM JIT to Windows ARM64. FFmpeg remains
an explicit blocked target; `--force` does not turn a blocked recipe into a valid
build. Source archives are official PyPI sdists pinned by SHA256; Git sources stay
pinned by full commit. Native extension and bytecode-only checks are distinguished
in `release.json`, including package-specific limitations.

```powershell
yarn plan --target windows-arm64-cp312-cpu --repo sunxfancy/ssui-python-packages
yarn plan --package pyworld --offline
yarn lock:toolchains --arm64
```

Successful releases are indexed at `simple/windows/arm64/cpu/`; torchaudio's torch
ABI-specific channel is `simple/windows/arm64/cpu/2.9.1/`. SSUI should consume exact
published versions and hashes when updating its lock. This repository does not
automatically re-enable previously excluded SSUI workflows based on build success.
