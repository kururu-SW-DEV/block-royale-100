"""
Block Royale 100 - 타이틀 로고
  - "BLOCK" 글자를 실제 테트로미노(4칸 블록) 조각들로 조립해서 표현합니다.
    글자 도안을 테트로미노로 빈틈없이 채우는 정확한 타일링을 프로그램이 찾아 조각마다 고유 색을 입힙니다.
  - 메뉴 진입 시 조각들이 위에서 떨어져 글자를 완성하는 연출 후, 완성된 로고는 캐시된 이미지로 그립니다.
  - 왕관(블록 제작) 부유 / 보석 반짝임 / 주기적인 빛 스윕 / ROYALE 100 열기
"""

import math
import random
import time
import pygame
from gfx import CANVAS, HiFont, HiSurf, mix_color as _mix
from config import PIECE_COLORS, TETROMINOES


# 6x6 블록 글자 도안 (칸 수가 모두 4의 배수 -> 테트로미노로 정확히 채울 수 있음)
LETTERS = {
    "B": ["XXXX..",
          "XX.XX.",
          "XXXX..",
          "XX.XX.",
          "XX.XX.",
          "XXXX.."],
    "L": ["XX....",
          "XX....",
          "XX....",
          "XX....",
          "XX....",
          "XXXXXX"],
    "O": [".XXXX.",
          "XX..XX",
          "XX..XX",
          "XX..XX",
          "XX..XX",
          ".XXXX."],
    "C": [".XXXX.",
          "XX..XX",
          "XX....",
          "XX....",
          "XX..XX",
          ".XXXX."],
    "K": ["XX..XX",
          "XX.XX.",
          "XXXX..",
          "XXXX..",
          "XX.XX.",
          "XX..XX"],
}
WORD = "BLOCK"
LETTER_KEYS = ["I", "T", "O", "S", "J"]     # 글자별 색 (config.PIECE_COLORS 키): 핑크-앰버-민트-스카이-바이올렛

# 왕관 도안: X = 몸통, 소문자 = 보석
CROWN = [
    "X...X...X",
    "XX.XXX.XX",
    "XXXXXXXXX",
    "XXXXXXXXX",
    "LjLiLzLjL",
]
JEWELS = {"j": "J", "i": "S", "z": "Z"}
ROW_PIECE = {0: "Y1", 1: "Y1", 2: "Y1", 3: "Y1", 4: "Y2"}


def _shapes():
    """테트로미노 7종 x 회전을 정규화(중복 제거)한 목록: [(piece, [(dx, dy), ...]), ...]"""
    out = []
    for piece, rots in TETROMINOES.items():
        seen = set()
        for shape in rots:
            mx = min(x for x, _ in shape)
            my = min(y for _, y in shape)
            norm = tuple(sorted((x - mx, y - my) for x, y in shape))
            if norm not in seen:
                seen.add(norm)
                out.append((piece, list(norm)))
    return out


def tile_with_tetrominoes(cells, seed):
    """cells(집합)를 테트로미노로 빈틈없이 채우는 배치를 찾아 [(piece, [(x, y) x4]), ...] 로 반환. 불가능하면 None."""
    rng = random.Random(seed)
    shapes = _shapes()
    remaining = set(cells)
    placed = []

    def dfs():
        if not remaining:
            return True
        first = min(remaining, key=lambda c: (c[1], c[0]))
        options = []
        for piece, shape in shapes:
            for ax, ay in shape:
                ox, oy = first[0] - ax, first[1] - ay
                placed_cells = [(x + ox, y + oy) for x, y in shape]
                if all(c in remaining for c in placed_cells):
                    options.append((piece, placed_cells))
        rng.shuffle(options)
        for piece, pc in options:
            for c in pc:
                remaining.discard(c)
            placed.append((piece, pc))
            if dfs():
                return True
            placed.pop()
            for c in pc:
                remaining.add(c)
        return False

    return placed if dfs() else None


def _ease_out_bounce(t):
    t = max(0.0, min(1.0, t))
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


