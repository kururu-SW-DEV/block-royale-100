"""
Block Royale 100 - In-game UI Renderer
1366x768 해상도에서 1개의 메인 보드와 최대 99개의 주변 미니 보드를 렌더링합니다.
깔끔한 글래스 패널 + 네온 액센트 스타일, 시인성과 조작성(조작 안내 / 조준 모드 표시 / 락 딜레이 바)에 초점을 맞춘 UI.
"""

import time
import math
import random
import pygame
from gfx import CANVAS, HiFont, mix_color as _mix
from config import NAME_COLORS
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BOARD_WIDTH, BOARD_HEIGHT,
    TETROMINOES, PIECE_COLORS, TARGET_MODES, BADGE_TIERS
)

# ---------------------------------------------------------------- 팔레트
C_BG_TOP = (14, 17, 30)
C_BG_BOTTOM = (8, 9, 16)
C_PANEL = (20, 25, 42)
C_PANEL_BORDER = (52, 64, 98)
C_TEXT = (235, 240, 252)
C_DIM = (130, 142, 170)
C_ACCENT = (90, 205, 255)
C_GOLD = (255, 205, 90)
C_GREEN = (95, 235, 165)
C_DANGER = (255, 85, 95)
C_ORANGE = (255, 165, 70)

BUTTON_STYLES = {
    "green": ((24, 78, 56), (36, 112, 80), (95, 235, 165)),
    "gold": ((92, 68, 22), (130, 96, 30), (255, 205, 90)),
    "blue": ((24, 56, 104), (36, 82, 150), (110, 190, 255)),
    "red": ((92, 30, 40), (130, 42, 56), (255, 110, 125)),
}

TARGET_MODE_LABELS = {
    "AUTO": "자동", "KO": "K.O.", "ATTACKERS": "반격", "BADGES": "배지", "RANDOM": "랜덤"
}


_orig_rect = CANVAS._orig["rect"]          # 좌표 변환을 거치지 않는 원래 pygame.draw.rect


