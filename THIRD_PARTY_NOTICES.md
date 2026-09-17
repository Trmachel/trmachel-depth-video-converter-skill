# Third-Party Notices

This repository's original application code, tests, documentation, and Codex Skill are licensed under Apache-2.0 unless a file states otherwise. Third-party software and model weights retain their own licenses.

This document is informational and is not legal advice. Users are responsible for confirming that their selected model, dependencies, media, codecs, and deployment comply with their intended use.

## Depth Anything V2

The application can download and use Depth Anything V2 model weights. The upstream project currently states:

| Model family | Upstream license |
| --- | --- |
| Depth Anything V2 Small | Apache-2.0 |
| Depth Anything V2 Base | CC BY-NC 4.0 |
| Depth Anything V2 Large | CC BY-NC 4.0 |

The Base and Large licenses include a non-commercial restriction. Check the upstream repository and model card at the time of use because terms and model artifacts can change.

Upstream project: <https://github.com/DepthAnything/Depth-Anything-V2>

## Python dependencies

PyTorch, Transformers, Gradio, OpenCV, NumPy, Pillow, imageio-ffmpeg, and other installed packages are distributed under their own licenses. The authoritative list for a particular installation is the package metadata in that environment.

Useful commands:

```bash
python -m pip list
python -m pip show torch transformers gradio opencv-python imageio-ffmpeg
```

## FFmpeg and codecs

The program may use a system FFmpeg binary or the executable supplied through `imageio-ffmpeg`. FFmpeg licensing can depend on how a binary was built and which codecs are enabled. H.264 and other codecs may also involve patent or regional obligations outside the software license.

## User media

The repository does not grant rights to source videos, audio, images, or other user-provided media. Only process material you are authorized to use.
