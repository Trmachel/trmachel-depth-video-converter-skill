# Platform Setup and Troubleshooting

## Supported runtime

- Python 3.10 through 3.14.
- Windows 10/11 64-bit.
- macOS 12.3 or later.
- Apple Silicon is recommended for MPS acceleration.

The launcher stores its isolated environment outside the Skill:

- Windows: `%LOCALAPPDATA%\convert-depth-video`
- macOS: `~/Library/Caches/convert-depth-video`
- Linux fallback: `${XDG_CACHE_HOME:-~/.cache}/convert-depth-video`

Use `python scripts/launch.py --reinstall` after dependency corruption or a
requirements change.

## Acceleration

The application selects devices in this order:

1. NVIDIA CUDA.
2. Apple MPS.
3. CPU.

Check Windows CUDA:

```text
python -c "import torch; print(torch.cuda.is_available())"
```

If CUDA is false on an NVIDIA system, use the current selector at
`https://pytorch.org/get-started/locally/`. Select Windows, Pip, Python, and a
CUDA build supported by the installed driver. Do not assume a CUDA wheel URL.

Check macOS MPS:

```text
python -c "import torch; print(torch.backends.mps.is_available())"
```

Use `python scripts/launch.py --force-cpu` when GPU execution is unstable.

## ffmpeg

The runtime includes `imageio-ffmpeg` and prefers a system ffmpeg when present.

Optional system installation:

```text
macOS:  brew install ffmpeg
Windows: winget install --id Gyan.FFmpeg
```

Check availability with `ffmpeg -version`.

## Models

Models download from Hugging Face on first use. Later conversions reuse the
normal Hugging Face cache. An access token is not required for the public
checkpoints, although unauthenticated downloads may be rate limited.

Common model-load failures:

- No network during first use.
- Insufficient disk space.
- Cache directory is not writable.
- A partially downloaded model needs a retry.
- `torchvision` is missing because installation was interrupted.

## Video compatibility

MP4 and MOV are containers; their internal codecs vary. Convert an unsupported
source with:

```text
ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p -c:a aac input.mp4
```

The first version converts variable-frame-rate input to the detected average
constant frame rate.
