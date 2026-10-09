"""
Block Royale 100 - 화려한 빛 연출 (가산 글로우)
pygame 소프트웨어 렌더링에는 셰이더가 없으므로 '빛 번짐'은 미리 만들어 둔 검은 바탕 그라데이션 스프라이트를 BLEND_RGB_ADD로 더해서 낸다.
- 스프라이트는 종류·네이티브 크기·색·밝기 단계(5단계)별로 한 번만 만들고 캐시한다 (매 프레임 만들거나 확대하지 않음)
- 평소(사건이 없을 때)의 비용을 늘리지 않는 것이 원칙: 줄 삭제/착지/하드 드롭/큰 기술 같은 사건 직후 몇십~몇백 ms 동안만 그림
- 설정 연결: visual_fx(최소/보통/화려하게) · fx_low(프레임이 느릴 때 자동 생략) · flash_enabled(꺼지면 밝기 상한 + 흰 심지 없음) · shake_scale(0이면 움직이는 연출 정지)
UIRenderer가 상속하는 믹스인
"""

import math
import time

import numpy as np
import pygame

from gfx import CANVAS

FX_MIN, FX_NORMAL, FX_FANCY = 0, 1, 2
FX_NAMES = {"min": FX_MIN, "normal": FX_NORMAL, "fancy": FX_FANCY}

_SPRITES = {}
_MAX_SPRITES = 120


def _profile(n, power):
    """0..1..0 (가운데가 가장 밝은) 길이 n의 1차원 밝기 곡선"""
    if n <= 1:
        return np.ones(max(1, n), dtype=np.float32)
    x = np.linspace(-1.0, 1.0, n, dtype=np.float32)
    return np.clip(1.0 - np.abs(x), 0.0, 1.0) ** power


def glow_sprite(kind, w, h, color, level):
    """검은 바탕의 빛 스프라이트 (네이티브 픽셀 크기 w x h). kind:
    'band'  = 가로 띠 (위아래로 부드럽게 사라지고 좌우 끝도 사라짐) - 줄 삭제/착지
    'column' = 세로 기둥 (위로 갈수록 옅어짐, 아래가 가장 밝음) - 하드 드롭 꼬리
    'orb'   = 방사형 구슬 (w = h)"""
    level = max(0, min(4, int(level)))
    key = (kind, w, h, tuple(color[:3]), level)
    spr = _SPRITES.get(key)
    if spr is not None:
        return spr
    k = (level + 1) / 5.0
    if kind == "band":
        a = np.outer(_profile(w, 0.6), _profile(h, 1.8))                    # (w, h)
    elif kind == "column":
        fall = np.linspace(0.0, 1.0, h, dtype=np.float32) ** 1.4            # 위(0) 옅음 -> 아래(1) 밝음
        a = np.outer(_profile(w, 1.1), fall)
    else:
        cx = (np.arange(w, dtype=np.float32) - (w - 1) / 2.0) / max(1.0, w / 2.0)
        cy = (np.arange(h, dtype=np.float32) - (h - 1) / 2.0) / max(1.0, h / 2.0)
        r = np.sqrt(cx[:, None] ** 2 + cy[None, :] ** 2)
        a = np.clip(1.0 - r, 0.0, 1.0) ** 1.6
    rgb = (a[:, :, None] * (np.array(color[:3], dtype=np.float32)[None, None, :] * k)).astype(np.uint8)
    spr = pygame.Surface((w, h))
    pygame.surfarray.blit_array(spr, rgb)
    if len(_SPRITES) >= _MAX_SPRITES:
        _SPRITES.clear()
    _SPRITES[key] = spr
    return spr


def add_glow(kind, x, y, w, h, color, level):
    """논리 좌표 사각형 (x, y, w, h)에 빛을 더해 그림. 해상도(배율)가 바뀌면 크기가 달라져 키가 달라지므로 따로 무효화할 필요 없음"""
    if w <= 0 or h <= 0:
        return
    nw, nh = max(2, CANVAS.length(w, 1)), max(2, CANVAS.length(h, 1))
    spr = glow_sprite(kind, nw, nh, color, level)
    CANVAS.display.blit(spr, (CANVAS.X(x), CANVAS.Y(y)), special_flags=pygame.BLEND_RGB_ADD)


