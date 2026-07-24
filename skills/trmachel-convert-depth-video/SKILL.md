---
name: trmachel-convert-depth-video
description: Install, launch, operate, and troubleshoot a local Depth Anything V2 video converter on Windows or macOS. Use when a user asks to convert MP4 or MOV files into grayscale relative-depth videos, start the Gradio converter UI, select a model size or output resolution, reduce video-depth flicker, preserve audio, or diagnose CUDA, Apple MPS, CPU, ffmpeg, model-download, and video-encoding failures.
---

# Convert Depth Video

Use the bundled Python application to create grayscale relative-depth MP4 videos
locally. Resolve every relative path from this skill directory.

## Launch

1. Confirm that Python 3.10 through 3.14 is available.
2. Run:

   ```text
   python scripts/launch.py
   ```

3. Keep the process running and report the printed localhost URL to the user.
4. Do not add `--server-name 0.0.0.0` or enable Gradio sharing unless the user
   explicitly requests network access and understands the exposure.

The launcher creates a versioned virtual environment in the operating system's
user cache directory. It installs dependencies only when the environment or
requirements change.

Useful options:

```text
python scripts/launch.py --inbrowser
python scripts/launch.py --force-cpu
python scripts/launch.py --port 7861
python scripts/launch.py --output-dir "/path/to/completed-videos"
python scripts/launch.py --setup-only
python scripts/launch.py --reinstall
```

Pass all arguments except `--setup-only` and `--reinstall` through to the
bundled `app.py`.

## Convert

Use these defaults unless the user specifies otherwise:

- Model: Small.
- Resolution: Original.
- Temporal smoothing: 0.65.
- Preserve audio: enabled.
- Invert grayscale: disabled.

Explain that the result is relative depth, not distance measured in meters.
Uploading a video must never transmit it to an external service. Model files
download from Hugging Face on first use and then run locally.

Model guidance:

- Use Small for CPU systems, long videos, previews, and commercial workflows.
- Use Base when quality and speed need a better balance.
- Use Large only when detail matters more than processing time and memory.
- Read `references/model-licenses.md` before advising about commercial use.

## Troubleshoot

Read `references/platform-setup.md` when installation, GPU acceleration,
ffmpeg, or model loading fails.

Apply these first responses:

- CUDA out of memory: select Small, lower resolution, or use `--force-cpu`.
- MPS unsupported operation: restart with `--force-cpu`.
- Model download failure: check network, cache permissions, and free space.
- Audio missing: verify the source has audio and Preserve Audio is enabled.
- MOV decoding failure: transcode the source to H.264/AAC MP4 with ffmpeg.
- Port already used: restart with `--port` and another local port.

Do not install CUDA toolkits speculatively. Use the current PyTorch installation
selector when a Windows NVIDIA wheel must be replaced.

## Maintain

Treat `scripts/app.py` as the installed application's source of truth inside
the Skill. Keep `scripts/requirements.txt` synchronized with it.

After changes, run:

```text
python scripts/launch.py --setup-only
python -m pytest -q
python /path/to/skill-creator/scripts/quick_validate.py /path/to/trmachel-convert-depth-video
```