class Logo:
    CELL = 18            # 타이틀 블록 한 칸 (논리 px)
    LETTER_GAP = 10      # 글자 사이 간격 (논리 px)
    CROWN_CELL = 14
    DROP_DURATION = 0.85
    STAGGER = 0.07

    def __init__(self, renderer, font_name):
        self.r = renderer
        self.f_sub = HiFont(font_name, 40, bold=True)
        self.f_badge = HiFont(font_name, 34, bold=True)
        self._ver = -1
        self._logo = None
        self._sub_layer = None
        self._face = None
        self._crown = None
        self.size = (0, 0)
        self._anim_start = time.time()
        self._pieces = self._layout_pieces()

    def restart(self, fast=False):
        """조립 연출을 처음부터 다시 재생. fast=True(게임에서 메뉴로 돌아올 때)는 조각 간격과 낙하 시간을 줄여 빨리 완성"""
        self.STAGGER = 0.03 if fast else Logo.STAGGER
        self.DROP_DURATION = 0.5 if fast else Logo.DROP_DURATION
        for p in self._pieces:
            p["delay"] = p["order"] * self.STAGGER
        self.anim_total = self._pieces[-1]["delay"] + self.DROP_DURATION if self._pieces else 0
        self._anim_start = time.time()

    # ------------------------------------------------------------ 글자 -> 테트로미노 조각 배치 (해상도 무관, 1회)
    def _layout_pieces(self):
        cs = self.CELL
        pad = 10
        pieces = []
        x0 = pad
        order = 0
        for li, ch in enumerate(WORD):
            grid = LETTERS[ch]
            cells = {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == "X"}
            tiles = tile_with_tetrominoes(cells, seed=1000 + li * 7 + 3)
            if tiles is None:                                  # 도안 오류 대비 (테스트로 검증됨)
                tiles = [("O", [c]) for c in sorted(cells)]
            tiles.sort(key=lambda t: (min(y for _, y in t[1]), min(x for x, _ in t[1])))
            for piece, pcs in tiles:
                pos = [(x0 + x * cs, pad + y * cs) for x, y in pcs]
                pset = set(pos)
                seams = []
                for (cx_, cy_) in pos:
                    if (cx_ + cs, cy_) in pset:
                        seams.append((cx_ + cs - 2, cy_ + 3, 4, cs - 6))
                    if (cx_, cy_ + cs) in pset:
                        seams.append((cx_ + 3, cy_ + cs - 2, cs - 6, 4))
                pieces.append({
                    "piece": LETTER_KEYS[li],          # 글자 단위로 무지개 색 (조각 경계는 어두운 테두리로 보임)
                    "shape": piece,
                    "seams": seams,
                    "cells": pos,
                    "order": order,
                    "delay": order * self.STAGGER,
                    "drop": 90 + 14 * (min(y for _, y in pcs)),
                })
                order += 1
            x0 += 6 * cs + self.LETTER_GAP
        self._title_size = (x0 - self.LETTER_GAP + pad, pad + 6 * cs + pad + 6)
        self.anim_total = pieces[-1]["delay"] + self.DROP_DURATION if pieces else 0
        return pieces

    # ------------------------------------------------------------ 캐시 빌드
    def _px(self, v):
        return int(round(v * CANVAS.S))

    def _build(self):
        S = CANVAS.S
        cs = self.CELL
        tw, th = self._title_size

        # 1) 타이틀: 그림자 + 블록 + (마스크용) 블록만 있는 레이어
        title = HiSurf((self._px(tw), self._px(th)), pygame.SRCALPHA, S)
        face = HiSurf((self._px(tw), self._px(th)), pygame.SRCALPHA, S)
        shadow_cell = HiSurf((self._px(cs), self._px(cs)), pygame.SRCALPHA, S)
        pygame.draw.rect(shadow_cell, (4, 6, 16, 170), (0, 0, self._px(cs), self._px(cs)),
                         border_radius=self._px(3))
        for p in self._pieces:
            for x, y in p["cells"]:
                title.blit(shadow_cell, (self._px(x), self._px(y + 6)))
        for p in self._pieces:
            cell = self.r._cell_surface(p["piece"], cs, skin="classic")
            seam_col = PIECE_COLORS.get(p["piece"], (180, 180, 200))
            for x, y in p["cells"]:
                title.blit(cell, (self._px(x), self._px(y)))
                face.blit(cell, (self._px(x), self._px(y)))
            for (sx_, sy_, sw_, sh_) in p["seams"]:        # 같은 조각의 칸 사이 이음새를 메워 한 덩어리로 보이게
                r_ = pygame.Rect(self._px(sx_), self._px(sy_), self._px(sw_), self._px(sh_))
                pygame.draw.rect(title, seam_col, r_)
                pygame.draw.rect(face, seam_col, r_)

        # 2) ROYALE + 100 열기
        gold = (255, 214, 90)
        sub, sw, sh = self._render_royale(gold)
        b_txt = self.f_badge.render("100", True, (30, 20, 6))
        bw, bh = b_txt.get_size()
        badge_w, badge_h = bw + 30, bh + 6

        W = max(tw, sw + 24 + badge_w + 24)
        H = th + sh + 2
        logo = HiSurf((self._px(W), self._px(H)), pygame.SRCALPHA, S)
        sublayer = HiSurf((self._px(W), self._px(H)), pygame.SRCALPHA, S)

        # 타이틀 뒤 글로우 (축소 -> 확대로 블러)
        rw, rh = pygame.Surface.get_size(title)
        small = pygame.transform.smoothscale(title, (max(1, rw // 10), max(1, rh // 10)))
        glow = pygame.transform.smoothscale(small, (rw, rh))
        glow.set_alpha(150)
        tx = (W - tw) // 2
        logo.blit(glow, (self._px(tx), 0))
        logo.blit(title, (self._px(tx), 0))
        face_full = HiSurf((self._px(W), self._px(H)), pygame.SRCALPHA, S)
        face_full.blit(face, (self._px(tx), 0))

        row_w = sw + 24 + badge_w
        sx = (W - row_w) // 2
        sy = th - 6
        for layer in (logo, sublayer):
            layer.blit(sub, (self._px(sx), self._px(sy)))
            bx, by = sx + sw + 24, sy + (sh - badge_h) // 2 + 2
            pygame.draw.rect(layer, (120, 80, 10), pygame.Rect(self._px(bx), self._px(by + 3), self._px(badge_w), self._px(badge_h)),
                             border_radius=self._px(10))
            pygame.draw.rect(layer, gold, pygame.Rect(self._px(bx), self._px(by), self._px(badge_w), self._px(badge_h)),
                             border_radius=self._px(10))
            pygame.draw.rect(layer, (255, 236, 150), pygame.Rect(self._px(bx + 3), self._px(by + 3), self._px(badge_w - 6), self._px(badge_h - 6)),
                             border_radius=self._px(8))
            layer.blit(b_txt, (self._px(bx + (badge_w - bw) // 2), self._px(by + (badge_h - bh) // 2)))

        self._logo, self._sub_layer, self._face = logo, sublayer, face_full
        self.size = (W, H)
        self._title_x = tx

        # 3) 왕관
        cs2 = self.CROWN_CELL
        cw, ch_ = len(CROWN[0]) * cs2, len(CROWN) * cs2
        crown = HiSurf((self._px(cw), self._px(ch_)), pygame.SRCALPHA, S)
        for row, line in enumerate(CROWN):
            for col, c in enumerate(line):
                if c == ".":
                    continue
                piece = JEWELS.get(c) or ROW_PIECE[row]
                crown.blit(self.r._cell_surface(piece, cs2, skin="classic"), (self._px(col * cs2), self._px(row * cs2)))
        self._crown = crown
        self._crown_size = (cw, ch_)

    def _render_royale(self, color):
        """금색 그라데이션 + 외곽선 + 두께를 가진 'ROYALE' (글자 간격 넓게)"""
        text, spacing, depth, outline = "ROYALE", 18, 4, 2
        font = self.f_sub
        widths = [font.size(ch)[0] for ch in text]
        total = sum(widths) + spacing * (len(text) - 1)
        pad = outline + 4
        W = total + pad * 2
        H = font.get_height() + depth + pad * 2
        layer = HiSurf((self._px(W), self._px(H)), pygame.SRCALPHA, CANVAS.S)
        edge = (8, 11, 26)
        x = pad
        for ch, w in zip(text, widths):
            o = font.render(ch, True, edge)
            for dx in range(-outline, outline + 1):
                for dy in range(-outline, outline + 1):
                    layer.blit(o, (self._px(x + dx), self._px(pad + dy)))
            side = font.render(ch, True, _mix(color, (0, 0, 0), 0.7))
            for d in range(depth, 0, -1):
                layer.blit(side, (self._px(x), self._px(pad + d)))
            face = font.render(ch, True, (255, 255, 255))
            fw, fh = pygame.Surface.get_size(face)
            grad = HiSurf((fw, fh), pygame.SRCALPHA, CANVAS.S)
            for yy in range(fh):
                t = yy / max(1, fh - 1)
                c = _mix(_mix(color, (255, 255, 255), 0.55), color, t / 0.45) if t < 0.45 else _mix(color, _mix(color, (0, 0, 0), 0.3), (t - 0.45) / 0.55)
                pygame.draw.line(grad, (*c, 255), (0, yy), (fw, yy))
            grad.blit(face, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            layer.blit(grad, (self._px(x), self._px(pad)))
            x += w + spacing
        return layer, W, H

    # ------------------------------------------------------------ 그리기
    def draw(self, screen, cx, top):
        """cx: 가로 중심, top: 왕관 상단 y (논리 좌표). 로고 전체 높이를 반환."""
        if self._ver != CANVAS.version or self._logo is None:
            self.r._check_ver()
            self._build()
            self._ver = CANVAS.version
        now = time.time()
        elapsed = now - self._anim_start

        cw, ch_ = self._crown_size
        W, H = self.size
        lx, ly = cx - W // 2, top + ch_ + 4

        # 왕관: 조립 초반에 위에서 내려와 자리잡음, 이후 천천히 부유
        drop_in = 1.0 - _ease_out_bounce(min(1.0, elapsed / 0.9)) if elapsed < 0.9 else 0.0
        bob = math.sin(now * 1.6) * 3
        crown_x, crown_y = cx - cw // 2, top + bob - drop_in * 140
        screen.blit(self._crown, (crown_x, crown_y))
        if elapsed > 1.0:
            self._sparkles(screen, crown_x, crown_y, now)

        if elapsed < self.anim_total + 0.5:
            self._draw_assembly(screen, lx + self._title_x, ly, elapsed)
            # ROYALE 열기는 조립이 거의 끝날 무렵 페이드인
            fade = max(0.0, min(1.0, (elapsed - (self.anim_total - 0.5)) / 0.5))
            if fade > 0:
                self._sub_layer.set_alpha(int(255 * fade))
                screen.blit(self._sub_layer, (lx, ly))
        else:
            screen.blit(self._logo, (lx, ly))
            self._shine(screen, lx, ly, now)
        return ch_ + 4 + H

    def _draw_assembly(self, screen, ox, oy, elapsed):
        """조각들이 순서대로 떨어지며 글자를 만드는 연출"""
        for p in self._pieces:
            t = (elapsed - p["delay"]) / self.DROP_DURATION
            if t <= 0:
                continue
            k = _ease_out_bounce(t) if t < 1 else 1.0
            y_off = -(1.0 - k) * p["drop"]
            cell = self.r._cell_surface(p["piece"], self.CELL, skin="classic")
            for x, y in p["cells"]:
                screen.blit(cell, (ox + x, oy + y + y_off))
            seam_col = PIECE_COLORS.get(p["piece"], (180, 180, 200))
            for (sx_, sy_, sw_, sh_) in p["seams"]:
                pygame.draw.rect(screen, seam_col, (ox + sx_, oy + sy_ + y_off, sw_, sh_))

    def _sparkles(self, screen, x, y, now):
        """왕관 보석 위치에서 반짝이는 4각 별"""
        cs = self.CROWN_CELL
        spots = [(1, 4, 0.0), (3, 4, 0.9), (5, 4, 1.7), (7, 4, 2.4), (0, 0, 2.3), (8, 0, 3.1), (4, 0, 0.4)]
        for col, row, phase in spots:
            t = (now * 0.9 + phase) % 3.0
            if t > 1.0:
                continue
            k = math.sin(t * math.pi)
            px, py = x + col * cs + cs / 2, y + row * cs + cs / 2
            r = 3 + 9 * k
            pygame.draw.line(screen, (255, 255, 255), (px - r, py), (px + r, py), 2)
            pygame.draw.line(screen, (255, 255, 255), (px, py - r), (px, py + r), 2)
            pygame.draw.line(screen, (255, 240, 180), (px - r * 0.55, py - r * 0.55), (px + r * 0.55, py + r * 0.55), 1)
            pygame.draw.line(screen, (255, 240, 180), (px - r * 0.55, py + r * 0.55), (px + r * 0.55, py - r * 0.55), 1)

    def _shine(self, screen, lx, ly, now):
        """블록 윗면 위로 비스듬한 빛줄기가 주기적으로 지나감"""
        period, dur = 5.5, 1.0
        t = (now - self._anim_start - self.anim_total) % period
        if t > dur:
            return
        p = t / dur
        W, H = self.size
        rw, rh = pygame.Surface.get_size(self._face)
        band = pygame.Surface((rw, rh), pygame.SRCALPHA)
        x0 = -120 + p * (W + 240)
        slant = 60
        for width, alpha in [(70, 70), (44, 120), (20, 190)]:
            pts = [(x0 - width / 2 + slant, 0), (x0 + width / 2 + slant, 0),
                   (x0 + width / 2 - slant, H), (x0 - width / 2 - slant, H)]
            pygame.draw.polygon(band, (255, 255, 255, alpha), [(self._px(a), self._px(b)) for a, b in pts])
        band.blit(self._face, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        band.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_MAX)
        hs = HiSurf((rw, rh), pygame.SRCALPHA, CANVAS.S)
        hs.blit(band, (0, 0))
        screen.blit(hs, (lx, ly))