# 이펙트 테마: 블록 스킨에 맞춰 줄 삭제 띠/오라/에너지 러너의 색을 한 세트로 바꿈 (블록 스킨 선택이 곧 테마 선택: 해금 스킨 UI를 그대로 씀).
# 장식 색만 바꾸고, 의미가 있는 색(위기 붉은색, 공격/피격, 블록 7색)과 띠의 '모양'(보통/쿼드/T-스핀 구분)은 그대로. 색약 모드는 기본 테마
FX_THEMES = {
    "default": {"wipe": {"clear": (70, 205, 255), "quad": (255, 205, 70), "tspin": (190, 110, 255)}, "aura": {1: (90, 170, 255), 2: (170, 110, 255), 3: (255, 200, 90)}},
    "neon": {"wipe": {"clear": (80, 255, 200), "quad": (255, 230, 60), "tspin": (255, 90, 220)}, "aura": {1: (80, 255, 200), 2: (255, 90, 220), 3: (255, 230, 60)}},
    "ember": {"wipe": {"clear": (255, 150, 70), "quad": (255, 215, 110), "tspin": (255, 120, 180)}, "aura": {1: (255, 160, 80), 2: (255, 120, 150), 3: (255, 215, 110)}},
    "starlight": {"wipe": {"clear": (170, 190, 255), "quad": (255, 235, 150), "tspin": (200, 150, 255)}, "aura": {1: (150, 180, 255), 2: (200, 150, 255), 3: (255, 235, 150)}},
    "prism": {"wipe": {"clear": (120, 255, 200), "quad": (255, 240, 120), "tspin": (255, 130, 220)}, "aura": {1: (120, 230, 255), 2: (255, 130, 220), 3: (255, 240, 120)}},
    "glass": {"wipe": {"clear": (150, 230, 255), "quad": (210, 255, 255), "tspin": (170, 200, 255)}, "aura": {1: (150, 230, 255), 2: (170, 200, 255), 3: (230, 255, 255)}},
}
SKIN_THEME = {"neon": "neon", "ember": "ember", "starlight": "starlight", "prism": "prism", "glass": "glass"}


