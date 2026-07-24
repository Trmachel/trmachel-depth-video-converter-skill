# Python 深度视频转换器

这是一个从零构建的本地 Python 应用：上传普通 MP4 或 MOV 视频，使用 Depth Anything V2 逐帧估算相对深度，并导出兼容性良好的灰度 H.264 MP4。

应用不会把视频上传到云端。首次使用某个模型尺寸时，会从 Hugging Face 下载模型并存入本机缓存；之后可离线使用该模型。

## 功能

- Gradio 本地 Web 界面，支持 MP4/MOV 上传、预览和下载
- Depth Anything V2 Small、Base、Large 三种模型
- Windows 自动优先使用 NVIDIA CUDA
- Apple Silicon Mac 自动优先使用 MPS
- 没有可用 GPU 时自动回退 CPU
- 原始、480p、720p、1080p 输出分辨率
- 2%–98% 稳健归一化与 EMA 时间平滑，减少闪烁
- 可选黑白反转
- 可选保留原视频音频
- H.264、`yuv420p`、fast-start MP4 输出
- 逐帧进度、速度、预计剩余时间和安全取消
- 不把整段视频载入内存

> 输出是单目模型估算的**相对深度**，不是以米为单位的真实测距数据。

## 系统要求

- Windows 10/11 64 位，或 macOS 12.3 及以上
- Python 3.10–3.14（推荐 Python 3.11 或 3.12）
- 至少 8 GB 内存；Large 模型建议更多内存/显存
- 首次下载模型需要联网
- 磁盘需要容纳模型缓存、输入视频和转换中的临时视频

模型越大通常细节越好，但速度更慢：

| 模型 | 推荐用途 | 大致要求 |
|---|---|---|
| Small | 默认、CPU、普通笔记本 | 最快、占用最低 |
| Base | 质量和速度平衡 | 建议 GPU 或 Apple Silicon |
| Large | 更重视细节 | 需要更多显存/内存 |

## Windows 安装

在 PowerShell 中进入项目目录：

```powershell
cd "你的项目目录"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r requirements.txt
```

如果 PowerShell 阻止激活脚本，可只为当前窗口允许脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Windows NVIDIA CUDA

先更新 NVIDIA 驱动。上面的 PyTorch 安装完成后检查 CUDA：

```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('PyTorch:', torch.__version__)"
```

若输出 `CUDA: False`，请在 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/) 中选择 Windows、Pip、Python 和适合当前驱动的 CUDA 版本，复制其安装命令重新安装 PyTorch。项目本身不要求单独编译 CUDA 扩展。

### Windows 启动

```powershell
.\.venv\Scripts\Activate.ps1
python app.py --inbrowser
```

浏览器默认打开 `http://127.0.0.1:7860`。

## macOS 安装

建议使用 Python 官网安装包或 Homebrew 的原生 arm64 Python。在 Terminal 中执行：

```bash
cd "/你的项目目录"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r requirements.txt
```

检查 Apple Silicon MPS：

```bash
python -c "import torch; print('MPS:', torch.backends.mps.is_available()); print('PyTorch:', torch.__version__)"
```

Intel Mac 或不支持 MPS 的系统会自动使用 CPU。

### macOS 启动

```bash
source .venv/bin/activate
python app.py --inbrowser
```

浏览器默认打开 `http://127.0.0.1:7860`。

## ffmpeg

`requirements.txt` 包含 `imageio-ffmpeg`，正常情况下不需要手动安装 ffmpeg。程序会先查找系统 `ffmpeg`，找不到时使用 `imageio-ffmpeg` 提供的可执行文件。

若需要手动安装：

macOS（Homebrew）：

```bash
brew install ffmpeg
```

Windows（Windows Package Manager）：

```powershell
winget install --id Gyan.FFmpeg
```

安装后重新打开终端，并用以下命令确认：

```text
ffmpeg -version
```

## 使用方法

1. 运行 `python app.py --inbrowser`。
2. 上传 MP4 或 MOV。
3. 选择模型尺寸与输出分辨率。
4. 调整时间平滑；默认 `0.65` 适合多数视频。
5. 按需选择黑白反转和保留音频。
6. 点击“开始转换”。
7. 完成后在右侧预览或下载 MP4。

