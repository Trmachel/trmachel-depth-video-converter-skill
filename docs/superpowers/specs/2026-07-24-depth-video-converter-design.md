# Cross-Platform Depth Video Converter — Design Specification

## 1. Goal

Build a standalone Python application that converts an uploaded RGB video into a grayscale relative-depth video using Depth Anything V2. The application runs locally on Windows and macOS, exposes a concise Gradio web interface, and does not copy or depend on another project's source code.

The application accepts MP4 and MOV inputs and exports a browser-compatible MP4. It supports model-size selection, output-resolution selection, grayscale inversion, temporal smoothing, optional source-audio preservation, progress reporting, and safe cancellation.

## 2. Scope

### Included

- A local Gradio single-page interface.
- MP4 and MOV upload, metadata inspection, conversion, preview, and download.
- Depth Anything V2 Small, Base, and Large model choices.
- Automatic device selection in this order: NVIDIA CUDA, Apple MPS, CPU.
- Original, 480p, 720p, and 1080p output choices with preserved aspect ratio.
- Robust grayscale normalization and configurable temporal smoothing.
- Optional black/white inversion.
- H.264 MP4 output with `yuv420p` pixel format.
- Optional source-audio stream reuse through ffmpeg.
- Per-task progress, processing speed, estimated remaining time, and cancellation.
- Actionable errors and automatic intermediate-file cleanup.
- Unit tests for deterministic core behavior and an end-to-end smoke-test path.
- Windows and macOS installation and launch instructions.

### Not included

- Metric depth in meters.
- Stereo, spatial-video, point-cloud, or 3D mesh generation.
- Cloud inference or external API calls.
- Multi-user server deployment.
- Bundling model weights inside the repository or application package.
- A native desktop wrapper or distributable installer.

## 3. Runtime and Dependencies

The application targets a current 64-bit CPython release supported by PyTorch, Transformers, Gradio, and OpenCV. The README will specify the tested Python range rather than assuming every Python version is compatible.

Primary libraries:

- `torch` for CUDA, MPS, and CPU inference.
- `transformers` for `AutoImageProcessor` and `AutoModelForDepthEstimation`.
- `gradio` for the local web interface.
- `opencv-python` for input decoding and frame conversion.
- `numpy` and `Pillow` for array and image processing.
- `imageio-ffmpeg` for locating a cross-platform ffmpeg executable when a system ffmpeg is not on `PATH`.
- `pytest` for tests.

Model identifiers:

- `depth-anything/Depth-Anything-V2-Small-hf`
- `depth-anything/Depth-Anything-V2-Base-hf`
- `depth-anything/Depth-Anything-V2-Large-hf`

Each selected model downloads on first use through Hugging Face and remains in the normal local cache for later offline use.

## 4. Architecture

The deliverable favors one runnable `app.py` as requested, while keeping internal responsibilities separated by small classes and functions:

1. **UI layer**
   - Builds the Gradio Blocks interface.
   - Validates user inputs and maps controls to a conversion request.
   - Streams progress and returns the completed video path.
   - Exposes cancellation without containing model or codec logic.

2. **Device and model manager**
   - Selects `cuda`, then `mps`, then `cpu`.
   - Lazily loads and caches one model/processor pair per model size.
   - Moves tensors to the selected device and uses inference-only execution.
   - Releases task tensors promptly while retaining cached model weights.

3. **Video conversion engine**
   - Probes input metadata and validates that frames can be decoded.
   - Calculates target dimensions.
   - Reads and processes frames sequentially to keep memory bounded.
   - Performs model preprocessing, inference, resizing, normalization, smoothing, inversion, and grayscale-to-video-frame conversion.
   - Checks cancellation between frames.

4. **Media exporter**
   - Encodes silent depth frames into H.264 MP4 with `yuv420p`.
   - Optionally remuxes the original audio stream into the final MP4.
   - Uses unique task paths and atomic final-file replacement.
   - Reports ffmpeg diagnostics in a concise, user-actionable form.

5. **Task workspace**
   - Creates an isolated temporary directory for every conversion.
   - Keeps the final output outside the temporary directory long enough for Gradio to serve it.
   - Removes partial and intermediate files on success, failure, or cancellation.

## 5. Data Flow

1. The user uploads an MP4 or MOV.
2. The application probes width, height, frame rate, frame count, duration, and audio presence.
3. The user selects model size, output resolution, smoothing strength, inversion, and audio preservation.
4. On Start, the application resolves the acceleration device and lazily downloads or loads the selected model.
5. OpenCV reads input frames sequentially.
6. Each frame is converted from BGR to RGB and passed through Depth Anything V2.
7. The predicted relative-depth tensor is resized to the target output dimensions.
8. The frame is robustly normalized and temporally stabilized.
9. Optional inversion is applied, then the single-channel result is expanded to three grayscale channels for broadly compatible video encoding.
10. ffmpeg produces H.264 video using the source frame rate.
11. If requested and available, the source audio is remuxed without re-encoding where the MP4 container permits it; otherwise ffmpeg uses a compatible AAC fallback only when necessary.
12. The completed MP4 is returned to the Gradio preview and download component.

## 6. Depth Post-Processing

Depth Anything V2 produces relative rather than metric depth. Raw values therefore require visualization mapping.

For each predicted depth map:

1. Compute the 2nd and 98th percentiles to resist isolated outliers.
2. Smooth the lower and upper bounds over time using an exponential moving average.
3. Normalize values to `[0, 1]` using the stabilized bounds and clip outliers.
4. Smooth the normalized depth map against the previous processed map using an exponential moving average.
5. Convert to 8-bit grayscale.
6. Apply `255 - value` when inversion is enabled.

