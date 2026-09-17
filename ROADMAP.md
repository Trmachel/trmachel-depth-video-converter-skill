# Roadmap

This roadmap records direction, not guaranteed delivery dates. Priorities may change based on user reports, security findings, upstream model changes, and maintainer capacity.

## Current baseline — v0.1

- Local Gradio interface for MP4 and MOV input.
- Relative-depth video generation with Depth Anything V2 Small, Base, and Large.
- Automatic CUDA, Apple MPS, or CPU selection.
- Resolution presets, robust normalization, temporal smoothing, optional inversion, and optional source audio.
- H.264 MP4 output and safe cancellation.
- Installable Codex Skill with a cross-platform launcher.
- Automated tests that avoid downloading real model weights.

## Near term — v0.2

- Publish reproducible installation and troubleshooting checks.
- Expand codec and variable-frame-rate test coverage.
- Add a machine-readable diagnostics bundle with automatic secret/path redaction.
- Add a non-GUI CLI conversion path for scripting.
- Publish benchmark methodology for CPU, CUDA, and Apple MPS.
- Improve model download status, cache visibility, and offline error messages.
- Tighten dependency constraints after cross-platform validation.

## Medium term

- Batch conversion queue with bounded resource use.
- Better handling of long videos and interrupted jobs.
- Optional scene-aware temporal stabilization experiments.
- Internationalized interface and documentation.
- Signed release assets and stronger supply-chain verification.

## Out of scope by default

- Uploading user media to a hosted service.
- Claiming metric distance from monocular relative-depth output.
- Circumventing third-party model or media licenses.
- Exposing the local interface publicly without authentication and security controls.

Suggestions are welcome through the feature request form.
