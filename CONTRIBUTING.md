# Contributing

Thank you for improving the depth video converter and its Codex Skill. Contributions should keep the project local-first, cross-platform, testable, and transparent about third-party licensing.

## Before opening an issue

- Search existing issues and review [ROADMAP.md](ROADMAP.md).
- Use the structured bug or feature form.
- Never upload private, sensitive, or unlicensed media. Prefer a short synthetic test clip.
- Report security vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Development setup

Use Python 3.11 or 3.12 for development.

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "pytest>=8,<10"
```

Run the tests:

```bash
python -m pytest -q
```

The test suite must not download real model weights. Use fakes, mocks, or tiny generated media fixtures for automated tests.

## Pull requests

A focused pull request is easier to review than a broad rewrite. Please:

1. Explain the user problem and the chosen design.
2. Add or update tests for behavior changes.
3. Consider Windows, Apple Silicon, Intel Mac, CUDA, MPS, and CPU paths where relevant.
4. Update documentation and `CHANGELOG.md` for user-visible changes.
5. Keep the default application local-only; do not introduce cloud upload or public sharing by default.
6. Avoid adding dependencies unless their maintenance and licenses are justified.

CI must pass before merge. The maintainer may request a smaller scope, additional tests, or license clarification.

## Commit messages

Use a concise imperative subject, for example:

```text
Fix cancellation cleanup on Windows
Add MOV codec details to bug reports
```

## Licensing

By submitting a contribution, you agree that your contribution may be distributed under the repository's Apache-2.0 license. Third-party code, model weights, media, and generated fixtures must retain their own notices and compatible licenses.
