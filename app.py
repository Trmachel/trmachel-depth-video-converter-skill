"""Local cross-platform RGB video to Depth Anything V2 video converter."""

from __future__ import annotations

import argparse
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np


LOGGER = logging.getLogger("depth_video_converter")

MODEL_IDS = {
    "small": "depth-anything/Depth-Anything-V2-Small-hf",
    "base": "depth-anything/Depth-Anything-V2-Base-hf",
    "large": "depth-anything/Depth-Anything-V2-Large-hf",
}

RESOLUTION_PRESETS = {
    "original": None,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
}

SUPPORTED_EXTENSIONS = {".mp4", ".mov"}
DEFAULT_SMOOTHING = 0.65


class ConversionError(RuntimeError):
    """A conversion failure that can be presented directly to the user."""


class ConversionCancelled(ConversionError):
    """Raised when a user cancels an active conversion."""


class ProgressCallback(Protocol):
    def __call__(self, fraction: float | None, description: str) -> None: ...


class DepthProvider(Protocol):
    def __call__(
        self, rgb_frame: np.ndarray, target_size: tuple[int, int]
    ) -> np.ndarray: ...


@dataclass(frozen=True)
class DeviceChoice:
    name: str
    label: str


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float | None


@dataclass(frozen=True)
class ConversionSettings:
    model_size: str = "small"
    resolution: str = "original"
    smoothing: float = DEFAULT_SMOOTHING
    invert: bool = False
    preserve_audio: bool = True
    force_cpu: bool = False


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    frames_processed: int
    width: int
    height: int
    fps: float
    device: str
    audio_message: str


def _optional_import_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise ConversionError(
            "缺少 OpenCV。请先运行 pip install -r requirements.txt。"
        ) from exc
    return cv2


def _optional_import_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise ConversionError(
            "缺少 PyTorch。请先按 README 安装 PyTorch，再安装其余依赖。"
        ) from exc
    return torch


