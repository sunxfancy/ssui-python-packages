# Windows ARM64 binary migration (2026-10-29)

This directory imports existing SSUI Windows ARM64 builds into immutable Releases
and the cumulative package index. It does **not** claim a fresh source rebuild or
hosted-CI GPU validation. The original wheel SHA256 is pinned in `registry.json`.
Original source commits/archives, local patches, submodule pins and historical
build adapters are retained alongside the migration. Existing `packages/` recipes,
their fingerprints, x64/ROCm releases and the shared build workflow are unchanged.

## Scope

| Channel | Python | Packages |
| --- | --- | --- |
| Windows ARM64 CUDA 13.4 / torch 2.16.0.dev20261026+cu134 / SM 12.1 | 3.13 | cumesh, flex-gemm, natten, nvdiffrast, o-voxel, cumm, spconv, flash-attn, pytorch3d, torch-cluster, torch-scatter |
| Windows ARM64 CPU | 3.13 | opencv-python-headless 4.11.0.86, freetype-py 2.5.1 with FreeType 2.13.3 |
| Windows ARM64 CPU | 3.12 | WeTextProcessing 1.0.4, migrated from the older pynini repository |

Official PyTorch, torchvision, Triton and ordinary PyPI dependencies remain
upstream dependencies. This is a supplement, not a full environment mirror.
The pure Python WeTextProcessing wheel is restricted to the ARM consumer's
validated Python 3.12 environment; other consumers retain their existing source.

CUDA index:
`https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cuda/13.4/2.16.0.dev20261026-cu134/sm121/`

CPU index:
`https://sunxfancy.github.io/ssui-python-packages/simple/windows/arm64/cpu/`

Use the generated `requirements-cp313.txt` only in a Windows ARM64 Python 3.13
environment with the exact NVIDIA PyTorch runtime above and its normal runtime
dependencies already installed:

```powershell
python -m pip install --no-deps --only-binary=:all: -r arm64/requirements-cp313.txt
```

Run GPU verification from an ARM64 MSVC developer shell with CUDA 13.4 on PATH.
FlexGEMM's Triton runtime needs a C compiler even though the distribution itself
is prebuilt; first-use sparse-kernel compilation/autotuning can take several minutes.

Do not install these builds into the Python 3.12 CPU profile. Wheel tags cannot
encode CUDA/PyTorch compatibility, so both the isolated channel and exact torch
metadata pin are required. The release index links include SHA256 digests.

## Migration and verification

The input wheel names and SHA256 digests are fixed. `prepare` rejects different
input bytes; it corrects filename, METADATA, dist-info and RECORD together, pins
CUDA torch and sibling dependencies, and validates every native PE binary as
ARM64. Source URL dependencies in o-voxel are replaced by the exact imported
CuMesh/FlexGEMM versions so installation does not silently build upstream code.
The batch registry is part of the fingerprint because sibling dependency pins
affect output metadata. Releases remain independent and immutable.

```powershell
yarn test
yarn validate
yarn arm64:prepare --raw C:/path/to/original-wheels
yarn arm64:check --python C:/path/to/arm64-cuda-python.exe --abi 3.13
yarn arm64:check --python C:/path/to/arm64-cpu-python.exe --abi 3.12
yarn arm64:validate
# Commit and push the exact migration inputs before publication.
yarn arm64:publish --commit FULL_COMMIT_SHA
```

`check` installs only these wheels into a fresh `.work/arm64-import/installed-*`
directory, reuses dependencies from the supplied Python and verifies installed
distribution versions before running operations. It never replaces packages in
that Python. Temporary files and Triton caches stay under `.work/arm64-import`.
The CUDA probe verifies exact torch, toolkit runtime and device capability before
GPU execution. Verification includes sparse convolution against a dense reference,
mesh geometry, rasterization, neighborhood attention, voxel round-trip, FPS,
CSR reductions, KNN, transforms, FlashAttention, spconv, OpenCV inpainting,
FreeType glyph rendering and Chinese text normalization.

Each release includes `release.json`, original input/source provenance, the
verification environment and applicable operator reports. The publisher verifies
local hashes and remote GitHub asset digests and refuses to overwrite any tag.
It refreshes the existing cumulative index only after publication completes.

## Source evidence and limits

`provenance/<package>/` records original Git source patches, recursive submodule
pins and licenses where present. NATTEN additionally has a patch inside Cutlass.
`rigging-build.py`, `sitecustomize.py`, `pixal-run-setup.py`, `patch-natten.py` and
the OpenCV adapter are historical build instructions from the SSUI workspace;
they are retained as evidence, not wired into the hosted build planner. The
rigging script expects its original SSUI directory layout.

FreeType packaging uses the unmodified freetype-py source archive's Python files
and metadata plus the ARM64 DLL built at the recorded FreeType commit. Its wheel
includes FTL.TXT. It is a CPU font library, not a CUDA kernel. The binary was
inspected as ARM64, rather than relabeling a Windows x64 wheel.

OpenCV excludes FFmpeg/Media Foundation and optional FP16 dispatch, as in the
existing ARM64 CPU recipe. CUDA tests cover the listed operations on RTX Spark
N1X, not every training/backward path or every model. Complete source rebuild
automation for this migrated GPU batch is future work; raw binary hashes are the
authoritative migration inputs. Existing CPU packages retain their normal recipes.
