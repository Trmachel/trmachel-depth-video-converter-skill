# Security Policy

## Supported versions

Security fixes are applied to the latest release and the `main` branch. Older releases may not receive backports.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| `main` | Yes |
| Older releases | Best effort only |

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could put users at risk.

Use **Security → Report a vulnerability** on this GitHub repository to submit a private security advisory. If private reporting is not visible, open a public issue containing no exploit details and ask the maintainer to establish a private channel.

Include, when possible:

- affected version or commit;
- operating system and Python version;
- minimal reproduction steps;
- potential impact;
- a non-sensitive proof of concept;
- relevant logs with paths, usernames, tokens, and personal data removed.

Do not attach private user videos or malicious media samples to public issues.

## Security-relevant surfaces

Reports are especially useful for:

- malformed or adversarial media handled by OpenCV or FFmpeg;
- command or argument injection around subprocesses;
- path traversal, unsafe temporary files, or unintended overwrites;
- model download, cache, or supply-chain integrity issues;
- unsafe network exposure of the local Gradio interface;
- denial of service through extreme dimensions, duration, or resource usage;
- vulnerable Python or GitHub Actions dependencies.

## Response targets

These are best-effort goals, not a service-level agreement:

- acknowledge a complete report within 7 days;
- provide an initial severity assessment within 14 days;
- coordinate disclosure after a fix or mitigation is available.

## User guidance

The application is not a security sandbox. Keep dependencies current, process media from trusted sources where possible, and retain the default loopback binding (`127.0.0.1`). Do not expose the interface to an untrusted network unless you add appropriate authentication and network controls.