def select_device(force_cpu: bool = False, torch_module: Any | None = None) -> DeviceChoice:
    """Choose CUDA, then Apple MPS, then CPU."""
    if force_cpu:
        return DeviceChoice("cpu", "CPU（手动指定）")

    torch_module = torch_module or _optional_import_torch()

    try:
        if torch_module.cuda.is_available():
            device_name = torch_module.cuda.get_device_name(0)
            return DeviceChoice("cuda", f"NVIDIA CUDA · {device_name}")
    except (AttributeError, RuntimeError):
        LOGGER.debug("CUDA capability check failed", exc_info=True)

    try:
        mps_backend = getattr(getattr(torch_module, "backends", None), "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return DeviceChoice("mps", "Apple Silicon · MPS")
    except (AttributeError, RuntimeError):
        LOGGER.debug("MPS capability check failed", exc_info=True)

    return DeviceChoice("cpu", "CPU")


def normalize_model_size(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in MODEL_IDS:
        choices = ", ".join(name.title() for name in MODEL_IDS)
        raise ConversionError(f"未知模型尺寸：{value}。可选值：{choices}。")
    return normalized


def normalize_resolution(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in RESOLUTION_PRESETS:
        choices = ", ".join(RESOLUTION_PRESETS)
        raise ConversionError(f"未知输出分辨率：{value}。可选值：{choices}。")
    return normalized


def _positive_even(value: float) -> int:
    rounded = max(2, int(round(value)))
    return rounded if rounded % 2 == 0 else rounded + 1


def calculate_target_size(width: int, height: int, preset: str) -> tuple[int, int]:
    """Return H.264-safe (width, height) while preserving aspect ratio."""
    if width <= 0 or height <= 0:
        raise ConversionError("源视频尺寸无效。")

    preset = normalize_resolution(preset)
    limit = RESOLUTION_PRESETS[preset]

    if limit is None:
        return _positive_even(width), _positive_even(height)

    if width >= height:
        target_height = float(limit)
        target_width = target_height * width / height
    else:
        target_width = float(limit)
        target_height = target_width * height / width

    return _positive_even(target_width), _positive_even(target_height)


class TemporalDepthSmoother:
    """Robustly normalize relative depth and reduce frame-to-frame flicker."""

    def __init__(self, smoothing: float = DEFAULT_SMOOTHING) -> None:
        if not 0.0 <= smoothing <= 0.95:
            raise ConversionError("时间平滑必须位于 0.0 到 0.95 之间。")
        self.smoothing = float(smoothing)
        self._low: float | None = None
        self._high: float | None = None
        self._frame: np.ndarray | None = None

    def reset(self) -> None:
        self._low = None
        self._high = None
        self._frame = None

    def process(self, depth: np.ndarray, invert: bool = False) -> np.ndarray:
        depth = np.asarray(depth, dtype=np.float32)
        if depth.ndim != 2 or depth.size == 0:
            raise ConversionError("模型返回了无效的深度图。")

        finite = depth[np.isfinite(depth)]
        if finite.size == 0:
            raise ConversionError("模型返回的深度图不包含有效数值。")

        current_low, current_high = np.percentile(finite, (2.0, 98.0)).tolist()
        current_low = float(current_low)
        current_high = float(current_high)

        if self._low is None or self.smoothing == 0.0:
            self._low = current_low
            self._high = current_high
        else:
            keep = self.smoothing
            self._low = keep * self._low + (1.0 - keep) * current_low
            self._high = keep * self._high + (1.0 - keep) * current_high

        value_range = float(self._high - self._low)
        if not math.isfinite(value_range) or value_range <= 1e-8:
            normalized = np.zeros_like(depth, dtype=np.float32)
        else:
            safe_depth = np.nan_to_num(
                depth, nan=self._low, posinf=self._high, neginf=self._low
            )
            normalized = np.clip(
                (safe_depth - self._low) / value_range, 0.0, 1.0
            ).astype(np.float32, copy=False)

        if (
            self._frame is not None
            and self._frame.shape == normalized.shape
            and self.smoothing > 0.0
        ):
            keep = self.smoothing
            normalized = keep * self._frame + (1.0 - keep) * normalized

        self._frame = normalized.copy()
        grayscale = np.rint(normalized * 255.0).astype(np.uint8)
        return 255 - grayscale if invert else grayscale


def probe_video(path: str | os.PathLike[str]) -> VideoMetadata:
    cv2 = _optional_import_cv2()
    input_path = Path(path).expanduser().resolve()

    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ConversionError("仅支持 MP4 和 MOV 视频。")
    if not input_path.is_file():
        raise ConversionError("找不到上传的视频文件。")

    capture = cv2.VideoCapture(str(input_path))
    try:
        if not capture.isOpened():
            raise ConversionError("无法打开视频；文件可能损坏或编码不受支持。")

        width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = max(0, int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))))

        if width <= 0 or height <= 0:
            raise ConversionError("无法读取视频分辨率。")
        if not math.isfinite(fps) or fps <= 0.0:
            raise ConversionError("无法读取有效帧率；暂不支持该视频。")

        duration = frame_count / fps if frame_count > 0 else None
        return VideoMetadata(
            path=input_path,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration_seconds=duration,
        )
    finally:
        capture.release()


