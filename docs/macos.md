# macOS supplements

Only macOS recipes are covered by this migration. Existing Windows and ROCm
recipes, toolchains and releases are unchanged.

| Package | Target | Ownership |
| --- | --- | --- |
| Pynini | CPython 3.12 / ARM64 / CPU | Existing recipe and published wheels |
| ssui-trellis-mps | CPython 3.12 / ARM64 / MPS / torch 2.4.1 | Metal native bridge and integer topology formerly vendored in SSUI |

`packages/ssui-trellis-mps/src/ssui_trellis_mps/` owns the migrated source.
Its recipe records the immutable SSUI source commit, and retains TRELLIS's MIT
license. The adapter stages only this package into the pinned checkout; no SSUI
application dependencies or CUDA renderers are built. The isolated toolchain
pins PyTorch and NumPy without changing other targets' build inputs.

```sh
yarn plan --package ssui-trellis-mps --offline
```

The bridge is compiled into the wheel at build time. Consumers need neither
Xcode nor ninja at runtime. The embedded Metal shader is still compiled by the
Metal driver on first use. PyTorch 2.4.1 is required because the native extension
uses its C++ / MPS stream ABI. Install the released wheel from the channel:

```sh
python -m pip install --index-url https://sunxfancy.github.io/ssui-python-packages/simple/macos/arm64/mps/2.4.1/ --no-deps ssui-trellis-mps
```

This command requires a successful main-branch publication and refreshed index.
A PR build is an Actions artifact, not an available release. Keep the SSUI
consumer migration dependent on publication, then verify the immutable wheel URL
in SSUI's macOS dependency configuration against release.json and its SHA-256.

Hosted runners load the compiled extension and check CPU topology behavior.
They do not validate Metal kernel execution or real model generation. After
installation on a Mac with MPS, run SSUI's `yarn test:trellis:topology --check-only`
and `yarn test:trellis:smoke --local-files-only --workflow` for GPU and real-weight
regression. Previously recorded SSUI benchmarks predate this package migration.

TRELLIS sparse tensor/decoder integration and model-specific MPS device fixes
(AnimateDiff, Wan, TripoSR, Kimodo) stay in SSUI: they are application integration,
not independently built native wheels. No Windows/Linux implementation is moved.

Local validation: the full package build/relabel/verification/smoke pipeline and
SSUI's exact GPU topology edge-case suite passed on Apple Silicon after
installation of the built wheel. This is operator validation, not a repeat of
real-weight TRELLIS inference. The build suppresses Clang's invalid-specialization
diagnostic for PyTorch 2.4.1 headers on newer Xcode; kernel code is unchanged.
