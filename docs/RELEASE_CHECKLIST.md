# Release Checklist

Use this checklist for every public version.

## Before tagging

- [ ] `main` is clean and up to date.
- [ ] CI passes on Windows, macOS, and Ubuntu.
- [ ] CodeQL has no unresolved high-confidence finding that affects the release.
- [ ] `CHANGELOG.md` contains the version and release date.
- [ ] User-visible changes are documented in both README files where relevant.
- [ ] Tests avoid model downloads and private media.
- [ ] New dependencies and model choices have license notices.
- [ ] The default server still binds to loopback and uses `share=False`.
- [ ] A clean virtual environment can install and launch the project.
- [ ] A short synthetic MP4 and MOV have been tested manually on at least one supported platform.

## Create the release

Use an annotated Semantic Versioning tag:

```bash
git switch main
git pull --ff-only
VERSION=v0.1.1
git tag -a "$VERSION" -m "Release $VERSION"
git push origin "$VERSION"
```

The release workflow will run tests, create a source archive and SHA-256 checksum, and create a GitHub Release with generated notes.

## After publishing

- [ ] Confirm the release page and both assets are visible.
- [ ] Download the archive and verify its checksum.
- [ ] Test setup from the release archive on a clean machine or virtual environment.
- [ ] Record release downloads and feedback in the maintainer metrics tracker.
- [ ] Triage release-related issues promptly.
- [ ] Publish a concise demo and release announcement using non-sensitive media.
