"""
Block Royale 100 - 장면별 빛 연출: 우승 광선/분수/충격 링, 순위표 1위 행 빛줄기, 미니 카드 소량 강화
UIRenderer가 상속하는 믹스인 (ui_glow의 _fx_mode/_fx_level/_fx_motion/add_glow를 씀)
"""

import math
import time

import numpy as np
import pygame

from gfx import CANVAS
from ui_glow import FX_FANCY, FX_NORMAL, add_glow


class GlowSceneMixin:
    # ---------------------------------------------------------------- 7. 우승 연출
    def _victory_ray_sprite(self, alt, level, cx, cy):
        """보드 뒤에서 퍼지는 금빛 광선 (12갈래, alt는 반 칸 어긋난 판). 낮은 해상도로 계산해 한 번만 네이티브로 키우고, 밝기 3단계로 캐시.
        두 판을 번갈아 밝혔다 어둡혔다 하면 광선이 일렁이며 도는 것처럼 보임 (회전 프레임을 여러 장 만들지 않아 메모리 절약)"""
        cache = self.__dict__.setdefault("_ray_cache", {})
        stamp = (CANVAS.version, CANVAS.length(self.width), CANVAS.length(self.height))
        if cache.get("_stamp") != stamp:
            cache.clear()
            cache["_stamp"] = stamp
        key = (alt, level)
        spr = cache.get(key)
        if spr is None:
            nw, nh = CANVAS.length(self.width), CANVAS.length(self.height)
            lw, lh = max(16, nw // 4), max(16, nh // 4)
            yy, xx = np.mgrid[0:lh, 0:lw].astype(np.float32)
            ccx, ccy = CANVAS.X(cx) / 4.0, CANVAS.Y(cy) / 4.0
            dx, dy = xx - ccx, yy - ccy
            r = np.sqrt(dx * dx + dy * dy)
            ang = np.arctan2(dy, dx)
            wedge = (np.cos((ang * 12.0) + (math.pi if alt else 0.0)) * 0.5 + 0.5) ** 6                # 가는 광선 12개
            fall = np.clip(1.0 - r / (0.75 * lw), 0.0, 1.0) ** 1.3
            a = (wedge * fall).astype(np.float32)
            gold = np.array((255, 205, 90), dtype=np.float32)
            rgb = (a.T[:, :, None] * gold[None, None, :] * (0.22 * (level + 1))).astype(np.uint8)       # (lw, lh, 3)
            small = pygame.Surface((lw, lh))
            pygame.surfarray.blit_array(small, rgb)
            spr = pygame.transform.smoothscale(small, (nw, nh))
            cache[key] = spr
        return spr

    def _render_victory_rays(self, match):
        """우승 후(세리머니 + 순위표 뒤): 금빛 광선이 일렁임 (보통 이상, 흔들림이 꺼져 있으면 일렁임 없이 은은하게 고정, 번쩍임이 꺼져 있으면 낮은 밝기)"""
        if self._vic_t0 is None or not getattr(match, "match_finished", False) or self._fx_mode(match) < FX_NORMAL:
            return
        t = time.time() - self._vic_t0 - 0.5
        if t <= 0:
            return
        cx = self.main_board_x + self.main_board_w // 2
        cy = self.main_board_y + self.main_board_h // 2
        k = min(1.0, t / 0.8)                                                  # 서서히 나타남
        cap = 1 if not getattr(match, "flash_enabled", True) else 2
        if self._fx_motion(match):
            wa = 0.5 + 0.5 * math.sin(t * 1.6)                                 # 약 0.25Hz로 두 판이 번갈아 밝아짐 (3Hz 미만)
        else:
            wa = 1.0
        for alt, w_ in ((False, wa), (True, 1.0 - wa)):
            lv = min(cap, int(w_ * k * 2.99))
            if lv <= 0 and not (alt is False and not self._fx_motion(match)):
                continue
            spr = self._victory_ray_sprite(alt, lv, cx, cy)
            CANVAS.display.blit(spr, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _render_victory_backdrop(self, match):
        """우승 장면: 상대 미니 카드를 0.7초에 걸쳐 어둡게 덮고(순위표 뒤까지 유지) 그 앞에서 금빛 광선이 일렁임.
        빛 연출이 '최소'면 예전처럼 카드가 그대로 보임"""
        if self._vic_t0 is None or not getattr(match, "match_finished", False) or self._fx_mode(match) < FX_NORMAL:
            return
        t = time.time() - self._vic_t0 - 0.3
        if t <= 0:
            return
        CANVAS.overlay((3, 5, 12, int(246 * min(1.0, t / 0.7))))          # 카드와 배경 장식을 어둡게 (광선이 가장 밝은 것이 되도록)
        self._render_victory_rays(match)

    def _victory_fountain(self, match, now):
        """왕관이 내려앉는 동안 보드 아래쪽에서 솟는 금빛 불티 분수 (화려하게 모드, 움직임 허용)"""
        if self._fx_mode(match) < FX_FANCY or not self._fx_motion(match) or self._vic_t0 is None:
            return
        t = now - self._vic_t0
        if 0.9 < t < 3.4:
            cx = self.main_board_x + self.main_board_w // 2
            by = self.main_board_y + self.main_board_h
            for dx in (-120, 120):
                self.particles.add_sparks(cx + dx, by - 10, (255, 215, 100), count=2, speed_mult=2.4, glow=True, up=True)

    def _victory_ring(self, match, now, cx, cy):
        """왕관이 자리를 잡는 순간 한 번: 충격 링 두 겹"""
        if getattr(self, "_vic_ring_done", None) is self._vic_t0:
            return
        self._vic_ring_done = self._vic_t0
        self.particles.add_shockwave(cx, cy + 40, (255, 215, 100), max_radius=190)
        self.particles.add_shockwave(cx, cy + 40, (255, 245, 190), max_radius=120)

    def _standings_shine(self, match, rr, now):
        """순위표 1위 행을 가로질러 지나가는 빛줄기 (보통 이상, 움직임 허용일 때)"""
        if self._fx_mode(match) < FX_NORMAL or not self._fx_motion(match):
            return
        u = (now * 0.45) % 1.7
        lv = self._fx_level(match, 0.6, cap=2)
        prev = CANVAS.display.get_clip()
        CANVAS.display.set_clip(CANVAS.rect(rr))
        add_glow("band", rr.x + u * rr.w - 140, rr.y - 8, 280, rr.h + 16, (255, 225, 120), lv)
        CANVAS.display.set_clip(prev)

    # ---------------------------------------------------------------- 8. 미니 카드 소량 강화
    def _card_wave_alpha(self, match, board_rect, now):
        """단계가 오를 때 카드 위를 왼쪽에서 오른쪽으로 지나가는 옅은 빛 물결의 세기(0~40). 번쩍임 설정이 꺼져 있으면 0"""
        fx = getattr(self, "_phase_fx", None)
        if fx is None or self._fx_mode(match) < FX_NORMAL or not getattr(match, "flash_enabled", True):
            return 0
        age = now - fx["t0"]
        if age > 0.9:
            return 0
        front = age / 0.9 * (self.width + 400) - 200
        return int(max(0.0, 1.0 - abs(board_rect.centerx - front) / 200.0) * 40)

    def _card_extras(self, match, pid, p, board_rect, now, is_alive):
        """미니 카드 위 소량 강화: (b) 나를 쏜 상대 카드의 붉은 테두리 번쩍(0.15초, 색 테두리라 번쩍임 설정과 무관하게 안전),
        (c) 최후의 10% 카드의 얇은 금빛 테두리. 색에만 기대지 않게 기존 조준 표시(브래킷/글자)와 함께 쓰임"""
        if not is_alive:
            return
        shot = p.get("shot_t")
        if shot is not None and now - shot < 0.15:
            a = int(230 * (1.0 - (now - shot) / 0.15))
            CANVAS.alpha_rect(board_rect.inflate(4, 4), (255, 80, 90, a), width=2, radius=4)
        total = max(1, getattr(match, "total_players", 1))
        if total >= 8 and match.alive_count <= max(2, int(round(total * 0.1))) and not getattr(match, "match_finished", False):
            CANVAS.alpha_rect(board_rect.inflate(2, 2), (255, 210, 90, 120), width=1, radius=4)
