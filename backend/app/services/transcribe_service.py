"""视频语音转文字服务（faster-whisper 本地推理，M1 可跑）。

模型来源优先级：
  1. 环境变量 WHISPER_MODEL（模型名或本地目录）
  2. 项目内 ModelScope 下载的模型 backend/data/models/models--*/snapshots/*/
  3. 项目内 HF 缓存 backend/data/hf_cache/hub/models--*/
  4. 默认 "small"（走 HuggingFace 下载）

首次使用会自动下载模型（约 460MB）。
"""
import os
from pathlib import Path

# 国内网络优先走 HuggingFace 镜像（模型下载兜底）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# 模型缓存放到项目 data 目录（避免写入用户 ~/.cache 受限）
from ..config import settings  # noqa: E402

os.environ.setdefault("HF_HOME", str(settings.data_dir / "hf_cache"))

_model = None


def _resolve_local_model() -> str | None:
    """在项目 data 目录递归查找已下载的 whisper 模型（含 model.bin 的目录）。"""
    roots = [settings.data_dir / "models", settings.data_dir / "hf_cache" / "hub"]
    for root in roots:
        if not root.exists():
            continue
        for d in root.rglob("*"):
            if d.is_dir() and (d / "model.bin").exists():
                return str(d)
    return None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        local = _resolve_local_model()
        model_name = local or os.environ.get("WHISPER_MODEL", "small")
        # M1/M2 用 cpu + int8 即可流畅跑 small；显式 int8 降内存
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _model


def transcribe_video(video_path: Path, language: str = "zh") -> str:
    """转写视频/音频文件为文字；失败返回空字符串。"""
    if not video_path.exists():
        return ""
    try:
        model = _get_model()
        segments, _info = model.transcribe(
            str(video_path),
            language=language,
            beam_size=5,
            vad_filter=True,  # 过滤静音段，提速
        )
        return "\n".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip())
    except Exception:
        return ""
