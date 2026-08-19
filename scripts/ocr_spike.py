"""RapidOCR 技术验证 spike：生成中文测试图片 → OCR 识别。

运行: .venv/bin/pip install rapidocr-onnxruntime pillow && .venv/bin/python spike_ocr.py
"""
import sys
from pathlib import Path

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def main() -> None:
    from PIL import Image, ImageDraw, ImageFont
    from rapidocr_onnxruntime import RapidOCR

    font_path = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
    if not font_path:
        print("未找到中文字体，跳过图片生成")
        sys.exit(2)
    font = ImageFont.truetype(font_path, 36)

    img = Image.new("RGB", (820, 320), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "红烧肉（家常版）",
        "步骤一：五花肉切块，冷水下锅焯水",
        "步骤二：加生抽、老抽、冰糖，小火炖40分钟",
    ]
    y = 24
    for line in lines:
        draw.text((32, y), line, fill="black", font=font)
        y += 92
    img.save("spike_ocr.png")
    print(f"已生成测试图: spike_ocr.png ({img.size})")

    engine = RapidOCR()
    result, _elapse = engine("spike_ocr.png")
    if not result:
        print("OCR 未识别到任何文字 ❌")
        sys.exit(1)
    text = "\n".join(r[1] for r in result)
    print("---- OCR 识别结果 ----")
    print(text)
    print("----------------------")
    ok = "红烧肉" in text and "步骤" in text
    print("OCR 验证" + ("通过 ✅" if ok else "部分失败 ⚠️（见上方结果）"))
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