class ParticleManager:
    """스파크 및 충격파 링 이펙트 매니저"""
    def __init__(self):
        self.particles = []
        self.rings = []

    def add_sparks(self, x, y, color, count=30, speed_mult=1.0):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(80, 340) * speed_mult
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 50,
                "color": color,
                "size": random.choice([2, 3, 4]),
                "life": 0.0,
                "max_life": random.uniform(0.3, 0.6),
            })
        # 과도한 파티클 누적 방지
        if len(self.particles) > 320:
            del self.particles[:len(self.particles) - 320]

    def add_shockwave(self, x, y, color, max_radius=80):
        self.rings.append({
            "x": x, "y": y, "radius": 4.0, "max_radius": max_radius,
            "color": color, "life": 0.0, "max_life": 0.35, "alpha": 255
        })

    def update(self, dt):
        alive_p = []
        for p in self.particles:
            p["life"] += dt
            if p["life"] < p["max_life"]:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vy"] += 450 * dt
                p["vx"] *= (1.0 - dt * 2.0)
                alive_p.append(p)
        self.particles = alive_p

        alive_r = []
        for r in self.rings:
            r["life"] += dt
            if r["life"] < r["max_life"]:
                progress = r["life"] / r["max_life"]
                r["radius"] = 4.0 + (r["max_radius"] - 4.0) * math.sin(progress * math.pi * 0.5)
                r["alpha"] = max(0, int(255 * (1.0 - progress)))
                alive_r.append(r)
        self.rings = alive_r

    def draw(self, surface, ox=0, oy=0):
        for r in self.rings:
            rx, ry = int(r["x"] + ox), int(r["y"] + oy)
            rad = max(1, int(r["radius"]))
            ring_surf = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(ring_surf, (*r["color"][:3], r["alpha"]), (2, 2 + rad // 2, rad * 2, rad), 2)
            surface.blit(ring_surf, (rx - rad - 2, ry - rad // 2 - 2))

        for p in self.particles:
            fade = 1.0 - p["life"] / p["max_life"]
            sz = max(1, int(p["size"] * (0.5 + 0.5 * fade)))
            pygame.draw.rect(surface, p["color"], (int(p["x"] + ox), int(p["y"] + oy), sz, sz))


class UIRenderer:
    def __init__(self, screen):
        self.screen = CANVAS.attach(screen)   # 논리 좌표(1366x768)로 그리면 실제 해상도에 맞춰 변환됨
        self.width = SCREEN_WIDTH
        self.height = SCREEN_HEIGHT

        pygame.font.init()
        self.text_boost = 0                 # 글자 크기 옵션(크게=+2): 작은 글씨 세 가지(mid/small/tiny)에 적용
        self._build_fonts()

        self.text_cache = {}
        self._ver = -1
        self.bg_surface = None
        self._panel_cache = {}
        self._overlay_cache = {}
        self._mini_layers = {}      # 미니 보드별 쌓인 블록 레이어 캐시 {pid: (key, surface)}
        self._card_layers = {}      # 미니 카드별 이름표/홀드·다음 칸 레이어 캐시 {(pid, 종류): (key, 원점, surface)}
        self._card_info = {}        # 미니 카드별 이름/K.O./홀드 표시 계산 결과 캐시 {pid: (신호값, ...)}
        self._mini_tabs = {}        # 미니 카드별 칸 좌표 표(작은 칸 그리기 가속) {pid: (key, XL, XR, YT, YB)}
        self._pcol = {}             # 조작 중인 블록 색 캐시
        self.mini_fast = True       # False면 예전 방식(매 프레임 전부 그림)으로 그림: 새 방식과 픽셀 비교하는 테스트용 기준
        self._mini_ghost = {}       # 미니 보드별 착지 위치 캐시 {pid: (key, drop)}
        self._cell_cache = {}
        self._ghost_cache = {}
        self.particles = ParticleManager()
        self.last_cleared_count = 0
        self.key_hints = []          # [(키, 설명)] - main에서 매 프레임 갱신
        self.chat_entries = []       # 네트워크 게임 채팅 기록 (main에서 매 프레임 갱신)
        self.chat_input = None       # 채팅 입력창이 열려 있으면 입력 중인 글자, 아니면 None
        self.chat_comp = ""           # IME 조합 중인 글자 (한글 입력)
        self.chat_my_id = ""
        self._standings_t0 = None    # 최종 순위표 애니메이션 시작 시각
        self.standings_scroll = 0

        # 메인 보드 규격
        self.cell_size = 29
        self.main_board_w = BOARD_WIDTH * self.cell_size
        self.main_board_h = BOARD_HEIGHT * self.cell_size
        self.main_board_x = (self.width - self.main_board_w) // 2
        self.main_board_y = 112

        self.mini_board_rects = {}
        self.mini_detailed = True        # 미니 보드 자세히 보기 (설정에서 변경): 조작 중 블록/착지 위치/홀드/다음 블록
        self.line_clear_flashes = []
        self.lock_flashes = []
        self._lock_seen = (None, 0)
        self.board_impact_flashes = {}
        self.result_return_btn = None
        self.result_restart_btn = None
        self.result_spectate_btn = None
        self.result_focus_id = "return"     # 결과 화면 키보드 포커스 (restart/spectate/return)
        self.pause_resume_btn = None
        self.pause_settings_btn = None
        self.pause_exit_btn = None
        self.pause_focus = 0            # 일시정지 메뉴 키보드 포커스 (0=계속하기 1=환경설정 2=나가기)

    # ---------------------------------------------------------------- 공용 헬퍼
    def _check_ver(self):
        """해상도(배율)가 바뀌면 네이티브 해상도로 만들어진 캐시를 모두 폐기"""
        if self._ver != CANVAS.version:
            self._ver = CANVAS.version
            self.text_cache.clear()
            self._panel_cache.clear()
            self._cell_cache.clear()
            self._ghost_cache.clear()
            self._overlay_cache.clear()
            self._mini_layers.clear()
            self._card_layers.clear()
            self._mini_tabs.clear()
            self._pcol.clear()
            self._card_info.clear()
            self.bg_surface = None

    def _build_fonts(self):
        font_name = "malgungothic,segoeui,consolas,arial"
        bo = self.text_boost
        self.font_title = HiFont(font_name, 34, bold=True)
        self.font_large = HiFont(font_name, 26, bold=True)
        self.font_big_num = HiFont(font_name, 24, bold=True)
        self.font_num = HiFont(font_name, 21, bold=True)      # 상단 HUD 숫자 (게이지와 겹치지 않는 크기)
        self.font_mid = HiFont(font_name, 16 + bo, bold=True)
        self.font_hud = HiFont(font_name, 17, bold=True)
        self.font_small = HiFont(font_name, 13 + bo, bold=True)
        self.font_tiny = HiFont(font_name, 12 + bo, bold=True)

    def set_text_boost(self, boost):
        """게임 화면 글자 크기 옵션 적용: 글꼴을 다시 만들고 글자/패널 캐시를 비움"""
        if boost == self.text_boost:
            return
        self.text_boost = boost
        self._build_fonts()
        self.clear_visual_caches()

    def clear_visual_caches(self):
        """색상 팔레트/글자 크기가 바뀌었을 때 그것으로 만들어 둔 캐시를 모두 비움"""
        for name in ("text_cache", "_panel_cache", "_cell_cache", "_ghost_cache", "_overlay_cache", "_mini_layers", "_card_layers", "_mini_ghost", "_mini_tabs", "_pcol", "_card_info"):
            c = getattr(self, name, None)
            if c is not None:
                c.clear()
        self.bg_surface = None
        self._led_bg_caches = {}

    def _blit_card_layer(self, slot, key, x, y, w, h, draw):
        """미니 카드의 자주 안 바뀌는 부분(이름표, 홀드/다음 칸)을 오프스크린에 한 번 그려 두고 한 장으로 붙임.
        draw()는 원래 그리기 코드 그대로이며, CANVAS의 출력 대상/원점만 잠시 바꿔 같은 좌표 반올림으로 그림 (_blit_mini_cells와 같은 방식)"""
        if not self.mini_fast:
            draw()
            return
        self._check_ver()
        X0, Y0 = CANVAS.X(x), CANVAS.Y(y)
        X0 -= X0 % 2
        Y0 -= Y0 % 2
        ent = self._card_layers.get(slot)
        if ent is None or ent[0] != key or ent[1] != (X0, Y0):
            surf = pygame.Surface((max(1, CANVAS.X(x + w) - X0 + 4), max(1, CANVAS.Y(y + h) - Y0 + 4)), pygame.SRCALPHA)
            saved = (CANVAS.display, CANVAS.ox, CANVAS.oy)
            CANVAS.display, CANVAS.ox, CANVAS.oy = surf, saved[1] - X0, saved[2] - Y0
            try:
                draw()
            finally:
                CANVAS.display, CANVAS.ox, CANVAS.oy = saved
            ent = self._card_layers[slot] = (key, (X0, Y0), surf)
        CANVAS.display.blit(ent[2], (X0, Y0))

    def _blit_overlay(self, key, size, build, pos, alpha=None):
        """알파 오버레이를 해상도별로 한 번만 만들어(네이티브 크기로 확대해) 재사용. 프레임마다 Surface 생성/확대를 하지 않음.
        build(surface): 논리 크기(size)의 SRCALPHA 서피스에 그리는 함수. 결과는 CANVAS.blit과 동일한 방식으로 확대·배치됨"""
        self._check_ver()
        surf = self._overlay_cache.get(key)
        if surf is None:
            w, h = size
            base = pygame.Surface((w, h), pygame.SRCALPHA)
            build(base)
            tw, th = CANVAS.length(w, 1), CANVAS.length(h, 1)
            if abs(CANVAS.S - 1.0) < 1e-3:
                surf = base
            else:
                try:
                    surf = pygame.transform.smoothscale(base, (tw, th))
                except ValueError:
                    surf = pygame.transform.scale(base, (tw, th))
            self._overlay_cache[key] = surf
        if alpha is not None:
            surf.set_alpha(alpha)
        CANVAS.display.blit(surf, (CANVAS.X(pos[0]), CANVAS.Y(pos[1])))

    def _bg(self):
        """배경 그라데이션 (네이티브 해상도로 1회 생성)"""
        self._check_ver()
        if self.bg_surface is None:
            surf = CANVAS.make_surface(self.width, self.height, alpha=False)
            w, h = pygame.Surface.get_size(surf)
            for y in range(h):
                pygame.draw.line(surf, _mix(C_BG_TOP, C_BG_BOTTOM, y / h), (0, y), (w, y))
            self.bg_surface = surf
        return self.bg_surface

    def _text(self, text, font, color):
        self._check_ver()
        key = (text, id(font), color)
        surf = self.text_cache.get(key)
        if surf is None:
            if len(self.text_cache) > 800:
                self.text_cache.clear()
            surf = font.render(text, True, color)
            self.text_cache[key] = surf
        return surf

    def _draw_text(self, text, font, color, x, y, anchor="topleft", shadow=False):
        surf = self._text(text, font, color)
        rect = surf.get_rect()
        setattr(rect, anchor, (int(x), int(y)))
        if shadow:
            self.screen.blit(self._text(text, font, (0, 0, 0)), (rect.x + 1, rect.y + 1))
        self.screen.blit(surf, rect)
        return rect

    def _panel(self, rect, border=C_PANEL_BORDER, bg=C_PANEL, radius=10, alpha=225, border_w=1):
        self._check_ver()
        rect = pygame.Rect(rect)
        key = (rect.w, rect.h, border, bg, radius, alpha, border_w)
        surf = self._panel_cache.get(key)
        if surf is None:
            S = CANVAS.S
            surf = CANVAS.make_surface(rect.w, rect.h)
            w, h = pygame.Surface.get_size(surf)
            pygame.draw.rect(surf, (*bg[:3], alpha), (0, 0, w, h), border_radius=int(round(radius * S)))
            pygame.draw.rect(surf, (*border[:3], 255), (0, 0, w, h), max(1, int(round(border_w * S))),
                             border_radius=int(round(radius * S)))
            if h >= 24 and w >= 24:                                    # 위쪽 안쪽 가장자리의 얇은 유리 하이라이트 (질감)
                inset = int(round(radius * S)) + 2
                hl_y = max(1, int(round(border_w * S)))
                pygame.draw.line(surf, (255, 255, 255, 20), (inset, hl_y), (w - inset, hl_y), 1)
            self._panel_cache[key] = surf
        self.screen.blit(surf, rect.topleft)

    def _button(self, rect, label, style, hover, key_hint=None):
        base, hov, accent = BUTTON_STYLES[style]
        rect = pygame.Rect(rect)
        if hover:                                            # 호버 글로우 캐시 (해상도/크기/색별 한 번만 생성)
            gw, gh = rect.w + 16, rect.h + 16
            self._blit_overlay(("btnglow2", gw, gh, tuple(accent)), (gw, gh),
                               lambda surf: pygame.draw.rect(surf, (*accent, 55), (0, 0, gw, gh), border_radius=14), (rect.x - 8, rect.y - 8))
        pygame.draw.rect(self.screen, hov if hover else base, rect, border_radius=9)
        pygame.draw.rect(self.screen, accent if hover else _mix(accent, base, 0.45), rect, 2 if hover else 1, border_radius=9)
        label_surf = self._text(label, self.font_mid, (255, 255, 255))
        total_w = label_surf.get_width()
        key_surf = None
        if key_hint:
            key_surf = self._text(key_hint, self.font_tiny, (20, 24, 36))
            total_w += key_surf.get_width() + 22
        tx = rect.centerx - total_w // 2
        if key_surf:
            kr = pygame.Rect(tx, rect.centery - 10, key_surf.get_width() + 14, 20)
            pygame.draw.rect(self.screen, accent, kr, border_radius=5)
            self.screen.blit(key_surf, (kr.x + 7, kr.centery - key_surf.get_height() // 2))
            tx = kr.right + 8
        self.screen.blit(label_surf, (tx, rect.centery - label_surf.get_height() // 2))

    def _draw_bar(self, rect, ratio, color, track=(12, 15, 26)):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, track, rect, border_radius=rect.h // 2)
        fill_w = int(rect.w * max(0.0, min(1.0, ratio)))
        if fill_w > 0:
            pygame.draw.rect(self.screen, color, (rect.x, rect.y, max(fill_w, rect.h), rect.h), border_radius=rect.h // 2)

    # ---------------------------------------------------------------- 메인 렌더
    def render(self, match, sound_mgr=None):
        shake = getattr(match, 'screen_shake', 0.0)
        ox = random.uniform(-shake, shake) if shake > 0 else 0
        oy = random.uniform(-shake, shake) if shake > 0 else 0

        self.particles.update(1.0 / 60.0)
        engine = match.local_engine
        spectating = getattr(match, 'is_spectating', False)

        if engine.lines_cleared_total > self.last_cleared_count:
            self.last_cleared_count = engine.lines_cleared_total
            cx = self.main_board_x + self.main_board_w // 2
            cy = self.main_board_y + self.main_board_h // 2
            self.particles.add_sparks(cx, cy, (255, 230, 120), count=40, speed_mult=1.4)
            self.particles.add_shockwave(cx, cy + 80, (110, 235, 255), max_radius=100)

        # 피스 고정 시 착지 플래시 + 스파크 (하드 드롭/락 공통)
        lock_key = (id(engine), engine.lock_events)
        if lock_key != self._lock_seen:
            self._lock_seen = lock_key
            if engine.lock_events > 0 and not spectating and engine.last_lock_cells:
                self.lock_flashes.append({"cells": list(engine.last_lock_cells), "birth": time.time()})
                bottom = max(y for _, y in engine.last_lock_cells)
                for x, y in engine.last_lock_cells:
                    if y == bottom:
                        self.particles.add_sparks(
                            self.main_board_x + x * self.cell_size + self.cell_size // 2,
                            self.main_board_y + (y + 1) * self.cell_size,
                            (200, 230, 255), count=3, speed_mult=0.6)

        # 라인 제거 시 수평 와이프 플래시
        if engine.cleared_row_indices:
            for r_idx in engine.cleared_row_indices:
                self.line_clear_flashes.append({"row": r_idx, "birth": time.time(), "duration": 0.40})
                row_y = self.main_board_y + r_idx * self.cell_size + self.cell_size // 2
                self.particles.add_sparks(self.main_board_x + 10, row_y, (110, 235, 255), count=10, speed_mult=1.2)
                self.particles.add_sparks(self.main_board_x + self.main_board_w - 10, row_y, (110, 235, 255), count=10, speed_mult=1.2)
                self.particles.add_sparks(self.main_board_x + self.main_board_w // 2, row_y, (255, 255, 255), count=12, speed_mult=1.4)
            engine.cleared_row_indices = []

        CANVAS.display.fill((0, 0, 0))
        self.screen.blit(self._bg(), (0, 0))

        self._render_mini_boards(match, ox, oy)
        self._render_attack_effects(match, ox, oy)
        self._render_main_board(match, ox, oy)
        self.particles.draw(self.screen, ox, oy)
        self._render_top_banner(match, ox, oy)
        if not getattr(match, 'is_paused', False):
            self._render_floating_texts(match, ox, oy)
        if not spectating:
            self._render_key_hints(ox, oy)
        self._render_scoreboard(match)
        self._render_chat_overlay()
        if getattr(match, 'is_paused', False):
            self._render_pause_overlay()

        if spectating and not match.match_finished:
            self._render_spectate_notice(match)
        if match.match_finished:
            self._render_standings_overlay(match)          # 누가 이기든(나 포함) 경기가 끝나면 전체 플레이어 성적표
        elif spectating:
            self._render_spectator_hud(match, ox, oy)
        elif not match.local_is_alive:
            self._render_result_overlay(match)

    # ---------------------------------------------------------------- 텍스트 팝업
    def _render_floating_texts(self, match, ox, oy):
        """
        - 액션 배너(쿼드/T-SPIN 등): 보드 상단부에 반투명 플레이트로 표시 (블록을 가리지 않도록 낮은 불투명도)
        - 전투 토스트(공격/피격/콤보/KO): 보드 위 전용 띠 영역에 최근 2개만 표시
        """
        now = time.time()
        active = [ft for ft in getattr(match, 'floating_texts', []) if now - ft["birth"] < ft["duration"]]
        if not active:
            return

        actions = [ft for ft in active if ft.get("category") == "action"]
        feed = sorted((ft for ft in active if ft.get("category") != "action"), key=lambda f: f["birth"])[-2:]

        cx_board = self.main_board_x + self.main_board_w // 2 + ox

        for slot, ft in enumerate(actions[-2:]):
            progress = (now - ft["birth"]) / ft["duration"]
            alpha = max(0, min(255, int(255 * (1.0 - progress ** 3))))
            # 좌우 패널(홀드/다음 블록)을 가리지 않도록 보드 폭 안에 들어가는 가장 큰 글꼴 선택
            max_w = self.main_board_w + 44
            preferred = [self.font_large, self.font_hud, self.font_small] if ft.get("size", 28) >= 30                 else [self.font_hud, self.font_small]
            font = preferred[-1]
            for cand in preferred:
                if cand.size(ft["text"])[0] + 32 <= max_w:
                    font = cand
                    break
            surf = font.render(ft["text"], True, ft["color"])
            tw, th = surf.get_size()
            cy = self.main_board_y + 140 + slot * (th + 18) - progress * 20 + oy
            plate = pygame.Rect(int(cx_board - (tw + 32) // 2), int(cy), tw + 32, th + 14)
            CANVAS.alpha_rect(plate, (10, 13, 24, int(alpha * 0.78)), radius=10)
            CANVAS.alpha_rect(plate, (*ft["color"][:3], alpha), width=2, radius=10)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (plate.x + 16, plate.y + 7))

        strip_y = 68
        for i, ft in enumerate(feed):
            progress = (now - ft["birth"]) / ft["duration"]
            alpha = max(0, min(255, int(255 * (1.0 - progress ** 4))))
            surf = self.font_small.render(ft["text"], True, ft["color"])
            tw, th = surf.get_size()
            plate = pygame.Rect(int(cx_board - (tw + 24) // 2), strip_y + i * 22 + int(oy), tw + 24, 22)
            CANVAS.alpha_rect(plate, (10, 13, 24, int(alpha * 0.88)), radius=11)
            CANVAS.alpha_rect(plate, (*ft["color"][:3], int(alpha * 0.9)), width=1, radius=11)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (plate.x + 12, plate.y + (22 - th) // 2))

    # ---------------------------------------------------------------- 채팅
    def wrap(self, text, font, max_w):
        """글자 단위 줄바꿈 (한글 포함)"""
        lines, cur = [], ""
        for ch in text:
            if cur and font.size(cur + ch)[0] > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines or [""]

    def chat_color(self, entry, my_id=None):
        """이름 색 (시스템 메시지는 금빛)"""
        if entry.get("sys"):
            return (200, 170, 90)
        idx = entry.get("color", 0)
        return NAME_COLORS[idx][1] if isinstance(idx, int) and 0 <= idx < len(NAME_COLORS) else C_TEXT

    def chat_lines(self, entries, font, width):
        """채팅 기록 -> 줄바꿈된 줄 목록. 각 줄은 [(글자, 색), ...] 조각 리스트 (이름은 고른 색, 내용은 밝은 회색)"""
        body = (222, 228, 242)
        out = []
        for e in entries:
            if e.get("sys"):
                for ln in self.wrap(e["text"], font, width):
                    out.append([(ln, (200, 170, 90))])
                continue
            prefix = f"{e['name']}: "
            name_col = self.chat_color(e)
            for i, ln in enumerate(self.wrap(prefix + e["text"], font, width)):
                if i == 0 and ln.startswith(prefix):
                    out.append([(prefix, name_col), (ln[len(prefix):], body)])
                else:
                    out.append([(ln, body)])
        return out

    def draw_segments(self, segs, font, x, y):
        for text, col in segs:
            if text:
                rect = self._draw_text(text, font, col, x, y)
                x += rect.w

    # ---------------------------------------------------------------- LED 전광판 (도트 매트릭스 전광판 글씨)
    LED_PITCH = 3           # 도트 간격 (논리 px)
    LED_BASE_SPEED = 38.0   # 전광판 기본 속도 (열/초)
    LED_MAX_SPEEDUP = 2.8   # 방송이 많이 밀렸을 때 최대 배율
    LED_BG = (8, 7, 6)

    def _led_font_get(self):
        if getattr(self, "_led_font", None) is None:
            self._led_font = pygame.font.SysFont("gulim,dotum,malgungothic,arial", 12)     # 비트맵 느낌이 나는 작은 글꼴
        return self._led_font

    def _led_build(self, items, rows):
        """중계 문구들을 안티앨리어싱 없는 도트 열 목록으로 변환: cols[x] = [(row, color), ...]"""
        font = self._led_font_get()
        cols = []
        gap = 14
        for n, e in enumerate(items):
            surf = font.render(e["text"], False, (255, 255, 255)).convert_alpha()
            w, h = surf.get_size()
            r0 = max(0, (rows - h) // 2)
            base = len(cols)
            cols.extend([] for _ in range(w))
            for x in range(w):
                for y in range(h):
                    if surf.get_at((x, y)).a > 128 and y + r0 < rows:
                        cols[base + x].append((y + r0, e["color"]))
            gcols = [[] for _ in range(gap)]                       # 문구 사이 구분 점
            mid = rows // 2
            dim = _mix(e["color"], self.LED_BG, 0.45)
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                gcols[gap // 2 + dx].append((mid + dy, dim))
            cols.extend(gcols)
        return cols

    def _led_panel_bg(self, rect):
        """전광판 틀과 꺼진 도트 배경 (해상도별로 한 번만 만들어 재사용)"""
        P = self.LED_PITCH
        ncols, nrows = (rect.w - 12) // P, (rect.h - 8) // P
        x0, y0 = rect.x + 7, rect.y + 5
        key = (CANVAS.version, rect.x, rect.y, rect.w, rect.h)
        caches = self.__dict__.setdefault("_led_bg_caches", {})
        cache = caches.get(rect.x)
        if cache is None or cache[0] != key:
            outer = CANVAS.rect(rect.inflate(4, 4))
            surf = pygame.Surface(outer.size, pygame.SRCALPHA)
            orig = CANVAS._orig["rect"]
            orig(surf, (52, 56, 70), (0, 0, outer.w, outer.h), 0, border_radius=int(8 * CANVAS.S))
            inner = CANVAS.rect(rect)
            ix, iy = inner.x - outer.x, inner.y - outer.y
            orig(surf, self.LED_BG, (ix, iy, inner.w, inner.h), 0, border_radius=int(6 * CANVAS.S))
            dsz = max(1, CANVAS.length(2, 1))
            for r in range(nrows):
                for c in range(ncols):
                    px, py = CANVAS.X(x0 + c * P) - outer.x, CANVAS.Y(y0 + r * P) - outer.y
                    surf.fill((26, 19, 10), (px, py, dsz, dsz))
            cache = caches[rect.x] = (key, surf, outer.topleft)
        _k, surf, pos = cache
        CANVAS.display.blit(surf, pos)
        return x0, y0, ncols, nrows

    def _render_scoreboard(self, match):
        """좌·우 상단 LED 전광판 한 쌍: 하나로 이어진 전광판처럼 글자가 오른쪽 판에서 나와 왼쪽 판으로 흘러감.
        새 소식이 오면 그 소식이 오른쪽 판 끝에서 새로 출발"""
        now = time.time()
        P = self.LED_PITCH
        bg = self.LED_BG
        left = pygame.Rect(16, 8, 272, 58)
        right = pygame.Rect(self.width - 16 - 272, 8, 272, 58)
        panels = []
        for rect in (left, right):
            x0, y0, ncols, nrows = self._led_panel_bg(rect)
            panels.append((x0, y0, ncols, nrows))

        def dot(cx, cy, col):
            self.screen.fill(_mix(col, bg, 0.72), (cx - 1, cy - 1, 4, 4))     # 번짐(글로우)
            self.screen.fill(col, (cx, cy, 2, 2))

        lamp = (255, 70, 60) if int(now * 1.6) % 2 == 0 else (110, 36, 32)      # LIVE 램프 (양쪽 판)
        for x0, y0, ncols, nrows in panels:
            for dy in range(nrows // 2 - 1, nrows // 2 + 2):
                for dx in range(1, 4):
                    dot(x0 + dx * P, y0 + dy * P, lamp)

        # ---- 방송 대기열: 새 소식이 와도 방송 중인 소식을 끊지 않고, 앞 소식 뒤에 이어서 흘림
        st = getattr(self, "_led_state", None)
        text_c0 = 6
        vis = panels[0][2] - text_c0
        link = 30                                                                                  # 두 판 사이를 잇는 가상 열 (배선 구간)
        virt = vis * 2 + link
        nrows = panels[0][3]
        if st is None or st["match"] != id(match):
            st = self._led_state = {"match": id(match), "seen": 0, "pending": [], "items": [], "scroll": 0.0, "last": now, "tail": 0.0}
        dt = max(0.0, min(0.1, now - st["last"]))
        st["last"] = now
        for e in match.commentary:                                                                 # 새로 생긴 소식만 대기열에 넣음
            if e.get("seq", 0) > st["seen"]:
                st["seen"] = e["seq"]
                pend = st["pending"]
                if e.get("prio", 0):
                    k = 0
                    while k < len(pend) and pend[k].get("prio", 0):
                        k += 1
                    pend.insert(k, e)                                                              # 중요 소식은 일반 소식보다 먼저 (방송 중인 것은 끊지 않음)
                else:
                    pend.append(e)
                while len(pend) > 4:                                                               # 너무 밀리면 오래된 일반 소식부터 버림
                    drop = next((i for i, x in enumerate(pend) if not x.get("prio", 0)), 0)
                    del pend[drop]
        # 속도: 밀린 방송이 다 흐르는 데 걸릴 시간(백로그)으로 정함. 1초 이하면 기본 속도, 길수록 부드럽게 빨라져 최대 LED_MAX_SPEEDUP배
        base_speed = self.LED_BASE_SPEED
        backlog_cols = max(0.0, st["tail"] - (st["scroll"] + virt))                                 # 이미 편성됐지만 아직 화면에 다 못 들어온 부분
        font = self._led_font_get()
        for e in st["pending"]:                                                                     # 대기 중인 소식의 예상 길이 (글자 폭 + 소식 사이 여백)
            backlog_cols += font.size(e["text"])[0] + 14
        backlog_sec = backlog_cols / base_speed
        target = 1.0 + (self.LED_MAX_SPEEDUP - 1.0) * max(0.0, min(1.0, (backlog_sec - 1.0) / 5.0))   # 1초 -> 1배, 6초 이상 -> 최대 배율
        st["mult"] = st.get("mult", 1.0) + (target - st.get("mult", 1.0)) * min(1.0, dt * 3.0)        # 목표 배율로 부드럽게 접근 (뚝뚝 바뀌지 않게)
        st["scroll"] += base_speed * st["mult"] * dt
        # 앞 소식의 꼬리가 오른쪽 끝 안으로 들어왔으면 다음 소식을 이어서 내보냄
        while st["pending"] and st["tail"] <= st["scroll"] + virt:
            e = st["pending"].pop(0)
            cols = self._led_build([e], nrows)
            start = max(st["tail"], st["scroll"] + virt)
            st["items"].append({"cols": cols, "start": start, "placed": now, "text": e["text"]})
            st["tail"] = start + len(cols)
        st["items"] = [it for it in st["items"] if it["start"] + len(it["cols"]) > st["scroll"]]   # 완전히 지나간 소식 정리
        base = int(st["scroll"])
        for pi, (x0, y0, ncols, _nr) in enumerate(panels):
            g0 = 0 if pi == 0 else vis + link                                                      # 가상 전광판에서 이 판의 시작 열
            for c in range(vis):
                s_col = base + g0 + c
                for it in st["items"]:
                    idx = s_col - int(it["start"])
                    if 0 <= idx < len(it["cols"]):
                        flash = (now - it["placed"]) < 0.5 and int((now - it["placed"]) * 12) % 2 == 0 and idx < 60
                        for r, col in it["cols"][idx]:
                            dot(x0 + (text_c0 + c) * P, y0 + r * P, (255, 255, 255) if flash else col)
                        break

    def _render_chat_overlay(self):
        """네트워크 게임: 화면 왼쪽 아래에 최근 채팅을 잠깐 보여주고, Enter로 입력창을 엶"""
        opening = self.chat_input is not None
        if not self.chat_entries and not opening:
            return
        now = time.time()
        x, w, line_h = 16, 340, 19        # 관전 바(가운데 하단)와 겹치지 않도록 폭을 제한
        visible = [e for e in self.chat_entries[-14:] if opening or now - e.get("rx", 0) < 10.0]
        lines = self.chat_lines(visible, self.font_small, w - 16)
        lines = lines[-(9 if opening else 6):]
        input_h = 32 if opening else 0
        bottom = 758 - (input_h + 8 if opening else 0)
        if lines:
            top = bottom - len(lines) * line_h
            CANVAS.alpha_rect((x - 6, top - 6, w + 12, len(lines) * line_h + 12), (8, 10, 20, 170), radius=10)
            for i, segs in enumerate(lines):
                self.draw_segments(segs, self.font_small, x + 4, top + i * line_h)
        if opening:
            rect = pygame.Rect(x - 6, 758 - input_h, w + 12, input_h)
            CANVAS.alpha_rect(rect, (10, 13, 26, 235), radius=8)
            CANVAS.alpha_rect(rect, (*C_ACCENT, 255), width=2, radius=8)
            shown = self.chat_input + self.chat_comp
            while shown and self.font_small.size(shown)[0] > w - 24:
                shown = shown[1:]
            t = self._draw_text(shown or "메시지 입력 (Enter 전송 · ESC 취소)", self.font_small,
                                C_TEXT if shown else C_DIM, rect.x + 10, rect.centery, "midleft")
            if shown and int(time.time() * 2) % 2 == 0:
                pygame.draw.rect(self.screen, C_ACCENT, (t.right + 3, rect.y + 7, 2, rect.h - 14))
        elif not lines:
            self._draw_text("Enter  채팅", self.font_tiny, (110, 122, 150), x, 750)

    # ---------------------------------------------------------------- 조작 안내
    def _render_key_hints(self, ox=0, oy=0):
        """보드 하단 조작 키 안내 (현재 키 설정 반영). 항목마다 실제 글자 폭으로 배치하고 줄마다 가운데 정렬해 좌우 미니 보드와 겹치지 않음"""
        if not self.key_hints:
            return
        per_row = 5 if len(self.key_hints) > 8 else 4
        gap = 14
        y0 = self.main_board_y + self.main_board_h + 16 + oy
        items = []
        for keys, label in self.key_hints:
            key_surf = self._text(keys, self.font_tiny, (215, 225, 245))
            lbl = self._text(label, self.font_tiny, (118, 128, 156))
            kw = key_surf.get_width() + 12
            items.append((key_surf, lbl, kw, kw + 6 + lbl.get_width()))
        for row in range(0, len(items), per_row):
            chunk = items[row:row + per_row]
            total = sum(it[3] for it in chunk) + gap * (len(chunk) - 1)
            x = self.width // 2 - total // 2 + ox
            y = y0 + (row // per_row) * 24
            for key_surf, lbl, kw, w in chunk:
                kr = pygame.Rect(int(x), int(y), kw, 19)
                pygame.draw.rect(self.screen, (36, 44, 70), kr, border_radius=5)
                pygame.draw.rect(self.screen, (78, 92, 132), kr, 1, border_radius=5)
                self.screen.blit(key_surf, (kr.x + 6, kr.centery - key_surf.get_height() // 2))
                self.screen.blit(lbl, (kr.right + 6, kr.centery - lbl.get_height() // 2))
                x += w + gap

    # ---------------------------------------------------------------- 일시정지
    def _render_pause_overlay(self):
        pw, ph = 440, 270
        px = (self.width - pw) // 2
        py = (self.height - ph) // 2

        CANVAS.overlay((4, 6, 12, 165))

        self._panel((px, py, pw, ph), border=C_GOLD, bg=(16, 20, 36), radius=16, alpha=245, border_w=2)
        self._draw_text("일시 정지", self.font_large, C_GOLD, px + pw // 2, py + 24, "midtop")
        self._draw_text("PAUSED", self.font_tiny, C_DIM, px + pw // 2, py + 58, "midtop")

        mx, my = pygame.mouse.get_pos()
        self.pause_resume_btn = pygame.Rect(px + 40, py + 88, pw - 80, 44)
        self.pause_settings_btn = pygame.Rect(px + 40, py + 142, pw - 80, 44)
        self.pause_exit_btn = pygame.Rect(px + 40, py + 196, pw - 80, 44)
        for i, btn in enumerate((self.pause_resume_btn, self.pause_settings_btn, self.pause_exit_btn)):
            if btn.collidepoint(mx, my):        # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮겨서, 두 버튼이 동시에 하이라이트되지 않게 함
                self.pause_focus = i
                break
        self._button(self.pause_resume_btn, "계속하기", "blue", self.pause_focus == 0, "P")
        self._button(self.pause_settings_btn, "환경 설정", "green", self.pause_focus == 1)
        self._button(self.pause_exit_btn, "메인 메뉴로 나가기", "red", self.pause_focus == 2, "ESC")

    # ---------------------------------------------------------------- 상단 HUD
    def _render_top_banner(self, match, ox=0, oy=0):
        """상단 3분할 HUD: 생존자 / 조준(모드 칩 + 대상) / 배지·K.O."""
        w1, w2, w3, gap, h = 170, 400, 170, 10, 58
        total_w = w1 + w2 + w3 + gap * 2
        sx = (self.width - total_w) // 2 + ox
        by = 8 + oy

        # 1. 생존자
        r1 = pygame.Rect(int(sx), int(by), w1, h)
        self._panel(r1, border=C_GOLD)
        self._draw_text("생존자", self.font_tiny, C_GOLD, r1.centerx, r1.y + 5, "midtop")
        self._draw_text(f"{match.alive_count} / {match.total_players}", self.font_num, C_TEXT, r1.centerx, r1.y + 16, "midtop")
        ratio = match.alive_count / max(1, match.total_players)
        self._draw_bar((r1.x + 14, r1.bottom - 9, w1 - 28, 3), ratio, C_GOLD)

        # 2. 조준 (모드 칩 + 현재 대상)
        r2 = pygame.Rect(int(sx + w1 + gap), int(by), w2 if getattr(match, "attacks_enabled", True) else w2 + gap + w3, h)   # 서바이벌: K.O. 칸을 없애고 그만큼 넓힘
        aim_on = getattr(match, "attacks_enabled", True)        # 서바이벌 모드에서는 조준 개념이 없음 (칩/락온/레이저 모두 숨김)
        target_pid = match.players[match.local_player_id].get("target_id") if aim_on else None
        target_p = match.players.get(target_pid, {})
        is_human = bool(target_p) and not target_p.get("is_ai", False)
        accent = C_GREEN if is_human else C_ACCENT
        self._panel(r2, border=accent)

        chip_gap = 4
        chip_w = (w2 - 20 - chip_gap * (len(TARGET_MODES) - 1)) // len(TARGET_MODES)
        manual = getattr(match, 'local_manual_target_id', None)
        for i, mode in enumerate(TARGET_MODES if aim_on else ()):
            cr = pygame.Rect(r2.x + 10 + i * (chip_w + chip_gap), r2.y + 6, chip_w, 19)
            active = (mode == match.local_target_mode and not manual)
            if active:
                pygame.draw.rect(self.screen, accent, cr, border_radius=9)
                col = (12, 16, 28)
            else:
                pygame.draw.rect(self.screen, (28, 34, 56), cr, border_radius=9)
                col = C_DIM
            self._draw_text(TARGET_MODE_LABELS.get(mode, mode), self.font_tiny, col, cr.centerx, cr.centery, "center")

        name = target_p.get("name", "탐색 중...")[:12]
        tag = "수동 지정" if manual else "TAB으로 변경"
        if aim_on:
            self._draw_text(f"● {name}" + ("  (사람)" if is_human else ""), self.font_hud,
                            C_GREEN if is_human else C_TEXT, r2.x + 12, r2.y + 31)
        else:
            self._draw_text("공격 없이 끝까지 생존", self.font_hud, C_TEXT, r2.centerx, r2.y + 10, "midtop")
        att_count = match.get_attackers_count_for(match.local_player_id)
        if not getattr(match, "attacks_enabled", True):
            self._draw_text("서바이벌 모드", self.font_small, C_GREEN, r2.centerx, r2.y + 36, "midtop")
        elif att_count >= 2:
            self._draw_text(f"피조준 {att_count}명  반격 +{match.get_attacker_bonus(att_count)}", self.font_small,
                            C_DANGER, r2.right - 12, r2.y + 34, "topright")
        elif att_count == 1:
            self._draw_text("피조준 1명", self.font_small, C_ORANGE, r2.right - 12, r2.y + 34, "topright")
        else:
            self._draw_text(tag, self.font_tiny, C_DIM, r2.right - 12, r2.y + 36, "topright")

        if not getattr(match, "attacks_enabled", True):
            return                                                  # 서바이벌: 배지/K.O. 칸 없음
        # 3. 배지 / K.O.
        r3 = pygame.Rect(int(sx + w1 + w2 + gap * 2), int(by), w3, h)
        tier, _, pct = match.get_badge_info()
        # 0킬일 때는 위험 신호처럼 보이지 않도록 차분한 색, 처치가 생기면 붉은색, 배지가 있으면 금색
        border3 = C_GOLD if tier > 0 else ((255, 120, 120) if match.local_ko_count > 0 else (74, 88, 128))
        self._panel(r3, border=border3)
        title = f"배지 Lv.{tier}  +{pct}" if tier > 0 else "K.O. 처치"
        self._draw_text(title, self.font_tiny, border3 if tier > 0 or match.local_ko_count > 0 else C_DIM, r3.centerx, r3.y + 5, "midtop")
        self._draw_text(f"{match.local_ko_count} K.O.", self.font_num, C_TEXT, r3.centerx, r3.y + 16, "midtop")
        ko = match.local_ko_count
        cur_thr, next_thr = 0, None
        for thr, _rate in BADGE_TIERS:
            if ko >= thr:
                cur_thr = thr
            elif next_thr is None:
                next_thr = thr
        prog = 1.0 if next_thr is None else (ko - cur_thr) / max(1, next_thr - cur_thr)
        self._draw_bar((r3.x + 14, r3.bottom - 9, w3 - 28, 3), prog, border3)

    # ---------------------------------------------------------------- 셀 렌더
    def _cell_surface(self, piece_type, size, dim=False, alpha=None):
        """블록 셀 (네이티브 해상도로 생성하여 캐시)"""
        self._check_ver()
        key = (piece_type, size, dim, alpha)
        surf = self._cell_cache.get(key)
        if surf is not None:
            return surf
        S = CANVAS.S
        color = PIECE_COLORS.get(piece_type, (180, 180, 200))
        surf = CANVAS.make_surface(size, size)
        n = pygame.Surface.get_width(surf)
        sc = lambda v: max(1, int(round(v * S)))
        outer = pygame.Rect(sc(1), sc(1), n - 2 * sc(1), n - 2 * sc(1))
        radius = int(round(max(2, size // 6) * S))
        pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.45), outer, border_radius=radius)
        inner = outer.inflate(-sc(3), -sc(3))
        pygame.draw.rect(surf, color, inner, border_radius=max(1, radius - sc(1)))
        if size >= 12:
            hl = pygame.Rect(inner.x + sc(1), inner.y + sc(1), inner.w - 2 * sc(1), max(sc(2), inner.h // 3))
            pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.42), hl, border_radius=max(1, radius - sc(2)))
            sh_h = max(sc(2), inner.h // 5)
            sh = pygame.Rect(inner.x + sc(1), inner.bottom - sh_h - sc(1), inner.w - 2 * sc(1), sh_h)
            pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.22), sh, border_radius=sc(1))
        if alpha is not None:
            surf.set_alpha(alpha)
        elif dim:
            surf.set_alpha(120)
        self._cell_cache[key] = surf
        return surf

    def _ghost_surface(self, piece_type, size):
        self._check_ver()
        key = (piece_type, size)
        surf = self._ghost_cache.get(key)
        if surf is not None:
            return surf
        S = CANVAS.S
        color = PIECE_COLORS.get(piece_type, (180, 180, 200))
        surf = CANVAS.make_surface(size, size)
        n = pygame.Surface.get_width(surf)
        r = pygame.Rect(int(round(2 * S)), int(round(2 * S)), n - int(round(4 * S)), n - int(round(4 * S)))
        rad = int(round(max(2, size // 7) * S))
        pygame.draw.rect(surf, (*color, 46), r, border_radius=rad)
        pygame.draw.rect(surf, (*color, 190), r, max(1, int(round(2 * S))), border_radius=rad)
        self._ghost_cache[key] = surf
        return surf

    def _draw_cell(self, x, y, size, piece_type):
        self.screen.blit(self._cell_surface(piece_type, int(size)), (int(x), int(y)))

    # ---------------------------------------------------------------- 메인 보드
    def _render_main_board(self, match, ox=0, oy=0):
        spectating = getattr(match, 'is_spectating', False)
        engine = match.local_engine
        spectated_grid = None
        if spectating and match.spectate_target_id:
            sp = match.players.get(match.spectate_target_id)
            remote_engine = match.get_spectate_engine(match.spectate_target_id) if sp else None
            if remote_engine is not None:
                engine = remote_engine          # 봇 엔진 또는 네트워크로 받은 스냅샷 -> 실제 플레이 화면
            elif sp:
                # 아직 상세 정보가 도착하기 전: 압축 그리드만 임시 표시
                engine = None
                spectated_grid = sp.get("compact_grid", [])

        cs = self.cell_size
        bx = self.main_board_x + ox
        by = self.main_board_y + oy
        bw, bh = self.main_board_w, self.main_board_h
        board_rect = pygame.Rect(bx, by, bw, bh)

        # 1. 보드 배경 + 미세 그리드
        border_col = C_GOLD if spectating else (72, 92, 150)
        def _build_glow(surf):
            pygame.draw.rect(surf, (*border_col, 26), (0, 0, bw + 24, bh + 24), border_radius=18)
        self._blit_overlay(("board_glow", bw, bh, border_col), (bw + 24, bh + 24), _build_glow, (bx - 12, by - 12))
        pygame.draw.rect(self.screen, (10, 12, 22), board_rect, border_radius=6)
        for x in range(1, BOARD_WIDTH):
            pygame.draw.line(self.screen, (22, 27, 44), (bx + x * cs, by + 2), (bx + x * cs, by + bh - 2))
        for y in range(1, BOARD_HEIGHT):
            pygame.draw.line(self.screen, (22, 27, 44), (bx + 2, by + y * cs), (bx + bw - 2, by + y * cs))
        # 스폰 구역 표시 (상단 2줄)
        self._blit_overlay(("spawn", bw, cs), (bw, cs * 2), lambda surf: surf.fill((255, 255, 255, 8)), (bx, by))

        if engine is None:
            # 압축 그리드 관전
            for y, row_val in enumerate(spectated_grid or []):
                for x in range(BOARD_WIDTH):
                    if (row_val >> (BOARD_WIDTH - 1 - x)) & 1:
                        self._draw_cell(bx + x * cs, by + y * cs, cs, 'G')
            pygame.draw.rect(self.screen, border_col, board_rect, 2, border_radius=6)
            self._render_stats_box(match, ox, oy)
            return

        # 2. 쓰레기 경고 게이지 (보드 좌측)
        bar_x = bx - 14
        pygame.draw.rect(self.screen, (16, 19, 32), (bar_x, by, 8, bh), border_radius=4)
        incoming = engine.incoming_garbage
        if incoming > 0:
            seg = min(BOARD_HEIGHT, incoming)
            color = C_DANGER if incoming >= 4 else C_ORANGE
            for i in range(seg):                                       # 받을 공격 1줄 = 1칸 (몇 줄인지 바로 셀 수 있게)
                cy0 = by + bh - (i + 1) * cs
                pygame.draw.rect(self.screen, color, (bar_x + 1, cy0 + 1, 6, cs - 2), border_radius=2)

        # 3. 고정된 블록
        for y in range(BOARD_HEIGHT):
            row = engine.grid[y]
            for x in range(BOARD_WIDTH):
                piece = row[x]
                if piece:
                    self._draw_cell(bx + x * cs, by + y * cs, cs, piece)

        # 3-1. 착지 플래시
        now = time.time()
        alive_lock = []
        for lf in self.lock_flashes:
            age = now - lf["birth"]
            if age < 0.16:
                alive_lock.append(lf)
                a = int(150 * (1.0 - age / 0.16))
                fl = pygame.Surface((cs, cs), pygame.SRCALPHA)
                pygame.draw.rect(fl, (255, 255, 255, a), (1, 1, cs - 2, cs - 2), border_radius=5)
                for cx_, cy_ in lf["cells"]:
                    self.screen.blit(fl, (bx + cx_ * cs, by + cy_ * cs))
        self.lock_flashes = alive_lock

        # 3-2. 라인 클리어 와이프
        alive_flashes = []
        for fl in self.line_clear_flashes:
            elapsed = now - fl["birth"]
            if elapsed < fl["duration"]:
                alive_flashes.append(fl)
                progress = elapsed / fl["duration"]
                alpha = max(0, min(255, int(255 * (1.0 - progress))))
                spread = int(4 * math.sin(progress * math.pi))
                fs = pygame.Surface((bw + 16, cs + spread * 2), pygame.SRCALPHA)
                fs.fill((70, 205, 255, alpha // 3))
                pygame.draw.rect(fs, (255, 255, 255, alpha), (0, spread + 3, bw + 16, cs - 6), border_radius=6)
                self.screen.blit(fs, (bx - 8, by + fl["row"] * cs - spread))
        self.line_clear_flashes = alive_flashes

        # 4. 위험 경고 (유입 쓰레기 4줄 이상 또는 블록이 천장 근처)
        highest = engine.get_highest_block_row()
        is_danger = (incoming >= 4) or (not engine.game_over and highest <= 5)
        if is_danger and not spectating:
            pulse = int(50 + 40 * math.sin(time.time() * 8.0))
            # 테두리와 천장 광채를 각각 최대 밝기(255)로 한 번씩만 만들고, 맥박은 투명도로 조절 (겹치는 부분은 화면 위에서 합성됨)
            def _build_edge(ds):
                pygame.draw.rect(ds, (255, 40, 50, 255), (0, 0, bw, bh), 5, border_radius=6)

            def _build_top_glow(ds):
                for i in range(cs * 3):
                    pygame.draw.line(ds, (255, 50, 60, int(255 * 0.9 * (1 - i / (cs * 3)))), (0, i), (bw, i))
            a = max(0, min(255, pulse))
            self._blit_overlay(("danger_edge", bw, bh), (bw, bh), _build_edge, (bx, by), alpha=a)
            self._blit_overlay(("danger_glow", bw, cs), (bw, cs * 3), _build_top_glow, (bx, by), alpha=a)

        # 5. 고스트 + 현재 피스
        if not engine.game_over and engine.current_piece:
            ghost_y = engine.get_ghost_y()
            gsurf = self._ghost_surface(engine.current_piece, cs)
            if ghost_y != engine.current_y:
                for gx, gy in engine._get_blocks(engine.current_piece, engine.current_rot, engine.current_x, ghost_y):
                    if 0 <= gy < BOARD_HEIGHT:
                        self.screen.blit(gsurf, (bx + gx * cs, by + gy * cs))
            for px, py in engine._get_blocks(engine.current_piece, engine.current_rot, engine.current_x, engine.current_y):
                if 0 <= py < BOARD_HEIGHT:
                    self._draw_cell(bx + px * cs, by + py * cs, cs, engine.current_piece)

        pygame.draw.rect(self.screen, border_col, board_rect, 2, border_radius=6)

        # 6. 락 딜레이 진행 바 (바닥에 닿아 고정되기까지)
        lock_p = engine.get_lock_progress()
        track = pygame.Rect(bx, by + bh + 4, bw, 4)
        pygame.draw.rect(self.screen, (20, 24, 40), track, border_radius=2)
        if lock_p > 0:
            pygame.draw.rect(self.screen, _mix(C_ACCENT, C_DANGER, lock_p),
                             (bx, by + bh + 4, max(4, int(bw * (1.0 - lock_p))), 4), border_radius=2)

        # 7. 사이드 패널들
        self._render_hold_box(engine, ox, oy)
        self._render_stats_box(match, ox, oy)
        self._render_status_box(engine, ox, oy)
        self._render_next_box(engine, ox, oy)
        if getattr(match, "attacks_enabled", True):
            self._render_incoming_box(engine, ox, oy)               # 서바이벌: 받을 공격 칸 없음

    # ---------------------------------------------------------------- 사이드 패널
    def _left_x(self, ox):
        return self.main_board_x - 108 - 30 + ox

    def _right_x(self, ox):
        return self.main_board_x + self.main_board_w + 30 + ox

    def _render_hold_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._left_x(ox), self.main_board_y + oy, 108, 104)
        self._panel(rect)
        self._draw_text("홀드", self.font_tiny, C_GOLD, rect.centerx, rect.y + 8, "midtop")
        if engine.hold_piece:
            # 이번 턴 홀드 불가 상태면 흐리게 표시하여 시인성 확보
            self._render_preview_piece(engine.hold_piece, rect.centerx, rect.y + 64, scale=20, dim=not engine.can_hold)

    def _render_stats_box(self, match, ox=0, oy=0):
        rect = pygame.Rect(self._left_x(ox), self.main_board_y + 114 + oy, 108, 148)
        spectating = getattr(match, 'is_spectating', False) and match.spectate_target_id in match.players
        self._panel(rect, border=C_GOLD if spectating else C_PANEL_BORDER, border_w=2 if spectating else 1)
        if spectating:
            st = match.player_stats(match.spectate_target_id)
            sec = int(st["time"])
            apm, lpm, time_str, score = st["apm"], st["lpm"], f"{sec // 60:02d}:{sec % 60:02d}", st["score"]
            tag = pygame.Rect(rect.x + 4, rect.y - 12, rect.w - 8, 18)
            pygame.draw.rect(self.screen, C_GOLD, tag, border_radius=9)
            name = match.players[match.spectate_target_id]["name"][:9]
            self._draw_text(name, self.font_tiny, (16, 20, 30), tag.centerx, tag.centery, "center")
        else:
            apm, lpm, time_str = match.get_combat_stats()
            score = match.local_engine.score
        score_str = f"{score:,}" if score < 100000 else f"{score // 1000}k"
        rows = [("시간", time_str, C_TEXT), ("APM", f"{apm:.1f}", C_GOLD),
                ("LPM", f"{lpm:.1f}", C_GREEN), ("점수", score_str, C_ACCENT)]
        for i, (label, value, col) in enumerate(rows):
            cy = rect.y + 8 + i * 34 + 17                       # 행 중앙: 라벨과 값을 같은 높이에 맞춤
            self._draw_text(label, self.font_small, C_DIM, rect.x + 12, cy, "midleft")
            self._draw_text(value, self.font_hud, col, rect.right - 12, cy, "midright")
            if i < len(rows) - 1:
                pygame.draw.line(self.screen, (38, 46, 72), (rect.x + 10, cy + 17), (rect.right - 10, cy + 17), 1)

    def _render_status_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._left_x(ox), self.main_board_y + 272 + oy, 108, 96)
        self._panel(rect)
        combo = max(0, engine.combo)
        self._draw_text("콤보", self.font_tiny, C_DIM, rect.x + 12, rect.y + 10)
        self._draw_text(str(combo) if combo > 0 else "-", self.font_big_num,
                        C_ORANGE if combo > 0 else C_DIM, rect.right - 12, rect.y + 6, "topright")
        chip = pygame.Rect(rect.x + 12, rect.y + 52, rect.w - 24, 30)
        if engine.b2b:
            pygame.draw.rect(self.screen, (98, 74, 20), chip, border_radius=8)
            pygame.draw.rect(self.screen, C_GOLD, chip, 2, border_radius=8)
            chain = getattr(engine, "b2b_chain", 0)
            self._draw_text(f"B2B x{chain}" if chain >= 1 else "B2B 유지", self.font_small, C_GOLD, chip.centerx, chip.centery, "center")
        else:
            pygame.draw.rect(self.screen, (26, 31, 50), chip, border_radius=8)
            self._draw_text("B2B", self.font_small, C_DIM, chip.centerx, chip.centery, "center")

    def _render_next_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._right_x(ox), self.main_board_y + oy, 108, 266)
        self._panel(rect)
        self._draw_text("다음 블록", self.font_tiny, C_ACCENT, rect.centerx, rect.y + 8, "midtop")
        for i in range(min(5, len(engine.next_queue))):
            scale = 22 if i == 0 else 15
            cy = rect.y + 56 if i == 0 else rect.y + 108 + (i - 1) * 40
            self._render_preview_piece(engine.next_queue[i], rect.centerx, cy, scale=scale, dim=(i > 0))

    def _render_incoming_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._right_x(ox), self.main_board_y + 276 + oy, 108, 92)
        n = engine.incoming_garbage
        danger = n >= 4
        border = C_DANGER if danger else (C_ORANGE if n > 0 else C_PANEL_BORDER)
        self._panel(rect, border=border, border_w=2 if n > 0 else 1)
        self._draw_text("받을 공격", self.font_tiny, border if n > 0 else C_DIM, rect.centerx, rect.y + 10, "midtop")
        col = C_DANGER if danger else (C_ORANGE if n > 0 else C_DIM)
        # 숫자와 "줄"을 한 줄에 나란히, 박스 가운데 정렬
        num = self._text(f"+{n}" if n > 0 else "0", self.font_title, col)
        unit = self._text("줄", self.font_mid, C_DIM)
        gap = 6
        total = num.get_width() + gap + unit.get_width()
        x0 = rect.centerx - total // 2
        cy = rect.y + 58
        self.screen.blit(num, (x0, cy - num.get_height() // 2))
        self.screen.blit(unit, (x0 + num.get_width() + gap, cy + num.get_height() // 2 - unit.get_height() - 3))

    def _render_preview_piece(self, piece_type, center_x, center_y, scale=16, dim=False):
        shape = TETROMINOES[piece_type][0]
        min_x = min(x for x, y in shape)
        max_x = max(x for x, y in shape)
        min_y = min(y for x, y in shape)
        max_y = max(y for x, y in shape)
        start_x = center_x - (max_x - min_x + 1) * scale // 2
        start_y = center_y - (max_y - min_y + 1) * scale // 2
        surf = self._cell_surface(piece_type, scale, dim=dim)
        for bx, by in shape:
            self.screen.blit(surf, (int(start_x + (bx - min_x) * scale), int(start_y + (by - min_y) * scale)))

    # ---------------------------------------------------------------- 미니 보드
    def _render_mini_boards(self, match, ox=0, oy=0):
        self.mini_board_rects.clear()
        others = [(pid, p) for pid, p in match.players.items() if pid != match.local_player_id]
        n = len(others)
        if n == 0:
            return

        half = (n + 1) // 2
        margin_x = 15
        left_x = margin_x
        left_w = self.main_board_x - 145 - margin_x
        right_x = self.main_board_x + self.main_board_w + 145
        right_w = self.width - right_x - margin_x
        start_y = 78
        area_h = self.height - start_y - 16

        # 인원이 적을수록 미니 보드를 크게 (100인 규모: 최대 56px, 2인 대전: 화면을 채우도록 최대 200px)
        max_bw = 56.0 if n >= 30 else min(200.0, 56.0 + (30 - n) * 5.5)
        colors = match.get_name_colors()
        self._render_mini_grid(others[:half], left_x + ox, start_y + oy, left_w, area_h, match, max_bw, colors)
        self._render_mini_grid(others[half:], right_x + ox, start_y + oy, right_w, area_h, match, max_bw, colors)
        if n == 1:                                          # 2인 대전: 비어 있는 쪽에 상대 지표 카드 표시
            self._render_opponent_card(match, others[0][0], right_x + ox, start_y + oy, right_w, area_h, colors)

    def _render_opponent_card(self, match, pid, x, y, w, h, colors):
        """2인 대전에서 미니 보드 반대편에 상대의 실시간 지표(시간, APM, LPM, 점수, 라인, K.O.)를 보여주는 카드"""
        p = match.players.get(pid)
        if not p:
            return
        st = match.player_stats(pid)
        cw, ch = min(300, w), 350
        rect = pygame.Rect(int(x + (w - cw) / 2), int(y + (h - ch) / 2), cw, ch)
        alive = p["is_alive"]
        targeted = getattr(match, "attacks_enabled", True) and match.players[match.local_player_id].get("target_id") == pid
        is_spec = bool(getattr(match, 'is_spectating', False)) and match.spectate_target_id == pid
        border = (255, 255, 255) if is_spec else (C_DANGER if (targeted and alive) else (C_PANEL_BORDER if alive else (60, 40, 46)))
        self._panel(rect, border=border, border_w=3 if is_spec else (2 if targeted else 1))
        if is_spec:
            self._draw_text("관전 중", self.font_tiny, C_GOLD, rect.right - 14, rect.y + 14, "topright")
        is_human = not p.get("is_ai", False)
        name_col = NAME_COLORS[colors.get(pid, 0)][1] if is_human else C_TEXT

        self._draw_text("상대 플레이어", self.font_tiny, C_DIM, rect.centerx, rect.y + 14, "midtop")
        name = p["name"][:14]
        self._draw_text(name, self.font_large, name_col, rect.centerx, rect.y + 34, "midtop")
        status = ("생존 중" if alive else "탈락") + ("  ·  사람" if is_human else "  ·  봇")
        self._draw_text(status, self.font_small, C_GREEN if alive else C_DANGER, rect.centerx, rect.y + 72, "midtop")
        pygame.draw.line(self.screen, (44, 54, 84), (rect.x + 16, rect.y + 98), (rect.right - 16, rect.y + 98), 1)

        sec = int(st["time"])
        rows = [("시간", f"{sec // 60:02d}:{sec % 60:02d}", C_TEXT), ("APM", f"{st['apm']:.1f}", C_GOLD),
                ("LPM", f"{st['lpm']:.1f}", C_GREEN), ("점수", f"{st['score']:,}", C_ACCENT),
                ("라인", str(st["lines"]), C_TEXT), ("K.O.", str(st["ko"]), C_DANGER if st["ko"] else C_TEXT)]
        for i, (label, value, col) in enumerate(rows):
            cy = rect.y + 116 + i * 38 + 17
            self._draw_text(label, self.font_small, C_DIM, rect.x + 22, cy, "midleft")
            self._draw_text(value, self.font_big_num, col, rect.right - 22, cy, "midright")
            if i < len(rows) - 1:
                pygame.draw.line(self.screen, (34, 42, 68), (rect.x + 16, cy + 19), (rect.right - 16, cy + 19), 1)

    @staticmethod
    def _best_layout(count, total_w, total_h):
        """미니 보드가 가장 크게 보이는 열 수 선택"""
        best = (1, 0.0)
        for cols in range(1, 11):
            rows = math.ceil(count / cols)
            bw = min(total_w / cols - 6, (total_h / rows - 16) / 2)
            if bw > best[1]:
                best = (cols, bw)
        return best

    @staticmethod
    def _build_mini_danger(surf, w, h):
        """위기 카드용 붉은 경고: 위쪽 35% 구간에서 아래로 갈수록 옅어지는 그라데이션 (크기별로 한 번만 만듦)"""
        gh = max(2, int(h * 0.35))
        for i in range(gh):
            pygame.draw.line(surf, (255, 50, 60, int(120 * (1 - i / gh))), (0, i), (w, i))

    def _draw_brackets(self, rect, col):
        """카드 네 모서리의 L자 락온 브래킷 (관전/조준 대상 표시)"""
        ln = max(4, min(9, rect.w // 5))
        x0, y0, x1, y1 = rect.x - 1, rect.y - 1, rect.right, rect.bottom
        for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            pygame.draw.line(self.screen, col, (cx, cy), (cx + dx * ln, cy), 2)
            pygame.draw.line(self.screen, col, (cx, cy), (cx, cy + dy * ln), 2)

    def _blit_mini_cells(self, pid, cgt, bx, by, bw, bh, cp):
        """미니 보드에 쌓인 블록 레이어. 보드마다 (블록 배치가 바뀔 때만) 오프스크린에 한 번 그려 두고 매 프레임 그 한 장만 붙임.
        기존 그리기 코드를 그대로 쓰되 CANVAS의 출력 대상/원점만 잠시 바꿔 같은 좌표 반올림으로 그림"""
        self._check_ver()
        use_cells = cp >= 9
        cell_px = int(cp)
        key = (cgt, bw, bh, use_cells, cell_px)
        X0, Y0 = CANVAS.X(bx), CANVAS.Y(by)
        X0 -= X0 % 2                    # 원점은 짝수 픽셀로: round()의 '짝수로 반올림' 규칙이 원본과 똑같이 적용되도록
        Y0 -= Y0 % 2
        ent = self._mini_layers.get(pid)
        if ent is None or ent[0] != key:
            w = CANVAS.X(bx + bw) - X0 + 4
            h = CANVAS.Y(by + bh) - Y0 + 4
            surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            saved = (CANVAS.display, CANVAS.ox, CANVAS.oy)
            CANVAS.display, CANVAS.ox, CANVAS.oy = surf, saved[1] - X0, saved[2] - Y0
            try:
                for y_idx, row in enumerate(cgt):
                    if row == "." * BOARD_WIDTH:
                        continue
                    x_idx = 0
                    while x_idx < BOARD_WIDTH:
                        ch = row[x_idx]
                        if ch == ".":
                            x_idx += 1
                            continue
                        if use_cells:                                  # 큰 보드는 입체 셀
                            self._draw_cell(bx + x_idx * cp, by + y_idx * cp, cell_px, ch)
                            x_idx += 1
                            continue
                        start = x_idx                                  # 작은 보드: 같은 종류가 이어지면 한 덩어리로
                        while x_idx < BOARD_WIDTH and row[x_idx] == ch:
                            x_idx += 1
                        col = PIECE_COLORS.get(ch, (150, 150, 170))
                        if self.mini_fast:
                            # 좌표 변환(CANVAS.rect_f)과 똑같은 계산을 한 곳에서 직접 수행 (호출 단계를 줄여 빠르게, 결과 픽셀은 동일)
                            S_, ox_, oy_ = CANVAS.S, CANVAS.ox, CANVAS.oy
                            x0 = bx + start * cp
                            ww = (x_idx - start) * cp - 0.6
                            y0 = by + y_idx * cp
                            hh = max(1, cp - 0.6)
                            l_ = int(round(ox_ + x0 * S_))
                            t_ = int(round(oy_ + y0 * S_))
                            rw_ = int(round(ox_ + (x0 + ww) * S_)) - l_
                            rh_ = int(round(oy_ + (y0 + hh) * S_)) - t_
                            _orig_rect(surf, col, (l_, t_, rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1), 0, border_radius=0)
                        else:
                            pygame.draw.rect(self.screen, col, (bx + start * cp, by + y_idx * cp, (x_idx - start) * cp - 0.6, max(1, cp - 0.6)))
            finally:
                CANVAS.display, CANVAS.ox, CANVAS.oy = saved
            ent = self._mini_layers[pid] = (key, surf)
        CANVAS.display.blit(ent[1], (X0, Y0))

    def _render_mini_grid(self, player_list, ox, oy, total_w, total_h, match, max_bw=56.0, colors=None):
        colors = colors or {}
        if not player_list:
            return

        cols, bw = self._best_layout(len(player_list), total_w, total_h)
        bw = max(18.0, min(bw, max_bw))
        # 보드가 충분히 크면 오른쪽에 홀드/다음 블록 칸을 두고 보드 폭을 그만큼 줄임
        strip_w = 0.0
        detailed = self.mini_detailed
        if detailed and bw >= 66:
            strip_w = bw * 0.30
            bw -= strip_w
        rows = math.ceil(len(player_list) / cols)
        slot_w = total_w / cols
        slot_h = total_h / max(1, rows)
        bh = bw * 2
        cell_pixel = bw / 10.0
        show_names = bw >= 46

        spectating = bool(getattr(match, 'is_spectating', False))
        spec_id = match.spectate_target_id if spectating else None
        # 관전 중에는 (탈락한) 내 조준 표시를 숨기고, 대신 지금 보고 있는 상대를 강조
        aim_on = getattr(match, "attacks_enabled", True)
        local_target_id = None if (spectating or not aim_on) else match.players[match.local_player_id].get("target_id")
        now = time.time()
        # 지금 나를 노리고 있는 생존자 집합 (프레임당 한 번만 계산: 카드마다 다시 세지 않음)
        attackers_of_me = set() if (spectating or not aim_on) else {q for q, pp in match.players.items()
                                                     if pp["is_alive"] and pp.get("target_id") == match.local_player_id and q != match.local_player_id}

        for idx, (pid, p) in enumerate(player_list):
            r, c = divmod(idx, cols)
            bx = ox + c * slot_w + (slot_w - (bw + strip_w + (4 if strip_w else 0))) / 2
            by = oy + r * slot_h + (slot_h - bh) / 2 + 6

            flash_age = now - self.board_impact_flashes.get(pid, 0)
            is_flashing = flash_age < 0.22
            if is_flashing:
                bx += random.uniform(-2.0, 2.0)
                by += random.uniform(-2.0, 2.0)

            board_rect = pygame.Rect(int(bx), int(by), int(bw), int(bh))
            self.mini_board_rects[pid] = board_rect

            is_targeted = (local_target_id == pid)
            is_alive = p["is_alive"]
            is_human = not p.get("is_ai", False)
            highest_y = p.get("highest_y", 20)
            in_danger = is_alive and highest_y <= 5

            is_spec = (pid == spec_id)
            if not is_alive:
                bg_color, border_color, thick = (10, 11, 16), (28, 31, 40), 1
            elif is_spec:
                bg_color, border_color, thick = (17, 21, 35), (255, 226, 150), 2
            elif is_targeted:
                bg_color, border_color, thick = (17, 21, 35), (232, 84, 94), 2
            elif in_danger:
                bg_color, border_color, thick = (17, 21, 35), (170, 55, 65), 1
            elif is_human:
                bg_color, border_color, thick = (17, 21, 35), C_GOLD, 2
            else:
                bg_color, border_color, thick = (17, 21, 35), (52, 68, 104), 1
            # 카드 프레임(바탕+테두리)은 상태별로 한 번만 만들어 재사용 (프레임마다 도형을 새로 그리지 않음)
            self._panel(board_rect, border=border_color, bg=bg_color, radius=3, alpha=255, border_w=thick)
            if in_danger and not is_spec:                    # 위기: 위쪽에서 붉게 번지는 경고 (모든 위기 카드가 같은 박자로 깜빡임)
                dw, dh = board_rect.w, board_rect.h
                pulse_a = int(150 + 90 * math.sin(now * 6.0))
                self._blit_overlay(("mini_danger", dw, dh), (dw, dh), lambda surf, dw=dw, dh=dh: self._build_mini_danger(surf, dw, dh),
                                   (board_rect.x, board_rect.y), alpha=max(0, min(255, pulse_a)))
            if is_alive and pid in attackers_of_me and not is_targeted:
                CANVAS.display.fill((232, 84, 94), CANVAS.rect_f(board_rect.x + 2, board_rect.y + 1, board_rect.w - 4, 2))   # 나를 노리는 상대: 카드 위쪽 붉은 줄 (변환된 실제 좌표에 직접 채움)
            if is_spec or is_targeted:                       # 락온 코너 브래킷: 관전 대상은 금색(맥박), 조준 대상은 붉은색
                pl = 0.5 + 0.5 * math.sin(now * (5.0 if is_spec else 8.0))
                bcol = _mix((255, 200, 80), (255, 255, 255), 0.55 * pl) if is_spec else _mix((255, 84, 96), (255, 190, 190), 0.5 * pl)
                self._draw_brackets(board_rect, bcol)
            # 이름/K.O. 알약/홀드 아이콘 계산(글자 폭 측정 포함)은 카드 내용이 바뀔 때만 다시 함
            sig = (p["name"], is_human, is_alive, is_targeted, is_spec, colors.get(pid, 0), p.get("ko_count", 0), bw, show_names, detailed,
                   strip_w, p.get("hold"), id(self.font_small), id(self.font_tiny), self._ver)
            info = self._card_info.get(pid) if self.mini_fast else None
            if info is not None and info[0] == sig:
                _, name_str, name_col, tag_font, ko, ko_surf, ko_w, hold_icon, hold_w, name_surf = info
            else:
                maxc = max(5, int(bw / 7))                       # 보드가 클수록 이름을 더 길게 표시
                if is_human and is_alive:
                    name_str, name_col = f"★{p['name'][:maxc]}", NAME_COLORS[colors.get(pid, 0)][1]
                elif is_targeted:
                    name_str, name_col = f"▶{p['name'][:maxc]}", C_DANGER
                elif not is_alive:
                    name_str, name_col = p["name"][:max(6, maxc)], (86, 92, 112)
                else:
                    name_str, name_col = p["name"][:max(6, maxc)], (145, 165, 205)
                if (not show_names or (p.get("ko_count", 0) > 0 and bw < 70)) and name_str.startswith("CPU_"):
                    name_str = name_str[4:]                       # 좁은 카드(또는 K.O. 알약이 있는 카드)는 CPU_ 접두어를 생략해 이름이 잘리지 않게
                tag_font = self.font_small if bw >= 90 else self.font_tiny
                ko = p.get("ko_count", 0)
                ko_surf = None
                ko_w = 0
                if ko > 0:                                       # 이름 오른쪽에 처치 수 알약 (좁은 카드는 숫자만, 두 자리도 끝까지 표시)
                    ko_surf = self._text(f"×{ko}" if bw >= 46 else str(ko), tag_font, (255, 150, 150))
                    ko_w = ko_surf.get_width() + (9 if bw >= 46 else 6)
                # 이름이 K.O. 표시와 겹치지 않도록 남는 폭에 맞춰 자름
                # 홀드 칸을 둘 수 없는 작은 보드(100인 등)는 이름 줄에 홀드한 블록을 작게 표시
                hold_icon = p.get("hold") if (detailed and not strip_w and is_alive) else None
                hold_w = 13 if hold_icon else 0
                spec_pad = 8 if is_spec else 0                   # 관전 대상은 이름 뒤에 금색 판 여백이 붙음
                max_name_w = max(8, int(bw) - ko_w - hold_w - spec_pad)
                if hold_icon and tag_font.size(name_str[:2])[0] > max_name_w:
                    hold_icon, hold_w = None, 0                  # 이름(최소 2글자, 예: 번호 "03")이 우선: 자리가 모자라면 홀드 아이콘부터 뺌
                    max_name_w = max(8, int(bw) - ko_w - spec_pad)
                while len(name_str) > 2 and tag_font.size(name_str)[0] > max_name_w:
                    name_str = name_str[:-1]                     # 최소 2글자는 남김 (두 자리 번호가 한 글자로 잘리지 않게)
                name_surf = self._text(name_str, tag_font, (16, 20, 30) if is_spec else name_col)
                if self.mini_fast:
                    self._card_info[pid] = (sig, name_str, name_col, tag_font, ko, ko_surf, ko_w, hold_icon, hold_w, name_surf)
            tag_y = board_rect.y - (16 if bw >= 90 else 13)

            def draw_tag():
                if is_spec:
                    # 관전 중인 상대: 이름을 금색 판 위에 표시 (별도 표지 없이도 어디서든 눈에 띔)
                    plate = pygame.Rect(board_rect.x - 1, tag_y - 1, name_surf.get_width() + 8, name_surf.get_height() + 2)
                    pygame.draw.rect(self.screen, C_GOLD, plate, border_radius=4)
                    self.screen.blit(name_surf, (board_rect.x + 3, tag_y))
                else:
                    self.screen.blit(name_surf, (board_rect.x, tag_y))
                if ko_surf is not None:
                    pill = pygame.Rect(board_rect.right - ko_surf.get_width() - 6, tag_y, ko_surf.get_width() + 6, ko_surf.get_height() - 1)
                    self._panel(pill, border=(120, 44, 54), bg=(70, 24, 32), radius=4, alpha=255, border_w=1)
                    self.screen.blit(ko_surf, (pill.x + 3, pill.y))
                if hold_icon:
                    icon_cx = board_rect.right - ko_w - 7
                    icon_cy = tag_y + tag_font.get_height() // 2
                    pygame.draw.rect(self.screen, C_GOLD, (icon_cx - 6, icon_cy - 5, 12, 10), 1, border_radius=2)
                    self._render_preview_piece(hold_icon, icon_cx, icon_cy, scale=2)

            # 이름표(이름/판/K.O. 알약/홀드 아이콘)는 내용이 바뀔 때만 다시 그림
            self._blit_card_layer((pid, "tag"), (board_rect.x, board_rect.y, board_rect.w, tag_y, name_str, tuple(name_col), is_spec, ko, ko_w,
                                                 hold_icon, hold_w, id(tag_font), bw >= 46),
                                  board_rect.x - 3, tag_y - 4, board_rect.w + 6, tag_font.get_height() + 8, draw_tag)

            # 블록: 쌓인 블록은 보드별 캐시 서피스 한 장으로 붙임 (고정/쓰레기/줄 제거로 모양이 바뀔 때만 다시 그림)
            cg = p.get("cg")
            cgt = tuple(cg) if cg else None
            if is_alive and cg and len(cg) == BOARD_HEIGHT:
                cp = cell_pixel
                self._blit_mini_cells(pid, cgt, bx, by, bw, bh, cp)
            cpiece = p.get("cpiece")
            if detailed and is_alive and cpiece and cg and len(cg) == BOARD_HEIGHT:
                # 조작 중인 블록도 표시 (고정된 블록보다 밝게)
                ptype, prot, px, py = cpiece
                cells = [(px + dx, py + dy) for dx, dy in TETROMINOES[ptype][prot % 4]]
                gk = (cpiece, cgt)
                ent = self._mini_ghost.get(pid)
                if ent is not None and ent[0] == gk:
                    drop = ent[1]                            # 조작 블록/쌓인 블록이 그대로면 착지 위치를 다시 계산하지 않음
                else:
                    def _hit(off):
                        for gx_, gy_ in cells:
                            yy = gy_ + off
                            if gx_ < 0 or gx_ >= BOARD_WIDTH or yy >= BOARD_HEIGHT:
                                return True
                            if yy >= 0 and cg[yy][gx_] != ".":
                                return True
                        return False

                    drop = 0
                    while drop < BOARD_HEIGHT and not _hit(drop + 1):
                        drop += 1
                    self._mini_ghost[pid] = (gk, drop)
                fast_small = self.mini_fast and cell_pixel < 9
                if fast_small:
                    # 작은 칸: 칸 좌표(변환·반올림 결과)를 카드별로 한 번 계산해 두고 재사용 (CANVAS.rect_f와 같은 계산이라 픽셀은 동일)
                    tkey = (bx, by, cell_pixel, CANVAS.S, CANVAS.ox, CANVAS.oy)
                    tab = self._mini_tabs.get(pid)
                    if tab is None or tab[0] != tkey:
                        cw_ = max(1, cell_pixel - 0.6)
                        XL, XR, YT, YB = [], [], [], []
                        for i_ in range(BOARD_WIDTH):
                            x_ = bx + i_ * cell_pixel
                            XL.append(CANVAS.X(x_))
                            XR.append(CANVAS.X(x_ + cw_))
                        for i_ in range(BOARD_HEIGHT):
                            y_ = by + i_ * cell_pixel
                            YT.append(CANVAS.Y(y_))
                            YB.append(CANVAS.Y(y_ + cw_))
                        tab = self._mini_tabs[pid] = (tkey, XL, XR, YT, YB)
                    _, XL, XR, YT, YB = tab
                    disp = CANVAS.display
                if drop > 0:                                 # 착지 위치: 색 테두리만 그림
                    gcol = PIECE_COLORS.get(ptype, (200, 200, 220))
                    gw_ = CANVAS.length(1, 1)
                    for gx_, gy_ in cells:
                        yy = gy_ + drop
                        if 0 <= yy < BOARD_HEIGHT:
                            if cell_pixel >= 9:
                                self.screen.blit(self._ghost_surface(ptype, int(cell_pixel)), (bx + gx_ * cell_pixel, by + yy * cell_pixel))
                            elif fast_small and 0 <= gx_ < BOARD_WIDTH:
                                rw_ = XR[gx_] - XL[gx_]
                                rh_ = YB[yy] - YT[yy]
                                _orig_rect(disp, gcol, (XL[gx_], YT[yy], rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1), gw_, border_radius=0)
                            else:
                                pygame.draw.rect(self.screen, gcol, (bx + gx_ * cell_pixel, by + yy * cell_pixel, max(1, cell_pixel - 0.6), max(1, cell_pixel - 0.6)), 1)
                cpp = cell_pixel
                pcol = self._pcol.get(ptype)
                if pcol is None:
                    pcol = self._pcol[ptype] = _mix(PIECE_COLORS.get(ptype, (200, 200, 220)), (255, 255, 255), 0.25)
                for gx, gy in cells:
                    if 0 <= gy < BOARD_HEIGHT and 0 <= gx < BOARD_WIDTH:
                        if cpp >= 9:
                            self._draw_cell(bx + gx * cpp, by + gy * cpp, int(cpp), ptype)
                        elif fast_small:                     # 작은 칸: 미리 계산한 좌표로 바로 채움
                            rw_ = XR[gx] - XL[gx]
                            rh_ = YB[gy] - YT[gy]
                            disp.fill(pcol, (XL[gx], YT[gy], rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1))
                        else:                                # 작은 칸: 좌표 변환 후 바로 채움 (그리기 래퍼 생략)
                            CANVAS.display.fill(pcol, CANVAS.rect_f(bx + gx * cpp, by + gy * cpp, max(1, cpp - 0.6), max(1, cpp - 0.6)))
            if is_alive and cg and len(cg) == BOARD_HEIGHT:
                pass
            elif is_alive:
                block_col = (140, 240, 255) if is_human else ((255, 125, 125) if in_danger else (128, 158, 214))
                cp = cell_pixel
                for y_idx, row_val in enumerate(p.get("compact_grid", [])):
                    if not row_val:
                        continue
                    x_idx = 0
                    while x_idx < BOARD_WIDTH:
                        if (row_val >> (BOARD_WIDTH - 1 - x_idx)) & 1:
                            start = x_idx
                            while x_idx < BOARD_WIDTH and (row_val >> (BOARD_WIDTH - 1 - x_idx)) & 1:
                                x_idx += 1
                            pygame.draw.rect(self.screen, block_col,
                                             (bx + start * cp, by + y_idx * cp, (x_idx - start) * cp - 0.6, max(1, cp - 0.6)))
                        else:
                            x_idx += 1
            else:
                # 탈락 카드: 빨간 X 대신 조용한 표시 (순위 + 짧은 선). 생존자가 더 눈에 띄도록 채도를 낮춤
                rk = p.get("rank", 0)
                if rk and bw >= 30:
                    rs = self._text(f"#{rk}", self.font_tiny if bw < 90 else self.font_small, (96, 104, 128))
                    self.screen.blit(rs, (board_rect.centerx - rs.get_width() // 2, board_rect.centery - rs.get_height() // 2))
                    pygame.draw.line(self.screen, (66, 34, 40), (board_rect.centerx - 6, board_rect.centery + rs.get_height() // 2 + 3),
                                     (board_rect.centerx + 6, board_rect.centery + rs.get_height() // 2 + 3), 2)
                else:
                    pygame.draw.line(self.screen, (66, 34, 40), (board_rect.centerx - 5, board_rect.centery), (board_rect.centerx + 5, board_rect.centery), 2)

            # 받을 공격(쓰레기) 게이지: 카드 왼쪽 안쪽의 얇은 막대 (많이 쌓일수록 주황 -> 빨강)
            ig = p.get("ig", 0)
            if is_alive and ig > 0:
                gh = min(ig, 20) * cell_pixel
                gw = 2 if bw < 46 else 3
                CANVAS.display.fill((255, 84, 94) if ig >= 4 else (255, 165, 70), CANVAS.rect_f(bx + 1, by + bh - gh - 1, gw, gh))

            if is_flashing:
                a = max(0, min(255, int(220 * (1.0 - flash_age / 0.22))))
                self._blit_overlay(("mini_flash", board_rect.w, board_rect.h), (board_rect.w, board_rect.h),
                                   lambda surf: surf.fill((255, 255, 255, 255)), board_rect.topleft, alpha=a)

            if strip_w and is_alive:
                # 보드 오른쪽: 홀드 1칸 + 다음 블록 (최대 3칸). 홀드/다음 블록이 바뀔 때만 다시 그림
                def draw_strip():
                    sx = board_rect.right + 4
                    hs = max(4, int(strip_w / 4.0))               # 홀드는 다음 블록보다 크게 표시
                    s_px = max(3, int(strip_w / 5.2))
                    sc_x = sx + strip_w / 2
                    label_font = self.font_tiny if bw < 90 else self.font_small
                    nxt = p.get("next") or []
                    hold_piece = p.get("hold")
                    nb = s_px * 2 + 8
                    slots = [("HOLD", hold_piece, hs, hs * 2 + 12), ("NEXT", nxt[0] if len(nxt) > 0 else None, s_px, nb),
                             ("", nxt[1] if len(nxt) > 1 else None, s_px, nb)]
                    lab_h = label_font.get_height() + 1
                    if lab_h * 2 + (hs * 2 + 12) + nb * 3 + 5 * 4 <= bh:      # 세로 공간이 충분하면 다음 블록 3개까지 표시
                        slots.append(("", nxt[2] if len(nxt) > 2 else None, s_px, nb))
                    cy_ = board_rect.y
                    for lab, piece, scale, box_h in slots:
                        if lab and bw >= 60:
                            self.screen.blit(self._text(lab, label_font, C_GOLD if (lab == "HOLD" and hold_piece) else (120, 134, 170)), (sx, cy_ - 1))
                            cy_ += label_font.get_height() + 1
                        box = pygame.Rect(int(sx), int(cy_), int(strip_w), box_h)
                        bcol = (C_GOLD if hold_piece else (60, 74, 110)) if lab == "HOLD" else (34, 42, 66)
                        self._panel(box, border=bcol, bg=(24, 30, 50), radius=5, alpha=225, border_w=1)
                        if piece:
                            self._render_preview_piece(piece, int(sc_x), int(box.centery), scale=scale)
                        cy_ += box_h + 5

                nxt_key = tuple(p.get("next") or [])
                self._blit_card_layer((pid, "strip"), (board_rect.x, board_rect.y, board_rect.w, board_rect.h, strip_w, bw, p.get("hold"), nxt_key,
                                                       id(self.font_tiny if bw < 90 else self.font_small)),
                                      board_rect.right + 2, board_rect.y - 3, strip_w + 6, bh + 6, draw_strip)

    # ---------------------------------------------------------------- 공격 이펙트
    def _render_attack_effects(self, match, ox=0, oy=0):
        now = time.time()
        main_center = (self.main_board_x + self.main_board_w // 2 + ox, self.main_board_y + self.main_board_h // 2 + oy)

        if match.local_is_alive and not getattr(match, 'is_spectating', False) and getattr(match, "attacks_enabled", True):
            local_target_id = match.players[match.local_player_id].get("target_id")
            if local_target_id and local_target_id in self.mini_board_rects:
                t_center = self.mini_board_rects[local_target_id].center
                self._draw_targeting_laser(main_center, t_center, color=(70, 240, 185), pulse_speed=180.0, is_incoming=False)

                b_sz = 14
                tcx, tcy = t_center
                a = int(180 + 75 * math.sin(now * 12.0))
                b_surf = pygame.Surface((b_sz * 2 + 4, b_sz * 2 + 4), pygame.SRCALPHA)
                pygame.draw.rect(b_surf, (70, 240, 185, a), (0, 0, b_sz * 2 + 4, b_sz * 2 + 4), 2, border_radius=6)
                self.screen.blit(b_surf, (tcx - b_sz - 2, tcy - b_sz - 2))

            shown = 0
            for pid, p in match.players.items():
                if p["is_alive"] and p.get("target_id") == match.local_player_id and pid in self.mini_board_rects:
                    self._draw_targeting_laser(self.mini_board_rects[pid].center, main_center,
                                               color=(200, 62, 70), pulse_speed=-220.0, is_incoming=False)
                    shown += 1
                    if shown >= 6:   # 다수에게 조준당해도 화면이 붉은 선으로 뒤덮이지 않도록 제한
                        break

        for eff in match.attack_effects:
            fid, tid = eff["from_id"], eff["to_id"]
            p1 = main_center if fid == match.local_player_id else (self.mini_board_rects[fid].center if fid in self.mini_board_rects else None)
            p2 = main_center if tid == match.local_player_id else (self.mini_board_rects[tid].center if tid in self.mini_board_rects else None)
            if not p1 or not p2:
                continue

            elapsed = now - eff["start_time"]
            if elapsed < 0:
                continue                                                # 다중 포격의 아직 발사 전인 빔
            progress = min(1.0, elapsed / eff.get("duration", 0.58))
            lines = eff.get("lines", 1)
            travel_t = min(1.0, elapsed / 0.25)

            if travel_t >= 1.0 and not eff.get("impacted", False):
                eff["impacted"] = True
                self.board_impact_flashes[tid] = now
                if tid == match.local_player_id:
                    impact_col = (255, 70, 75)
                    match.trigger_screen_shake(min(14.0, 5.0 + lines * 2.2))
                elif fid == match.local_player_id:
                    impact_col = (255, 230, 90)
                else:
                    impact_col = (120, 220, 255)
                if eff.get("local"):
                    self.particles.add_sparks(p2[0], p2[1], impact_col, count=20 + min(30, lines * 6), speed_mult=1.5)
                    self.particles.add_shockwave(p2[0], p2[1], impact_col, max_radius=35 + min(35, lines * 8) + (18 if eff.get("multi", 1) >= 2 else 0))
                else:                                                   # 나와 무관한 봇끼리의 공격은 작고 가볍게
                    self.particles.add_sparks(p2[0], p2[1], impact_col, count=5, speed_mult=1.2)
                    self.particles.add_shockwave(p2[0], p2[1], impact_col, max_radius=22)

            self._draw_energy_laser_beam(p1, p2, eff, travel_t, progress, fid == match.local_player_id, tid == match.local_player_id)

    def _draw_targeting_laser(self, p1, p2, color, pulse_speed, is_incoming=False):
        """조준선: 점선이 흐르는 락온 레이저"""
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 8:
            return
        ux, uy = dx / dist, dy / dist

        dash_len, gap_len = 10.0, 14.0
        cycle = dash_len + gap_len
        offset = (time.time() * pulse_speed) % cycle
        thick = 2 if is_incoming else 1
        curr = offset
        while curr < dist:
            end = min(dist, curr + dash_len)
            pygame.draw.line(self.screen, color,
                             (int(p1[0] + ux * curr), int(p1[1] + uy * curr)),
                             (int(p1[0] + ux * end), int(p1[1] + uy * end)), thick)
            curr += cycle

    def _draw_energy_laser_beam(self, p1, p2, eff, travel_t, progress, is_local_sender, is_local_target):
        """공격 발사체: 빔 + 탄두 + 착탄 링"""
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 2:
            return
        fade = max(0.0, 1.0 - progress)
        if fade <= 0:
            return

        lines = eff.get("lines", 1)
        is_heavy = is_local_sender or is_local_target
        multi = eff.get("multi", 1) >= 2 and is_local_sender             # 다중 포격: 주황~금색 굵은 빔 + 발사 지점 확산 링

        if multi:
            core_c, mid_c, glow_c = (255, 255, 255), (255, 200, 90), (255, 110, 40)
            base_w = 10
            age = time.time() - eff["start_time"]
            if age < 0.3:
                rr = int(14 + age / 0.3 * 46)
                pygame.draw.circle(self.screen, (255, int(200 - 90 * age / 0.3), 90), (int(p1[0]), int(p1[1])), rr, max(1, int(4 * (1 - age / 0.3))))
        elif is_local_sender:
            core_c = (255, 255, 255)
            mid_c = (255, 235, 100) if lines >= 4 else (110, 245, 255)
            glow_c = (255, 170, 50) if lines >= 4 else (55, 160, 255)
            base_w = 12 if lines >= 4 else 7
        elif is_local_target:
            core_c, mid_c, glow_c = (255, 255, 255), (255, 125, 90), (255, 40, 40)
            base_w = 11 if lines >= 4 else 6
        else:
            core_c, mid_c, glow_c = (220, 245, 255), (120, 200, 255), (55, 105, 220)
            base_w = 4

        head_x = p1[0] + dx * travel_t
        head_y = p1[1] + dy * travel_t
        if travel_t < 1.0:
            tail_t = max(0.0, travel_t - 0.45)
            t_start = (int(p1[0] + dx * tail_t), int(p1[1] + dy * tail_t))
            t_end = (int(head_x), int(head_y))
        else:
            t_start, t_end = p1, p2

        if is_heavy or multi:                                          # 나와 무관한 빔은 바깥 빛 번짐 없이 선 2개만
            pygame.draw.line(self.screen, glow_c, t_start, t_end, base_w + 4)
        pygame.draw.line(self.screen, mid_c, t_start, t_end, base_w)
        pygame.draw.line(self.screen, core_c, t_start, t_end, max(2, base_w - 4))

        if is_heavy and travel_t >= 0.15:
            num = max(3, int(dist // 45))
            px_, py_ = -dy / dist, dx / dist
            pts = [t_start]
            for i in range(1, num):
                seg = i / num
                j = random.uniform(-6, 6) * fade
                pts.append((int(t_start[0] + (t_end[0] - t_start[0]) * seg + px_ * j),
                            int(t_start[1] + (t_end[1] - t_start[1]) * seg + py_ * j)))
            pts.append(t_end)
            pygame.draw.lines(self.screen, (255, 255, 255), False, pts, 1)

        if travel_t < 1.0:
            r = 7 + (3 if is_heavy else 0)
            hx, hy = int(head_x), int(head_y)
            pygame.draw.circle(self.screen, glow_c, (hx, hy), r + 4)
            pygame.draw.circle(self.screen, mid_c, (hx, hy), r)
            pygame.draw.circle(self.screen, (255, 255, 255), (hx, hy), max(2, r - 3))
            if random.random() < 0.5:
                self.particles.add_sparks(hx, hy, mid_c, count=2, speed_mult=0.5)

        if travel_t >= 0.95 and progress < 0.75:
            bloom = int((22 + lines * 5) * (1.0 - (progress - 0.25) / 0.5))
            if bloom > 0:
                pygame.draw.circle(self.screen, (255, 255, 255), (int(p2[0]), int(p2[1])), max(1, bloom // 3))
                pygame.draw.circle(self.screen, mid_c, (int(p2[0]), int(p2[1])), bloom, 2)

    # ---------------------------------------------------------------- 결과 화면
    def _render_spectate_notice(self, match):
        """관전 대상이 패배해 다음 대상으로 넘어갈 때 잠깐 표시하는 알림 (2.6초, 서서히 사라짐)"""
        n = getattr(match, "spectate_notice", None)
        if not n:
            return
        age = time.time() - n["t0"]
        if age > 2.6:
            match.spectate_notice = None
            return
        k = self._ease_out(age / 0.25)
        fade = 1.0 if age < 2.0 else max(0.0, 1.0 - (age - 2.0) / 0.6)
        a = k * fade
        w, h = 400, 78
        rect = pygame.Rect(self.main_board_x + self.main_board_w // 2 - w // 2, self.main_board_y + 170 - int((1 - k) * 14), w, h)
        CANVAS.alpha_rect(rect, (24, 8, 12, int(235 * a)), radius=12)
        CANVAS.alpha_rect(rect, (255, 90, 100, int(255 * a)), width=2, radius=12)
        self._fade_text(n["text"], self.font_large, (255, 110, 120), rect.centerx, rect.y + 12, 255 * a, "midtop")
        self._fade_text(n["sub"], self.font_small, (220, 200, 205), rect.centerx, rect.y + 50, 255 * a, "midtop")

    # ---------------------------------------------------------------- 최종 순위표 (애니메이션)
    def reset_standings(self):
        self._standings_t0 = None
        self.standings_scroll = 0

    def scroll_standings(self, delta):
        self.standings_scroll = max(0, self.standings_scroll + int(delta))

    @staticmethod
    def _ease_out(t):
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 3

    def _fade_text(self, text, font, color, x, y, alpha, anchor="topleft"):
        """투명도를 줄 수 있는 텍스트 (순위표 행 등장 애니메이션용)"""
        if alpha <= 0:
            return
        surf = font.render(text, True, color)
        surf.set_alpha(max(0, min(255, int(alpha))))
        rect = surf.get_rect()
        setattr(rect, anchor, (int(x), int(y)))
        self.screen.blit(surf, rect)

    def _render_standings_overlay(self, match):
        """경기 종료: 전체 플레이어 성적 리스트. 행이 아래에서부터 차례로 미끄러져 들어오고, 숫자가 올라가며 우승자는 빛남."""
        now = time.time()
        if self._standings_t0 is None:
            self._standings_t0 = now
            self.scroll_standings(-99999)
        t = now - self._standings_t0
        CANVAS.overlay((4, 6, 12, int(210 * self._ease_out(t / 0.5))))

        rows = match.standings()
        n = len(rows)
        box_w, box_h = 1100, 640
        bx, by = (self.width - box_w) // 2, 60
        pop = self._ease_out(t / 0.45)
        by_off = int((1 - pop) * 40)
        won = match.local_rank == 1
        accent = C_GOLD if won else C_ACCENT
        self._panel((bx, by + by_off, box_w, box_h), border=accent, bg=(15, 19, 34), radius=18, alpha=int(248 * pop), border_w=2)
        if pop < 0.6:
            return
        a_head = 255 * self._ease_out((t - 0.3) / 0.4)

        winner = next((r for r in rows if r["rank"] == 1), rows[0] if rows else None)
        me = next((r for r in rows if r["is_local"]), None)
        title = "로열 빅토리!" if won else "경기 종료"
        self._fade_text(title, self.font_title, C_GOLD if won else C_TEXT, bx + box_w // 2, by + 20, a_head, "midtop")
        if winner:
            sub = f"우승  {winner['name']}" + ("  (나)" if won else "")
            self._fade_text(sub, self.font_hud, C_GOLD, bx + box_w // 2, by + 66, a_head, "midtop")
        if me and not won:
            self._fade_text(f"내 순위  {me['rank']}위 / {n}명", self.font_mid, C_DIM, bx + box_w // 2, by + 92, a_head, "midtop")

        # 열 머리글
        head_y = by + 124
        cols = [("순위", 46, "center"), ("이름", 96, "topleft"), ("K.O.", 520, "topright"), ("라인", 610, "topright"),
                ("APM", 706, "topright"), ("LPM", 800, "topright"), ("점수", 920, "topright"), ("시간", 1030, "topright")]
        for label, cx_, anc in cols:
            self._fade_text(label, self.font_tiny, C_DIM, bx + cx_, head_y, a_head, anc)
        pygame.draw.line(self.screen, (52, 64, 98), (bx + 24, head_y + 22), (bx + box_w - 24, head_y + 22), 1)

        # 행 (스크롤)
        row_h, top = 34, head_y + 30
        visible = 10
        max_scroll = max(0, n - visible)
        self.standings_scroll = min(self.standings_scroll, max_scroll)
        start = self.standings_scroll
        shown = rows[start:start + visible]
        top_score = max((r["score"] for r in rows), default=1) or 1
        count = self._ease_out((t - 0.5) / 1.1)                    # 숫자 올라가는 진행률
        intro_done = t > 0.4 + 0.06 * visible + 0.5
        for vi, r in enumerate(shown):
            # 아래쪽 행부터 차례로 등장 (1위가 마지막으로 나타나 강조됨)
            delay = 0.35 + (len(shown) - 1 - vi) * 0.06
            k = 1.0 if intro_done and self._standings_scroll_seen(start) else self._ease_out((t - delay) / 0.4)
            if k <= 0:
                continue
            y = top + vi * row_h
            xo = int((1 - k) * 120)
            a = 255 * k
            rr = pygame.Rect(bx + 20 + xo, y, box_w - 40, row_h - 4)
            is_win = r["rank"] == 1
            is_me = r["is_local"]
            if is_win:
                glow = 0.5 + 0.5 * math.sin(now * 4.0)
                CANVAS.alpha_rect(rr.inflate(8, 6), (255, 210, 90, int((40 + 50 * glow) * k)), radius=12)
                CANVAS.alpha_rect(rr, (60, 48, 18, int(235 * k)), radius=9)
                CANVAS.alpha_rect(rr, (255, 210, 90, int(230 * k)), width=2, radius=9)
            elif is_me:
                CANVAS.alpha_rect(rr, (22, 50, 66, int(235 * k)), radius=9)
                CANVAS.alpha_rect(rr, (100, 220, 255, int(220 * k)), width=1, radius=9)
            else:
                CANVAS.alpha_rect(rr, ((26, 32, 54, int(220 * k)) if (start + vi) % 2 == 0 else (20, 25, 44, int(220 * k))), radius=9)
            # 점수 비율 막대
            frac = (r["score"] / top_score) * count
            if frac > 0:
                CANVAS.alpha_rect((rr.x + 10, rr.bottom - 5, int((rr.w - 20) * frac * 0.999) + 1, 3), (*(C_GOLD if is_win else C_ACCENT), int(150 * k)), radius=2)
            col = C_GOLD if is_win else (C_ACCENT if is_me else C_TEXT)
            cy = rr.centery - 9 + 0
            rank_txt = f"{r['rank']}" if r["rank"] > 0 else "-"
            self._fade_text(rank_txt, self.font_hud, C_GOLD if is_win else col, bx + 46 + xo, rr.centery, a, "center")
            nm = r["name"] + ("  (나)" if is_me else "")
            self._fade_text(nm[:22], self.font_mid, col, bx + 96 + xo, rr.centery, a, "midleft")
            self._fade_text(str(int(r["ko"] * count)), self.font_mid, col, bx + 520 + xo, rr.centery, a, "midright")
            self._fade_text(str(int(r["lines"] * count)), self.font_mid, col, bx + 610 + xo, rr.centery, a, "midright")
            self._fade_text(f"{r['apm'] * count:.1f}", self.font_mid, C_GOLD if not is_win else col, bx + 706 + xo, rr.centery, a, "midright")
            self._fade_text(f"{r['lpm'] * count:.1f}", self.font_mid, C_GREEN if not is_win else col, bx + 800 + xo, rr.centery, a, "midright")
            self._fade_text(f"{int(r['score'] * count):,}", self.font_mid, col, bx + 920 + xo, rr.centery, a, "midright")
            sec = int(r["time"])
            self._fade_text(f"{sec // 60}:{sec % 60:02d}", self.font_mid, C_DIM if not is_win else col, bx + 1030 + xo, rr.centery, a, "midright")
        self._standings_last_start = start

        # 스크롤 막대 + 내 행이 화면 밖이면 아래에 고정 표시
        if n > visible:
            track = pygame.Rect(bx + box_w - 16, top, 5, visible * row_h - 4)
            pygame.draw.rect(self.screen, (28, 34, 56), track, border_radius=3)
            th = max(24, int(track.h * visible / n))
            ty = track.y + int((track.h - th) * (start / max_scroll if max_scroll else 0))
            pygame.draw.rect(self.screen, accent, (track.x, ty, track.w, th), border_radius=3)
        if me and me not in shown and intro_done:
            y = top + visible * row_h + 2
            rr = pygame.Rect(bx + 20, y, box_w - 40, row_h - 4)
            CANVAS.alpha_rect(rr, (22, 50, 66, 240), radius=9)
            CANVAS.alpha_rect(rr, (100, 220, 255, 220), width=1, radius=9)
            self._draw_text(f"{me['rank']}", self.font_hud, C_ACCENT, bx + 46, rr.centery, "center")
            self._draw_text(f"{me['name']}  (나)"[:22], self.font_mid, C_ACCENT, bx + 96, rr.centery, "midleft")
            for val, cx_ in ((str(me["ko"]), 520), (str(me["lines"]), 610), (f"{me['apm']:.1f}", 706), (f"{me['lpm']:.1f}", 800),
                             (f"{me['score']:,}", 920), (f"{int(me['time']) // 60}:{int(me['time']) % 60:02d}", 1030)):
                self._draw_text(val, self.font_mid, C_ACCENT, bx + cx_, rr.centery, "midright")

        # 버튼
        mx, my = pygame.mouse.get_pos()
        btn_y = by + box_h - 64
        self.result_spectate_btn = None
        self.result_restart_btn = pygame.Rect(bx + box_w // 2 - 260, btn_y, 250, 46)
        self.result_return_btn = pygame.Rect(bx + box_w // 2 + 10, btn_y, 250, 46)
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        self._button(self.result_restart_btn, "대기실로 돌아가기" if net_on else "재도전", "green",
                     self.result_restart_btn.collidepoint(mx, my), "R")
        self._button(self.result_return_btn, "메인 메뉴", "blue", self.result_return_btn.collidepoint(mx, my), "ESC")
        if n > visible:
            self._draw_text("마우스 휠 / ↑ ↓ / PageUp·PageDown 으로 스크롤", self.font_tiny, C_DIM, bx + box_w // 2, by + box_h - 96, "midtop")

    def _standings_scroll_seen(self, start):
        """스크롤로 새로 보이게 된 행은 등장 애니메이션 없이 바로 표시"""
        return True

    def _render_result_overlay(self, match):
        CANVAS.overlay((4, 6, 12, 200))

        won = match.local_rank == 1
        accent = C_GOLD if won else C_DANGER
        box_w, box_h = 660, 346
        bx = (self.width - box_w) // 2
        by = (self.height - box_h) // 2
        self._panel((bx, by, box_w, box_h), border=accent, bg=(15, 19, 34), radius=18, alpha=248, border_w=2)

        if won:
            self._draw_text("로열 빅토리!", self.font_title, C_GOLD, bx + box_w // 2, by + 22, "midtop", shadow=True)
            self._draw_text("최후의 1인으로 살아남았습니다", self.font_mid, C_GREEN, bx + box_w // 2, by + 66, "midtop")
            rank_txt = "#1"
        else:
            self._draw_text("K.O.  경기 탈락", self.font_title, C_DANGER, bx + box_w // 2, by + 22, "midtop", shadow=True)
            self._draw_text(f"최종 순위  {match.local_rank}위 / {match.total_players}명", self.font_mid, C_TEXT,
                            bx + box_w // 2, by + 66, "midtop")
            rank_txt = f"#{match.local_rank}"

        # 통계 카드
        apm, lpm, time_str = match.get_combat_stats()
        tier, _, pct = match.get_badge_info()
        cards = [
            ("순위", rank_txt, accent),
            ("K.O.", str(match.local_ko_count), C_TEXT),
            ("제거 라인", str(match.local_engine.lines_cleared_total), C_ACCENT),
            ("최대 콤보", str(match.local_engine.max_combo), C_ORANGE),
            ("APM", f"{apm:.1f}", C_GOLD),
            ("생존 시간", time_str, C_GREEN),
        ]
        cw, gap = 96, 10
        sx = bx + (box_w - (cw * len(cards) + gap * (len(cards) - 1))) // 2
        for i, (lbl, val, col) in enumerate(cards):
            r = pygame.Rect(sx + i * (cw + gap), by + 108, cw, 66)
            self._panel(r, border=(50, 62, 96), bg=(22, 27, 46), radius=10)
            self._draw_text(lbl, self.font_tiny, C_DIM, r.centerx, r.y + 9, "midtop")
            self._draw_text(val, self.font_big_num, col, r.centerx, r.y + 28, "midtop")
        badge_txt = f"최종 배지 Lv.{tier} (공격력 +{pct})" if tier > 0 else "최종 배지 Lv.0"
        self._draw_text(badge_txt, self.font_small, C_DIM, bx + box_w // 2, by + 188, "midtop")

        mx, my = pygame.mouse.get_pos()
        can_spectate = (not match.match_finished and match.alive_count > 1 and not match.local_is_alive)
        btn_y, btn_h = by + 226, 50

        self.result_restart_btn = self.result_spectate_btn = self.result_return_btn = None
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        if net_on and not match.match_finished:
            # 네트워크 경기 도중 탈락: 재도전은 없음 (경기가 끝나면 대기실로 복귀). 관전 / 메인 메뉴만.
            btn_w, g = 260, 16
            sbx = bx + (box_w - (btn_w * 2 + g)) // 2
            specs = []
            if can_spectate:
                specs.append(("spectate", pygame.Rect(sbx, btn_y, btn_w, btn_h), "경기 관전", "gold", "S"))
            specs.append(("return", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"))
        elif can_spectate:
            btn_w, g = 196, 12
            sbx = bx + (box_w - (btn_w * 3 + g * 2)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("spectate", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "경기 관전", "gold", "S"),
                ("return", pygame.Rect(sbx + (btn_w + g) * 2, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]
        else:
            btn_w, g = 260, 16
            sbx = bx + (box_w - (btn_w * 2 + g)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("return", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]

        ids = [s[0] for s in specs]
        if self.result_focus_id not in ids:
            self.result_focus_id = ids[0]
        for bid, rect, _label, _style, _hint in specs:
            if rect.collidepoint(mx, my):       # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮김 (이중 하이라이트 방지)
                self.result_focus_id = bid
                break
        for bid, rect, label, style, hint in specs:
            if bid == "restart":
                self.result_restart_btn = rect
            elif bid == "spectate":
                self.result_spectate_btn = rect
            elif bid == "return":
                self.result_return_btn = rect
            self._button(rect, label, style, self.result_focus_id == bid, hint)

        self._draw_text("버튼을 클릭하거나 단축키로, ← → 와 Enter 로도 실행할 수 있습니다", self.font_tiny, C_DIM,
                        bx + box_w // 2, by + box_h - 36, "midtop")

    # ---------------------------------------------------------------- 관전 HUD
    def _render_spectator_hud(self, match, ox=0, oy=0):
        """관전 바: 미니 보드 영역(좌우)을 가리지 않도록 보드 아래 중앙 빈 공간에 2줄로 표시"""
        target_p = match.players.get(match.spectate_target_id, {})
        name = target_p.get("name", "생존자 탐색 중")
        who = "봇" if target_p.get("is_ai", False) else "사람"
        ko = target_p.get("ko_count", 0)

        bar_w, bar_h = 580, 60
        rect = pygame.Rect(self.width // 2 - bar_w // 2 + int(ox),
                           self.main_board_y + self.main_board_h + 10 + int(oy), bar_w, bar_h)
        self._panel(rect, border=C_GOLD, bg=(16, 20, 36), radius=12, alpha=245, border_w=2)

        badge = pygame.Rect(rect.x + 12, rect.y + 8, 64, 22)
        pygame.draw.rect(self.screen, C_GOLD, badge, border_radius=11)
        self._draw_text("관전 중", self.font_small, (16, 20, 30), badge.centerx, badge.centery, "center")
        name_col = C_TEXT
        if not target_p.get("is_ai", False):
            name_col = NAME_COLORS[match.get_name_colors().get(match.spectate_target_id, 0)][1]
        self._draw_text(f"{name}  ({who}, K.O. {ko})", self.font_hud, name_col, rect.x + 88, rect.y + 19, "midleft")
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        hints = [("← →", "대상 변경"), ("클릭", "미니 보드 선택")]
        if not net_on:
            hints.append(("R", "재도전"))
        hints.append(("ESC", "일시정지" if not net_on else "메뉴"))
        self._keycap_hints(hints, rect.centerx, rect.y + 36)

    def _keycap_hints(self, items, cx, y, gap=14):
        parts = []
        total = 0
        for key, label in items:
            ks = self._text(key, self.font_tiny, (215, 225, 245))
            ls = self._text(label, self.font_tiny, C_DIM)
            w = ks.get_width() + 12 + 5 + ls.get_width()
            parts.append((ks, ls, w))
            total += w
        total += gap * (len(parts) - 1)
        x = cx - total // 2
        for ks, ls, w in parts:
            kr = pygame.Rect(x, y, ks.get_width() + 12, 18)
            pygame.draw.rect(self.screen, (36, 44, 70), kr, border_radius=5)
            pygame.draw.rect(self.screen, (78, 92, 132), kr, 1, border_radius=5)
            self.screen.blit(ks, (kr.x + 6, kr.centery - ks.get_height() // 2))
            self.screen.blit(ls, (kr.right + 5, kr.centery - ls.get_height() // 2))
            x += w + gap
