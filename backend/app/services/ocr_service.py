"""RapidOCR 封装：按顺序识别图片列表（图文菜谱的图片顺序即步骤顺序）。"""
from pathlib import Path

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def recognize_images(paths: list[Path]) -> list[dict]:
    """返回 [{index, path, text}]，保持输入顺序；识别失败返回空文本。"""
    engine = _get_engine()
    results: list[dict] = []
    for i, path in enumerate(paths):
        try:
            res, _elapse = engine(str(path))
            text = "\n".join(r[1] for r in res) if res else ""
        except Exception:
            text = ""
        results.append({"index": i, "path": path.name, "text": text})
    return results
