# Platydoc data

This repository builds the compiler and source data used by Platydoc's offline
structure browser. It is intended to live at Platydoc's root as the
`platydoc-data/` submodule. It does not render the handbook or require a Platydoc checkout.
All compilation and validation happen locally; publication uploads finished data.

## Setup

Use Python 3.12+, Node.js 20+, CMake, Ninja, Clang/Clang++, GCC, make, autoconf,
automake, flex, bison, tcsh and unifdef. Install missing system tools through your
package manager. GitHub CLI is needed only to publish releases.

`xnu/` and `bootstrap_cmds/` are pinned Git submodules at the repository root.
Build scripts never modify these source checkouts. The selected XNU revision
must match the source checkout used by the handbook.

```sh
python3 make_data.py setup
python3 make_data.py build
```

`setup` explicitly initializes submodules, downloads checksum-pinned LLVM and
Emscripten archives, and installs the pinned Emscripten SDK locally. `build`
uses installed inputs without network access. It builds native/Wasm compiler
artifacts as needed, generates configuration and syscall/MIG headers, surveys
structure layouts, compares native/Wasm results, and packages the data.

The MIG generator is built from the pinned `bootstrap_cmds/` checkout in a cache
copy. No manually downloaded MIG archive is needed. The small `inputs/trustcache/`
directory preserves the selected Apple OSS headers, provenance and license;
synthetic CoreEntitlements parsing aids remain explicitly disclosed in the
layout profiles. Original KDK headers are not included.

## Output and publication

```sh
python3 make_data.py check
python3 make_data.py publish --repo lcq2/platydoc-data
```

The output is `dist/prepared-layouts.tar.gz`. Publication checks that package
and uploads it to an immutable `layouts-<sha256>` release. It does not build.
The release reference is also written to `dist/prepared-layouts.release.json`.

The package contains the Wasm compiler/loader, headers, configuration metadata,
structure catalog, common-profile data, validation evidence and original notices.
Native executables, compiler sources and build directories stay local. Browser
presentation and current handbook chapter/source links are supplied by Platydoc.

In the handbook checkout, select the printed release tag:

```sh
python3 make_docs.py --update-data layouts-<sha256> --data-repo lcq2/platydoc-data
python3 make_docs.py
```

For a local unpublished package, use
`python3 make_docs.py --prepared-layouts platydoc-data/dist/prepared-layouts.tar.gz`.
Ordinary handbook and UI edits do not require a new data package.

## Files and cleanup

- `tools/layouts/`: compiler source, individual build/generation/packaging scripts,
  profiles, compatibility definitions, contracts, fixtures and tests.
- `tools/layouts/profiles/structure-catalog.json`: the structures to survey.
- `tools/layouts/profiles/ios-catalog.json`: target and header/configuration contexts.
- `.docs-cache/layouts/compiler/`: reusable native and Wasm compiler outputs.
- `.docs-cache/layouts/compiler-build/`: LLVM sources and intermediate build files.
- `.docs-cache/layouts/emsdk/`, `downloads/`: installed SDK and pinned archives.
- `.docs-cache/layouts/configs/`, `generated-syscalls/`, `generated-mig/`,
  `mig-tools/`, `bundles/`, `runtime/`, `common-profiles/`: derived preparation data.
- `dist/`: publishable output; ignored by Git.
- `legacy/`: preserved former handbook/CI integration scripts for reference;
  these are not part of the active build and there is no compiler CI workflow.

All `.docs-cache/` and `dist/` contents are derived and may be deleted when no
build is running. Deleting compiler outputs requires rebuilding; deleting the SDK
or archives requires rerunning `setup`. Keep source scripts, profiles, inputs,
submodules and license files. Intermediate caches never belong in Git.

The individual scripts and earlier proof/test recipes remain in
`tools/layouts/README.txt`; `make_data.py` is the supported orchestration entry.
Legacy proof scripts that accept a book need that optional book explicitly and
are not prerequisites for producing data.

Build software is GPL-2.0-only. Original documentation is CC BY 4.0.
Compiler, XNU, MIG and copied third-party inputs retain their upstream licenses.