class GlowMixin:
    def _fx_theme(self):
        """지금 블록 스킨의 이펙트 테마 (색약 모드면 기본)"""
        from config import is_colorblind
        if is_colorblind():
            return FX_THEMES["default"]
        return FX_THEMES[SKIN_THEME.get(getattr(self, "block_skin", "classic"), "default")]

    # ---------------------------------------------------------------- 설정 연결
    def _fx_mode(self, match):
        """빛 연출 단계: FX_MIN(끔: 지금까지와 같음) / FX_NORMAL / FX_FANCY. 화면이 느려 fx_low면 최소"""
        if match is None or getattr(match, "fx_low", False):
            return FX_MIN
        return FX_NAMES.get(getattr(match, "visual_fx", "normal"), FX_NORMAL)

    def _fx_level(self, match, fade, cap=4):
        """페이드(1~0)를 0~4 밝기 단계로. 번쩍임이 꺼져 있으면 밝기 상한을 낮춤"""
        if not getattr(match, "flash_enabled", True):
            cap = min(cap, 1)
        return max(0, min(cap, int(fade * 4.99)))

    def _fx_motion(self, match):
        """위치가 움직이는 연출(회전/흐름/시차)을 해도 되는가: 화면 흔들림이 꺼져 있으면 정지"""
        return getattr(match, "shake_scale", 1.0) > 0

    # ---------------------------------------------------------------- 1. 줄 삭제 / 착지 빛 번짐
    def _glow_wipe(self, match, fl, bx, by, bw, cs, progress, kind):
        """줄 삭제 띠 위아래로 번지는 빛. 쿼드는 금빛이 보드 좌우 밖으로 새어 나옴 (줄마다 가산 blit 1회, 0.4초)"""
        if self._fx_mode(match) < FX_NORMAL:
            return
        wc = self._fx_theme()["wipe"]
        col = wc.get(kind, wc["clear"])
        level = self._fx_level(match, 1.0 - progress, cap=4 if kind != "clear" else 3)
        if level <= 0:
            return
        side = 40 if kind == "quad" else 10
        h = int(cs * 2.6)
        add_glow("band", bx - side, by + fl["row"] * cs + cs // 2 - h // 2, bw + 2 * side, h, col, level)

    def _glow_lock(self, match, lf, bx, by, cs, age):
        """착지한 블록 둘레의 옅은 후광 (0.16초, 블록 묶음 하나에 blit 1회)"""
        if self._fx_mode(match) < FX_NORMAL:
            return
        level = self._fx_level(match, 1.0 - age / 0.16, cap=2)
        if level <= 0:
            return
        xs = [c[0] for c in lf["cells"]]
        ys = [c[1] for c in lf["cells"]]
        x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
        add_glow("band", bx + x0 * cs - cs, by + y0 * cs - cs // 2, (x1 - x0) * cs + 2 * cs, (y1 - y0) * cs + cs, lf.get("col", (140, 200, 255)), level)

    # ---------------------------------------------------------------- 2. 하드 드롭 혜성 꼬리 + 착지 충격선
    def _glow_trail(self, match, tr, x, y0, h, a, cs):
        if self._fx_mode(match) < FX_NORMAL:
            return
        level = self._fx_level(match, a, cap=3)
        if level <= 0 or h <= 0:
            return
        add_glow("column", x - cs * 0.3, y0, cs * 1.6, h, tr["col"], level)
        if a > 0.55:                                                         # 착지 순간(앞 40%)만: 착지 줄 좌우로 퍼지는 가는 빛 선
            add_glow("band", x - cs * 2.2, y0 + h - cs * 0.9, cs * 5.4, cs * 1.8, tr["col"], max(0, level - 1))

    # ---------------------------------------------------------------- 3. 보드 테두리 에너지 러너
    def _render_energy_runner(self, match, engine, bx, by, bw, bh, level):
        """콤보/B2B 오라 단계(1~3)에 따라 빛 점 1~3개가 보드 둘레를 돌고, 단계가 높을수록 빠르고 꼬리가 길어짐"""
        mode = self._fx_mode(match)
        if mode < FX_NORMAL:
            return
        n = level
        perim = 2 * (bw + bh)
        speed = (0.22 + 0.12 * level) if self._fx_motion(match) else 0.0
        t = time.time() * speed
        col = self._fx_theme()["aura"][level]
        danger = getattr(self, "_danger_now", False)
        base = 2 if danger else 3                                            # 위기 중에는 붉은 경고가 가장 밝은 신호로 남게 어둡게
        for i in range(n):
            for tail in range(3):
                u = (t + i / n - tail * 0.012) % 1.0 if speed else (i + 0.5) / n * 0.8
                d = u * perim
                if d < bw:
                    px, py = bx + d, by
                elif d < bw + bh:
                    px, py = bx + bw, by + (d - bw)
                elif d < 2 * bw + bh:
                    px, py = bx + bw - (d - bw - bh), by + bh
                else:
                    px, py = bx, by + bh - (d - 2 * bw - bh)
                r = (16 + 4 * level) - tail * 4
                lv = max(0, min(4, base + (1 if level >= 3 else 0)) - tail)
                if not getattr(match, "flash_enabled", True):
                    lv = min(lv, 1)
                add_glow("orb", px - r, py - r, 2 * r, 2 * r, col, lv)

    # ---------------------------------------------------------------- 4. 내 파티클 발광화 (ParticleManager.draw의 glow_n 인자로 처리)
    def _particle_glow_budget(self, match):
        mode = self._fx_mode(match)
        n = {FX_MIN: 0, FX_NORMAL: 40, FX_FANCY: 80}[mode]
        if not getattr(match, "flash_enabled", True):
            n //= 2
        return n