输出分辨率规则：

- `Original`：保持源尺寸，仅在必要时调整为偶数。
- `480p / 720p / 1080p`：横屏以高度、竖屏以宽度作为目标边，保持宽高比。
- 明确选择大于源视频的预设会执行上采样，但不会增加真实深度细节。

时间平滑越高，画面闪烁越少；快速移动物体可能出现轻微拖影。设为 `0` 可关闭跨帧平滑。

## 启动参数

```text
python app.py [--force-cpu] [--server-name ADDRESS] [--port PORT]
              [--output-dir DIRECTORY] [--inbrowser] [--verbose]
```

常用示例：

```bash
# GPU 出现兼容问题时强制 CPU
python app.py --force-cpu --inbrowser

# 修改端口
python app.py --port 7861

# 指定成品目录
python app.py --output-dir "./converted"
```

应用默认只监听 `127.0.0.1`，且始终以 `share=False` 启动，不会创建 Gradio 公网分享链接。除非了解网络暴露风险，否则不要把 `--server-name` 设置为 `0.0.0.0`。

## 模型缓存

Hugging Face 默认缓存位置：

- Windows：`%USERPROFILE%\.cache\huggingface\hub`
- macOS：`~/.cache/huggingface/hub`

首次切换到尚未使用过的模型尺寸时会再次下载。删除缓存会导致下次运行重新下载。

## 运行测试

测试不会下载真实模型权重。端到端冒烟测试使用确定性的假深度提供器：

```bash
python -m pytest -q
```

## 故障排查

### CUDA 显存不足

- 改用 Small 模型。
- 降低到 480p 或 720p。
- 使用 `python app.py --force-cpu`。

### MPS 不支持某个算子

用 CPU 模式重启：

```bash
python app.py --force-cpu
```

### 首次模型下载失败

- 检查网络与代理。
- 确认模型缓存目录可写且磁盘空间充足。
- 重新运行；Transformers 会复用已下载的完整文件。

### MP4 没有声音

- 确认已勾选“保留原始音频”。
- 源视频必须包含音轨。
- 查看终端日志；不兼容音频会自动尝试转为 AAC。

### MOV 无法读取

MOV 是容器格式，内部编码可能不受当前 OpenCV/ffmpeg 构建支持。可先使用 ffmpeg 转成常见 H.264 MP4：

```bash
ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p -c:a aac input_compatible.mp4
```

## 已知限制

- 深度是相对值，不是实际距离。
- 单目模型无法保证透明、反光、极暗或快速运动场景完全准确。
- 首版按视频探测到的平均帧率输出；可变帧率视频会被转换为恒定帧率。
- 同一本地界面默认一次只处理一个任务。
- Large 模型在 CPU 上可能非常慢。

## 项目文件

```text
app.py
requirements.txt
README.md
tests/test_app.py
docs/superpowers/specs/2026-07-24-depth-video-converter-design.md
```

## 作为 Codex Skill 使用

仓库中的可安装 Skill 位于：

```text
skills/trmachel-convert-depth-video/
```

安装后，可以对 Codex 说：

```text
Use $trmachel-convert-depth-video to launch the local depth video converter.
```

Skill 自带跨平台启动器。它会在用户缓存目录创建隔离虚拟环境，不会把
`.venv` 或模型权重写入 Skill 目录：

```bash
python skills/trmachel-convert-depth-video/scripts/launch.py --setup-only
python skills/trmachel-convert-depth-video/scripts/launch.py --inbrowser
```

从 GitHub 安装时，使用指向技能子目录的地址：

```text
https://github.com/Trmachel/trmachel-depth-video-converter-skill/tree/main/skills/trmachel-convert-depth-video
```

本仓库应用代码和 Skill 使用 Apache-2.0 许可证。Depth Anything V2 模型
权重采用独立许可证：Small 为 Apache-2.0，Base/Large 为 CC BY-NC 4.0。
