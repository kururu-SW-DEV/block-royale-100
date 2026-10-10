"""
Block Royale 100 - 배경 빛 연출: 비트 맞춤 맥동, 단계별 배경 장식, 3단계 불씨
UIRenderer가 ui_glow.GlowMixin과 함께 상속하는 믹스인 (ui_glow의 _fx_mode/_fx_motion/glow_sprite를 씀)
"""

import math
import random
import time

import pygame

from gfx import CANVAS, mix_color as _mix
import numpy as np

from ui_glow import FX_FANCY, FX_NORMAL, glow_sprite


class GlowBgMixin:
    # ---------------------------------------------------------------- 5. 비트 맞춤 배경 맥동
    def _beat_k(self, match):
        """BGM 박자에 맞춰 0~4 (박자 직후 가장 밝고 천천히 가라앉음). 박자 정보가 없거나 움직임/위기/최소 모드면 0.
        박자 주파수는 2~2.7Hz(3Hz 미만), 밝기 변화는 4% 안쪽이라 광과민 기준 안"""
        if self._fx_mode(match) < FX_FANCY or not self._fx_motion(match) or getattr(self, "_danger_now", False):
            return 0                                                          # 음악에 맞춘 밝기 맥동은 '화려하게'에서만 (보통은 배경이 번쩍이지 않음)
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
            pygame.Surface.blit(surf, self._nebula_surface(w, h, rng, kx0, kx1, 110 * S), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            for _ in range(170):                                            # 별: 대부분 1px, 일부 2px, 몇 개는 작게 빛남
                x, y = rng.randrange(w), rng.randrange(int(h * 0.92))
                c = _mix(bg_at(y), (205, 200, 255), rng.choice((0.18, 0.28, 0.4, 0.6)))
                if rng.random() < 0.12:
                    pygame.draw.rect(surf, c, (x, y, max(2, int(2 * S)), max(2, int(2 * S))))
                else:
                    surf.set_at((x, y), c)
            for _ in range(14):
                sx, sy = rng.randrange(w), rng.randrange(int(h * 0.85))
                r_ = rng.choice((5, 6, 8))
                pygame.Surface.blit(surf, glow_sprite("orb", 2 * r_, 2 * r_, (170, 160, 255), 1), (sx - r_, sy - r_), special_flags=pygame.BLEND_RGB_ADD)
        else:
            for y in range(int(h * 0.62), h):
                t = max(0.0, (y - h * 0.62) / (h * 0.38))
                pygame.draw.line(surf, _mix(bg_at(y), (84, 34, 10), 0.5 * t ** 2.2), (0, y), (w, y))
            for _ in range(60):
                x, y = rng.randrange(w), rng.randrange(int(h * 0.55), h)
                surf.set_at((x, y), _mix(bg_at(y), (255, 150, 60), rng.choice((0.25, 0.4, 0.6))))
        for y in range(h):                                                  # 보드 둘레는 장식을 지우고 원래 그라데이션으로 되돌림
            pygame.draw.line(surf, bg_at(y), (kx0, y), (kx1, y))

    @staticmethod
    def _noise_field(w, h, cells, rng):
        """부드러운 2차원 노이즈(0~1): 작은 무작위 격자를 두 번 나눠 키워 구름 같은 덩어리 모양을 만듦"""
        gw, gh = max(2, cells), max(2, int(cells * h / w))
        g = np.array([[rng.random() for _ in range(gw)] for _ in range(gh)], dtype=np.float32)
        small = pygame.Surface((gw, gh))
        pygame.surfarray.blit_array(small, (np.repeat(g.T[:, :, None], 3, axis=2) * 255).astype(np.uint8))
        mid = pygame.transform.smoothscale(small, (max(gw * 4, 8), max(gh * 4, 8)))
        big = pygame.transform.smoothscale(mid, (w, h))
        return pygame.surfarray.array3d(big)[:, :, 0].T.astype(np.float32) / 255.0      # (h, w)

    def _nebula_surface(self, w, h, rng, kx0=0, kx1=0, ramp=100.0):
        """2단계 성운: 1/3 해상도에서 큰 가우시안 덩어리에 3겹 노이즈를 곱해 구름결을 내고, 두 색을 섞고, 디더링으로 색 띠(banding)를 없앤 뒤 2배로 키움.
        (전에는 1/8 해상도에 원을 겹쳐 그린 뒤 확대해 계단과 띠가 보였음). 경기 시작 직후 세 프레임에 나눠 한 번만 굽는 배경 안에서만 계산됨 (비움 구간 가장자리는 ramp로 서서히)"""
        hw = max(32, min(w // 3, 460))                                  # 계산 해상도에 상한: 4K에서도 1366 기준과 같은 계산량(약 100ms)
        hh = max(32, int(round(hw * h / float(w))))                       # 3분의 1 해상도로 계산해(약 100ms) 부드럽게 키움: 구름은 원래 흐려서 충분
        yy, xx = np.mgrid[0:hh, 0:hw].astype(np.float32)
        xx /= hw
        yy /= hh
        blobs = ((0.10, 0.28, 0.34, 0.20, 0.5), (0.92, 0.20, 0.30, 0.22, -0.4), (0.16, 0.82, 0.30, 0.18, 0.3),
                 (0.88, 0.78, 0.34, 0.20, -0.2), (0.50, 0.06, 0.26, 0.10, 0.0), (0.04, 0.55, 0.20, 0.30, 0.0), (0.97, 0.50, 0.20, 0.28, 0.0))
        field = np.zeros((hh, hw), dtype=np.float32)
        for cx, cy, sx, sy, rot in blobs:
            dx, dy = xx - cx, yy - cy
            c_, s_ = np.cos(rot), np.sin(rot)
            u, v = dx * c_ + dy * s_, -dx * s_ + dy * c_
            field += np.exp(-((u / sx) ** 2 + (v / sy) ** 2) * 1.6)
        n1 = self._noise_field(hw, hh, 5, rng)
        n2 = self._noise_field(hw, hh, 11, rng)
        n3 = self._noise_field(hw, hh, 23, rng)
        cloud = np.clip(0.30 + 0.55 * n1 + 0.30 * n2 + 0.16 * n3 - 0.45, 0.0, 1.0)             # 덩어리 사이가 비는 구름결
        inten = np.clip(field, 0.0, 1.4) * cloud
        if kx1 > kx0:                                                                          # 보드 둘레 비움 구간 가장자리는 급히 끊지 않고 ramp 폭으로 서서히 사라짐
            px = (np.arange(hw, dtype=np.float32) + 0.5) * (w / hw)
            outside = np.maximum(kx0 - px, px - kx1)
            inten = inten * np.clip(outside / max(1.0, ramp), 0.0, 1.0)[None, :]
        mix = self._noise_field(hw, hh, 4, rng)[..., None]
        c1 = np.array((88.0, 40.0, 132.0), dtype=np.float32)                                   # 보라
        c2 = np.array((40.0, 62.0, 150.0), dtype=np.float32)                                   # 파랑
        rgb = inten[..., None] * (c1 * (1.0 - mix) + c2 * mix) * 0.62
        dither = (np.random.default_rng(11).random((hh, hw, 1)).astype(np.float32) - 0.5) * 1.6
        rgb = np.clip(rgb + dither, 0, 255).astype(np.uint8)                                   # (hh, hw, 3)
        small = pygame.Surface((hw, hh))
        pygame.surfarray.blit_array(small, np.transpose(rgb, (1, 0, 2)))
        return pygame.transform.smoothscale(small, (w, h))

    def _render_embers(self, match):
        """3단계에서 아래에서 천천히 올라오는 주황 불씨 (보통 이상 + 움직임 허용 + 평소일 때만, 20개 안팎의 작은 빛 구슬)"""
        if self._fx_mode(match) < FX_NORMAL or not self._fx_motion(match) or getattr(match, "phase", 1) < 3 or getattr(self, "_danger_now", False):
            return
        now = time.time()
        em = self.__dict__.setdefault("_embers", [])
        dt = min(0.1, now - getattr(self, "_embers_t", now))
        self._embers_t = now
        zx0, zx1 = self.main_board_x - 170, self.main_board_x + self.main_board_w + 170
        want = 26 if self._fx_mode(match) >= FX_FANCY else 18                # 보통 18개, 화려하게 26개
        del em[want:]
        while len(em) < want:
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
