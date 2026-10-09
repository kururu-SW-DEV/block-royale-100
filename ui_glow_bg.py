"""
Block Royale 100 - 배경 빛 연출: 비트 맞춤 맥동, 단계별 배경 장식, 3단계 불씨
UIRenderer가 ui_glow.GlowMixin과 함께 상속하는 믹스인 (ui_glow의 _fx_mode/_fx_motion/glow_sprite를 씀)
"""

import math
import random
import time

import pygame

from gfx import CANVAS, mix_color as _mix
from ui_glow import FX_FANCY, FX_NORMAL, glow_sprite


class GlowBgMixin:
    # ---------------------------------------------------------------- 5. 비트 맞춤 배경 맥동
    def _beat_k(self, match):
        """BGM 박자에 맞춰 0~4 (박자 직후 가장 밝고 천천히 가라앉음). 박자 정보가 없거나 움직임/위기/최소 모드면 0.
        박자 주파수는 2~2.7Hz(3Hz 미만), 밝기 변화는 4% 안쪽이라 광과민 기준 안"""
        if self._fx_mode(match) < FX_NORMAL or not self._fx_motion(match) or getattr(self, "_danger_now", False):
            return 0
        info = getattr(self, "_beat_info", None)
        if not info:
            return 0
        k = int(round(3 * (1.0 - info[0]) ** 3))
        if time.time() - getattr(match, "impact_t", -9.0) < 0.3:               # 큰 기술 직후 한 박자는 더 밝게
            k = min(4, k + 1)
        if not getattr(match, "flash_enabled", True):
            k = min(k, 1)
        return k

    def _bg_beat(self, phase, deco, k):
        """단계 배경의 밝기 변형(k=0..4)을 한 번만 만들어 둠: 매 프레임은 장수만 골라 blit (추가 blit/연산 없음). 단계가 바뀌면 이전 단계 변형은 버림"""
        base = self._bg(phase, deco)
        if k <= 0:
            return base
        cache = self.__dict__.setdefault("_bg_beat_cache", {})
        stamp = (phase, deco, CANVAS.version)
        if cache.get("_stamp") != stamp:
            cache.clear()
            cache["_stamp"] = stamp
        v = cache.get(k)
        if v is None:
            v = CANVAS.make_surface(self.width, self.height, alpha=False)
            pygame.Surface.blit(v, base, (0, 0))
            v.fill((3 * k, 3 * k, 4 * k), special_flags=pygame.BLEND_RGB_ADD)
            cache[k] = v
        return v

    # ---------------------------------------------------------------- 6. 단계별 배경 테마
    def _bake_stage_deco(self, surf, phase, top, bottom):
        """단계별 배경 장식을 배경 서피스에 한 번만 구워 넣음 (비용 0). 보드/게이지/HOLD·NEXT 둘레(보드 ±170px)는 비워 대비를 지킴.
        1단계 네온 원근 그리드, 2단계 보라 성운과 별, 3단계 바닥의 주황빛 (빨강은 위기 경고 색이라 쓰지 않음)"""
        w, h = pygame.Surface.get_size(surf)
        S = CANVAS.S
        rng = random.Random(7000 + phase)
        kx0 = max(0, int((self.main_board_x - 170) * S))
        kx1 = min(w, int((self.main_board_x + self.main_board_w + 170) * S))

        def bg_at(y):
            return _mix(top, bottom, min(1.0, max(0.0, y / h)))
        lw_ = max(1, int(S))
        if phase == 1:
            hz = int(h * 0.64)
            vx = w // 2
            for i in range(-16, 17):
                far, near = vx + i * w * 0.045, vx + i * w * 0.17
                pygame.draw.line(surf, _mix(bg_at(h * 0.8), (60, 170, 220), 0.13), (int(far), hz), (int(near), h), lw_)
            for k in range(1, 11):
                y = int(hz + (h - hz) * (k / 10.0) ** 2)
                pygame.draw.line(surf, _mix(bg_at(y), (60, 170, 220), 0.08 + 0.10 * k / 10.0), (0, y), (w, y), lw_)
        elif phase == 2:
            lw, lh = max(8, w // 8), max(8, h // 8)
            lr = pygame.Surface((lw, lh))
            for (fx, fy, fr, col) in ((0.12, 0.30, 0.30, (46, 20, 70)), (0.90, 0.22, 0.28, (30, 26, 78)), (0.18, 0.80, 0.26, (36, 18, 64)),
                                      (0.88, 0.76, 0.30, (50, 24, 72)), (0.50, 0.10, 0.20, (28, 20, 60))):
                for rr in range(int(fr * lw), 0, -2):
                    f = (1.0 - rr / (fr * lw)) ** 1.4
                    pygame.draw.circle(lr, (int(col[0] * f), int(col[1] * f), int(col[2] * f)), (int(fx * lw), int(fy * lh)), rr)
            big = pygame.transform.smoothscale(lr, (w, h))
            pygame.Surface.blit(surf, big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            for _ in range(150):
                x, y = rng.randrange(w), rng.randrange(int(h * 0.9))
                c = _mix(bg_at(y), (205, 200, 255), rng.choice((0.18, 0.28, 0.4, 0.6)))
                if rng.random() < 0.12:
                    pygame.draw.rect(surf, c, (x, y, max(2, int(2 * S)), max(2, int(2 * S))))
                else:
                    surf.set_at((x, y), c)
        else:
            for y in range(int(h * 0.62), h):
                t = max(0.0, (y - h * 0.62) / (h * 0.38))
                pygame.draw.line(surf, _mix(bg_at(y), (84, 34, 10), 0.5 * t ** 2.2), (0, y), (w, y))
            for _ in range(60):
                x, y = rng.randrange(w), rng.randrange(int(h * 0.55), h)
                surf.set_at((x, y), _mix(bg_at(y), (255, 150, 60), rng.choice((0.25, 0.4, 0.6))))
        for y in range(h):                                                  # 보드 둘레는 장식을 지우고 원래 그라데이션으로 되돌림
            pygame.draw.line(surf, bg_at(y), (kx0, y), (kx1, y))

    def _render_embers(self, match):
        """3단계에서 아래에서 천천히 올라오는 주황 불씨 (화려하게 모드 + 움직임 허용 + 평소일 때만, 20개 안팎의 작은 빛 구슬)"""
        if self._fx_mode(match) < FX_FANCY or not self._fx_motion(match) or getattr(match, "phase", 1) < 3 or getattr(self, "_danger_now", False):
            return
        now = time.time()
        em = self.__dict__.setdefault("_embers", [])
        dt = min(0.1, now - getattr(self, "_embers_t", now))
        self._embers_t = now
        zx0, zx1 = self.main_board_x - 170, self.main_board_x + self.main_board_w + 170
        while len(em) < 20:
            x = random.choice((random.uniform(10, zx0), random.uniform(zx1, self.width - 10)))
            em.append({"x": x, "y": random.uniform(self.height * 0.5, self.height + 20), "v": random.uniform(14, 34),
                       "r": random.choice((5, 7, 9)), "ph": random.random() * 6.28})
        for e in em:
            e["y"] -= e["v"] * dt
            e["x"] += math.sin(now * 0.8 + e["ph"]) * 6 * dt
            if e["y"] < self.height * 0.2:
                e["y"] = self.height + 10
            fade = max(0.0, min(1.0, (e["y"] - self.height * 0.2) / (self.height * 0.6)))
            lv = max(0, min(2, int(fade * 2.4)))
            if not getattr(match, "flash_enabled", True):
                lv = min(lv, 1)
            r = CANVAS.length(e["r"], 2)
            CANVAS.display.blit(glow_sprite("orb", 2 * r, 2 * r, (255, 150, 60), lv), (CANVAS.X(e["x"]) - r, CANVAS.Y(e["y"]) - r),
                                special_flags=pygame.BLEND_RGB_ADD)
