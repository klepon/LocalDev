"""Render assets/icon.ico ({*} on a blue rounded square) at several sizes."""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def render(size: int) -> bytes:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2563eb"))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    font = QFont("Consolas")
    font.setBold(True)
    font.setPixelSize(round(size * 0.46))
    p.setFont(font)
    p.setPen(QColor("white"))
    # Monospace: the space in "{ }" is as wide as "*", so the asterisk can be drawn
    # separately and lowered, since Consolas puts it high like a superscript.
    p.drawText(QRectF(0, 0, size, size * 0.96), Qt.AlignmentFlag.AlignCenter, "{ }")
    p.drawText(QRectF(0, size * 0.1, size, size * 0.96), Qt.AlignmentFlag.AlignCenter, "*")
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def main():
    QGuiApplication(sys.argv)
    images = [render(s) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, data = b"", b""
    for size, png in zip(SIZES, images):
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(header + entries + data)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
