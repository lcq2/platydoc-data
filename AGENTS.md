# Maintaining Platydoc data

This repository owns expensive offline preprocessing for Platydoc. Keep compiler
builds, header generation, structure surveys and native/Wasm checks here. The
handbook repository owns Markdown, HTML rendering and browser presentation.

Use make_data.py as the public entry point. Keep all individual scripts and
fixtures in tools/layouts/. Treat xnu/ and bootstrap_cmds/ as read-only source
submodules; change pinned revisions deliberately. All build outputs belong in
.docs-cache/ or dist/, never in source checkouts or Git.

Build and validate locally. No native/compiler/preprocessing/validation workflow
is needed on GitHub. Publication only uploads the existing checked package.
Do not publish or create a remote repository without the user's instruction.

Preserve PAC-enabled arm64e iOS defaults, explicit applied directives, exact
original declarations, compatibility disclosures, upstream licenses and offline
file:// browsing. Keep package format changes coordinated with the consumer.
Do not add dependencies on a handbook checkout, generated HTML or sibling caches.
Choose focused checks appropriate to a change; do not rerun broad suites without
new failures or evidence that requires them. Keep progress notes private.
