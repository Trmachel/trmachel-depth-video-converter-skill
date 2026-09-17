# Trmachel Depth Video Converter

[简体中文](README.md) | **English**

[![CI](https://github.com/Trmachel/trmachel-depth-video-converter-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/Trmachel/trmachel-depth-video-converter-skill/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Trmachel/trmachel-depth-video-converter-skill/actions/workflows/codeql.yml/badge.svg)](https://github.com/Trmachel/trmachel-depth-video-converter-skill/actions/workflows/codeql.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A local-first Python application and installable Codex Skill that converts MP4 or MOV video into temporally smoothed relative-depth video with Depth Anything V2.

User media is processed on the local machine. The application does not upload the source video to a hosted service. Model weights are downloaded from Hugging Face on first use and then reused from the local cache.

> The output is monocular **relative depth**, not real-world distance measured in meters.

## Highlights

- Local Gradio web interface with upload, preview, progress, cancellation, and download.
- Depth Anything V2 Small, Base, and Large model choices.
- Automatic NVIDIA CUDA, Apple MPS, or CPU fallback.
- Original, 480p, 720p, and 1080p output presets with aspect-ratio preservation.
- Robust 2%–98% normalization and EMA temporal smoothing to reduce frame-to-frame flicker.
- Optional black/white inversion and source-audio preservation.
- H.264, `yuv420p`, fast-start MP4 output.
- Streaming frame processing instead of loading the entire video into memory.
- Automated tests that use a deterministic fake depth provider rather than downloading model weights.
- Cross-platform launcher packaged as a Codex Skill.

## System requirements

- Windows 10/11 64-bit or macOS 12.3+.
- Python 3.10–3.14; Python 3.11 or 3.12 is recommended for development and CI parity.
- At least 8 GB RAM. Base and Large may require substantially more memory or VRAM.
- Internet access the first time each model is downloaded.
- Enough disk space for model cache, input media, temporary files, and output.

| Model | Suggested use | Practical note |
| --- | --- | --- |
| Small | Default, CPU, ordinary laptops | Fastest and lowest resource use |
| Base | Quality/speed balance | GPU or Apple Silicon recommended |
| Large | More detail | Highest memory and compute demand |

## Windows quick start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r requirements.txt
python app.py --inbrowser
```

If PowerShell blocks activation for the current window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Check CUDA:

```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('PyTorch:', torch.__version__)"
```

When CUDA is unavailable, use the official PyTorch installation selector for a build compatible with the installed NVIDIA driver.

## macOS quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r requirements.txt
python app.py --inbrowser
```

Check Apple MPS:

```bash
python -c "import torch; print('MPS:', torch.backends.mps.is_available()); print('PyTorch:', torch.__version__)"
```

Intel Mac systems and unsupported Apple Silicon configurations fall back to CPU.

## Usage

1. Run `python app.py --inbrowser`.
2. Upload an MP4 or MOV file.
3. Choose the model and output resolution.
4. Adjust temporal smoothing; `0.65` is a practical default.
5. Choose inversion and audio preservation when needed.
6. Start conversion and download the resulting MP4.

Resolution behavior:

- `Original` keeps the source dimensions, adjusted to even values when required.
- `480p`, `720p`, and `1080p` use the target height for landscape video or target width for portrait video while preserving aspect ratio.
- Upscaling does not create real depth detail that is absent from the source or model estimate.

Higher temporal smoothing usually reduces flicker but can introduce mild trails around fast motion. Set it to `0` to disable cross-frame smoothing.

## Command-line options

```text
python app.py [--force-cpu] [--server-name ADDRESS] [--port PORT]
              [--output-dir DIRECTORY] [--inbrowser] [--verbose]
```

Examples:

```bash
python app.py --force-cpu --inbrowser
python app.py --port 7861
python app.py --output-dir "./converted"
```

The application listens on `127.0.0.1` by default and starts Gradio with `share=False`. Do not bind to `0.0.0.0` on an untrusted network without authentication and network controls.

## FFmpeg

`imageio-ffmpeg` is included in the Python dependencies. The application first checks for a system FFmpeg executable and otherwise uses the executable supplied by `imageio-ffmpeg`.

Manual installation examples:

```bash
# macOS
brew install ffmpeg

# Windows
winget install --id Gyan.FFmpeg
```

## Tests

```bash
python -m pip install "pytest>=8,<10"
python -m pytest -q
```

Automated tests must not download real model weights or depend on private media.

## Codex Skill

The installable Skill is located at:

```text
skills/trmachel-convert-depth-video/
```

After installation, ask Codex:

```text
Use $trmachel-convert-depth-video to launch the local depth video converter.
```

The launcher creates an isolated virtual environment in the user cache rather than writing `.venv` or model weights into the Skill directory.

Setup and launch directly from the repository:

```bash
python skills/trmachel-convert-depth-video/scripts/launch.py --setup-only
python skills/trmachel-convert-depth-video/scripts/launch.py --inbrowser
```

## Privacy and security

- Source media remains on the local machine unless the user separately uploads it elsewhere.
- The tool is not a sandbox for hostile media. Keep OpenCV, FFmpeg, PyTorch, Transformers, and Gradio current.
- Do not expose the local server publicly without authentication and network controls.
- Never attach private media or unredacted logs to a public issue.
- Report vulnerabilities through [SECURITY.md](SECURITY.md).

See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for the main trust boundaries.

## Licensing

Repository code and the Codex Skill are licensed under Apache-2.0.

Depth Anything V2 model weights have separate terms:

- Small: Apache-2.0.
- Base and Large: CC BY-NC 4.0, including a non-commercial restriction.

Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and verify the current upstream terms before use.

## Project maintenance

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Maintainers](MAINTAINERS.md)
