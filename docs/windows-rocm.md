# Windows ROCm recipes

The ROCm migration targets Windows x64, CPython 3.12, ROCm 7.2.1,
PyTorch 2.9.1 and gfx1201 only. CPU, CUDA, ARM64 and Linux targets are unchanged.

Package-owned recipes now cover bitsandbytes, CuMesh, FlexGEMM, o-voxel,
nvdiffrast, NATTEN, torch-cluster, torch-scatter and diso. Each package remains
independently selectable and fingerprinted. Sources stay in their upstream
repositories at immutable commits. Adaptations migrated from SSUI live beside
their recipes; no sibling SSUI checkout is required to build them.

CuMesh revision 2 includes SSUI's bounded tensor-copy fix for meshes with more
than 1,048,576 rows. Its previous releases remain immutable. NATTEN builds the
non-CUTLASS naive kernels only. nvdiffrast records its separate RDNA4 patch source
in `packages/nvdiffrast/kernel-source.json`; changing it changes that package's
fingerprint. diso retains its upstream CC BY-NC 4.0 license.

FlexGEMM and o-voxel smoke checks load their native modules directly. The full
Python pipelines require Triton or sibling native wheels and are tested separately
on the target machine, rather than fetched from floating indexes during a build.
Hosted runners verify native imports or DLL loading, and record GPU runtime as
untested. Real GPU checks must run separately on a matching machine before SSUI
adopts newly published wheels. A recipe being present does not mean its wheel has
built, published or passed GPU validation. Keep existing dependency URLs until
the replacement release and its provenance have been verified.

```sh
yarn plan --target windows-x64-cp312-rocm721-gfx1201 --offline
yarn plan --package nvdiffrast --offline
```
