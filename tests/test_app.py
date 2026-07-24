from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import app


class FakeCuda:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def get_device_name(self, index: int) -> str:
        assert index == 0
        return "Test GPU"


class FakeMPS:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


def fake_torch(cuda: bool, mps: bool) -> SimpleNamespace:
    return SimpleNamespace(
        cuda=FakeCuda(cuda),
        backends=SimpleNamespace(mps=FakeMPS(mps)),
    )


def test_device_priority_and_force_cpu() -> None:
    assert app.select_device(torch_module=fake_torch(True, True)).name == "cuda"
    assert app.select_device(torch_module=fake_torch(False, True)).name == "mps"
    assert app.select_device(torch_module=fake_torch(False, False)).name == "cpu"
    assert app.select_device(force_cpu=True, torch_module=object()).name == "cpu"


def test_model_mapping() -> None:
    assert app.normalize_model_size("Small") == "small"
    assert "Depth-Anything-V2-Base-hf" in app.MODEL_IDS["base"]
    with pytest.raises(app.ConversionError):
        app.normalize_model_size("giant")


@pytest.mark.parametrize(
    ("width", "height", "preset", "expected"),
    [
        (1920, 1080, "720p", (1280, 720)),
        (1080, 1920, "480p", (480, 854)),
        (641, 479, "original", (642, 480)),
        (1, 1, "original", (2, 2)),
        (320, 240, "1080p", (1440, 1080)),
    ],
)
def test_calculate_target_size(
    width: int, height: int, preset: str, expected: tuple[int, int]
) -> None:
    assert app.calculate_target_size(width, height, preset) == expected


def test_normalization_constant_and_inversion() -> None:
    smoother = app.TemporalDepthSmoother(0.0)
    constant = np.full((4, 5), 7.0, dtype=np.float32)
    assert np.all(smoother.process(constant) == 0)
    assert np.all(smoother.process(constant, invert=True) == 255)


def test_normalization_robust_to_outlier() -> None:
    depth = np.linspace(0.0, 1.0, 100, dtype=np.float32).reshape(10, 10)
    depth[-1, -1] = 10000.0
    output = app.TemporalDepthSmoother(0.0).process(depth)
    assert output.dtype == np.uint8
    assert output.shape == depth.shape
    assert 100 < int(output[5, 0]) < 200
    assert output[-1, -1] == 255


def test_temporal_smoothing_and_reset() -> None:
    first = np.tile(np.arange(10, dtype=np.float32), (10, 1))
    second = np.fliplr(first)
    smoother = app.TemporalDepthSmoother(0.8)
    output_a = smoother.process(first)
    output_b = smoother.process(second)
    immediate_b = app.TemporalDepthSmoother(0.0).process(second)
    assert not np.array_equal(output_b, immediate_b)
    smoother.reset()
    reset_b = smoother.process(second)
    assert np.array_equal(reset_b, immediate_b)
    assert not np.array_equal(output_a, output_b)


def test_invalid_smoothing() -> None:
    with pytest.raises(app.ConversionError):
        app.TemporalDepthSmoother(1.0)
    with pytest.raises(app.ConversionError):
        app.TemporalDepthSmoother(-0.1)


def test_encode_and_mux_commands(tmp_path: Path) -> None:
    encoded = tmp_path / "silent.mp4"
    final = tmp_path / "final.mp4"
    source = tmp_path / "source.mov"
    command = app.build_encode_command("ffmpeg", 640, 480, 29.97, encoded)
    assert ["-s", "640x480"] == command[command.index("-s") : command.index("-s") + 2]
    assert "libx264" in command
    assert "yuv420p" in command
    assert command[-1] == str(encoded)

    mux = app.build_audio_mux_command(
        "ffmpeg", encoded, source, final, "copy"
    )
    assert mux[mux.index("-c:a") + 1] == "copy"
    assert "1:a:0" in mux


def test_active_task_registry() -> None:
    registry = app.ActiveTaskRegistry()
    first = registry.start("session")
    second = registry.start("session")
    assert first.is_set()
    assert not second.is_set()
    assert registry.cancel("session")
    assert second.is_set()
    registry.finish("session", second)
    assert not registry.cancel("session")


def test_gradio_interface_builds_with_injected_request() -> None:
    pytest.importorskip("gradio")
    from gradio.helpers import special_args

    demo = app.build_interface(force_cpu=True)
    request_callbacks = [
        dependency.fn
        for dependency in demo.fns.values()
        if dependency.fn
        and dependency.fn.__name__ in {"convert_from_ui", "cancel_from_ui"}
    ]
    assert len(request_callbacks) == 2
    for callback in request_callbacks:
        parameters = list(__import__("inspect").signature(callback).parameters)
        input_count = 6 if callback.__name__ == "convert_from_ui" else 0
        inputs = [None] * input_count
        injected, _, _, _ = special_args(callback, inputs=inputs)
        assert len(injected) == len(parameters)


