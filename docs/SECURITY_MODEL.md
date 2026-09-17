# Security Model

This document describes the project's main trust boundaries and intended security posture. It is not a formal audit.

## Assets to protect

- User source media and audio.
- Local filesystem paths and temporary files.
- Model cache integrity.
- Availability of the user's CPU, GPU, memory, and disk.
- The local Gradio interface and any machine on the same network.
- Repository and release integrity.

## Trust boundaries

### 1. Untrusted media input

MP4 and MOV files are parsed by libraries and external media tooling. Malformed files can trigger excessive resource use or vulnerabilities in decoders.

Controls and expectations:

- process trusted media when possible;
- keep OpenCV and FFmpeg current;
- avoid running as an administrator/root user;
- use bounded dimensions, duration, and temporary storage where practical;
- never publish a malicious sample in a public issue.

### 2. FFmpeg subprocesses

Command construction must pass arguments as a list and avoid shell interpolation. File paths must remain data, not executable syntax. Temporary files should be unique, private to the current user, and removed after success, cancellation, or failure.

### 3. Model downloads and cache

Model artifacts are obtained from an external model host and stored in a user cache. Users should verify upstream model identity and licensing. Future hardening may include pinned revisions and published hashes where upstream delivery permits it.

### 4. Local web interface

The intended default is loopback-only (`127.0.0.1`) with Gradio sharing disabled. Binding to `0.0.0.0`, using a public tunnel, or placing the interface behind a reverse proxy changes the threat model and requires authentication, TLS, rate limits, and network access controls.

### 5. Output and temporary storage

The converter writes temporary and final media to local disk. It must avoid path traversal, accidental overwrite, predictable shared temporary names, and incomplete cleanup after cancellation.

### 6. Dependencies and automation

Python packages and GitHub Actions are supply-chain dependencies. Dependabot, CodeQL, restricted workflow permissions, reviewed updates, and release checks reduce risk but do not eliminate it.

## Security invariants

Changes should preserve these properties unless a documented design explicitly replaces them:

- no source-media upload by default;
- no public Gradio share link by default;
- loopback-only listening by default;
- no shell execution for user-controlled file paths;
- tests do not fetch real model weights;
- secrets and personal paths are excluded from logs and issue templates;
- model and dependency licenses remain visible to users.

## Known limitations

- The application is not a malware analysis sandbox.
- Media decoders and ML frameworks are large third-party attack surfaces.
- Relative-depth inference can be computationally expensive and may exhaust resources on extreme inputs.
- Local-only operation protects against routine upload but does not protect a compromised host.