The UI exposes smoothing as a value from `0.0` to `0.95`, with a documented medium default. Zero disables temporal depth-map smoothing. Strong smoothing reduces flicker but may introduce trailing around rapidly moving subjects. Both percentile bounds and processed maps reset at the start of each task.

## 7. Resolution Rules

- **Original:** retain source dimensions.
- **480p, 720p, 1080p:** treat the preset number as the maximum output height for landscape video and the maximum output width for portrait video.
- Preserve aspect ratio in all cases.
- Never upscale above the source dimensions unless the user explicitly selects a larger preset; the documented behavior is that a selected preset is an explicit upscale request.
- Round both dimensions to positive even integers for H.264 compatibility.

## 8. Device Selection and Failure Behavior

Device detection uses:

1. `torch.cuda.is_available()`
2. `torch.backends.mps.is_available()`
3. CPU fallback

The resolved device is shown in the interface. The application does not silently change devices during a task because restarting mid-video could produce inconsistent normalization and confusing timing. CUDA out-of-memory errors recommend a smaller model or output size. MPS operator failures recommend retrying on CPU. The user can force CPU from a command-line option for troubleshooting even though automatic selection is the default.

## 9. Interface Design

The Gradio page uses a two-column primary area:

- Left: upload control and source metadata.
- Right: completed depth-video preview and download.

A settings card contains:

- Model size: Small (default), Base, Large.
- Resolution: Original (default), 480p, 720p, 1080p.
- Temporal smoothing slider.
- Invert black and white checkbox.
- Preserve original audio checkbox.
- Start and Cancel actions.

A status area shows the selected device, current stage, processed and total frames when known, percentage, effective frames per second, and estimated remaining time. Parameters lock while a task is active. Upload alone does not download a model or start conversion.

The application binds only to localhost by default and does not enable Gradio public sharing.

## 10. Encoding and Audio

The exporter discovers ffmpeg in this order:

1. A valid executable on `PATH`.
2. The executable supplied by `imageio-ffmpeg`.

Silent depth frames are encoded as H.264 MP4 with `yuv420p` for browser and media-player compatibility. Variable-frame-rate inputs are processed using the probed average frame rate in the first version; the README states this limitation.

When Preserve Audio is enabled:

- The exporter maps the newly encoded video stream and the first source audio stream.
- It first attempts compatible stream copy.
- If stream copy is incompatible with MP4, it retries with AAC audio encoding.
- If the source has no audio, conversion succeeds and reports that the output is silent.
- If audio muxing fails for another reason, the silent encoded depth video remains available and the UI reports the audio-specific failure.

## 11. Progress, Cancellation, and Cleanup

Progress stages are metadata probe, model load, depth inference, video encode, audio mux, and completion. Frame progress uses decoded frame count when reliable; otherwise it reports processed frames and elapsed time without inventing a percentage.

Cancellation is cooperative:

- The UI sets a task-specific cancellation event.
- The frame loop checks it before reading and after processing every frame.
- Long ffmpeg processes are terminated when cancellation is requested.
- Partial outputs and task intermediates are removed.

Every task receives a unique identifier and isolated workspace. User uploads are treated as read-only. Final output names include the source stem and a unique suffix, so existing files are never overwritten.

## 12. Error Handling

The UI reports concise errors with a recommended action for:

- Unsupported extension or undecodable input.
- Empty or zero-frame video.
- Invalid or missing frame rate.
- Model download, cache, or loading failure.
- CUDA out-of-memory.
- Unsupported MPS operation.
- ffmpeg discovery or encoding failure.
- Audio remux failure.
- Insufficient disk space or filesystem permission failure.
- User cancellation.

Detailed exception information remains available in the local terminal for diagnosis. No uploaded video or frame is sent to an external service.

## 13. Testing Strategy

Unit tests cover:

- Device-priority selection using mocked PyTorch capability checks.
- Model-name mapping.
- Resolution calculation for landscape, portrait, odd, tiny, and upscale cases.
- Percentile normalization for constant frames, outliers, and normal ranges.
- Temporal smoothing boundary values and state reset.
- Black/white inversion.
- ffmpeg discovery and command construction.
- Cancellation and cleanup behavior.

An end-to-end smoke test creates a very short synthetic input video, substitutes a deterministic lightweight fake depth model, runs the conversion pipeline, and verifies:

- A non-empty MP4 is produced.
- Output dimensions and approximate duration are correct.
- Frames are grayscale.
- Temporary intermediates are removed.

Real model inference remains a documented manual verification because downloading large weights is unsuitable for routine unit tests.

## 14. Deliverables

- `app.py` — complete runnable application and CLI entry point.
- `requirements.txt` — cross-platform Python dependencies.
- `README.md` — features, limitations, model storage, Windows setup, macOS setup, ffmpeg guidance, launch commands, and troubleshooting.
- `tests/test_app.py` — deterministic unit and smoke tests.
- `.gitignore` — virtual environments, caches, generated videos, and visual-companion artifacts.

## 15. Acceptance Criteria

The implementation is complete when:

1. A user can install dependencies with documented commands on Windows or macOS.
2. `python app.py` opens a localhost Gradio interface.
3. MP4 and MOV files can be uploaded.
4. Small, Base, and Large Depth Anything V2 choices resolve to the documented models.
5. CUDA is selected on a supported NVIDIA Windows system, MPS on a supported Apple Silicon Mac, and CPU otherwise.
6. Each decoded frame is converted to an 8-bit grayscale relative-depth visualization.
7. Resolution, inversion, smoothing, and audio controls affect the output as documented.
8. The result is an H.264, `yuv420p` MP4 playable in Gradio and common desktop players.
9. Progress, cancellation, actionable failures, and cleanup work without corrupting the input.
10. Automated tests pass without downloading actual model weights.

