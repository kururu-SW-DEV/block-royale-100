"""
색약 보정 팔레트 테스트: 적색약/녹색약/청황색약 시뮬레이션(Machado 2009, 선형 sRGB)에서도 블록 7종이 서로 구분되고
(가장 가까운 두 색의 색차 ΔE), 널리 쓰이는 표준 배색과는 겹치지 않는지 확인한다.
실행: python tests/test_colorblind_palette.py
"""
import itertools
import math
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
# 널리 쓰이는 표준 배색 (I 하늘색, J 파랑, L 주황, O 노랑, S 초록, T 보라, Z 빨강)
STANDARD = {'I': (0, 240, 240), 'J': (0, 0, 240), 'L': (240, 160, 0), 'O': (240, 240, 0), 'S': (0, 240, 0), 'T': (160, 0, 240), 'Z': (240, 0, 0)}
OLD_PALETTE = {'I': (86, 200, 245), 'J': (60, 100, 230), 'L': (240, 150, 20), 'O': (245, 232, 70), 'S': (40, 190, 150), 'T': (215, 130, 185), 'Z': (235, 95, 35)}


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _delin(v):
    v = max(0.0, min(1.0, v))
    return 255.0 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)


def _simulate(rgb, kind):
    if kind == "normal":
        return rgb
    m = CVD[kind]
    l = [_lin(c) for c in rgb]
    return tuple(_delin(sum(m[i][j] * l[j] for j in range(3))) for i in range(3))


def _lab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _de(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(_lab(a), _lab(b))))


def _min_pair(palette, kind):
    sims = {p: _simulate(c, kind) for p, c in palette.items()}
    return min(_de(sims[a], sims[b]) for a, b in itertools.combinations(sims, 2))


def test_every_piece_is_distinguishable_under_color_blindness():
    pal = {k: config.PIECE_COLORS_COLORBLIND[k] for k in "IJLOSTZ"}
    floor = {"normal": 30.0, "protan": 21.0, "deutan": 19.0, "tritan": 12.0}
    for kind, lo in floor.items():
        new, old = _min_pair(pal, kind), _min_pair(OLD_PALETTE, kind)
        assert new >= lo, (kind, new)
        assert new > old, (kind, "이전 팔레트보다 구분이 나빠지면 안 됨", new, old)


def test_colorblind_palette_does_not_reuse_the_common_standard_color_layout():
    for piece, std in STANDARD.items():
        assert _de(config.PIECE_COLORS_COLORBLIND[piece], std) >= 60.0, (piece, config.PIECE_COLORS_COLORBLIND[piece])
    assert len(set(config.PIECE_COLORS_COLORBLIND.values())) == 7
    for c in config.PIECE_COLORS_COLORBLIND.values():
        assert all(0 <= v <= 255 for v in c)


def test_switching_color_mode_applies_and_restores_the_palette():
    config.apply_color_mode("colorblind")
    try:
        assert config.PIECE_COLORS['I'] == config.PIECE_COLORS_COLORBLIND['I']
    finally:
        config.apply_color_mode("normal")
    assert config.PIECE_COLORS['I'] == config.PIECE_COLORS_DEFAULT['I']


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL COLORBLIND PALETTE TESTS PASSED]")