def test_pre_cancelled_conversion_does_not_create_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"placeholder")
    metadata = app.VideoMetadata(source, 64, 48, 24.0, 1, 1 / 24)
    monkeypatch.setattr(app, "probe_video", lambda path: metadata)
    monkeypatch.setattr(app, "_optional_import_cv2", lambda: object())
    monkeypatch.setattr(
        app, "select_device", lambda force_cpu=False: app.DeviceChoice("cpu", "CPU")
    )
    event = threading.Event()
    event.set()
    with pytest.raises(app.ConversionCancelled):
        app.convert_video(
            source,
            app.ConversionSettings(),
            tmp_path / "out",
            cancel_event=event,
            depth_provider=lambda frame, size: np.zeros((48, 64)),
            ffmpeg_path="ffmpeg",
        )
    assert not (tmp_path / "out").exists()


def _smoke_dependencies_available() -> bool:
    try:
        import cv2  # noqa: F401

        app.find_ffmpeg()
        return True
    except (ImportError, app.ConversionError):
        return False


@pytest.mark.skipif(
    not _smoke_dependencies_available(),
    reason="OpenCV or ffmpeg is unavailable",
)
def test_end_to_end_with_fake_depth_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cv2

    source = tmp_path / "synthetic.mp4"
    writer = cv2.VideoWriter(
        str(source),
        cv2.VideoWriter_fourcc(*"mp4v"),
        12.0,
        (64, 48),
    )
    if not writer.isOpened():
        pytest.skip("OpenCV cannot create an MP4 on this machine")
    for frame_index in range(8):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[:, :, 0] = frame_index * 20
        frame[:, :, 1] = np.arange(64, dtype=np.uint8)[None, :]
        frame[:, :, 2] = np.arange(48, dtype=np.uint8)[:, None]
        writer.write(frame)
    writer.release()

    monkeypatch.setattr(
        app, "select_device", lambda force_cpu=False: app.DeviceChoice("cpu", "CPU")
    )

    def fake_depth(
        rgb_frame: np.ndarray, target_size: tuple[int, int]
    ) -> np.ndarray:
        width, height = target_size
        horizontal = np.linspace(0.0, 1.0, width, dtype=np.float32)
        vertical = np.linspace(0.0, 0.25, height, dtype=np.float32)[:, None]
        return horizontal[None, :] + vertical + rgb_frame.mean() / 2550.0

    output_dir = tmp_path / "outputs"
    result = app.convert_video(
        source,
        app.ConversionSettings(
            resolution="original",
            smoothing=0.5,
            preserve_audio=False,
        ),
        output_dir,
        depth_provider=fake_depth,
    )

    assert result.frames_processed == 8
    assert result.output_path.is_file()
    assert result.output_path.stat().st_size > 0
    assert list(output_dir.glob("*.mp4")) == [result.output_path]

    capture = cv2.VideoCapture(str(result.output_path))
    assert capture.isOpened()
    assert int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == 64
    assert int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 48
    ok, frame = capture.read()
    capture.release()
    assert ok
    channel_delta = np.max(
        np.abs(frame[:, :, 0].astype(int) - frame[:, :, 1].astype(int))
    )
    assert channel_delta <= 4


@pytest.mark.skipif(
    not _smoke_dependencies_available(),
    reason="OpenCV or ffmpeg is unavailable",
)
def test_end_to_end_preserves_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ffmpeg = app.find_ffmpeg()
    source = tmp_path / "with_audio.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x48:rate=10:duration=0.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )

    monkeypatch.setattr(
        app, "select_device", lambda force_cpu=False: app.DeviceChoice("cpu", "CPU")
    )

    def fake_depth(
        rgb_frame: np.ndarray, target_size: tuple[int, int]
    ) -> np.ndarray:
        width, height = target_size
        return np.tile(
            np.linspace(0.0, 1.0, width, dtype=np.float32),
            (height, 1),
        )

    result = app.convert_video(
        source,
        app.ConversionSettings(
            resolution="original",
            smoothing=0.0,
            preserve_audio=True,
        ),
        tmp_path / "outputs",
        depth_provider=fake_depth,
        ffmpeg_path=ffmpeg,
    )

    assert result.output_path.is_file()
    assert result.audio_message == "已保留原始音频。"
    assert app._source_has_audio(ffmpeg, result.output_path, threading.Event())
