# Windows ARM64 compatibility follow-up (2026-10-24)

The FFmpeg, MediaPipe/OpenCV and Transformers streaming blockers are resolved for
SSUI's CPython 3.12 / Windows ARM64 / CPU profile. Four independently published
packages cover the three issues and a transitive ControlNet compatibility issue.

| Package | Published version | Release |
| --- | --- | --- |
| imageio-ffmpeg | `0.6.0+ssui.cpu.r2.b06fa0f77c82a` | [FFmpeg](https://github.com/sunxfancy/ssui-python-packages/releases/tag/imageio-ffmpeg-0.6.0-r2--windows-arm64-cp312-cpu--06fa0f77c82ac1081f40) |
| mediapipe | `1.1.1+ssui.cpu.r1.b45e54946cee2` | [MediaPipe](https://github.com/sunxfancy/ssui-python-packages/releases/tag/mediapipe-1.1.1-r1--windows-arm64-cp312-cpu--45e54946cee2e6d50963) |
| transformers-stream-generator | `0.0.4+ssui.cpu.r2.b410865ecf176` | [Streaming](https://github.com/sunxfancy/ssui-python-packages/releases/tag/transformers-stream-generator-0.0.4-r2--windows-arm64-cp312-cpu--410865ecf176901544d5) |
| controlnet-aux | `0.0.10+ssui.cpu.r1.b7286b30fa4bc` | [ControlNet](https://github.com/sunxfancy/ssui-python-packages/releases/tag/controlnet-aux-0.0.10-r1--windows-arm64-cp312-cpu--7286b30fa4bc0f97d5d4) |

All four cloud builds and independent publish jobs passed. The shared builder and
toolchain were unchanged, preserving the other targets' build fingerprints.

## Native FFmpeg

The imageio wrapper retains its pinned 0.6.0 source. Its package-owned adapter
builds FFmpeg 9.0.2 and x264 at immutable commits with a hash-pinned native ARM64
LLVM/MinGW compiler. A separately pinned MSYS2 shell/make/pkgconf runs as build
tools only; it is not shipped as an application runtime.

The wheel includes `ffmpeg.exe`, `ffprobe.exe` and the matching ARM64 FFmpeg DLLs.
Windows `platform.machine()` case normalization and the ARM64 filename mapping
are fixed in the wrapper. Every executable and DLL is checked for ARM64 PE machine
type; native H.264 encode/decode, ffprobe inspection and PCM audio decode pass.

FFmpeg/x264 is GPL-2.0-or-later; the Python wrapper remains BSD-2-Clause. The same
immutable release supplies complete matching FFmpeg/x264 source archives, licenses,
source/tool hashes, configure arguments and the build adapter. Assembly and hardware
encoder acceleration are disabled. Other external codec libraries are not enabled.

## One cv2 provider and current MediaPipe APIs

MediaPipe's official 1.1.1 ARM64 wheel is pinned by SHA256. Its native libraries
are copied unchanged; only its OpenCV requirement is changed from the contrib
distribution to the verified SSUI `opencv-python-headless` version. The release's
`upstream-wheel-provenance.json` records upstream wheel/native-file hashes.
No duplicate cv2 provider or dummy package is installed.

Tests execute CPU FaceLandmarker and video-mode PoseLandmarker with hash-pinned
official models and images, checking actual face/pose detection and empty images.
MediaPipe 1.x uses Tasks. SSUI's face annotator and the downstream controlnet-aux
face helper were adapted to Tasks while retaining their legacy Solutions branches
for older environments. ControlNet Canny and positive face annotation pass.

## Streaming generation

The legacy copied generation loop depended on removed Transformers imports.
The replacement keeps `init_stream_support`, `StreamGenerationConfig`,
`NewGenerationMixin`, `setup_seed` and token-tensor iteration. It delegates model
generation to public GenerationMixin/streamer APIs, propagates worker exceptions,
and cancels/joins its worker when a stream closes.

Tests use a tiny randomly initialized GPT-2 model without downloaded LLM weights:
normal and beam generation, batched greedy streaming, equivalence to ordinary
sampling with a fixed seed, worker errors and cancellation all pass. The validated
combination is Transformers 4.57.6 with torch 2.9.1 CPU. Streaming beam search is
explicitly unsupported; ordinary beam generation is preserved. GPU is untested.

## SSUI integration

SSUI pins these four exact versions in its ARM64 CPU dependency override and
regenerates its binary-only lock. Its startup exposes the wheel's `ffmpeg.exe` to
child processes, respecting explicit user overrides. Motion video input falls
back to the packaged FFmpeg when headless OpenCV cannot decode a file.

The integrated checks cover imageio video round trips, Motion video frames,
Whisper file decoding, SSUI/ControlNet face annotation and pose tracking.
Full application/model regressions, GPU execution and OpenGL rendering remain
separate from these CPU compatibility checks. Older disabled Numba/llvmlite
recipes are not needed by SSUI's newer official 0.68.0/0.50.0 wheel combination.
