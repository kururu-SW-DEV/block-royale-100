"""
BLOCK ROYALE 100 - 아이콘 생성 스크립트 (개발용)
icon.png / icon.ico 를 코드로 직접 그려서 만듭니다. 외부 이미지를 쓰지 않으므로 출처가 명확합니다.
  python make_icon.py
"""

import io
import os
import struct
import pygame
from config import PIECE_COLORS
from logo import CROWN, JEWELS, ROW_PIECE

HERE = os.path.dirname(os.path.abspath(__file__))


def _mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3]))


def draw_cell(surf, x, y, size, color):
    """게임 내 블록 셀과 같은 모양(테두리 + 밝은 윗면 + 어두운 아랫면)"""
    outer = pygame.Rect(x + 1, y + 1, size - 2, size - 2)
    r = max(2, size // 6)
    pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.45), outer, border_radius=r)
    inner = outer.inflate(-max(2, size // 8), -max(2, size // 8))
    pygame.draw.rect(surf, color, inner, border_radius=max(1, r - 1))
    hl = pygame.Rect(inner.x + 1, inner.y + 1, inner.w - 2, max(2, inner.h // 3))
    pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.42), hl, border_radius=max(1, r - 2))
    sh_h = max(2, inner.h // 5)
    pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.22), (inner.x + 1, inner.bottom - sh_h - 1, inner.w - 2, sh_h))


def render(size=1024):
    """고해상도로 그린 뒤 축소해서 사용 (부드러운 가장자리)"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pad = int(size * 0.03)
    tile = pygame.Rect(pad, pad, size - 2 * pad, size - 2 * pad)
    radius = int(size * 0.2)
    # 배경 (세로 그라데이션 + 네온 테두리)
    bg = pygame.Surface(tile.size, pygame.SRCALPHA)
    for y in range(tile.h):
        pygame.draw.line(bg, (*_mix((26, 30, 60), (10, 12, 26), y / tile.h), 255), (0, y), (tile.w, y))
    mask = pygame.Surface(tile.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, *tile.size), border_radius=radius)
    bg.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(bg, tile.topleft)
    pygame.draw.rect(s, (110, 90, 255), tile, max(3, size // 60), border_radius=radius)
    pygame.draw.rect(s, (80, 200, 255), tile.inflate(-size // 30, -size // 30), max(2, size // 130), border_radius=radius - size // 60)

    # 블록으로 만든 금색 왕관
    cols, rows = len(CROWN[0]), len(CROWN)
    cell = int(size * 0.078)
    cw, ch = cols * cell, rows * cell
    ox, oy = (size - cw) // 2, int(size * 0.24)
    for row, line in enumerate(CROWN):
        for col, c in enumerate(line):
            if c == ".":
                continue
            key = JEWELS.get(c) or ROW_PIECE[row]
            draw_cell(s, ox + col * cell, oy + row * cell, cell, PIECE_COLORS[key])

    # 아래에 쌓인 블록 3줄 (자체 팔레트의 7색)
    base_y = oy + ch + int(size * 0.07)
    cs = int(size * 0.095)
    keys = "ITOSJLZ"
    for i in range(7):
        draw_cell(s, (size - 7 * cs) // 2 + i * cs, base_y + cs, cs, PIECE_COLORS[keys[i]])
    for i, k in enumerate("OSJ"):
        draw_cell(s, (size - 7 * cs) // 2 + (i + 2) * cs, base_y, cs, PIECE_COLORS[k])
    return s


def png_bytes(surface):
    buf = io.BytesIO()
    pygame.image.save(surface, buf, "icon.png")
    return buf.getvalue()


def write_ico(path, images):
    """PNG 압축 이미지를 담은 ICO 파일 작성 (Vista 이상 지원)"""
    entries, blobs, offset = [], [], 6 + 16 * len(images)
    for size, data in images:
        entries.append(struct.pack("<BBBBHHII", 0 if size >= 256 else size, 0 if size >= 256 else size, 0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)))
        for e in entries:
            f.write(e)
        for b in blobs:
            f.write(b)


def main():
    pygame.init()
    big = render(1024)
    images = []
    for sz in (256, 128, 64, 48, 32, 16):
        scaled = pygame.transform.smoothscale(big, (sz, sz))
        images.append((sz, png_bytes(scaled)))
    with open(os.path.join(HERE, "icon.png"), "wb") as f:
        f.write(images[0][1])
    write_ico(os.path.join(HERE, "icon.ico"), images)
    print("icon.png / icon.ico 생성 완료")


if __name__ == "__main__":
    main()