def format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "未知"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ModelManager:
    """Lazily load and cache Depth Anything V2 models."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[Any, Any]] = {}
        self._lock = threading.Lock()

    def get(self, model_size: str, device: DeviceChoice) -> tuple[Any, Any]:
        model_size = normalize_model_size(model_size)
        key = (model_size, device.name)

        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            try:
                from transformers import AutoImageProcessor, AutoModelForDepthEstimation

                model_id = MODEL_IDS[model_size]
                processor = AutoImageProcessor.from_pretrained(model_id)
                model = AutoModelForDepthEstimation.from_pretrained(model_id)
                model.to(device.name)
                model.eval()
            except Exception as exc:
                raise _friendly_model_error(exc, model_size, device) from exc

            self._cache[key] = (processor, model)
            return processor, model

    def predictor(self, model_size: str, device: DeviceChoice) -> DepthProvider:
        processor, model = self.get(model_size, device)
        torch = _optional_import_torch()

        def predict(
            rgb_frame: np.ndarray, target_size: tuple[int, int]
        ) -> np.ndarray:
            target_width, target_height = target_size
            try:
                inputs = processor(images=rgb_frame, return_tensors="pt")
                inputs = {name: value.to(device.name) for name, value in inputs.items()}
                with torch.inference_mode():
                    outputs = model(**inputs)
                    depth = torch.nn.functional.interpolate(
                        outputs.predicted_depth.unsqueeze(1),
                        size=(target_height, target_width),
                        mode="bicubic",
                        align_corners=False,
                    ).squeeze(0).squeeze(0)
                return depth.float().cpu().numpy()
            except Exception as exc:
                raise _friendly_inference_error(exc, model_size, device) from exc

        return predict


def _friendly_model_error(
    exc: Exception, model_size: str, device: DeviceChoice
) -> ConversionError:
    text = str(exc).lower()
    if "torchvision" in text or "requires the" in text and "library" in text:
        return ConversionError(
            "模型图像处理依赖不完整。请重新运行 "
            "pip install -r requirements.txt 后再试。"
        )
    if "out of memory" in text:
        return ConversionError(
            f"{device.label} 显存不足。请改用 Small 模型、降低分辨率或使用 --force-cpu。"
        )
    return ConversionError(
        f"无法加载 Depth Anything V2 {model_size.title()} 模型。"
        "请检查网络、磁盘空间和 Hugging Face 缓存权限。"
    )


def _friendly_inference_error(
    exc: Exception, model_size: str, device: DeviceChoice
) -> ConversionError:
    text = str(exc).lower()
    if "out of memory" in text:
        return ConversionError(
            f"{device.label} 显存不足。请改用 Small 模型或降低输出分辨率。"
        )
    if device.name == "mps" and (
        "not implemented" in text or "not supported" in text or "mps" in text
    ):
        return ConversionError(
            "Apple MPS 无法执行当前算子。请使用 --force-cpu 重新启动后再试。"
        )
    return ConversionError(
        f"Depth Anything V2 {model_size.title()} 推理失败：{exc}"
    )


def find_ffmpeg() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        bundled = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if bundled.is_file():
            return str(bundled)
    except Exception:
        LOGGER.debug("imageio-ffmpeg discovery failed", exc_info=True)

    raise ConversionError(
        "找不到 ffmpeg。请安装 requirements.txt 中的 imageio-ffmpeg，"
        "或按 README 安装系统 ffmpeg。"
    )


def build_encode_command(
    ffmpeg: str,
    width: int,
    height: int,
    fps: float,
    output_path: Path,
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.8f}",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def build_audio_mux_command(
    ffmpeg: str,
    silent_video: Path,
    source_video: Path,
    output_path: Path,
    audio_codec: str,
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(silent_video),
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        audio_codec,
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _read_process_error(error_file: Any) -> str:
    try:
        error_file.flush()
        error_file.seek(0)
        raw = error_file.read()
        return raw.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _run_command(
    command: list[str],
    cancel_event: threading.Event,
    error_label: str,
) -> tuple[bool, str]:
    with tempfile.TemporaryFile(mode="w+b") as error_file:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=error_file,
            )
        except OSError as exc:
            raise ConversionError(f"{error_label}无法启动：{exc}") from exc

        while process.poll() is None:
            if cancel_event.wait(0.1):
                _terminate_process(process)
                raise ConversionCancelled("转换已取消。")

        error_text = _read_process_error(error_file)
        return process.returncode == 0, error_text


def _source_has_audio(
    ffmpeg: str, source_video: Path, cancel_event: threading.Event
) -> bool:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_video),
        "-map",
        "0:a:0",
        "-t",
        "0.1",
        "-f",
        "null",
        "-",
    ]
    success, _ = _run_command(command, cancel_event, "音频探测")
    return success


def _mux_audio(
    ffmpeg: str,
    silent_video: Path,
    source_video: Path,
    final_output: Path,
    cancel_event: threading.Event,
) -> str:
    try:
        if not _source_has_audio(ffmpeg, source_video, cancel_event):
            shutil.copy2(silent_video, final_output)
            return "源视频没有音轨，已导出静音深度视频。"

        copy_command = build_audio_mux_command(
            ffmpeg, silent_video, source_video, final_output, "copy"
        )
        success, copy_error = _run_command(copy_command, cancel_event, "音频复用")
        if success:
            return "已保留原始音频。"

        aac_command = build_audio_mux_command(
            ffmpeg, silent_video, source_video, final_output, "aac"
        )
        success, aac_error = _run_command(
            aac_command, cancel_event, "音频兼容编码"
        )
        if success:
            return "原音频与 MP4 不兼容，已自动转换为 AAC。"

        shutil.copy2(silent_video, final_output)
        LOGGER.warning("Audio mux failed. copy=%s aac=%s", copy_error, aac_error)
        return "音频保留失败，已提供静音深度视频。"
    except BaseException:
        final_output.unlink(missing_ok=True)
        raise


def _safe_output_stem(source: Path) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._")
    return cleaned[:80] or "video"


def _progress(
    callback: ProgressCallback | None,
    fraction: float | None,
    description: str,
) -> None:
    if callback is not None:
        callback(fraction, description)


def convert_video(
    input_path: str | os.PathLike[str],
    settings: ConversionSettings,
    output_dir: str | os.PathLike[str],
    *,
    progress_callback: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    model_manager: ModelManager | None = None,
    depth_provider: DepthProvider | None = None,
    ffmpeg_path: str | None = None,
) -> ConversionResult:
    """Convert an RGB video into an H.264 grayscale relative-depth video."""
    cv2 = _optional_import_cv2()
    cancel_event = cancel_event or threading.Event()
    model_size = normalize_model_size(settings.model_size)
    resolution = normalize_resolution(settings.resolution)
    smoother = TemporalDepthSmoother(settings.smoothing)

    _progress(progress_callback, 0.0, "正在读取视频信息…")
    metadata = probe_video(input_path)
    target_width, target_height = calculate_target_size(
        metadata.width, metadata.height, resolution
    )
    device = select_device(settings.force_cpu)
    ffmpeg = ffmpeg_path or find_ffmpeg()

    if cancel_event.is_set():
        raise ConversionCancelled("转换已取消。")

    if depth_provider is None:
        _progress(progress_callback, 0.02, f"正在加载 {model_size.title()} 模型…")
        manager = model_manager or GLOBAL_MODEL_MANAGER
        depth_provider = manager.predictor(model_size, device)

    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    task_id = uuid.uuid4().hex[:10]
    output_name = f"{_safe_output_stem(metadata.path)}_depth_{task_id}.mp4"
    final_output = output_root / output_name
    staged_output = output_root / f".{output_name}.partial.mp4"

    capture = cv2.VideoCapture(str(metadata.path))
    if not capture.isOpened():
        raise ConversionError("视频探测成功，但在转换阶段无法再次打开。")

    frames_processed = 0
    started_at = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="depth-video-") as task_dir_text:
        task_dir = Path(task_dir_text)
        silent_video = task_dir / "depth_silent.mp4"
        command = build_encode_command(
            ffmpeg, target_width, target_height, metadata.fps, silent_video
        )

        with tempfile.TemporaryFile(mode="w+b") as error_file:
            try:
                encoder = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=error_file,
                )
            except OSError as exc:
                capture.release()
                raise ConversionError(f"无法启动 ffmpeg 编码器：{exc}") from exc

            try:
                if encoder.stdin is None:
                    raise ConversionError("ffmpeg 编码管道创建失败。")

                while True:
                    if cancel_event.is_set():
                        raise ConversionCancelled("转换已取消。")

                    ok, bgr_frame = capture.read()
                    if not ok:
                        break

                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    depth = depth_provider(
                        rgb_frame, (target_width, target_height)
                    )
                    grayscale = smoother.process(depth, invert=settings.invert)
                    if grayscale.shape != (target_height, target_width):
                        grayscale = cv2.resize(
                            grayscale,
                            (target_width, target_height),
                            interpolation=cv2.INTER_LINEAR,
                        )
                    output_frame = cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)

                    try:
                        encoder.stdin.write(output_frame.tobytes())
                    except (BrokenPipeError, OSError) as exc:
                        error_text = _read_process_error(error_file)
                        raise ConversionError(
                            f"ffmpeg 在写入第 {frames_processed + 1} 帧时失败："
                            f"{error_text or exc}"
                        ) from exc

                    frames_processed += 1
                    elapsed = max(1e-6, time.monotonic() - started_at)
                    speed = frames_processed / elapsed
                    if metadata.frame_count > 0:
                        fraction = min(0.92, 0.03 + 0.89 * frames_processed / metadata.frame_count)
                        remaining_frames = max(
                            0, metadata.frame_count - frames_processed
                        )
                        eta = remaining_frames / speed if speed > 0 else 0
                        description = (
                            f"深度推理 {frames_processed}/{metadata.frame_count} 帧 · "
                            f"{speed:.1f} FPS · 剩余约 {format_duration(eta)}"
                        )
                    else:
                        fraction = None
                        description = (
                            f"深度推理 {frames_processed} 帧 · {speed:.1f} FPS"
                        )
                    _progress(progress_callback, fraction, description)

                if frames_processed == 0:
                    raise ConversionError("视频中没有可解码的画面帧。")

                encoder.stdin.close()
                return_code = encoder.wait()
                if return_code != 0:
                    error_text = _read_process_error(error_file)
                    raise ConversionError(
                        f"ffmpeg H.264 编码失败：{error_text or '未知错误'}"
                    )
            except BaseException:
                if encoder.stdin is not None and not encoder.stdin.closed:
                    try:
                        encoder.stdin.close()
                    except OSError:
                        pass
                _terminate_process(encoder)
                raise
            finally:
                capture.release()

        if not silent_video.is_file() or silent_video.stat().st_size == 0:
            raise ConversionError("ffmpeg 未生成有效的视频文件。")

        _progress(progress_callback, 0.94, "正在整理 MP4 与音频…")
        try:
            if settings.preserve_audio:
                audio_message = _mux_audio(
                    ffmpeg,
                    silent_video,
                    metadata.path,
                    staged_output,
                    cancel_event,
                )
            else:
                shutil.copy2(silent_video, staged_output)
                audio_message = "未保留原始音频。"
        except BaseException:
            staged_output.unlink(missing_ok=True)
            raise

    if cancel_event.is_set():
        staged_output.unlink(missing_ok=True)
        raise ConversionCancelled("转换已取消。")

    if not staged_output.is_file() or staged_output.stat().st_size == 0:
        staged_output.unlink(missing_ok=True)
        raise ConversionError("最终 MP4 文件生成失败。")
    os.replace(staged_output, final_output)

    _progress(progress_callback, 1.0, "转换完成。")
    return ConversionResult(
        output_path=final_output,
        frames_processed=frames_processed,
        width=target_width,
        height=target_height,
        fps=metadata.fps,
        device=device.label,
        audio_message=audio_message,
    )


class ActiveTaskRegistry:
    """Track one cooperative cancellation event per Gradio browser session."""

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self, session_id: str) -> threading.Event:
        event = threading.Event()
        with self._lock:
            previous = self._events.get(session_id)
            if previous is not None:
                previous.set()
            self._events[session_id] = event
        return event

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            event = self._events.get(session_id)
        if event is None:
            return False
        event.set()
        return True

    def finish(self, session_id: str, event: threading.Event) -> None:
        with self._lock:
            if self._events.get(session_id) is event:
                self._events.pop(session_id, None)


GLOBAL_MODEL_MANAGER = ModelManager()
ACTIVE_TASKS = ActiveTaskRegistry()


def metadata_markdown(video_path: str | None) -> str:
    if not video_path:
        return "上传 MP4 或 MOV 后将在此显示视频信息。"
    try:
        metadata = probe_video(video_path)
    except ConversionError as exc:
        return f"⚠️ {exc}"
    frames = f"{metadata.frame_count:,}" if metadata.frame_count > 0 else "未知"
    return (
        f"**{metadata.width}×{metadata.height}** · "
        f"**{metadata.fps:.3f} FPS** · "
        f"**{format_duration(metadata.duration_seconds)}** · "
        f"{frames} 帧"
    )


def cleanup_stale_outputs(output_dir: Path, max_age_days: int = 7) -> None:
    if not output_dir.is_dir():
        return
    cutoff = time.time() - max_age_days * 86400
    candidates = list(output_dir.glob("*_depth_*.mp4"))
    candidates.extend(output_dir.glob(".*_depth_*.partial.mp4"))
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:
            LOGGER.debug("Could not remove stale output %s", candidate, exc_info=True)


def build_interface(force_cpu: bool = False, output_dir: Path | None = None) -> Any:
    try:
        import gradio as gr
    except ImportError as exc:
        raise ConversionError(
            "缺少 Gradio。请先运行 pip install -r requirements.txt。"
        ) from exc

    output_dir = output_dir or Path(tempfile.gettempdir()) / "depth-video-converter"
    output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_stale_outputs(output_dir)
    device = select_device(force_cpu)

    with gr.Blocks(title="Depth Video Converter") as demo:
        gr.Markdown(
            """
            <div class="hero">
              <h1>Depth Video Converter</h1>
              <p>使用 Depth Anything V2，在本机把 MP4 / MOV 转换为灰度深度视频</p>
            </div>
            """
        )
        gr.Markdown(
            f"<div class='device-badge'>当前推理设备：<b>{device.label}</b></div>"
        )

        with gr.Row(equal_height=True):
            with gr.Column(scale=1):
                source_video = gr.Video(
                    label="输入视频",
                    sources=["upload"],
                    format=None,
                    include_audio=True,
                )
                source_metadata = gr.Markdown(
                    "上传 MP4 或 MOV 后将在此显示视频信息。"
                )
            with gr.Column(scale=1):
                output_video = gr.Video(
                    label="深度视频输出",
                    format="mp4",
                    interactive=False,
                    buttons=["download"],
                )

        with gr.Group():
            gr.Markdown("### 转换设置")
            with gr.Row():
                model_size = gr.Dropdown(
                    choices=["Small", "Base", "Large"],
                    value="Small",
                    label="模型尺寸",
                )
                resolution = gr.Dropdown(
                    choices=["Original", "480p", "720p", "1080p"],
                    value="Original",
                    label="输出分辨率",
                )
                smoothing = gr.Slider(
                    minimum=0.0,
                    maximum=0.95,
                    value=DEFAULT_SMOOTHING,
                    step=0.05,
                    label="时间平滑",
                    info="越高越稳定，但快速运动可能出现轻微拖影",
                )
            with gr.Row():
                invert = gr.Checkbox(value=False, label="黑白反转")
                preserve_audio = gr.Checkbox(value=True, label="保留原始音频")

        with gr.Row():
            start_button = gr.Button(
                "开始转换", variant="primary"
            )
            cancel_button = gr.Button("取消", variant="stop")

        status = gr.Markdown("就绪。上传视频并选择参数后开始转换。")

        source_video.upload(
            fn=metadata_markdown,
            inputs=source_video,
            outputs=source_metadata,
            queue=False,
        )
        source_video.clear(
            fn=lambda: "上传 MP4 或 MOV 后将在此显示视频信息。",
            outputs=source_metadata,
            queue=False,
        )

        def convert_from_ui(
            video_path: str | None,
            selected_model: str,
            selected_resolution: str,
            selected_smoothing: float,
            selected_invert: bool,
            selected_audio: bool,
            progress: Any = gr.Progress(),
            request: Any = None,
        ) -> tuple[str | None, str]:
            if not video_path:
                return None, "⚠️ 请先上传 MP4 或 MOV 视频。"

            session_id = getattr(request, "session_hash", None) or "local"
            cancel_event = ACTIVE_TASKS.start(session_id)

            def report(fraction: float | None, description: str) -> None:
                if fraction is None:
                    progress(0, desc=description)
                else:
                    progress(float(fraction), desc=description)

            settings = ConversionSettings(
                model_size=selected_model,
                resolution=selected_resolution,
                smoothing=float(selected_smoothing),
                invert=bool(selected_invert),
                preserve_audio=bool(selected_audio),
                force_cpu=force_cpu,
            )

            try:
                result = convert_video(
                    video_path,
                    settings,
                    output_dir,
                    progress_callback=report,
                    cancel_event=cancel_event,
                )
                summary = (
                    f"✅ **转换完成** · {result.frames_processed:,} 帧 · "
                    f"{result.width}×{result.height} · {result.fps:.3f} FPS  \n"
                    f"设备：{result.device}  \n"
                    f"{result.audio_message}"
                )
                return str(result.output_path), summary
            except ConversionCancelled:
                return None, "⏹️ 转换已取消，临时文件已清理。"
            except ConversionError as exc:
                LOGGER.exception("Conversion failed")
                return None, f"⚠️ **转换失败**：{exc}"
            except Exception as exc:
                LOGGER.exception("Unexpected conversion failure")
                return None, f"⚠️ **发生未预期错误**：{exc}"
            finally:
                ACTIVE_TASKS.finish(session_id, cancel_event)

        def cancel_from_ui(request: Any = None) -> str:
            session_id = getattr(request, "session_hash", None) or "local"
            if ACTIVE_TASKS.cancel(session_id):
                return "正在安全取消，请稍候…"
            return "当前没有正在运行的转换任务。"

        # Gradio recognizes Request by its runtime annotation. Assign it here
        # because Gradio is intentionally imported lazily inside this function.
        convert_from_ui.__annotations__["request"] = gr.Request
        cancel_from_ui.__annotations__["request"] = gr.Request

        start_button.click(
            fn=convert_from_ui,
            inputs=[
                source_video,
                model_size,
                resolution,
                smoothing,
                invert,
                preserve_audio,
            ],
            outputs=[output_video, status],
        )
        cancel_button.click(
            fn=cancel_from_ui,
            outputs=status,
            queue=False,
        )

    return demo


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local Depth Anything V2 video converter."
    )
    parser.add_argument(
        "--force-cpu",
        action="store_true",
        help="Disable CUDA/MPS and run inference on CPU.",
    )
    parser.add_argument(
        "--server-name",
        default="127.0.0.1",
        help="Gradio bind address (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Gradio server port (default: 7860).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "depth-video-converter",
        help="Directory for completed MP4 files.",
    )
    parser.add_argument(
        "--inbrowser",
        action="store_true",
        help="Open the local interface in the default browser.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed local logs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    demo = build_interface(force_cpu=args.force_cpu, output_dir=args.output_dir)
    demo.queue(default_concurrency_limit=1).launch(
        server_name=args.server_name,
        server_port=args.port,
        share=False,
        inbrowser=args.inbrowser,
        show_error=True,
    )


if __name__ == "__main__":
    main()
