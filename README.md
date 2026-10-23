# SSUI Python Packages

Independent, reproducible-input wheel recipes for missing architecture and GPU
builds used by SSUI. A source repository stays pinned at an immutable commit;
this repository owns orchestration, target configuration, patches, verification
and distribution. It does not rebuild every package on every commit.

## Initial migration

| Package | Pinned source | Initial targets | Verification |
| --- | --- | --- | --- |
| Pynini 2.1.6.post1 | `sunxfancy/pynini-2.1.6.post1@c6c0d6c` | CPython 3.12, Windows x64 and macOS ARM64 | Import, FST operation, upstream tests |
| CuMesh 0.0.1 | `sunxfancy/CuMesh.rocm72@bb2ed49` | CPython 3.12, Windows x64, ROCm 7.2.1, torch 2.9.1, gfx1201 | All native extension imports |
| bitsandbytes 0.49.2 | `sunxfancy/bitsandbytes-0.49.2.rocm72@19d2059` | Same ROCm target | ROCm DLL load and version check |

The original repositories and published wheels are retained. This first migration
ports Python 3.12 targets, rather than silently claiming every upstream matrix
entry. Additional Python/OS/arch/backend combinations are separate target files.
GPU kernels are **not tested on hosted CPU runners**. Every release records
`gpu_runtime: false`; do not equate native import/load checks with GPU validation.

## Layout

* `packages/<name>/recipe.json`: upstream version, downstream revision, pinned source.
* `packages/<name>/targets/*.json`: independent OS, architecture, compute backend,
  Python ABI, toolkit, PyTorch ABI, GPU architecture and runner selections.
* `packages/<name>/build.py`, `smoke_test.py`, `patches/`: package-owned adapters.
* `toolchains/*.json`, `common.lock`: shared, explicitly referenced build inputs.
* `scripts/`: planning, building, wheel verification and immutable releases.
* `.github/workflows/build-wheel.yml`: reusable per-target build/publish pipeline.

## Local commands

Python 3.12+ and Git are required. The orchestration/tests use the standard library
and need no pip dependencies. Yarn only provides consistent command entrypoints;
equivalent `python scripts/...` invocations are shown in package.json.

```sh
yarn test
yarn validate
yarn plan --all --offline
yarn plan --package cumesh --offline
yarn plan --package cumesh --repo sunxfancy/ssui-python-packages
yarn plan --base <full-base-sha> --head <full-head-sha> --repo sunxfancy/ssui-python-packages
```

Actual wheel builds run on native target machines through Actions. `plan.json`
contains the exact matrix, fingerprints and independently skipped targets.

## Incremental selection and fingerprints

The planner selects candidates by changed paths. Changes to one package select
that package; changes to one target select that target. A deleted patch still
selects its owner. A toolchain selects only its consumers. Documentation, tests,
planning and publication logic do not themselves force wheel compilation.

Each target fingerprints its pinned source/recipe, package build/smoke scripts and
patches, that target file, referenced toolchain/lock files, and shared build/verify
code plus the reusable build workflow. **The overall repository commit is not a
build input.** Editing a sibling package or adding a sibling target leaves the
existing target fingerprint unchanged.

For each candidate, the planner checks its immutable release manifest, successful
smoke status, and GitHub's SHA256/size metadata for every released asset. A matching
fingerprint with complete validated assets is skipped. Missing/draft/failed or
inconsistent releases are not considered build evidence. Dependency download
caches and expiring Actions artifacts are never used as proof of publication.

Shared build input changes deliberately invalidate consumers. Pinning declared
inputs is not a claim of bit-for-bit reproducibility: hosted runner image updates
can change MSVC/Xcode. The actual image and installed dependency versions are
recorded in release provenance. Deliberately updating that compiler/toolchain
requires a toolchain revision. An implicit cross-package build DAG is not guessed;
recipes declaring build_dependencies are rejected until explicit DAG support is added.

## Independent releases

Every matrix target runs its own build, smoke test and publish jobs. `fail-fast`
is disabled. One failed package does not prevent another target's successful
release. Pushes to main publish successful targets; PRs never publish. Manual
dispatch accepts package/target selectors and defaults to **no publication**.

Tags are namespaced by package, upstream version, recipe revision, target and
fingerprint. Wheels get downstream PEP 440 local versions, with corrected
METADATA/dist-info/RECORD, and GPU variants include toolkit/PyTorch/gfx labels.
The local version also includes a fingerprint prefix, so a toolchain change
cannot silently produce different wheels with the same version and filename.
Published assets are never overwritten. A partial draft is left for inspection;
bump the package revision for a fresh immutable release after fixing inputs.
`--force` is for diagnostic rebuilds; avoid publishing a byte-different rebuild
under an already-published fingerprint.

Release assets include the wheel, `release.json` (SHA256 and provenance), and
`build-environment.txt`. Source licenses remain upstream; each recipe identifies
its upstream license and wheels retain their included license files. Repository
orchestration code is MIT licensed.

## Package indexes

GPU compatibility is not represented by ordinary wheel platform tags. Separate
channels must isolate OS/arch/backend/toolkit/PyTorch/gfx combinations. Never put
all GPU variants into one undifferentiated extra-index and expect pip to choose
the right GPU. SSUI should select a channel before generating its own lock.

The release catalog/index workflow publishes static Simple API pages separately
from wheel builds. Refreshing indexes does not rebuild wheels; old releases stay
available. The generated `gh-pages` branch is deployment output, not build state.

## Updating a package

Change only its source commit, patches or recipe; bump `revision` when changing a
published build intentionally. Add a target JSON to expand its matrix. Shared
toolchain changes affect only targets referencing it. To update build dependencies,
edit `toolchains/common.in`, run `yarn lock:toolchains` with uv available, review
the resulting fully pinned lock, then run tests and plan before pushing.
