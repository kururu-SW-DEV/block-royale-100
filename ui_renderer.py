"""
Block Royale 100 - In-game UI Renderer
1366x768 해상도에서 1개의 메인 보드와 최대 99개의 주변 미니 보드를 렌더링합니다.
깔끔한 글래스 패널 + 네온 액센트 스타일, 시인성과 조작성(조작 안내 / 조준 모드 표시 / 락 딜레이 바)에 초점을 맞춘 UI.
"""

import time
import math
import random
import pygame
import challenges
from gfx import CANVAS, Canvas, HiFont, HiSurf, mix_color as _mix
from config import is_colorblind
from config import NAME_COLORS
from stats_manager import LADDER_NAMES, ACHIEVEMENTS, level_of
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BOARD_WIDTH, BOARD_HEIGHT,
    TETROMINOES, PIECE_COLORS, TARGET_MODES, BADGE_TIERS
)

# ---------------------------------------------------------------- 팔레트
C_BG_TOP = (14, 17, 30)
C_BG_BOTTOM = (8, 9, 16)

def _ease_out(x):
    """0~1 진행도를 처음엔 빠르게 끝에선 천천히 (연출용)"""
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return 1.0 - (1.0 - x) ** 3


# 경기 단계별 테마 (1: 100~51인 · 2: 50인 이하 · 3: 최후의 결전). 배경 그라데이션 + 메인 보드 테두리 색
TARGET_MODE_HELP = {
    "AUTO": "자동: 사람 상대가 있으면 사람 우선, 아니면 탈락 직전(쌓인 블록+받을 공격이 가장 큰) 상대를 노립니다.",
    "KO": "K.O.: 쌓인 블록과 받을 공격이 가장 큰, 탈락 직전인 상대를 노립니다.",
    "ATTACKERS": "반격: 나를 노리는 상대에게 되돌려줍니다. 둘 이상이면 전원에게 동시 포격합니다.",
    "BADGES": "배지: K.O.를 가장 많이 쌓은(공격력이 오른) 상대를 노립니다.",
    "RANDOM": "랜덤: 생존자 중 무작위 1명을 노리고, 그 상대가 살아 있는 동안 유지합니다.",
}

STAGE_THEMES = {
    1: {"top": C_BG_TOP, "bottom": C_BG_BOTTOM, "border": (72, 92, 150)},
    2: {"top": (30, 20, 38), "bottom": (16, 9, 20), "border": (176, 118, 210)},
    3: {"top": (42, 12, 18), "bottom": (18, 5, 9), "border": (214, 74, 84)},
}
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
_orig_circle = CANVAS._orig["circle"]


_GLOW_CACHE = {}


def _glow_sprite(radius, color, level):
    """검은 바탕의 방사형 그라데이션 (BLEND_RGB_ADD로 더하면 빛나 보임). 크기·색·밝기 단계별로 한 번만 만듦"""
    key = (radius, tuple(color[:3]), level)
    spr = _GLOW_CACHE.get(key)
    if spr is None:
        spr = pygame.Surface((radius * 2, radius * 2))
        k = (level + 1) / 5.0
        for i in range(radius, 0, -1):
            f = (1.0 - i / radius) ** 1.6 * k
            _orig_circle(spr, (int(color[0] * f), int(color[1] * f), int(color[2] * f)), (radius, radius), i)
        if len(_GLOW_CACHE) > 160:
            _GLOW_CACHE.clear()
        _GLOW_CACHE[key] = spr
    return spr


def draw_glow(surface, x, y, radius, color, fade=1.0):
    """(x, y) 논리 좌표에 빛 구슬을 더해 그림 (큰 순간 전용: 개수는 호출 쪽에서 제한)"""
    level = max(0, min(4, int(fade * 4.99)))
    if isinstance(surface, Canvas):
        r = max(2, CANVAS.length(radius))
        surface.display.blit(_glow_sprite(r, color, level), (CANVAS.X(x) - r, CANVAS.Y(y) - r), special_flags=pygame.BLEND_RGB_ADD)
    else:
        r = max(2, int(radius))
        surface.blit(_glow_sprite(r, color, level), (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


class ParticleManager:
    """스파크 및 충격파 링 이펙트 매니저"""
    def __init__(self):
        self.particles = []
        self.rings = []

    def add_sparks(self, x, y, color, count=30, speed_mult=1.0, glow=False):
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
                "glow": glow,
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
            if isinstance(surface, Canvas):                 # 네이티브 해상도로 직접 그려 4K에서도 흐려지지 않게 함
                S = CANVAS.S
                pw, ph = max(1, int(round((rad * 2 + 4) * S))), max(1, int(round((rad * 2 + 4) * S)))
                ring_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
                CANVAS._orig["ellipse"](ring_surf, (*r["color"][:3], r["alpha"]),
                                        pygame.Rect(int(round(2 * S)), int(round((2 + rad // 2) * S)), max(2, int(round(rad * 2 * S))), max(2, int(round(rad * S)))),
                                        max(1, int(round(2 * S))))
                CANVAS.display.blit(ring_surf, (CANVAS.X(rx - rad - 2), CANVAS.Y(ry - rad // 2 - 2)))
                continue
            ring_surf = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(ring_surf, (*r["color"][:3], r["alpha"]), (2, 2 + rad // 2, rad * 2, rad), 2)
            surface.blit(ring_surf, (rx - rad - 2, ry - rad // 2 - 2))

        for p in self.particles:
            fade = 1.0 - p["life"] / p["max_life"]
            if p.get("glow"):
                draw_glow(surface, p["x"] + ox, p["y"] + oy, p["size"] * 4 + 2, p["color"], fade)
                continue
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
        self.target_chip_rects = {}      # 상단 조준 모드 칩의 클릭 영역 {모드: Rect} (프레임마다 갱신)
        self.mini_focus = False          # 미니 보드 집중 보기: 나를 노리는 상대/조준 대상/위기 카드가 아닌 카드는 어둡게 (설정에서 변경)
        self.mini_detailed = True        # 미니 보드 자세히 보기 (설정에서 변경): 조작 중 블록/착지 위치/홀드/다음 블록
        self.line_clear_flashes = []
        self.lock_flashes = []
        self._lock_seen = (None, 0)
        self.board_impact_flashes = {}
        # v1.1.6 도파민 연출 상태
        self.impact_numbers = []         # 내 공격이 상대 카드에 꽂힌 자리에 뜨는 "+N" [{x, y, n, t0}]
        self._combo_seen = -1            # 콤보 숫자 팝/끊김 연출용
        self._combo_pop_t = -9.0
        self._combo_break_t = -9.0
        self._combo_break_n = 0
        self._cancel_seen = 0            # 방어(막은 줄) 반응
        self._cancel_t0 = -9.0
        self._pc_seen = 0                # 퍼펙트 금빛 쓸어올림
        self._pc_t0 = -9.0
        # v1.1.7 블록 반응 연출 (내 보드 전용)
        self._react_eng = None
        self.shards = []                 # 지운 줄/무너지는 칸의 조각
        self._settle = None              # 줄 제거 뒤 위 블록 내려앉기 {t0, offs}
        self._rise = None                # 쓰레기 줄 상승 {t0, n}
        self.hole_flashes = []           # 쓰레기 줄 구멍 깜빡임
        self.drop_trails = []            # 하드 드롭 궤적
        self._hd_seen = 0
        self._gp_seen = 0
        self._bounce_t0 = -9.0
        self._bounce_amp = 0.0
        self._bg_pulses = []             # 배경 링 {t0, x, y, col}
        self._ko_seen = 0
        self._topout = None              # 내 탑아웃 붕괴 {t0, row}
        self._vic_t0 = None              # 우승 세리머니 시작 시각
        self._vic_row = BOARD_HEIGHT
        self.confetti = []
        self.result_return_btn = None
        self.result_restart_btn = None
        self.result_spectate_btn = None
        self.result_focus_id = "return"     # 결과 화면 키보드 포커스 (restart/spectate/return)
        self._result_match = None           # 결과 화면 연출 시작 시각 기준 (경기마다 한 번만 재생)
        self._result_t0 = 0.0
        self.block_skin = "classic"         # 블록 모양 (settings의 block_skin, core.apply_visual_options가 갱신)
        self._bg_by_phase = {}
        self._hud_tip = None                # 프레임 끝에 그릴 HUD 툴팁 (문구, 기준 사각형)
        self._hud_rects = {}                # 코치 마크가 가리킬 HUD 사각형 (survivors / aim / incoming)
        self._theme_match_id = None
        self._theme_from = self._theme_to = 1
        self._theme_t0 = -10.0
        self._theme_border = STAGE_THEMES[1]["border"]
        self.pause_resume_btn = None
        self.pause_settings_btn = None
        self.pause_exit_btn = None
        self.lobby_return_left = None   # (참가자) 방장이 대기실로 돌아간 뒤 자동 이동까지 남은 초 (None이면 안내 없음)
        self.pause_focus = 0            # 일시정지 메뉴 키보드 포커스 (0=계속하기 1=다시 시작 2=환경설정 3=나가기)

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
        self.font_countdown = HiFont(font_name, 110, bold=True)       # 시작 카운트다운 숫자
        self.font_banner = {1: HiFont(font_name, 21, bold=True), 2: HiFont(font_name, 30, bold=True), 3: HiFont(font_name, 40, bold=True)}      # 액션 배너 단계별 글꼴

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
        if not self.mini_fast or getattr(self, "_shaking", False):
            draw()
            return
        self._check_ver()
        X0, Y0 = CANVAS.X(x), CANVAS.Y(y)
        X0 -= X0 % 2
        Y0 -= Y0 % 2
        frac = (round((CANVAS.ox + x * CANVAS.S) % 2.0, 3), round((CANVAS.oy + y * CANVAS.S) % 2.0, 3))   # 반올림이 달라지는 위치만 키로 (같은 2px 격자 이동은 재사용)
        ent = self._card_layers.get(slot)
        if ent is None or ent[0] != key or ent[1] != frac:
            surf = pygame.Surface((max(1, CANVAS.X(x + w) - X0 + 4), max(1, CANVAS.Y(y + h) - Y0 + 4)), pygame.SRCALPHA)
            with CANVAS.redirect(surf, X0, Y0):
                draw()
            ent = self._card_layers[slot] = (key, frac, surf)
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

    def _make_bg(self, top, bottom):
        surf = CANVAS.make_surface(self.width, self.height, alpha=False)
        w, h = pygame.Surface.get_size(surf)
        for y in range(h):
            pygame.draw.line(surf, _mix(top, bottom, y / h), (0, y), (w, y))
        return surf

    def _bg(self, phase=1):
        """배경 그라데이션 (네이티브 해상도로 단계별 1회 생성). phase: 경기 단계 1/2/3"""
        self._check_ver()
        if self.bg_surface is None:
            self._bg_by_phase = {}
            self.bg_surface = self._make_bg(C_BG_TOP, C_BG_BOTTOM)
            self._bg_by_phase[1] = self.bg_surface
        surf = self._bg_by_phase.get(phase)
        if surf is None:
            th = STAGE_THEMES[phase]
            surf = self._bg_by_phase[phase] = self._make_bg(th["top"], th["bottom"])
        return surf

    def _update_stage_theme(self, match):
        """경기 단계(1/2/3)가 바뀌면 배경과 보드 테두리 색을 1.4초에 걸쳐 새 단계 색으로 바꿈"""
        phase = min(3, max(1, getattr(match, "phase", 1)))
        now = time.time()
        if self._theme_match_id != id(match):                 # 새 경기는 이전 경기의 단계 색에서 페이드하지 않고 바로 시작
            self._theme_match_id = id(match)
            self._theme_from = self._theme_to = phase
            self._theme_t0 = -10.0
        elif phase != self._theme_to:
            self._theme_from, self._theme_to, self._theme_t0 = self._theme_to, phase, now
        t = min(1.0, (now - self._theme_t0) / 1.4)
        if t >= 1.0:
            self.screen.blit(self._bg(self._theme_to), (0, 0))
            self._theme_border = STAGE_THEMES[self._theme_to]["border"]
            return
        self.screen.blit(self._bg(self._theme_from), (0, 0))
        nxt = self._bg(self._theme_to)
        nxt.set_alpha(int(255 * t))
        self.screen.blit(nxt, (0, 0))
        nxt.set_alpha(None)
        tq = round(t * 6) / 6                                   # 테두리 글로우 캐시가 프레임마다 늘지 않도록 6단계로 끊음
        self._theme_border = _mix(STAGE_THEMES[self._theme_from]["border"], STAGE_THEMES[self._theme_to]["border"], tq)

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
        sdir = getattr(match, 'shake_dir', None)
        if shake > 0 and sdir:                           # 방향성 흔들림: 그 축으로 감쇠하는 사인파(약 18Hz) + 아주 작은 수직 떨림. 쿼드는 세로 펀치, 피격은 아래쪽
            kk = math.cos((time.time() - getattr(match, 'shake_t0', time.time())) * 2.0 * math.pi * 18.0)
            ox = sdir[0] * shake * kk + random.uniform(-0.15, 0.15) * shake
            oy = sdir[1] * shake * kk + random.uniform(-0.15, 0.15) * shake
        else:
            ox = random.uniform(-shake, shake) if shake > 0 else 0
            oy = random.uniform(-shake, shake) if shake > 0 else 0
        self._shaking = shake > 0                        # 흔들리는 동안은 미니 카드 레이어 캐시를 쓰지 않고 직접 그림 (틀과 내용이 같은 반올림으로 그려져 어긋나지 않고, 매 프레임 레이어를 새로 만드는 비용도 없음)

        now_t = time.perf_counter()
        pdt = min(0.1, max(0.0, now_t - getattr(self, "_last_render_t", now_t - 1.0 / 60.0)))
        self._last_render_t = now_t
        if time.time() - getattr(match, 'impact_t', 0.0) < 0.15 and getattr(match, 'shake_scale', 1.0) > 0:
            pdt *= 0.3                                    # 임팩트 프레임: 파티클만 잠깐 느려져 무게감 (경기 로직은 그대로)
        self.particles.update(pdt)
        engine = match.local_engine
        spectating = getattr(match, 'is_spectating', False)

        if engine.lines_cleared_total > self.last_cleared_count:
            self.last_cleared_count = engine.lines_cleared_total
            cx = self.main_board_x + self.main_board_w // 2
            cy = self.main_board_y + self.main_board_h // 2
            self.particles.add_sparks(cx, cy, (255, 230, 120), count=40, speed_mult=1.4)
            self.particles.add_shockwave(cx, cy + 80, (110, 235, 255), max_radius=100)
            ci = getattr(engine, "last_clear_info", None) or {}
            if ci.get("cleared", 0) >= 4 or ci.get("is_tspin"):                      # 큰 기술만 발광 파티클과 배경 링 (개수 제한)
                self.particles.add_sparks(cx, cy, (255, 235, 150), count=12, speed_mult=1.7, glow=True)
                self._add_bg_pulse(cx, cy, (255, 215, 110) if ci.get("cleared", 0) >= 4 else (200, 130, 255))

        if getattr(match, 'pc_count', 0) != self._pc_seen:             # 퍼펙트 클리어: 금빛 파티클과 쓸어올림 시작
            self._pc_seen = match.pc_count
            if match.pc_count > 0:
                self._pc_t0 = time.time()
                self.particles.add_sparks(self.main_board_x + self.main_board_w // 2, self.main_board_y + self.main_board_h // 2, (255, 215, 90), count=80, speed_mult=1.9)
        if getattr(match, 'cancel_seq', 0) != self._cancel_seen:        # 줄을 지워 공격을 막음: 받을 공격 칸에서 청록 스파크
            self._cancel_seen = match.cancel_seq
            self._cancel_t0 = time.time()
            ir = self._hud_rects.get("incoming")
            if ir is not None:
                self.particles.add_sparks(ir.centerx, ir.centery, (110, 235, 255), count=14, speed_mult=1.1)

        self._detect_board_reactions(match, engine, spectating, pdt)

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
        self.next_visible = (getattr(match, "mutator", None) or {}).get("next_visible", 5)      # 주간 변형 '안개 속': NEXT가 1개만 보임
        self._update_stage_theme(match)
        self._render_bg_pulses(match, ox, oy)

        self._render_mini_boards(match, ox, oy)
        self._render_attack_effects(match, ox, oy)
        self._render_main_board(match, ox, oy)
        self.particles.draw(self.screen, ox, oy)
        self._render_reactions(match, ox, oy)
        self._render_board_juice(match, ox, oy)
        self._render_top_banner(match, ox, oy)
        if not getattr(match, 'is_paused', False):
            self._render_floating_texts(match, ox, oy)
        if not spectating:
            self._render_key_hints(ox, oy)
        self._render_scoreboard(match)
        self._render_chat_overlay()
        self._render_ko_orbs(match)
        self._draw_hud_tooltip()
        if self.lobby_return_left is not None:                       # 방장이 대기실로 돌아감: 순위표를 읽을 시간을 주고 안내
            msg = f"방장이 대기실로 돌아갔습니다 · R 키로 바로 이동 ({int(self.lobby_return_left) + 1}초 뒤 자동 이동)"
            ts = self._text(msg, self.font_small, (225, 232, 250))
            br = pygame.Rect(0, 0, ts.get_width() + 32, 34)
            br.midbottom = (self.width // 2, self.height - 10)
            pygame.draw.rect(self.screen, (14, 18, 32), br, border_radius=10)
            pygame.draw.rect(self.screen, C_GOLD, br, 1, border_radius=10)
            self.screen.blit(ts, (br.x + 16, br.centery - ts.get_height() // 2))
        self._draw_coach_marks(match)
        self._render_countdown(match, ox, oy)
        if getattr(match, 'is_paused', False):
            self._render_pause_overlay()

        if spectating and not match.match_finished:
            self._render_spectate_notice(match)
        if match.match_finished and self._vic_t0 is not None and time.time() - self._vic_t0 < self.VICTORY_CEREMONY:
            pass                                           # 우승 세리머니(보드가 금빛으로 터지고 왕관·색종이) 동안은 순위표를 미룸
        elif match.match_finished:
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
        pins = sorted((ft for ft in active if ft.get("category") == "pin"), key=lambda f: f["birth"])[-1:]      # 후반전 예고/배율 알림은 토스트 칸 한 자리를 차지하고 다른 토스트에 밀려나지 않음
        tips = sorted((ft for ft in active if ft.get("category") == "tip"), key=lambda f: f["birth"])[-1:]      # 첫 경험 팁: 한 번에 하나, 전투 토스트 칸과 별도
        feed = sorted((ft for ft in active if ft.get("category") not in ("action", "pin", "tip")), key=lambda f: f["birth"])
        prio = {"alert": 3, "ko": 3, "attack": 2}                     # 칸이 모자라면 낮은 것부터 밀어냄: 피격·K.O. > 공격 > 콤보 등 (같으면 오래된 것부터)
        while len(feed) > 2 - len(pins):
            drop = min(range(len(feed)), key=lambda i: (prio.get(feed[i].get("category"), 1), feed[i]["birth"]))
            del feed[drop]
        feed = pins + feed

        cx_board = self.main_board_x + self.main_board_w // 2 + ox

        self._render_action_banner(actions, now, cx_board, oy)

        for ft in tips:
            progress = (now - ft["birth"]) / ft["duration"]
            alpha = max(0, min(255, int(255 * (1.0 - progress ** 6))))
            surf = self.font_small.render(ft["text"], True, (250, 240, 200))
            tw, th = surf.get_size()
            plate = pygame.Rect(0, 0, tw + 28, th + 12)
            plate.midtop = (int(cx_board), 68 + 2 * 22 + 8 + int(oy))
            CANVAS.alpha_rect(plate, (34, 30, 12, int(alpha * 0.92)), radius=10)
            CANVAS.alpha_rect(plate, (*C_GOLD, int(alpha * 0.9)), width=2, radius=10)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (plate.x + 14, plate.y + 6))

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

    def _render_board_juice(self, match, ox, oy):
        """퍼펙트 클리어의 금빛 쓸어올림 + 아주 큰 순간의 임팩트 프레임(약 70ms 하얀 번쩍임). 번쩍임은 화면 흔들림 설정이 '끔'이면 그리지 않고 '약하게'면 약해짐"""
        now = time.time()
        board = pygame.Rect(int(self.main_board_x + ox), int(self.main_board_y + oy), self.main_board_w, self.main_board_h)
        age = now - self._pc_t0
        if 0.0 <= age < 0.8:
            k = self._ease_out(age / 0.8)
            band = 90
            top_y = board.bottom - (board.h + band) * k
            fade = 1.0 - age / 0.8
            for i, (hh, aa) in enumerate(((band, 40), (int(band * 0.6), 60), (int(band * 0.25), 90))):
                y0 = int(top_y + (band - hh) / 2)
                r = pygame.Rect(board.x, max(board.y, y0), board.w, 0)
                r.h = max(0, min(board.bottom, y0 + hh) - r.y)
                if r.h > 0:
                    CANVAS.alpha_rect(r, (255, 215, 90, int(aa * fade * 2.2)))
        scale = getattr(match, 'shake_scale', 1.0)
        ia = now - getattr(match, 'impact_t', 0.0)
        if scale > 0 and 0.0 <= ia < 0.07:
            a = int(110 * getattr(match, 'impact_power', 1.0) * min(1.0, scale + 0.3) * (1.0 - ia / 0.07))
            if a > 0:
                CANVAS.alpha_rect(board.inflate(8, 8), (255, 255, 255, a), radius=6)

    POP_SECS = 0.14                      # 배너가 처음 나타날 때 커졌다 줄어드는 시간

    def _scaled_hi(self, surf, factor):
        """HiSurf를 factor배로 키운(줄인) HiSurf (논리 크기도 factor배로 보고됨)"""
        w, h = pygame.Surface.get_size(surf)
        nw, nh = max(1, int(w * factor)), max(1, int(h * factor))
        out = HiSurf((nw, nh), pygame.SRCALPHA, surf.scale)
        out.blit(pygame.transform.smoothscale(surf, (nw, nh)), (0, 0))
        return out

    def _render_action_banner(self, actions, now, cx_board, oy):
        """액션 배너: 한 번에 메인 1개(가장 높은 tier, 같으면 최신) + 같은 순간에 나온 배너 1개를 아래 작은 줄로 (위기 탈출/복수가 큰 기술 배너에 가려 안 보이던 문제).
        tier가 클수록 큰 글꼴, 나타날 때 1.35배에서 1.0배로 줄어드는 팝인과 테두리 흰 번쩍임, tier 3은 금빛 광채"""
        if not actions:
            return
        ranked = sorted(actions, key=lambda f: (f.get("tier", 1), f["birth"]))
        main = ranked[-1]
        subs = [f for f in ranked[:-1] if abs(f["birth"] - main["birth"]) < 0.5][-1:]
        max_w = self.main_board_w + 44
        progress = (now - main["birth"]) / main["duration"]
        alpha = max(0, min(255, int(255 * (1.0 - progress ** 3))))
        age = now - main["birth"]
        tier = main.get("tier", 1)
        chain = [self.font_banner[tier], self.font_banner[max(1, tier - 1)], self.font_banner[1], self.font_hud, self.font_small]   # 보드 폭 안에 들어가는 가장 큰 글꼴
        font = chain[-1]
        for cand in chain:
            if cand.size(main["text"])[0] + 32 <= max_w:
                font = cand
                break
        surf = font.render(main["text"], True, main["color"])
        pop = 1.0
        if age < self.POP_SECS and getattr(self, "banner_pop", True):
            pop = 1.0 + 0.35 * (1.0 - age / self.POP_SECS) ** 2
            surf = self._scaled_hi(surf, pop)
        tw, th = surf.get_size()
        cy = self.main_board_y + self.cell_size * 2 + 4 - progress * 10 + oy        # 스폰 구역(위 2줄) 바로 아래: 쌓인 블록이 보이는 쪽과 가장 멀다
        plate = pygame.Rect(int(cx_board - (tw + 32) // 2), int(cy), tw + 32, th + 14)
        if tier >= 3:                                                                # 가장 큰 기술: 금빛 광채
            CANVAS.alpha_rect(plate.inflate(14, 12), (255, 210, 80, int(alpha * 0.16)), radius=16)
            CANVAS.alpha_rect(plate.inflate(6, 5), (255, 225, 120, int(alpha * 0.22)), radius=13)
        CANVAS.alpha_rect(plate, (10, 13, 24, int(alpha * 0.55)), radius=10)
        flash = max(0.0, 1.0 - age / self.POP_SECS) if age < self.POP_SECS else 0.0
        edge = _mix(main["color"][:3], (255, 255, 255), flash)
        CANVAS.alpha_rect(plate, (*edge, int(alpha * 0.85)), width=2, radius=10)
        surf.set_alpha(alpha)
        self.screen.blit(surf, (plate.x + 16, plate.y + 7))
        for k, sub in enumerate(subs):                                              # 같은 순간의 보조 배너: 메인 아래에 작게
            s2 = self.font_hud.render(sub["text"], True, sub["color"])
            sw, sh = s2.get_size()
            p2 = pygame.Rect(0, 0, sw + 26, sh + 8)
            p2.midtop = (int(cx_board), plate.bottom + 4 + k * (sh + 12))
            CANVAS.alpha_rect(p2, (10, 13, 24, int(alpha * 0.55)), radius=9)
            CANVAS.alpha_rect(p2, (*sub["color"][:3], int(alpha * 0.8)), width=1, radius=9)
            s2.set_alpha(alpha)
            self.screen.blit(s2, (p2.x + 13, p2.y + 4))

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
                    drop = next((i for i, x in enumerate(pend) if not x.get("prio", 0) and not x.get("mine")), None)      # 남의 일반 소식부터, 그다음 내 소식, 마지막이 중요 소식
                    if drop is None:
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
        pw, ph = 440, 324
        px = (self.width - pw) // 2
        py = (self.height - ph) // 2

        CANVAS.overlay((4, 6, 12, 165))

        self._panel((px, py, pw, ph), border=C_GOLD, bg=(16, 20, 36), radius=16, alpha=245, border_w=2)
        self._draw_text("일시 정지", self.font_large, C_GOLD, px + pw // 2, py + 24, "midtop")
        self._draw_text("PAUSED  ·  F1 규칙 요약", self.font_tiny, C_DIM, px + pw // 2, py + 58, "midtop")

        mx, my = pygame.mouse.get_pos()
        self.pause_resume_btn = pygame.Rect(px + 40, py + 88, pw - 80, 44)
        self.pause_restart_btn = pygame.Rect(px + 40, py + 142, pw - 80, 44)
        self.pause_settings_btn = pygame.Rect(px + 40, py + 196, pw - 80, 44)
        self.pause_exit_btn = pygame.Rect(px + 40, py + 250, pw - 80, 44)
        moved = (mx, my) != getattr(self, "_pause_last_mouse", None)       # 마우스가 실제로 움직였을 때만 호버로 포커스를 옮김 (↑↓ 키 탐색이 되돌려지지 않게)
        self._pause_last_mouse = (mx, my)
        if moved:
            for i, btn in enumerate((self.pause_resume_btn, self.pause_restart_btn, self.pause_settings_btn, self.pause_exit_btn)):
                if btn.collidepoint(mx, my):    # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮겨서, 두 버튼이 동시에 하이라이트되지 않게 함
                    self.pause_focus = i
                    break
        self._button(self.pause_resume_btn, "계속하기", "blue", self.pause_focus == 0, "P")
        self._button(self.pause_restart_btn, "다시 시작", "blue", self.pause_focus == 1, "R")
        self._button(self.pause_settings_btn, "환경 설정", "green", self.pause_focus == 2)
        self._button(self.pause_exit_btn, "메인 메뉴로 나가기", "red", self.pause_focus == 3, "ESC")

    # ---------------------------------------------------------------- 상단 HUD
    KO_ORB_FLIGHT = 0.7      # 처치한 상대 카드에서 K.O. 칸까지 날아가는 시간(초)

    def _render_ko_orbs(self, match):
        """내가 K.O.를 낼 때 처치한 상대 카드에서 K.O. 칸으로 빛 구슬이 날아가 도착하면 칸이 번쩍임 (배지 진행이 몸으로 느껴지게)"""
        orbs = getattr(match, "ko_orbs", None)
        dest_rect = self._hud_rects.get("ko")
        if not orbs or dest_rect is None:
            return
        now = time.time()
        dest = dest_rect.center
        fly = self.KO_ORB_FLIGHT
        match.ko_orbs = orbs = [o for o in orbs if now - o["t0"] < fly + 0.35]
        for o in orbs:
            age = now - o["t0"]
            src_rect = self.mini_board_rects.get(o["victim"])
            src = src_rect.center if src_rect is not None else (self.main_board_x + self.main_board_w // 2, self.main_board_y + self.main_board_h // 2)
            if age < fly:
                def pos(a):
                    k = _ease_out(a / fly)
                    x = src[0] + (dest[0] - src[0]) * k
                    y = src[1] + (dest[1] - src[1]) * k - math.sin(k * math.pi) * 60      # 위로 살짝 휘어 날아감
                    return x, y
                big = 4 if o.get("gold") else 0                                        # 현상금 처치: 더 크고 진한 금빛 구슬
                for j in range(6, 0, -1):                                              # 꼬리
                    tx, ty = pos(max(0.0, age - j * 0.03))
                    pygame.draw.circle(self.screen, _mix((255, 210, 80), (255, 120, 40), j / 6.0), (int(tx), int(ty)), max(2, 8 - j + big // 2))
                x, y = pos(age)
                pygame.draw.circle(self.screen, (255, 200, 60) if big else (255, 240, 170), (int(x), int(y)), 9 + big)
                pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), 5 + big // 2)
            else:
                k = (age - fly) / 0.35                                                 # 도착: K.O. 칸이 번쩍임
                pygame.draw.rect(self.screen, _mix((255, 230, 120), (255, 255, 255), 1.0 - k), dest_rect.inflate(int(10 * k), int(10 * k)), 3, border_radius=10)
                pygame.draw.circle(self.screen, (255, 240, 170), dest, int(14 + 30 * k), max(1, int(4 * (1.0 - k))))

    def _render_countdown(self, match, ox=0, oy=0):
        """혼자 하는 경기 시작 전 3-2-1 (끝나면 잠깐 GO!). 보드 한가운데에 크게"""
        until = getattr(match, "countdown_until", 0.0)
        if until <= 0.0:
            return
        left = until - time.time()
        if left > 0:
            n = int(math.ceil(left))
            frac = left - (n - 1)                            # 숫자 하나가 보이는 1초 동안 1 -> 0
            text, col = str(n), (255, 226, 130)
            alpha = int(255 * min(1.0, 0.35 + frac))
        elif left > -0.6:
            text, col = "GO!", (140, 255, 170)
            alpha = int(255 * (1.0 - (-left) / 0.6))
        else:
            return
        cx = self.main_board_x + self.main_board_w // 2 + ox
        cy = self.main_board_y + self.main_board_h // 2 - 20 + oy
        surf = self.font_countdown.render(text, True, col)
        surf.set_alpha(max(0, min(255, alpha)))
        self.screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))
        if left > 0:
            sub = self.font_mid.render("준비하세요!", True, (225, 232, 250))
            sub.set_alpha(max(0, min(255, alpha)))
            self.screen.blit(sub, (cx - sub.get_width() // 2, cy + surf.get_height() // 2))

    def _draw_coach_marks(self, match):
        """첫 경기 한 번만: 핵심 HUD 3곳(생존자 / 조준 모드 / 받을 공격) 말풍선. 끝나기 2초 전부터 사라짐"""
        left = getattr(match, "coach_until", 0.0) - time.time()
        if left <= 0 or not getattr(match, "local_is_alive", True) or getattr(match, "is_spectating", False):
            return
        rects = self._hud_rects
        specs = [("survivors", "① 남은 생존자 수. 마지막 1명이 우승!  (Enter/클릭으로 닫기)", "below-left"),
                 ("aim", "② 조준 모드: 공격 대상을 정해요. 처음엔 자동(AUTO) 그대로 OK  (TAB / 1~5)", "below-left"),
                 ]                                                                       # ③받을 공격 ④K.O.는 처음 일어날 때 '첫 경험 팁'으로 알려 줌 (처음부터 한꺼번에 가리지 않게)
        y_top = None
        alpha = 255 if left > 2.0 else int(255 * left / 2.0)
        for key, text, place in specs:
            anchor = rects.get(key)
            if anchor is None:
                continue
            surf = self._text(text, self.font_small, (250, 240, 200))
            w, h = surf.get_width() + 22, surf.get_height() + 14
            if place == "below-right":
                r = pygame.Rect(max(8, anchor.right - w), anchor.bottom + 10, w, h)
            else:
                r = pygame.Rect(max(8, min(self.width - w - 8, anchor.x)), (y_top if y_top is not None else anchor.bottom + 10), w, h)
                y_top = r.bottom + 8
            pygame.draw.line(self.screen, C_GOLD, (anchor.centerx if place == "below-right" else min(anchor.right - 10, max(anchor.x + 10, r.x + 20)), anchor.bottom),
                             (r.x + 20 if place != "below-right" else r.right - 20, r.y), 2)
            CANVAS.alpha_rect(r, (34, 30, 12, int(235 * alpha / 255)), radius=9)          # 화면 배율이 1.0이 아니어도 글자가 잘리지 않게 임시 서피스 대신 직접 그림
            CANVAS.alpha_rect(r, (*C_GOLD, alpha), width=2, radius=9)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (r.x + 11, r.y + 7))
            surf.set_alpha(255)                                                          # 글자 서피스는 캐시되므로 투명도를 되돌려 둠

    def _draw_hud_tooltip(self):
        tip, self._hud_tip = self._hud_tip, None
        if not tip or not tip[0]:
            return
        text, anchor = tip
        max_w = min(340, self.width - 16 - 20)                                  # 화면 폭을 넘지 않게 줄바꿈 (한글은 글자 단위)
        lines, cur = [], ""
        for ch in text:
            if cur and self.font_small.size(cur + ch)[0] > max_w:
                lines.append(cur)
                cur = ch.lstrip()
            else:
                cur += ch
        if cur:
            lines.append(cur)
        surfs = [self._text(ln, self.font_small, (225, 232, 250)) for ln in lines]
        lh = surfs[0].get_height() + 2
        w, h = max(sf.get_width() for sf in surfs) + 20, lh * len(surfs) + 10
        x = max(8, min(self.width - w - 8, anchor.x - 8))
        r = pygame.Rect(x, anchor.bottom + 10, w, h)
        pygame.draw.rect(self.screen, (14, 18, 32), r, border_radius=8)
        pygame.draw.rect(self.screen, C_ACCENT, r, 1, border_radius=8)
        for i, sf in enumerate(surfs):
            self.screen.blit(sf, (r.x + 10, r.y + 5 + i * lh))

    def _survivor_title(self, match):
        """생존자 칸 제목: 평소 '생존자', 주간 변형이면 규칙 이름, 오늘의 도전이면 지난 최고 기록과의 비교(고스트)"""
        if getattr(match, "practice", False):
            return "연습"
        mut = getattr(match, "mutator", None)
        if mut and getattr(match, "weekly", None):
            return f"생존자 · {mut['name']}"
        if getattr(match, "daily", None):
            ghost = getattr(match, "ghost", None)
            if not ghost:
                return "생존자 · 첫 시도"
            left = int(ghost["secs"]) - int(match.elapsed)
            if not getattr(match, "local_is_alive", True) or getattr(match, "match_finished", False):
                return "생존자"
            return f"생존자 · 기록까지 {left // 60}:{left % 60:02d}" if left > 0 else "생존자 · ★기록 경신 중"
        return "생존자"

    def _render_top_banner(self, match, ox=0, oy=0):
        """상단 3분할 HUD: 생존자 / 조준(모드 칩 + 대상) / 배지·K.O."""
        w1, w2, w3, gap, h = 170, 400, 170, 10, 58
        total_w = w1 + w2 + w3 + gap * 2
        sx = (self.width - total_w) // 2 + ox
        by = 8 + oy

        # 1. 생존자
        r1 = pygame.Rect(int(sx), int(by), w1, h)
        self._hud_rects["survivors"] = r1
        self._panel(r1, border=C_GOLD)
        practice = getattr(match, "practice", False)
        self._draw_text(self._survivor_title(match), self.font_tiny, C_GOLD, r1.centerx, r1.y + 5, "midtop")
        self._draw_text("연습 중" if practice else f"{match.alive_count} / {match.total_players}", self.font_num, C_TEXT, r1.centerx, r1.y + 16, "midtop")
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
        self._hud_rects["aim"] = r2

        chip_gap = 4
        chip_w = (w2 - 20 - chip_gap * (len(TARGET_MODES) - 1)) // len(TARGET_MODES)
        manual = getattr(match, 'local_manual_target_id', None)
        self.target_chip_rects = {}
        for i, mode in enumerate(TARGET_MODES if aim_on else ()):
            cr = pygame.Rect(r2.x + 10 + i * (chip_w + chip_gap), r2.y + 6, chip_w, 19)
            self.target_chip_rects[mode] = cr
            active = (mode == match.local_target_mode and not manual)
            if active:
                pygame.draw.rect(self.screen, accent, cr, border_radius=9)
                col = (12, 16, 28)
            else:
                novice_dim = getattr(match, "novice", False) and mode != "AUTO"          # 첫 3판: 자동 칩만 또렷하게 (다른 모드는 알아서 보게 흐리게)
                pygame.draw.rect(self.screen, (20, 25, 42) if novice_dim else (28, 34, 56), cr, border_radius=9)
                col = (72, 80, 104) if novice_dim else C_DIM
            self._draw_text(TARGET_MODE_LABELS.get(mode, mode), self.font_tiny, col, cr.centerx, cr.centery, "center")
            if cr.collidepoint(pygame.mouse.get_pos()):                # 칩에 마우스를 올리면 설명 (다른 그림 위에 그리려고 프레임 끝에서 표시)
                self._hud_tip = (TARGET_MODE_HELP.get(mode, ""), cr)

        name = target_p.get("name", "탐색 중...")[:12]
        tag = "수동 지정 · 우클릭 해제" if manual else "TAB으로 변경"
        spec_now = aim_on and getattr(match, 'is_spectating', False)
        if spec_now:                                                # 관전 중에는 죽은 내 조준 대상/TAB 안내 대신 관전 안내 (TAB은 동작하지 않음)
            self._draw_text("관전 중 · 조준은 사용할 수 없습니다", self.font_small, C_DIM, r2.centerx, r2.y + 37, "center")
            att_count = 0
        elif aim_on:
            self._draw_text(f"● {name}" + ("  (사람)" if is_human else ""), self.font_hud,
                            C_GREEN if is_human else C_TEXT, r2.x + 12, r2.y + 37, "midleft")
            if target_p:                                           # 대상의 위험도(쌓인 높이 + 곧 올라올 쓰레기): 한 방 더로 K.O.가 가능한지 한눈에
                dg = min(1.0, match._danger(target_p) / float(BOARD_HEIGHT))
                dcol = C_DANGER if dg >= 0.75 else (C_ORANGE if dg >= 0.5 else C_GREEN)
                if is_colorblind():                                 # 색약 보정: 파랑/노랑/주황 + 글자로도 위험 단계를 알림
                    dcol = (255, 120, 40) if dg >= 0.75 else ((255, 205, 70) if dg >= 0.5 else (80, 160, 255))
                    if dg >= 0.5:
                        self._draw_text("위험!" if dg >= 0.75 else "주의", self.font_tiny, dcol, r2.x + w2 - 14, r2.bottom - 8, "bottomright")
                self._draw_bar((r2.x + 14, r2.bottom - 5, w2 - 28, 3), dg, dcol)
        else:
            self._draw_text("연습 모드" if getattr(match, "practice", False) else "공격 없이 끝까지 생존", self.font_hud, C_TEXT, r2.centerx, r2.y + 10, "midtop")
        if not spec_now:
            att_count = match.get_attackers_count_for(match.local_player_id)
        if spec_now:
            pass
        elif not getattr(match, "attacks_enabled", True):
            task = match.practice_current_task() if getattr(match, "practice", False) else None
            if getattr(match, "practice", False):
                ttxt = f"과제 {task[0] + 1}/{len(match.PRACTICE_TASKS)} · {task[1]}" if task else "과제 모두 완료!  G 쓰레기 · B 초기화"
                while len(ttxt) > 6 and self.font_small.size(ttxt)[0] > r2.w - 20:
                    ttxt = ttxt[:-2].rstrip(" ·") + "…"
                self._draw_text(ttxt, self.font_small, C_GREEN, r2.centerx, r2.y + 36, "midtop")
                if getattr(match, "drill_on", False):
                    self._draw_text(f"드릴 {match.drill_seconds()}초 · Lv.{match.drill_level() + 1} · 최고 {match.drill_best}초", self.font_tiny, C_ORANGE, r2.right - 10, r2.y + 14, "topright")
                else:
                    self._draw_text("G 쓰레기 · B 초기화 · V 드릴", self.font_tiny, C_DIM, r2.right - 10, r2.y + 14, "topright")
            else:
                self._draw_text("서바이벌 모드", self.font_small, C_GREEN, r2.centerx, r2.y + 36, "midtop")
        elif att_count >= 2:
            self._draw_text(f"나를 노림 {att_count}명  역습 +{match.get_attacker_bonus(att_count)}", self.font_small,
                            C_DANGER, r2.right - 12, r2.y + 37, "midright")
        elif att_count == 1:
            self._draw_text("나를 노림 1명", self.font_small, C_ORANGE, r2.right - 12, r2.y + 37, "midright")
        else:
            self._draw_text(tag, self.font_tiny, C_DIM, r2.right - 12, r2.y + 37, "midright")

        if not getattr(match, "attacks_enabled", True):
            return                                                  # 서바이벌: 배지/K.O. 칸 없음
        # 3. 배지 / K.O.
        r3 = pygame.Rect(int(sx + w1 + w2 + gap * 2), int(by), w3, h)
        self._hud_rects["ko"] = r3
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
    def _cell_surface(self, piece_type, size, dim=False, alpha=None, skin=None):
        """블록 셀 (네이티브 해상도로 생성하여 캐시). skin이 없으면 설정의 블록 스킨을 따름 (로고/메뉴 배경은 "classic"을 지정)"""
        self._check_ver()
        skin = skin or self.block_skin
        key = (piece_type, size, dim, alpha, skin)
        surf = self._cell_cache.get(key)
        if surf is not None:
            return surf
        S = CANVAS.S
        color = PIECE_COLORS.get(piece_type, (180, 180, 200))
        surf = CANVAS.make_surface(size, size)
        n = pygame.Surface.get_width(surf)
        sc = lambda v: max(1, int(round(v * S)))
        outer = pygame.Rect(sc(1), sc(1), n - 2 * sc(1), n - 2 * sc(1))
        if skin == "neon":
            radius = int(round(max(2, size // 5) * S))
            pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.82), outer, border_radius=radius)          # 어두운 몸통
            pygame.draw.rect(surf, color, outer, max(1, sc(2)), border_radius=radius)                   # 빛나는 테두리
            if size >= 12:
                ring = outer.inflate(-sc(6), -sc(6))
                pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.55), ring, 1, border_radius=max(1, radius - sc(2)))
                core = pygame.Rect(0, 0, max(sc(3), n // 4), max(sc(3), n // 4))
                core.center = outer.center
                pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.55), core, border_radius=max(1, core.w // 3))
        elif skin == "pixel":                                                   # 각진 8비트: 밝은 윗/왼쪽 변, 어두운 아래/오른쪽 변, 가운데 단색
            pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.50), outer)
            bev = max(sc(2), n // 8)
            body = pygame.Rect(outer.x, outer.y, outer.w - bev, outer.h - bev)
            pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.35), body)
            inner = pygame.Rect(outer.x + bev, outer.y + bev, outer.w - 2 * bev, outer.h - 2 * bev)
            pygame.draw.rect(surf, color, inner)
            if size >= 14:
                step = max(sc(3), n // 5)
                for gx in range(inner.x + step, inner.right - 1, step):
                    pygame.draw.line(surf, _mix(color, (0, 0, 0), 0.18), (gx, inner.y), (gx, inner.bottom - 1), 1)
                for gy in range(inner.y + step, inner.bottom - 1, step):
                    pygame.draw.line(surf, _mix(color, (0, 0, 0), 0.18), (inner.x, gy), (inner.right - 1, gy), 1)
        elif skin == "glass":                                                   # 반투명 유리: 옅은 몸통 + 밝은 테두리 + 위쪽 반사광
            radius = int(round(max(2, size // 6) * S))
            glass = pygame.Surface((n, n), pygame.SRCALPHA)
            pygame.draw.rect(glass, (*color, 150), outer, border_radius=radius)
            pygame.draw.rect(glass, (*_mix(color, (255, 255, 255), 0.6), 235), outer, max(1, sc(2)), border_radius=radius)
            if size >= 12:
                hl = pygame.Rect(outer.x + sc(3), outer.y + sc(3), outer.w - 2 * sc(3), max(sc(2), outer.h // 4))
                pygame.draw.rect(glass, (255, 255, 255, 80), hl, border_radius=max(1, radius - sc(2)))
            surf.blit(glass, (0, 0))
        elif skin == "starlight":                                               # 별빛: 어두운 몸통 + 은은한 테두리 + 가운데 4갈래 별
            radius = int(round(max(2, size // 6) * S))
            pygame.draw.rect(surf, _mix(color, (8, 10, 24), 0.72), outer, border_radius=radius)
            pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.25), outer, max(1, sc(1)), border_radius=radius)
            if size >= 10:
                cx, cy = outer.center
                arm = max(sc(2), n // 3)
                thin = max(1, sc(1))
                star = _mix(color, (255, 255, 255), 0.75)
                pygame.draw.line(surf, star, (cx - arm, cy), (cx + arm, cy), thin)
                pygame.draw.line(surf, star, (cx, cy - arm), (cx, cy + arm), thin)
                pygame.draw.circle(surf, (255, 255, 255), (cx, cy), max(1, sc(1)))
        elif skin == "ember":                                                   # 불씨: 어두운 숯 몸통 + 색이 번지는 안쪽 테두리 + 가운데 뜨거운 불씨
            radius = int(round(max(2, size // 6) * S))
            pygame.draw.rect(surf, _mix(color, (18, 8, 4), 0.78), outer, border_radius=radius)
            pygame.draw.rect(surf, _mix(color, (255, 150, 60), 0.35), outer, max(1, sc(2)), border_radius=radius)
            if size >= 10:
                inner = outer.inflate(-sc(6), -sc(6))
                pygame.draw.rect(surf, _mix(color, (60, 14, 6), 0.55), inner, 1, border_radius=max(1, radius - sc(2)))
                core = pygame.Rect(0, 0, max(sc(3), n // 3), max(sc(3), n // 3))
                core.center = outer.center
                pygame.draw.rect(surf, _mix(color, (255, 190, 90), 0.7), core, border_radius=max(1, core.w // 3))
                pygame.draw.rect(surf, (255, 235, 170), core.inflate(-core.w // 2, -core.h // 2), border_radius=1)
        elif skin == "prism":                                                   # 프리즘: 위/왼/오른/아래 삼각 면의 밝기가 다른 보석
            c0, c1, c2, c3 = outer.topleft, outer.topright, outer.bottomright, outer.bottomleft
            ctr = outer.center
            faces = (((c0, c1, ctr), 0.55), ((c0, c3, ctr), 0.25), ((c1, c2, ctr), -0.18), ((c3, c2, ctr), -0.38))
            for pts, k in faces:
                col = _mix(color, (255, 255, 255), k) if k > 0 else _mix(color, (0, 0, 0), -k)
                pygame.draw.polygon(surf, col, pts)
            pygame.draw.rect(surf, _mix(color, (255, 255, 255), 0.7), outer, max(1, sc(1)))
        elif skin == "flat":
            radius = int(round(max(1, size // 10) * S))
            pygame.draw.rect(surf, color, outer, border_radius=radius)
            pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.30), outer, 1, border_radius=radius)
        elif skin == "jelly":
            radius = int(round(max(3, size * 0.34) * S))
            pygame.draw.rect(surf, _mix(color, (0, 0, 0), 0.40), outer, border_radius=radius)           # 아래쪽 그늘
            body = pygame.Rect(outer.x, outer.y, outer.w, outer.h - sc(2))
            pygame.draw.rect(surf, color, body, border_radius=radius)
            if size >= 12:
                gw, gh = max(2, int(body.w * 0.62)), max(2, int(body.h * 0.34))
                gloss = pygame.Surface((gw, gh), pygame.SRCALPHA)
                pygame.draw.ellipse(gloss, (255, 255, 255, 105), (0, 0, gw, gh))
                surf.blit(gloss, (body.x + int(body.w * 0.14), body.y + sc(2)))
                dot = max(sc(2), n // 9)
                spec = pygame.Surface((dot * 2, dot * 2), pygame.SRCALPHA)
                pygame.draw.circle(spec, (255, 255, 255, 170), (dot, dot), dot)
                surf.blit(spec, (body.x + int(body.w * 0.14) - dot // 2, body.y + int(body.h * 0.10)))
        else:
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
        thick = max(1, int(round(2 * S)))
        if size < 14:                                             # 아주 작은 칸(미니 보드)은 점선이 뭉개지므로 실선 유지
            pygame.draw.rect(surf, (*color, 190), r, thick, border_radius=rad)
        else:                                                     # 점선 테두리: 한 변에 굵은 대시 2개(큰 칸은 3개)
            k = 2 if size < 30 else 3
            corners = [r.topleft, r.topright, r.bottomright, r.bottomleft]
            for i in range(4):
                (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
                for d in range(k):
                    s0, s1 = (d + 0.2) / k, (d + 0.8) / k
                    pygame.draw.line(surf, (*color, 205), (ax + (bx - ax) * s0, ay + (by - ay) * s0),
                                     (ax + (bx - ax) * s1, ay + (by - ay) * s1), thick)
        self._ghost_cache[key] = surf
        return surf

    @staticmethod
    def _garbage_level_color(i):
        """받을 공격 게이지 i번째 줄(0=맨 아래)의 색: 적을 땐 초록, 쌓일수록 노랑 -> 빨강 (8줄 이상이면 빨강)"""
        t = min(1.0, i / 7.0)
        if is_colorblind():                                   # 색약 보정: 초록-빨강 대신 파랑 -> 주황 (밝기 차이도 큼)
            return _mix((70, 150, 255), (255, 140, 40), t)
        if t < 0.5:
            return _mix((90, 225, 130), (255, 222, 90), t * 2.0)
        return _mix((255, 222, 90), (255, 84, 94), (t - 0.5) * 2.0)

    def _draw_garbage_bar(self, engine, incoming, bar_x, by, bh, cs):
        """받을 공격 게이지: 1줄 = 1칸, 아래쪽이 먼저 올라올 것. 색은 쌓인 양(초록 -> 빨강), 공격을 받은 묶음 사이는 한 칸 틈으로 구분.
        차징 중(아직 안 올라옴)은 어둡게, 다음 락다운에 올라올 수 있는 것은 밝게"""
        segs_fn = getattr(engine, "garbage_segments", None)
        segs = segs_fn() if callable(segs_fn) else [(incoming, True, None)]
        bg = (16, 19, 32)
        i = 0
        for lines, ready, _source in segs:
            for k in range(lines):
                if i >= BOARD_HEIGHT:
                    break
                base = self._garbage_level_color(i)
                col = base if ready else _mix(base, bg, 0.6)
                cy0 = by + bh - (i + 1) * cs
                top_gap = 2 if (k == lines - 1 and i < incoming - 1) else 1      # 묶음의 맨 위 칸은 위쪽 틈을 넓혀 묶음 경계를 보이게
                pygame.draw.rect(self.screen, col, (bar_x + 1, cy0 + top_gap, 6, cs - 1 - top_gap), border_radius=2)
                i += 1

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
        bounce = 0.0
        ba = time.time() - self._bounce_t0
        if 0.0 <= ba < 0.12:
            bounce = self._bounce_amp * (1.0 - ba / 0.12) ** 2         # 하드 드롭: 보드만 살짝 눌렸다 돌아옴 (패널은 그대로)
        by = self.main_board_y + oy + bounce
        bw, bh = self.main_board_w, self.main_board_h
        board_rect = pygame.Rect(bx, by, bw, bh)

        # 1. 보드 배경 + 미세 그리드
        border_col = C_GOLD if spectating else self._theme_border
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
        bar_x = bx - 14                                                # 게이지는 배경/테두리 없이 칸만 그림 (복잡해 보이지 않게)
        incoming = engine.incoming_garbage
        if incoming > 0:
            self._draw_garbage_bar(engine, incoming, bar_x, by, bh, cs)

        # 3. 고정된 블록 (줄 제거 뒤 내려앉기 / 쓰레기 줄 상승 / 탑아웃 붕괴 / 우승 세리머니 반영)
        now = time.time()
        settle, rise, topout = self._settle, self._rise, self._topout
        s_rem = r_rem = 0.0
        if settle is not None:
            if now - settle["t0"] < self.SETTLE_SECS and not spectating:
                s_rem = 1.0 - _ease_out((now - settle["t0"]) / self.SETTLE_SECS)
            else:
                self._settle = settle = None
        if rise is not None:
            if now - rise["t0"] < self.RISE_SECS and not spectating:
                r_rem = rise["n"] * (1.0 - _ease_out((now - rise["t0"]) / self.RISE_SECS))
            else:
                self._rise = rise = None
        gray_to = int((now - topout["t0"]) / 0.04) if (topout is not None and not spectating) else -1
        vic_row = self._vic_row if (self._vic_t0 is not None and not spectating) else BOARD_HEIGHT
        if r_rem > 0:
            CANVAS.display.set_clip(CANVAS.rect(board_rect))           # 아래에서 올라오는 줄이 보드 밖으로 비치지 않게
        for y in range(min(BOARD_HEIGHT, vic_row)):
            row = engine.grid[y]
            dy = r_rem - (settle["offs"][y] * s_rem if settle is not None else 0.0)
            gray = y <= gray_to
            yy = by + (y + dy) * cs
            for x in range(BOARD_WIDTH):
                piece = row[x]
                if piece:
                    self._draw_cell(bx + x * cs, yy, cs, 'G' if gray else piece)
        if r_rem > 0:
            CANVAS.display.set_clip(None)

        # 3-0. 쓰레기 줄 구멍 깜빡임 (색에 기대지 않게 흰 테두리 포함)
        alive_h = []
        for hf in self.hole_flashes:
            age = now - hf["t0"]
            if age < 0.45:
                alive_h.append(hf)
                a = 1.0 - age / 0.45
                hr = pygame.Rect(bx + hf["x"] * cs, by + (hf["row"] + r_rem) * cs, cs, cs)
                CANVAS.alpha_rect(hr, (255, 70, 80, int(110 * a)), radius=3)
                CANVAS.alpha_rect(hr, (255, 255, 255, int(220 * a)), width=2, radius=3)
        self.hole_flashes = alive_h

        # 3-1. 착지 플래시
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
            self._render_danger_breath(engine, highest, bx, by, bw, bh, cs, pulse)
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
        if not engine.game_over and engine.current_piece and vic_row >= BOARD_HEIGHT:
            ghost_y = engine.get_ghost_y()
            gsurf = self._ghost_surface(engine.current_piece, cs)
            if ghost_y != engine.current_y:
                for gx, gy in engine._get_blocks(engine.current_piece, engine.current_rot, engine.current_x, ghost_y):
                    if 0 <= gy < BOARD_HEIGHT:
                        self.screen.blit(gsurf, (bx + gx * cs, by + gy * cs))
            cur_cells = [(px, py) for px, py in engine._get_blocks(engine.current_piece, engine.current_rot, engine.current_x, engine.current_y) if 0 <= py < BOARD_HEIGHT]
            for px, py in cur_cells:
                self._draw_cell(bx + px * cs, by + py * cs, cs, engine.current_piece)
            if not spectating and cur_cells and engine.current_piece == 'T' and engine._is_touching_ground() and engine._detect_tspin():
                self._render_tspin_hint(cur_cells, bx, by, cs)            # 지금 고정하면 T-스핀: 윤곽이 반짝이고 "T-SPIN" 글자가 뜸

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
        self._render_challenge_panel(match, ox, oy)

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
        battle = not getattr(match, 'is_spectating', False) and match.attacks_enabled
        n_rows = 5 if battle else 4                              # 배틀: 시간 · APM · LPM · 보낸 줄 · 막은 줄
        rect = pygame.Rect(self._left_x(ox), self.main_board_y + 114 + oy, 108, 8 + n_rows * 34 + 4)
        self._stats_h = rect.h                                   # 아래 상태 칸(콤보/B2B)이 이 높이만큼 내려가 겹치지 않게
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
        time_row = 0                                             # 시간(후반 배율 표시)이 있는 행 번호 (항상 맨 위)
        if battle:
            # 배틀: 시간 · APM · LPM · 보낸 줄 · 막은 줄 (점수 대신 규칙을 숫자로 보여 줌: 줄을 지우면 받을 공격이 깎임)
            rows = [("시간", time_str, C_TEXT), ("APM", f"{apm:.1f}", C_GOLD), ("LPM", f"{lpm:.1f}", C_GREEN),
                    ("보낸 줄", str(int(match.total_attacks_sent)), C_GREEN),
                    ("막은 줄", str(int(match.local_engine.garbage_canceled_total)), C_ACCENT)]
        esc = 1.0
        if battle and not match.practice:
            esc = match.attack_multiplier()                      # 5분 뒤부터 매분 올라가는 공격력 배율 (예전에는 화면에 전혀 안 보였음)
        for i, (label, value, col) in enumerate(rows):
            cy = rect.y + 8 + i * 34 + 17                       # 행 중앙: 라벨과 값을 같은 높이에 맞춤
            if i == time_row and esc > 1.0:
                self._draw_text(label, self.font_small, C_ORANGE, rect.x + 12, cy - 6, "midleft")
                self._draw_text(f"×{esc:.1f}", self.font_tiny, C_ORANGE, rect.x + 12, cy + 9, "midleft")      # 값(시계)과 겹치지 않게 짧게. 설명은 후반전 알림에 있음
                self._draw_text(value, self.font_hud, C_ORANGE, rect.right - 12, cy, "midright")
                pygame.draw.line(self.screen, (38, 46, 72), (rect.x + 10, cy + 17), (rect.right - 10, cy + 17), 1)
                continue
            self._draw_text(label, self.font_small, C_DIM, rect.x + 12, cy, "midleft")
            self._draw_text(value, self.font_hud, col, rect.right - 12, cy, "midright")
            if i < len(rows) - 1:
                pygame.draw.line(self.screen, (38, 46, 72), (rect.x + 10, cy + 17), (rect.right - 10, cy + 17), 1)

    def _render_status_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._left_x(ox), self.main_board_y + 114 + getattr(self, '_stats_h', 148) + 10 + oy, 108, 96)
        self._panel(rect)
        combo = max(0, engine.combo)
        now = time.time()
        raw = engine.combo
        if raw != self._combo_seen:                                  # 콤보가 바뀐 순간: 숫자 팝, 3 이상 쌓은 콤보가 끊기면 "끝 ×N"
            if self._combo_seen >= 3 and raw < 0:
                self._combo_break_t, self._combo_break_n = now, self._combo_seen
            if raw > 0:
                self._combo_pop_t = now
            self._combo_seen = raw
        ccol = (255, 120, 220) if combo >= 8 else ((255, 170, 70) if combo >= 4 else C_ORANGE)       # 콤보가 쌓일수록 주황 -> 분홍
        if combo >= 8:
            CANVAS.alpha_rect(rect, (255, 120, 220, int(120 + 90 * math.sin(now * 8.0))), width=2, radius=10)
        self._draw_text("콤보", self.font_tiny, C_DIM, rect.x + 12, rect.y + 10)
        if combo > 0:
            surf = self.font_big_num.render(str(combo), True, ccol)
            pa = now - self._combo_pop_t
            if pa < 0.25:
                surf = self._scaled_hi(surf, 1.0 + 0.6 * (1.0 - pa / 0.25) ** 2)
            self.screen.blit(surf, (rect.right - 12 - surf.get_width(), rect.y + 6 + (self.font_big_num.get_height() - surf.get_height()) // 2))
        elif now - self._combo_break_t < 0.9:
            fa = max(0.0, 1.0 - (now - self._combo_break_t) / 0.9)
            self._fade_text(f"끝 ×{self._combo_break_n}", self.font_small, (170, 180, 205), rect.right - 12, rect.y + 10, 255 * fa, "topright")
        else:
            self._draw_text("-", self.font_big_num, C_DIM, rect.right - 12, rect.y + 6, "topright")
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
        for i in range(min(getattr(self, "next_visible", 5), len(engine.next_queue))):
            scale = 22 if i == 0 else 15
            cy = rect.y + 56 if i == 0 else rect.y + 108 + (i - 1) * 40
            self._render_preview_piece(engine.next_queue[i], rect.centerx, cy, scale=scale, dim=(i > 0))

    @staticmethod
    def _fmt_goal_value(metric, v):
        if metric in ("survive", "esc_survive", "drill_secs"):
            v = int(v)
            return f"{v // 60}:{v % 60:02d}"
        return str(int(v))

    def _render_challenge_panel(self, match, ox=0, oy=0):
        """오른쪽 열 아래(받을 공격 칸 밑): 연습 과제 / 오늘의 도전 / 주간 변형의 목표와 진행도. 탈락·관전 중에는 그리지 않음"""
        ch = getattr(match, "challenge", None)
        if ch is None or not match.local_is_alive or match.match_finished or getattr(match, "is_spectating", False):
            return
        x, y, w = self._right_x(ox), self.main_board_y + 390 + oy, 108
        kind = match.challenge_kind
        if kind == "practice":
            return                                                      # 연습: 과제 목록/타임어택은 좌우 패널(_render_practice_sides)에서 보여 줌
        n = len(ch.order)
        rect = pygame.Rect(x, y, w, 28 + n * 34 + 6)
        accent = C_ORANGE if kind == "weekly" else C_GREEN
        self._panel(rect, border=accent)
        self._draw_text(f"도전 ★{len(ch.done)}/{n}", self.font_tiny, accent, rect.centerx, rect.y + 7, "midtop")
        for i, gid in enumerate(ch.order):
            g = ch.by_id[gid]
            got = gid in ch.done
            ry = rect.y + 28 + i * 34
            self._draw_text(("✓ " if got else "· ") + g["short"], self.font_tiny, C_GREEN if got else C_TEXT, rect.x + 8, ry)
            if got:
                continue
            prog = ch.progress(gid)
            if prog is None:                                            # 순위 목표: 지금 생존자 수와 비교
                txt = f"{match.alive_count}명 남음 → {g['goal']}"
                ratio = 0.0 if match.alive_count <= 0 else min(1.0, g["goal"] / max(1, match.alive_count))
            else:
                txt = f"{self._fmt_goal_value(g['metric'], prog[0])}/{self._fmt_goal_value(g['metric'], prog[1])}"
                ratio = prog[0] / max(1, prog[1])
            self._draw_text(txt, self.font_tiny, C_DIM, rect.x + 8, ry + 15)
            pygame.draw.rect(self.screen, (28, 34, 56), (rect.x + 8, ry + 29, w - 16, 3), border_radius=1)
            if ratio > 0:
                pygame.draw.rect(self.screen, accent, (rect.x + 8, ry + 29, max(2, int((w - 16) * ratio)), 3), border_radius=1)

    PRACTICE_KEYS = (("G", "쓰레기 받기 (Shift+G 8줄)"), ("V", "압박 드릴 켜기/끄기"), ("B", "보드 초기화"),
                     ("N", "다음 과제 (Shift+N 이전)"), ("Y", "타임어택 켜기/종류 변경"), ("F1", "규칙 카드"))
    practice_tab_rects = {}          # 연습 과제 목록 위쪽 페이지 탭의 클릭 영역 {난이도: Rect} (프레임마다 갱신)
    practice_row_rects = {}          # 연습 과제 목록의 각 과제 행 클릭 영역 {과제 id: Rect} (프레임마다 갱신, 클릭하면 그 과제를 고름)
    practice_page = None             # 연습 과제 목록에서 보고 있는 페이지(난이도 1~3). None이면 지금 도전 중인 과제의 페이지를 따라감
    _prac_last_cur = None

    def _render_practice_sides(self, match, ox=0, oy=0):
        """연습 모드 좌우 빈 공간: 왼쪽 = 과제 목록(기초/중급/고급 페이지, 현재 과제 강조 + 진행도), 오른쪽 = 이번 연습 기록 + 연습 조작키 + 타임어택"""
        ch = getattr(match, "challenge", None)
        if ch is None:
            return
        pw = min(330, self.main_board_x - 145 - 15)
        top = 78 + oy
        tier_col = {1: C_GREEN, 2: C_GOLD, 3: C_ORANGE, 4: (200, 150, 255)}
        cur = match.practice_current_task()
        cur_id = ch.order[cur[0]] if cur else None
        if cur_id != self._prac_last_cur:                               # N 키 등으로 과제가 바뀌면 그 과제의 페이지로 자동 이동
            self._prac_last_cur = cur_id
            self.practice_page = None
        auto_page = ch.by_id[cur_id]["tier"] if cur_id else 1
        page = self.practice_page if self.practice_page in (1, 2, 3, 4) else auto_page

        # --- 왼쪽: 과제 목록 (한 페이지 = 한 난이도)
        rows = [gid for gid in ch.order if ch.by_id[gid]["tier"] == page]
        lr = pygame.Rect(self.main_board_x - 145 - pw + ox, top, pw, 36 + 34 + len(rows) * 44 + 8)
        self._panel(lr, border=tier_col[page])
        self._draw_text(f"연습 과제  {len(ch.done)}/{len(ch.order)}", self.font_hud, C_GREEN, lr.x + 14, lr.y + 8)
        tw = (pw - 20 - 12) // 4
        for t in (1, 2, 3, 4):
            tr = pygame.Rect(lr.x + 10 + (t - 1) * (tw + 4), lr.y + 38, tw, 26)
            self.practice_tab_rects[t] = tr
            ids = [gid for gid in ch.order if ch.by_id[gid]["tier"] == t]
            n_done = sum(1 for gid in ids if gid in ch.done)
            on = t == page
            hov = tr.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, _mix((16, 20, 34), tier_col[t], 0.30 if on else (0.16 if hov else 0.04)), tr, border_radius=7)
            pygame.draw.rect(self.screen, tier_col[t] if on else (60, 72, 104), tr, 2 if on else 1, border_radius=7)
            full = n_done == len(ids)
            self._draw_text(f"{challenges.PRACTICE_TIER_NAMES[t]} {n_done}/{len(ids)}", self.font_tiny, tier_col[t] if (on or full) else C_DIM, tr.centerx, tr.centery, "center")
        for i, gid in enumerate(rows):
            g = ch.by_id[gid]
            ry = lr.y + 70 + i * 44
            row = pygame.Rect(lr.x + 6, ry, pw - 12, 41)
            got = gid in ch.done
            if not got:
                self.practice_row_rects[gid] = row
            if gid == cur_id:
                pygame.draw.rect(self.screen, (22, 44, 40), row, border_radius=8)
                pygame.draw.rect(self.screen, C_GREEN, row, 1, border_radius=8)
            elif not got and row.collidepoint(pygame.mouse.get_pos()):        # 마우스를 올린 과제: 클릭하면 이 과제로 바꿈
                pygame.draw.rect(self.screen, (24, 30, 52), row, border_radius=8)
                pygame.draw.rect(self.screen, (90, 110, 160), row, 1, border_radius=8)
            box = pygame.Rect(row.x + 8, row.y + 11, 16, 16)
            if got:
                pygame.draw.rect(self.screen, C_GOLD, box, border_radius=4)
                pygame.draw.lines(self.screen, (24, 20, 8), False, [(box.x + 4, box.centery), (box.x + 7, box.bottom - 5), (box.right - 4, box.y + 4)], 2)
            else:
                pygame.draw.rect(self.screen, (60, 72, 104), box, 1, border_radius=4)
            lines = self.wrap(g["text"], self.font_tiny, row.w - 52)[:2]
            for j, ln in enumerate(lines):
                self._draw_text(ln, self.font_tiny, C_DIM if got else C_TEXT, row.x + 34, row.y + (6 if len(lines) > 1 else 12) + j * 15)
            if gid == cur_id:
                prog = ch.progress(gid)
                if prog:
                    self._draw_text(f"{self._fmt_goal_value(g['metric'], prog[0])}/{self._fmt_goal_value(g['metric'], prog[1])}", self.font_tiny, C_GREEN, row.right - 8, row.y + 6, "topright")
                    pygame.draw.rect(self.screen, (28, 34, 56), (row.x + 34, row.bottom - 5, row.w - 44, 3), border_radius=1)
                    if prog[0] > 0:                                     # 0일 때는 그리지 않음 (최소 폭 2px 때문에 점으로 보이던 문제)
                        pygame.draw.rect(self.screen, C_GREEN, (row.x + 34, row.bottom - 5, max(2, int((row.w - 44) * prog[0] / max(1, prog[1]))), 3), border_radius=1)

        # --- 오른쪽: 이번 연습 기록 + 조작키 + 타임어택
        rr = pygame.Rect(self.main_board_x + self.main_board_w + 145 + ox, top, pw, 0)
        m = ch.m
        stats = [("지운 줄", m["lines"]), ("쿼드", m["quads"]), ("T-스핀", m["tspins"]), ("최고 콤보", m["combo_max"]),
                 ("최고 B2B", m["b2b_chain_max"]), ("퍼펙트", m["pcs"]), ("막은 줄", m["canceled_total"]),
                 ("드릴 최고", f"{match.drill_best}초" if getattr(match, "drill_best", 0) else "-")]
        rr.h = 36 + 4 * 40 + 14
        self._panel(rr, border=C_ACCENT)
        self._draw_text("이번 연습 기록", self.font_hud, C_ACCENT, rr.x + 14, rr.y + 8)
        cw = (pw - 20) // 2
        for i, (lab, val) in enumerate(stats):
            cx = rr.x + 10 + (i % 2) * cw
            cy = rr.y + 38 + (i // 2) * 40
            cell = pygame.Rect(cx, cy, cw - 6, 34)
            pygame.draw.rect(self.screen, (22, 27, 46), cell, border_radius=8)
            self._draw_text(lab, self.font_tiny, C_DIM, cell.x + 8, cell.y + 3)
            self._draw_text(str(val), self.font_hud, C_TEXT if val not in (0, "-") else C_DIM, cell.right - 8, cell.bottom - 3, "bottomright")
        kr = pygame.Rect(rr.x, rr.bottom + 10, pw, 36 + len(self.PRACTICE_KEYS) * 28 + 8)
        self._panel(kr)
        self._draw_text("연습 조작", self.font_hud, C_GOLD, kr.x + 14, kr.y + 8)
        for i, (k, d) in enumerate(self.PRACTICE_KEYS):
            ky = kr.y + 40 + i * 28
            kw = max(34, self.font_tiny.size(k)[0] + 16)
            pygame.draw.rect(self.screen, (34, 42, 70), (kr.x + 12, ky, kw, 22), border_radius=6)
            self._draw_text(k, self.font_tiny, C_TEXT, kr.x + 12 + kw // 2, ky + 11, "center")
            self._draw_text(d, self.font_tiny, C_DIM, kr.x + 12 + kw + 10, ky + 11, "midleft")
        tr = pygame.Rect(kr.x, kr.bottom + 10, pw, 100)
        on = bool(match.ta_mode)
        self._panel(tr, border=C_GOLD if on else (74, 88, 128))
        if on:
            _id, name, goal, unit = challenges.TA_BY_ID[match.ta_mode]
            secs = int(match.elapsed - match.ta_t0) if match.ta_t0 is not None else 0
            self._draw_text(f"타임어택 · {name}", self.font_hud, C_GOLD, tr.x + 14, tr.y + 8)
            self._draw_text(f"{match.ta_n}/{goal}{unit}", self.font_hud, C_TEXT, tr.x + 14, tr.y + 50)
            self._draw_text(f"{secs}초", self.font_hud, C_TEXT, tr.centerx + 20, tr.y + 50)
            self._draw_text(f"최고 {match.ta_best}초" if match.ta_best else "최고 -", self.font_small, C_DIM, tr.right - 14, tr.y + 54, "topright")
        else:
            self._draw_text("타임어택  (Y로 시작)", self.font_hud, C_DIM, tr.x + 14, tr.y + 8)
            for i, (mid, name, _goal, _unit) in enumerate(challenges.TA_MODES):
                b = int(match.ta_bests.get(mid, 0))
                self._draw_text(f"{name} {b}초" if b else f"{name} -", self.font_tiny, C_TEXT if b else C_DIM, tr.x + 14 + (i % 2) * (pw // 2 - 4), tr.y + 38 + (i // 2) * 18)

    def _render_incoming_box(self, engine, ox=0, oy=0):
        rect = pygame.Rect(self._right_x(ox), self.main_board_y + 276 + oy, 108, 104)
        self._hud_rects["incoming"] = rect
        n = engine.incoming_garbage
        danger = n >= 4
        border = C_DANGER if danger else (C_ORANGE if n > 0 else C_PANEL_BORDER)
        self._panel(rect, border=border, border_w=2 if n > 0 else 1)
        self._draw_text("받을 공격", self.font_tiny, border if n > 0 else C_DIM, rect.centerx, rect.y + 11, "midtop")
        col = C_DANGER if danger else (C_ORANGE if n > 0 else C_DIM)
        # 숫자와 "줄"은 실제로 그려진 글자 아래끝(기준선)을 맞춰 나란히, 박스 가운데 정렬
        num = self._text(f"+{n}" if n > 0 else "0", self.font_title, col)
        unit = self._text("줄", self.font_mid, C_DIM)
        nb, ub = num.get_bounding_rect(), unit.get_bounding_rect()
        gap = 8
        total = num.get_width() + gap + unit.get_width()
        x0 = rect.centerx - total // 2
        base_y = rect.y + 68                                        # 두 글자의 아래끝이 놓일 y
        ca = time.time() - self._cancel_t0
        if 0.0 <= ca < 0.3:                                          # 줄을 지워 공격을 막은 순간: 숫자가 흔들리고 청록 테두리가 번쩍임
            x0 += int(math.sin(ca * 70.0) * 5 * (1.0 - ca / 0.3))
            CANVAS.alpha_rect(rect, (110, 235, 255, int(150 * (1.0 - ca / 0.3))), width=3, radius=10)
        self.screen.blit(num, (x0, base_y - nb.bottom))
        self.screen.blit(unit, (x0 + num.get_width() + gap, base_y - ub.bottom))
        if n > 0:                                                    # 차징 상태: 다음 락다운에 올라올 수 있는 줄 수 / 아직 차징 중
            ready = getattr(engine, "ready_garbage", n)
            txt, tcol = (f"곧 {ready}줄 도착", col) if ready > 0 else ("차징 중", C_DIM)
            self._draw_text(txt, self.font_tiny, tcol, rect.centerx, rect.bottom - 10, "midbottom")

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
    LAYOUT_STAGES = (20, 10, 5)      # 상대 생존자가 이 수 이하로 처음 내려갈 때마다 살아남은 사람만 다시 배치해 미니 보드를 키움

    def _render_mini_boards(self, match, ox=0, oy=0):
        self.mini_board_rects.clear()
        self.practice_tab_rects = {}
        self.practice_row_rects = {}
        if getattr(match, "practice", False):
            self._render_practice_sides(match, ox, oy)      # 연습 모드: 상대 자리는 비어 있으니 좌우를 과제 목록/연습 기록으로 채움
            return
        others = [(pid, p) for pid, p in match.players.items() if pid != match.local_player_id]
        # 후반 재배치: 단계가 오를 때만 (죽을 때마다가 아님) 그 시점의 생존자만 다시 배치. 다음 단계까지는 자리를 유지해 특정 상대를 계속 눈으로 따라갈 수 있고,
        # 그 사이 탈락한 카드는 지금처럼 탈락 표시로 남음. 경기마다 한 번씩만 단계가 올라감 (단계는 내려가지 않음)
        alive_n = sum(1 for _pid, p in others if p["is_alive"])
        stage = sum(1 for t in self.LAYOUT_STAGES if alive_n <= t)
        if getattr(match, "layout_stage", 0) < stage and len(others) > alive_n:
            match.layout_stage = stage
            match.layout_ids = [pid for pid, p in others if p["is_alive"]]
        elif getattr(match, "layout_stage", 0) < stage:
            match.layout_stage = stage                      # 이미 전원이 살아 있으면 자리 그대로 (재배치할 것이 없음)
        ids = getattr(match, "layout_ids", None)
        if ids and getattr(match, "layout_stage", 0) > 0:
            others = [(pid, match.players[pid]) for pid in ids if pid in match.players]
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
        frac = (round((CANVAS.ox + bx * CANVAS.S) % 2.0, 3), round((CANVAS.oy + by * CANVAS.S) % 2.0, 3))   # 위치의 반올림 차이로 틀과 어긋나지 않게
        key = (cgt, bw, bh, use_cells, cell_px, frac)
        X0, Y0 = CANVAS.X(bx), CANVAS.Y(by)
        X0 -= X0 % 2                    # 원점은 짝수 픽셀로: round()의 '짝수로 반올림' 규칙이 원본과 똑같이 적용되도록
        Y0 -= Y0 % 2
        def paint(target):
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
                        _orig_rect(target, col, (l_, t_, rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1), 0, border_radius=0)
                    else:
                        pygame.draw.rect(self.screen, col, (bx + start * cp, by + y_idx * cp, (x_idx - start) * cp - 0.6, max(1, cp - 0.6)))
        if getattr(self, "_shaking", False):             # 흔들리는 동안은 레이어 없이 직접 그림 (틀과 같은 반올림, 레이어 재생성 비용 없음)
            paint(CANVAS.display)
            return
        ent = self._mini_layers.get(pid)
        if ent is None or ent[0] != key:
            w = CANVAS.X(bx + bw) - X0 + 4
            h = CANVAS.Y(by + bh) - Y0 + 4
            surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            with CANVAS.redirect(surf, X0, Y0):
                paint(surf)
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
            # 블록은 틀(소수점을 버린 정수 Rect) 안쪽 1px 기준으로 그림. 소수 좌표로 그리면 화면 배율에 따라 반올림 차이로 블록이 틀 오른쪽/아래로 삐져나옴
            ccp = min((board_rect.w - 2) / float(BOARD_WIDTH), (board_rect.h - 2) / float(BOARD_HEIGHT))
            cbx = board_rect.x + 1 + ((board_rect.w - 2) - ccp * BOARD_WIDTH) / 2.0
            cby = board_rect.bottom - 1 - ccp * BOARD_HEIGHT

            is_targeted = (local_target_id == pid)
            is_alive = p["is_alive"]
            is_bounty = is_alive and pid == getattr(match, "bounty_id", None) and not getattr(match, "bounty_claimed", False)
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
                CANVAS.display.fill((240, 78, 88), CANVAS.rect_f(board_rect.x + 2, board_rect.y + 1, board_rect.w - 4, 3))   # 나를 노리는 상대: 카드 위쪽 붉은 줄 (변환된 실제 좌표에 직접 채움)
            if is_alive and (is_bounty or pid == getattr(match, "final_opp_id", None)):       # 결승 상대/현상금 봇: 금빛 맥박 테두리
                pl2 = 0.5 + 0.5 * math.sin(now * (6.0 if pid == getattr(match, "final_opp_id", None) else 4.0))
                pygame.draw.rect(self.screen, _mix((255, 185, 55), (255, 245, 170), pl2), board_rect.inflate(2, 2), 2, border_radius=3)
            if is_spec or is_targeted:                       # 락온 코너 브래킷: 관전 대상은 금색(맥박), 조준 대상은 붉은색
                pl = 0.5 + 0.5 * math.sin(now * (5.0 if is_spec else 8.0))
                bcol = _mix((255, 200, 80), (255, 255, 255), 0.55 * pl) if is_spec else _mix((255, 84, 96), (255, 190, 190), 0.5 * pl)
                self._draw_brackets(board_rect, bcol)
            # 이름/K.O. 알약/홀드 아이콘 계산(글자 폭 측정 포함)은 카드 내용이 바뀔 때만 다시 함
            is_rival = (pid == getattr(match, "rival_id", None))
            sig = (p["name"], is_rival, is_bounty, is_human, is_alive, is_targeted, is_spec, colors.get(pid, 0), p.get("ko_count", 0), bw, show_names, detailed,
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
                elif is_bounty:                                    # 현상금 봇: 금빛 $ 표식 (처치하면 보너스)
                    name_str, name_col = f"${p['name'][:maxc]}", (255, 215, 80)
                elif is_rival and is_alive:                        # 라이벌 봇(나를 자주 탈락시킨 상대): 금빛 ◆ 표식
                    name_str, name_col = f"◆{p['name'][:maxc]}", (255, 190, 80)
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
                cp = ccp
                self._blit_mini_cells(pid, cgt, cbx, cby, ccp * BOARD_WIDTH, ccp * BOARD_HEIGHT, cp)
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
                fast_small = self.mini_fast and ccp < 9
                if fast_small:
                    # 작은 칸: 칸 좌표(변환·반올림 결과)를 카드별로 한 번 계산해 두고 재사용 (CANVAS.rect_f와 같은 계산이라 픽셀은 동일)
                    tkey = (cbx, cby, ccp, CANVAS.S, CANVAS.ox, CANVAS.oy)
                    tab = self._mini_tabs.get(pid)
                    if tab is None or tab[0] != tkey:
                        cw_ = max(1, ccp - 0.6)
                        XL, XR, YT, YB = [], [], [], []
                        for i_ in range(BOARD_WIDTH):
                            x_ = cbx + i_ * ccp
                            XL.append(CANVAS.X(x_))
                            XR.append(CANVAS.X(x_ + cw_))
                        for i_ in range(BOARD_HEIGHT):
                            y_ = cby + i_ * ccp
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
                            if ccp >= 9:
                                self.screen.blit(self._ghost_surface(ptype, int(ccp)), (cbx + gx_ * ccp, cby + yy * ccp))
                            elif fast_small and 0 <= gx_ < BOARD_WIDTH:
                                rw_ = XR[gx_] - XL[gx_]
                                rh_ = YB[yy] - YT[yy]
                                _orig_rect(disp, gcol, (XL[gx_], YT[yy], rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1), gw_, border_radius=0)
                            else:
                                pygame.draw.rect(self.screen, gcol, (cbx + gx_ * ccp, cby + yy * ccp, max(1, ccp - 0.6), max(1, ccp - 0.6)), 1)
                cpp = ccp
                pcol = self._pcol.get(ptype)
                if pcol is None:
                    pcol = self._pcol[ptype] = _mix(PIECE_COLORS.get(ptype, (200, 200, 220)), (255, 255, 255), 0.25)
                for gx, gy in cells:
                    if 0 <= gy < BOARD_HEIGHT and 0 <= gx < BOARD_WIDTH:
                        if cpp >= 9:
                            self._draw_cell(cbx + gx * cpp, cby + gy * cpp, int(cpp), ptype)
                        elif fast_small:                     # 작은 칸: 미리 계산한 좌표로 바로 채움
                            rw_ = XR[gx] - XL[gx]
                            rh_ = YB[gy] - YT[gy]
                            disp.fill(pcol, (XL[gx], YT[gy], rw_ if rw_ >= 1 else 1, rh_ if rh_ >= 1 else 1))
                        else:                                # 작은 칸: 좌표 변환 후 바로 채움 (그리기 래퍼 생략)
                            CANVAS.display.fill(pcol, CANVAS.rect_f(cbx + gx * cpp, cby + gy * cpp, max(1, cpp - 0.6), max(1, cpp - 0.6)))
            if is_alive and cg and len(cg) == BOARD_HEIGHT:
                pass
            elif is_alive:
                block_col = (140, 240, 255) if is_human else ((255, 125, 125) if in_danger else (128, 158, 214))
                cp = ccp
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
                                             (cbx + start * cp, cby + y_idx * cp, (x_idx - start) * cp - 0.6, max(1, cp - 0.6)))
                        else:
                            x_idx += 1
            elif now - (p.get("ko_t") or -9.0) < 0.7:
                # 막 탈락한 카드: 마지막 보드가 잠깐 남았다가 위에서부터 회색으로 무너지고, 내가 처치했으면 K.O. 도장
                ko_age = now - p["ko_t"]
                if cg and len(cg) == BOARD_HEIGHT:
                    self._blit_mini_cells(pid, tuple(cg), cbx, cby, ccp * BOARD_WIDTH, ccp * BOARD_HEIGHT, ccp)
                wipe_h = int((board_rect.h - 2) * min(1.0, ko_age / 0.5))
                if wipe_h > 0:
                    CANVAS.alpha_rect((board_rect.x + 1, board_rect.y + 1, board_rect.w - 2, wipe_h), (10, 11, 16, 240))
                if ko_age < 0.12:
                    CANVAS.alpha_rect(board_rect, (255, 255, 255, int(200 * (1.0 - ko_age / 0.12))))
                if ko_age > 0.12 and p.get("ko_by") == match.local_player_id and bw >= 30:
                    self._fade_text("K.O.", self.font_tiny if bw < 90 else self.font_small, (255, 215, 90), board_rect.centerx, board_rect.centery, 255 * min(1.0, (ko_age - 0.12) / 0.15), "center")
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
                gh = min(ig, 20) * ccp
                gw = 2 if bw < 46 else 3
                CANVAS.display.fill((255, 84, 94) if ig >= 4 else (255, 165, 70), CANVAS.rect_f(cbx + 1, cby + ccp * BOARD_HEIGHT - gh - 1, gw, gh))

            if self.mini_focus and is_alive and not (is_targeted or is_spec or in_danger or is_human or pid in attackers_of_me):
                self._blit_overlay(("mini_dim", board_rect.w, board_rect.h), (board_rect.w, board_rect.h),
                                   lambda surf: surf.fill((9, 11, 20, 255)), board_rect.topleft, alpha=96)      # 신호 대 잡음: 지금 신경 쓸 필요 없는 카드는 한 단계 어둡게

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
                            shown = lab if label_font.size(lab)[0] <= strip_w + 2 else lab[0]      # 칸보다 넓으면 첫 글자만 (옆 카드의 이름표와 겹치지 않게)
                            self.screen.blit(self._text(shown, label_font, C_GOLD if (lab == "HOLD" and hold_piece) else (120, 134, 170)), (sx, cy_ - 1))
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

    # ---------------------------------------------------------------- 블록 반응 연출 (v1.1.7)
    SETTLE_SECS = 0.14          # 줄 제거 뒤 위 블록이 내려앉는 시간
    RISE_SECS = 0.14            # 쓰레기 줄이 밀고 올라오는 시간
    VICTORY_CEREMONY = 2.4      # 우승 세리머니 길이 (이 뒤에 순위표)

    def _add_bg_pulse(self, x, y, col):
        self._bg_pulses.append({"t0": time.time(), "x": x, "y": y, "col": col})
        del self._bg_pulses[:-2]

    def _detect_board_reactions(self, match, engine, spectating, pdt):
        """엔진이 남긴 사건(줄 제거 · 쓰레기 줄 · 하드 드롭 · 탑아웃)을 보고 파쇄/내려앉기/상승/궤적/붕괴/세리머니를 시작하고 조각을 갱신"""
        now = time.time()
        m = getattr(match, 'shake_scale', 1.0)          # 흔들림 설정: 끔(0)이면 위치가 움직이는 연출은 하지 않음
        cs = self.cell_size
        bx, by = self.main_board_x, self.main_board_y
        if self._react_eng is not engine:
            self._react_eng = engine
            self.shards, self._settle, self._rise = [], None, None
            self.hole_flashes, self.drop_trails, self.confetti = [], [], []
            self._hd_seen, self._gp_seen = engine.hard_drop_events, engine.garbage_pushed_total
            self._topout, self._vic_t0, self._vic_row = None, None, BOARD_HEIGHT
            self._ko_seen = getattr(match, 'local_ko_count', 0)
            engine.cleared_row_cells, engine.push_holes = [], []
        mid = (BOARD_WIDTH - 1) / 2.0

        cells = engine.cleared_row_cells
        if cells:
            engine.cleared_row_cells = []
            if not spectating:
                budget = max(0, 260 - len(self.shards))
                for y, row in cells:
                    for x, piece in enumerate(row):
                        if not piece:
                            continue
                        col = PIECE_COLORS.get(piece, (150, 150, 170))
                        for _ in range(2):
                            if budget <= 0:
                                break
                            budget -= 1
                            self.shards.append({"x": bx + x * cs + cs / 2 + random.uniform(-cs / 3, cs / 3), "y": by + y * cs + cs / 2 + random.uniform(-cs / 3, cs / 3),
                                                "vx": (x - mid) * 34 + random.uniform(-70, 70), "vy": random.uniform(-260, -40), "col": col,
                                                "sz": random.choice((3, 4, 5)), "life": 0.0, "max": random.uniform(0.45, 0.8)})
                if m > 0 and engine.settle_offsets:
                    self._settle = {"t0": now, "offs": list(engine.settle_offsets)}

        gp = engine.garbage_pushed_total
        if gp != self._gp_seen:
            n = max(0, min(8, gp - self._gp_seen))
            self._gp_seen = gp
            holes = engine.push_holes[-n:] if n else []
            engine.push_holes = []
            if not spectating and holes:
                if m > 0:
                    self._rise = {"t0": now, "n": len(holes)}
                for i, hx in enumerate(holes):
                    self.hole_flashes.append({"x": hx, "row": BOARD_HEIGHT - len(holes) + i, "t0": now})
                del self.hole_flashes[:-12]

        if engine.hard_drop_events != self._hd_seen:
            self._hd_seen = engine.hard_drop_events
            hd = engine.last_hard_drop
            if hd and not spectating and hd["dist"] >= 2 and engine.last_lock_cells:
                start_top, land_top = {}, {}
                for x, y in hd["cells"]:
                    start_top[x] = min(start_top.get(x, 99), y)
                for x, y in engine.last_lock_cells:
                    land_top[x] = min(land_top.get(x, 99), y)
                col = PIECE_COLORS.get(engine.last_locked_piece, (200, 220, 255))
                for x, y0 in start_top.items():
                    y1 = land_top.get(x)
                    if y1 is not None and y1 > y0:
                        self.drop_trails.append({"x": x, "y0": max(0, y0), "y1": y1, "t0": now, "col": col})
                del self.drop_trails[:-8]
                if m > 0:
                    self._bounce_t0, self._bounce_amp = now, min(3.0, 1.0 + hd["dist"] * 0.1) * m

        ko = getattr(match, 'local_ko_count', 0)
        if ko != self._ko_seen:
            if ko > self._ko_seen:
                self._add_bg_pulse(bx + self.main_board_w // 2, by + self.main_board_h // 2, (255, 120, 110))
            self._ko_seen = ko

        if engine.game_over and not spectating:                       # 내 탑아웃: 스택이 위에서부터 회색으로 물들며 먼지처럼 부서짐
            if self._topout is None:
                self._topout = {"t0": now, "row": -1}
            tp = self._topout
            front = min(BOARD_HEIGHT - 1, int((now - tp["t0"]) / 0.04))
            budget = max(0, 260 - len(self.shards))
            while tp["row"] < front:
                tp["row"] += 1
                y = tp["row"]
                for x in range(BOARD_WIDTH):
                    if engine.grid[y][x] and budget > 0:
                        budget -= 1
                        self.shards.append({"x": bx + x * cs + cs / 2, "y": by + y * cs + cs / 2, "vx": random.uniform(-40, 40), "vy": random.uniform(-60, 20),
                                            "col": (110, 116, 135), "sz": random.choice((3, 4)), "life": 0.0, "max": random.uniform(0.5, 0.9)})
        else:
            self._topout = None

        if match.match_finished and getattr(match, 'local_rank', 0) == 1 and not spectating and not match.practice:      # 우승 세리머니: 아래에서 위로 한 줄씩 금빛으로 터짐
            if self._vic_t0 is None:
                self._vic_t0, self._vic_row = now, BOARD_HEIGHT
            front = BOARD_HEIGHT - 1 - int((now - self._vic_t0) / 0.045)
            budget = max(0, 260 - len(self.shards))
            while self._vic_row - 1 > front and self._vic_row > 0:
                self._vic_row -= 1
                y = self._vic_row
                for x in range(BOARD_WIDTH):
                    piece = engine.grid[y][x]
                    if piece and budget > 0:
                        budget -= 1
                        self.shards.append({"x": bx + x * cs + cs / 2, "y": by + y * cs + cs / 2, "vx": (x - mid) * 40 + random.uniform(-60, 60), "vy": random.uniform(-300, -60),
                                            "col": _mix(PIECE_COLORS.get(piece, (200, 200, 220)), (255, 215, 90), 0.55), "sz": random.choice((3, 4, 5)), "life": 0.0, "max": random.uniform(0.5, 0.9)})
                self.particles.add_sparks(bx + self.main_board_w // 2, by + y * cs + cs // 2, (255, 215, 90), count=6, speed_mult=1.5, glow=(y % 3 == 0))
            if now - self._vic_t0 > 0.9 and now - self._vic_t0 < 3.4 and len(self.confetti) < 110:
                for _ in range(3):
                    self.confetti.append({"x": random.uniform(80, self.width - 80), "y": -10.0, "vy": random.uniform(110, 220), "vx": random.uniform(-40, 40),
                                          "w": random.choice((5, 6, 8)), "h": random.choice((3, 4)), "ph": random.uniform(0, 6.28),
                                          "col": random.choice(((255, 215, 90), (255, 130, 160), (110, 235, 255), (170, 255, 150), (210, 150, 255)))})
        elif not match.match_finished:
            self._vic_t0, self._vic_row = None, BOARD_HEIGHT

        alive = []
        for sh in self.shards:
            sh["life"] += pdt
            if sh["life"] < sh["max"]:
                sh["x"] += sh["vx"] * pdt
                sh["y"] += sh["vy"] * pdt
                sh["vy"] += 900 * pdt
                alive.append(sh)
        self.shards = alive
        keep = []
        for cf in self.confetti:
            cf["y"] += cf["vy"] * pdt
            cf["x"] += (cf["vx"] + 30 * math.sin(now * 3.0 + cf["ph"])) * pdt
            if cf["y"] < self.height + 12:
                keep.append(cf)
        self.confetti = keep

    def _render_reactions(self, match, ox, oy):
        """조각 · 하드 드롭 궤적 · 색종이 · 우승 왕관"""
        now = time.time()
        cs = self.cell_size
        alive = []
        for tr in self.drop_trails:
            age = now - tr["t0"]
            if age < 0.14:
                alive.append(tr)
                a = 1.0 - age / 0.14
                x = self.main_board_x + tr["x"] * cs + ox
                y0 = self.main_board_y + tr["y0"] * cs + oy
                h = (tr["y1"] - tr["y0"]) * cs
                CANVAS.alpha_rect((x + cs * 0.12, y0, cs * 0.76, h), (*tr["col"], int(70 * a)), radius=3)
                CANVAS.alpha_rect((x + cs * 0.4, y0, cs * 0.2, h), (255, 255, 255, int(150 * a)), radius=2)
        self.drop_trails = alive
        for sh in self.shards:
            fade = 1.0 - sh["life"] / sh["max"]
            sz = max(1, int(sh["sz"] * (0.4 + 0.6 * fade)))
            pygame.draw.rect(self.screen, sh["col"], (int(sh["x"] + ox), int(sh["y"] + oy), sz, sz))
        for cf in self.confetti:
            w = max(1, int(cf["w"] * abs(math.cos(now * 6.0 + cf["ph"]))))
            pygame.draw.rect(self.screen, cf["col"], (int(cf["x"]), int(cf["y"]), w, cf["h"]))
        if self._vic_t0 is not None and getattr(match, 'match_finished', False):
            t = now - self._vic_t0 - 0.9
            if t > 0:
                self._draw_crown(self.main_board_x + self.main_board_w // 2 + ox, self.main_board_y + 290 + oy - 14 * math.sin(min(1.0, t / 0.6) * math.pi * 0.5), min(1.0, t / 0.45))

    def _draw_crown(self, cx, cy, grow):
        """우승 왕관 (금색 다각형 + 보석)"""
        w, h = 150 * grow, 100 * grow
        if w < 4:
            return
        pts = [(-0.5, 0.5), (-0.5, -0.1), (-0.25, 0.2), (0.0, -0.5), (0.25, 0.2), (0.5, -0.1), (0.5, 0.5)]
        poly = [(CANVAS.X(cx + px * w), CANVAS.Y(cy + py * h)) for px, py in pts]
        pygame.draw.polygon(CANVAS.display, (255, 205, 70), poly)
        pygame.draw.polygon(CANVAS.display, (255, 245, 190), poly, max(1, CANVAS.length(3)))
        band = pygame.Rect(cx - w * 0.5, cy + h * 0.32, w, h * 0.18)
        pygame.draw.rect(self.screen, (230, 160, 40), band, border_radius=3)
        for gx, gcol in ((-0.5, (255, 120, 150)), (0.0, (120, 230, 255)), (0.5, (170, 255, 150))):
            pygame.draw.circle(self.screen, gcol, (int(cx + gx * w), int(cy + (-0.1 if gx else -0.5) * h)), max(2, int(8 * grow)))
        draw_glow(self.screen, cx, cy, int(110 * grow), (255, 210, 90), 0.7)

    def _render_bg_pulses(self, match, ox, oy):
        """큰 기술/K.O. 때 보드 중심에서 배경으로 퍼지는 얇은 링 (카드 뒤에 그려짐)"""
        if not self._bg_pulses or getattr(match, 'shake_scale', 1.0) <= 0:
            self._bg_pulses = [] if getattr(match, 'shake_scale', 1.0) <= 0 else self._bg_pulses
            return
        now = time.time()
        alive = []
        for bp in self._bg_pulses:
            age = now - bp["t0"]
            if age < 0.7:
                alive.append(bp)
                k = age / 0.7
                col = _mix((14, 18, 32), bp["col"], 0.55 * (1.0 - k))
                pygame.draw.circle(self.screen, col, (int(bp["x"] + ox), int(bp["y"] + oy)), int(60 + 620 * _ease_out(k)), 3)
        self._bg_pulses = alive

    def _render_danger_breath(self, engine, highest, bx, by, bw, bh, cs, pulse):
        """위기 때 쌓인 블록이 맥박에 맞춰 붉게 숨 쉬고 화면 가장자리에 붉은 비네트. 색약 모드는 주황 + 점선 테두리"""
        cb = is_colorblind()
        col = (255, 150, 40) if cb else (255, 50, 60)
        rows = max(1, BOARD_HEIGHT - max(0, highest))
        self._blit_overlay(("danger_stack", bw, rows, cb), (bw, rows * cs),
                           lambda ds: ds.fill((*col, 150)), (bx, by + (BOARD_HEIGHT - rows) * cs), alpha=max(0, min(255, int(pulse * 1.7))))

        def _build_vig(ds):
            for i in range(0, 72, 4):
                _orig_rect(ds, (*col, int(110 * (1.0 - i / 72.0) ** 1.5)), (i, i, self.width - 2 * i, self.height - 2 * i), 4)
        self._blit_overlay(("danger_vig", cb, self.width, self.height), (self.width, self.height), _build_vig, (0, 0), alpha=max(0, min(255, int(pulse * 2.2))))
        if cb:
            for x0 in range(0, bw, 18):                                 # 점선 테두리: 색이 달라도 모양으로 위험을 알림
                pygame.draw.line(self.screen, (255, 255, 255), (bx + x0, by + 1), (bx + min(bw, x0 + 9), by + 1), 3)

    def _render_tspin_hint(self, cells, bx, by, cs):
        """T-스핀 성립 표시: 보라 윤곽이 반짝이고 글자로도 알림 (색약 모드는 흰 윤곽)"""
        a = int(150 + 100 * math.sin(time.time() * 14.0))
        col = (255, 255, 255) if is_colorblind() else (200, 130, 255)
        for px, py in cells:
            CANVAS.alpha_rect((bx + px * cs, by + py * cs, cs, cs), (*col, max(0, min(255, a))), width=2, radius=4)
        top = min(py for _, py in cells)
        mid = sum(px for px, _ in cells) / len(cells)
        self._draw_text("T-SPIN", self.font_tiny, col, bx + int((mid + 0.5) * cs), by + top * cs - 8, "midbottom")

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
                                               color=(240, 78, 88), pulse_speed=-220.0, is_incoming=True)      # 나를 노리는 상대: 굵고 밝은 붉은 점선(2px)이 나를 향해 흐름
                    shown += 1
                    if shown >= 6:   # 다수에게 조준당해도 화면이 붉은 선으로 뒤덮이지 않도록 제한
                        break

        for eff in match.attack_effects:
            fid, tid = eff["from_id"], eff["to_id"]
            p1 = main_center if fid == match.local_player_id else (self.mini_board_rects[fid].center if fid in self.mini_board_rects else None)
            if fid == match.local_player_id and eff.get("origin_row") is not None and not getattr(match, "is_spectating", False):
                p1 = (main_center[0], self.main_board_y + oy + (eff["origin_row"] + 0.5) * self.cell_size)      # 지운 줄이 그대로 탄환이 됨
                oage = now - eff["start_time"]
                if 0.0 <= oage < 0.3:
                    draw_glow(self.screen, p1[0], p1[1], 26, (255, 235, 150) if eff.get("lines", 1) >= 4 else (120, 235, 255), 1.0 - oage / 0.3)
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
                    match.trigger_screen_shake(min(14.0, 5.0 + lines * 2.2), (0, 1))
                elif fid == match.local_player_id:
                    impact_col = (255, 230, 90)
                else:
                    impact_col = (120, 220, 255)
                if eff.get("local"):
                    if fid == match.local_player_id and lines > 0:                # 내 공격이 꽂힌 자리에 보낸 줄 수를 띄움
                        self.impact_numbers.append({"x": p2[0], "y": p2[1], "n": lines, "t0": now})
                    self.particles.add_sparks(p2[0], p2[1], impact_col, count=20 + min(30, lines * 6), speed_mult=1.5)
                    self.particles.add_shockwave(p2[0], p2[1], impact_col, max_radius=35 + min(35, lines * 8) + (18 if eff.get("multi", 1) >= 2 else 0))
                else:                                                   # 나와 무관한 봇끼리의 공격은 작고 가볍게
                    self.particles.add_sparks(p2[0], p2[1], impact_col, count=5, speed_mult=1.2)
                    self.particles.add_shockwave(p2[0], p2[1], impact_col, max_radius=22)

            self._draw_energy_laser_beam(p1, p2, eff, travel_t, progress, fid == match.local_player_id, tid == match.local_player_id)

        self.impact_numbers = [n for n in self.impact_numbers if now - n["t0"] < 0.8]
        for n in self.impact_numbers:                                   # 착탄 숫자: 위로 떠오르며 사라짐 (4줄 이상은 크게)
            a = now - n["t0"]
            fa = 1.0 - (a / 0.8) ** 2
            font = self.font_large if n["n"] >= 4 else self.font_hud
            col = (255, 235, 110) if n["n"] >= 4 else (255, 215, 90)
            tx, ty = n["x"], n["y"] - 14 - 30 * self._ease_out(a / 0.8)
            self._fade_text(f"+{n['n']}", font, (20, 14, 6), tx + 1, ty + 1, 200 * fa, "center")
            self._fade_text(f"+{n['n']}", font, col, tx, ty, 255 * fa, "center")

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
        self.result_focus_id = "restart"        # 결과 화면은 '한 판 더'가 기본 (네트워크는 버튼 목록의 첫 항목으로 보정됨)
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
        info = self._standings_info_lines(match)               # 기록·업적·다음 목표·패인: 우승/상위권 때도 순위표에서 바로 보이게
        nl = len(info)
        box_w, box_h = 1100, 640 + 24 * nl
        bx, by = (self.width - box_w) // 2, max(8, min(60 - 6 * nl, self.height - box_h - 12))
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

        for li, (txt, col) in enumerate(info):
            self._fade_text(txt, self.font_small, col, bx + box_w // 2, by + (92 if won else 118) + 24 * li, a_head, "midtop")

        # 열 머리글
        head_y = by + 124 + 24 * nl
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
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        self.result_practice_btn = None
        if net_on:
            self.result_restart_btn = pygame.Rect(bx + box_w // 2 - 260, btn_y, 250, 46)
            self.result_return_btn = pygame.Rect(bx + box_w // 2 + 10, btn_y, 250, 46)
        else:
            self.result_restart_btn = pygame.Rect(bx + box_w // 2 - 318, btn_y, 200, 46)
            self.result_practice_btn = pygame.Rect(bx + box_w // 2 - 100, btn_y, 200, 46)
            self.result_return_btn = pygame.Rect(bx + box_w // 2 + 118, btn_y, 200, 46)
        self._button(self.result_restart_btn, "대기실로 돌아가기" if net_on else "재도전", "green",
                     self.result_restart_btn.collidepoint(mx, my), "R")
        if self.result_practice_btn:
            self._button(self.result_practice_btn, "연습하기", "blue", self.result_practice_btn.collidepoint(mx, my), "P")
        self._button(self.result_return_btn, "메인 메뉴", "blue", self.result_return_btn.collidepoint(mx, my), "ESC")
        if n > visible:
            self._draw_text("마우스 휠 / ↑ ↓ / PageUp·PageDown 으로 스크롤", self.font_tiny, C_DIM, bx + box_w // 2, by + box_h - 96, "midtop")

    @staticmethod
    def _reward_of(match):
        """결과 화면에 보여 줄 정산 {"xp": {...}, "highlights": [...], "unlocks": [...]} (없으면 None)"""
        r = getattr(match, "reward", None)
        return r if isinstance(r, dict) else None

    def _result_reward_height(self, match):
        """결과 창(탈락 화면)에 보상 줄(경험치 바 / 업적·해금 카드 / 명장면 도장)이 차지하는 높이 (없으면 0)"""
        rw = self._reward_of(match)
        if not rw:
            return 0
        h = 0
        if rw["xp"].get("gain", 0) > 0:
            h += 26
        if getattr(match, "new_achievements", None) or rw["unlocks"]:
            h += 34
        if rw["highlights"]:
            h += 30
        return h + (6 if h else 0)

    def _draw_result_rewards(self, match, bx, y, box_w, t, rec_t):
        """보상 줄: 경험치 바(레벨이 오르면 가득 찼다가 새 레벨로 다시 참) / 새 업적·해금 카드가 하나씩 미끄러져 들어옴 / 명장면 도장"""
        rw = self._reward_of(match)
        if not rw:
            return
        cx = bx + box_w // 2
        xp = rw["xp"]
        if xp.get("gain", 0) > 0:
            k = _ease_out((t - rec_t - 0.25) / 0.9)
            pos = xp["before"] + xp["gain"] * k
            lv, into, need = level_of(pos)
            label = f"Lv.{lv}"
            bar = pygame.Rect(bx + 120, y + 6, box_w - 120 - 150, 12)
            self._draw_text(label, self.font_mid, C_GOLD, bar.x - 12, y + 12, "midright")
            pygame.draw.rect(self.screen, (24, 29, 48), bar, border_radius=6)
            fw = int(bar.w * into / max(1, need))
            if fw > 0:
                pygame.draw.rect(self.screen, C_GOLD if lv > xp["lv_before"] else C_ACCENT, (bar.x, bar.y, max(fw, 8), bar.h), border_radius=6)
            pygame.draw.rect(self.screen, (60, 72, 108), bar, 1, border_radius=6)
            gtxt = f"+{int(xp['gain'] * k)} XP"
            self._draw_text(gtxt, self.font_small, C_TEXT, bar.right + 12, y + 12, "midleft")
            if xp["lv_after"] > xp["lv_before"] and k >= 1.0:
                pulse = 0.5 + 0.5 * math.sin(time.time() * 8.0)
                self._draw_text("LEVEL UP!", self.font_small, _mix(C_GOLD, (255, 255, 255), 0.5 * pulse), bar.right + 12 + self.font_small.size(gtxt)[0] + 10, y + 12, "midleft")
            y += 26
        titles = {a[0]: a[1] for a in ACHIEVEMENTS}
        pills = [("★ " + titles.get(a, a), C_GOLD) for a in (getattr(match, "new_achievements", None) or [])]
        pills += [(f"◆ 새 스킨 해금: {u}", (130, 235, 255)) for u in rw["unlocks"]]
        if pills:
            shown = pills[:3]
            if len(pills) > 3:
                shown[-1] = (f"외 {len(pills) - 2}개", C_DIM)
            widths = [self.font_small.size(txt)[0] + 26 for txt, _c in shown]
            x0 = cx - (sum(widths) + 10 * (len(shown) - 1)) // 2
            for i, ((txt, col), w_) in enumerate(zip(shown, widths)):
                k = _ease_out((t - rec_t - 0.25 * i) / 0.3)
                if k > 0:
                    r = pygame.Rect(x0, y + 4 + int((1 - k) * 14), w_, 26)
                    CANVAS.alpha_rect(r, (40, 34, 14, int(235 * k)), radius=13)
                    CANVAS.alpha_rect(r, (*col, int(230 * k)), width=1, radius=13)
                    self._fade_text(txt, self.font_small, col, r.centerx, r.centery, 255 * k, "center")
                x0 += w_ + 10
            y += 34
        hl = rw["highlights"]
        if hl:
            labels = [(match.HIGHLIGHT_LABELS.get(h, (h, C_GOLD))) for h in hl[:4]]
            widths = [self.font_small.size(txt)[0] + 24 for txt, _c in labels]
            x0 = cx - (sum(widths) + 8 * (len(labels) - 1)) // 2
            for i, ((txt, col), w_) in enumerate(zip(labels, widths)):
                k = _ease_out((t - rec_t - 0.45 - 0.22 * i) / 0.25)
                if k > 0:
                    sc = 1.0 + 0.4 * (1.0 - k) ** 2                          # 도장이 찍히듯 커졌다 줄어듦
                    r = pygame.Rect(0, 0, int(w_ * sc), int(24 * sc))
                    r.center = (x0 + w_ // 2, y + 14)
                    CANVAS.alpha_rect(r, (20, 22, 38, int(240 * k)), radius=8)
                    CANVAS.alpha_rect(r, (*col, int(255 * k)), width=2, radius=8)
                    self._fade_text(txt, self.font_small, col, r.centerx, r.centery, 255 * k, "center")
                x0 += w_ + 8

    def _standings_info_lines(self, match):
        """순위표 머리에 붙일 한두 줄 [(문구, 색)]: ★ 최고 기록/클리어/업적, 다음 목표, (탈락했다면) 패인 첫 줄. 없으면 빈 목록"""
        won = match.local_rank == 1
        lines = []
        records = tuple(getattr(match, "new_records", ()) or ())
        ladder_clear = getattr(match, "ladder_clear", None)
        ach = tuple(getattr(match, "new_achievements", ()) or ())
        names = {"rank": "순위", "ko": "K.O.", "combo": "최대 콤보"}
        parts = []
        if records:
            parts.append("최고 기록 갱신!  " + " · ".join(names[k] for k in records if k in names))
        if ladder_clear:
            parts.append(f"난이도 클리어!  {LADDER_NAMES.get(ladder_clear, ladder_clear)}")
        if ach:
            titles = {a[0]: a[1] for a in ACHIEVEMENTS}
            parts.append("업적 달성!  " + " · ".join(titles.get(x, x) for x in ach[:2]) + (f" 외 {len(ach) - 2}개" if len(ach) > 2 else ""))
        csum = match.challenge_summary() if hasattr(match, "challenge_summary") else None
        if csum:
            parts.append(csum[0] if self.font_small.size(csum[0])[0] < 700 else csum[1])
        rw = self._reward_of(match)
        if rw and rw["unlocks"]:
            parts.append("새 스킨 해금!  " + " · ".join(rw["unlocks"]))
        if parts:
            lines.append(("★ " + "   ★ ".join(parts), C_GOLD))
        if rw and rw["xp"].get("gain", 0) > 0:
            xp = rw["xp"]
            up = xp["lv_after"] > xp["lv_before"]
            lines.append((f"경험치 +{xp['gain']} XP   ·   Lv.{xp['lv_after']}" + ("   ★ 레벨 업!" if up else "") + (f"   ·   다음 해금: {rw['next_unlock']}" if rw.get("next_unlock") else ""), C_GOLD if up else (170, 200, 235)))
        if rw and rw["highlights"]:
            lines.append(("명장면:  " + " · ".join(match.HIGHLIGHT_LABELS.get(h, (h, None))[0] for h in rw["highlights"][:4]), (255, 215, 130)))
        goal = getattr(match, "next_goal", None)
        loss = None if won else match.defeat_summary()
        second = None
        if loss:
            second = (loss[0], (255, 190, 150))
        elif goal:
            second = (f"다음 목표: {goal}", C_DIM)
        if second:
            lines.append(second)
        out = []
        for txt, col in lines[:4]:
            while len(txt) > 8 and self.font_small.size(txt)[0] > 1060:
                txt = txt[:-2].rstrip(" ·(") + "…"
            out.append((txt, col))
        return out

    def _standings_scroll_seen(self, start):
        """스크롤로 새로 보이게 된 행은 등장 애니메이션 없이 바로 표시"""
        return True

    def _draw_timeline_graph(self, match, rect, legend_right, legend_y):
        """경기 흐름 미니 그래프: 주황=내 스택 높이(0~20줄), 파랑=생존자 비율. 점이 5개 미만이면 그리지 않음"""
        tl = getattr(match, "timeline", None)
        if not tl or len(tl) < 5:
            return
        pygame.draw.rect(self.screen, (18, 23, 40), rect, border_radius=8)
        pygame.draw.rect(self.screen, (44, 56, 92), rect, 1, border_radius=8)
        inner = rect.inflate(-10, -10)
        n = len(tl)
        total = max(1, match.total_players)
        def pts(fn):
            return [(inner.x + inner.w * i / max(1, n - 1), inner.bottom - inner.h * min(1.0, max(0.0, fn(t))))
                    for i, t in enumerate(tl)]
        pygame.draw.lines(self.screen, (90, 170, 255), False, pts(lambda t: t[1] / total), 2)          # 생존자 비율
        stack = pts(lambda t: t[2] / float(BOARD_HEIGHT))
        pygame.draw.lines(self.screen, (255, 165, 70), False, stack, 2)                                  # 내 스택 높이
        pygame.draw.circle(self.screen, (255, 90, 90), (int(stack[-1][0]), int(stack[-1][1])), 3)        # 탈락 지점
        # 범례는 오른쪽 위에 (그래프 아래에 두면 길어진 '최종 순위 … 에게 탈락' 줄과 겹침)
        self._draw_text("━ 내 스택 높이", self.font_tiny, (255, 165, 70), legend_right, legend_y, "topright")
        self._draw_text("━ 생존자 비율", self.font_tiny, (90, 170, 255), legend_right, legend_y + 16, "topright")

    def _render_result_overlay(self, match):
        CANVAS.overlay((4, 6, 12, 200))

        won = match.local_rank == 1
        accent = C_GOLD if won else C_DANGER
        records = tuple(getattr(match, "new_records", ()) or ())
        ladder_clear = getattr(match, "ladder_clear", None)
        ach = tuple(getattr(match, "new_achievements", ()) or ())
        csum = match.challenge_summary() if hasattr(match, "challenge_summary") else None
        lh = self.font_small.get_height()
        has_line = bool(records or ladder_clear or csum or (ach and not self._reward_of(match)))      # 업적은 보상 줄의 카드로 보여 주므로 요약 줄에서는 뺌
        # 최고 기록 줄이 있으면 그 줄 + 배지 줄 + 버튼 발광(위로 8px)이 겹치지 않도록 패널을 그만큼 늘림 (글자 크기 옵션에도 맞춰짐)
        extra = max(0, 178 + lh + 4 + lh + 12 - 226) if has_line else 0
        loss_lines = None if won else match.defeat_summary()          # 패인 한 줄 + 다음에 해 볼 한 줄: 그만큼 패널을 늘림
        if loss_lines:
            extra += (lh + 4) * len(loss_lines)
        extra += self._result_reward_height(match)                    # 경험치 바 / 업적·해금 카드 / 명장면 도장 줄
        box_w, box_h = 660, 346 + extra
        bx = (self.width - box_w) // 2
        by = (self.height - box_h) // 2
        self._panel((bx, by, box_w, box_h), border=accent, bg=(15, 19, 34), radius=18, alpha=248, border_w=2)

        if won:
            self._draw_text("로열 빅토리!", self.font_title, C_GOLD, bx + box_w // 2, by + 22, "midtop", shadow=True)
            self._draw_text("최후의 1인으로 살아남았습니다", self.font_mid, C_GREEN, bx + box_w // 2, by + 66, "midtop")
            rank_txt = "#1"
        else:
            self._draw_text("K.O.  경기 탈락", self.font_title, C_DANGER, bx + box_w // 2, by + 22, "midtop", shadow=True)
            killer = getattr(match, "local_killer_id", None)
            killer_txt = ""
            if killer and killer in match.players:
                kp = match.players[killer]
                killer_txt = f"  ·  {kp.get('name', '?')[:12]}" + (f"({kp['trait']})" if kp.get("trait") else "") + "에게 탈락"          # 나를 K.O.한 상대
            self._draw_text(f"최종 순위  {match.local_rank}위 / {match.total_players}명" + killer_txt, self.font_mid, C_TEXT,
                            bx + box_w // 2, by + 66, "midtop")
            self._draw_timeline_graph(match, pygame.Rect(bx + 22, by + 14, 140, 42), bx + box_w - 22, by + 16)
            rank_txt = f"#{match.local_rank}"

        # 통계 카드: 왼쪽부터 차례로 미끄러져 들어오고, 숫자는 카운트업 (순위는 꼴찌에서 최종 순위까지 카운트다운)
        if self._result_match is not match:
            self._result_match = match
            self._result_t0 = time.time()
        t = time.time() - self._result_t0
        apm, lpm, time_str = match.get_combat_stats()
        tier, _, pct = match.get_badge_info()
        rank_now = int(match.local_rank)
        rank_shown = rank_now + int(round((match.total_players - rank_now) * (1.0 - _ease_out((t - 0.35) / 1.0))))
        rec_t = 1.45                                                    # 카드가 다 나온 뒤 최고 기록 표시
        cards = [
            ("순위", f"#{rank_shown}", accent, "rank", None),
            ("K.O.", "{:d}", C_TEXT, "ko", match.local_ko_count),
            ("제거 라인", "{:d}", C_ACCENT, None, match.local_engine.lines_cleared_total),
            ("최대 콤보", "{:d}", C_ORANGE, "combo", match.local_engine.max_combo),
            ("APM", "{:.1f}", C_GOLD, None, apm),
            ("생존 시간", time_str, C_GREEN, None, None),
        ]
        cw, gap = 96, 10
        sx = bx + (box_w - (cw * len(cards) + gap * (len(cards) - 1))) // 2
        for i, (lbl, val, col, rec_key, num) in enumerate(cards):
            start = 0.20 + 0.09 * i
            if t < start:
                continue
            k = _ease_out((t - start) / 0.35)
            if num is not None:                                          # 등장한 뒤 0.6초 동안 0에서 목표 값까지 올라감
                val = val.format(num * _ease_out((t - start - 0.15) / 0.6) if "f" in val else int(round(num * _ease_out((t - start - 0.15) / 0.6))))
            r = pygame.Rect(sx + i * (cw + gap), by + 108 + int((1.0 - k) * 16), cw, 66)
            self._panel(r, border=(50, 62, 96), bg=(22, 27, 46), radius=10)
            self._draw_text(lbl, self.font_tiny, C_DIM, r.centerx, r.y + 9, "midtop")
            self._draw_text(val, self.font_big_num, col, r.centerx, r.y + 28, "midtop")
            if rec_key in records and t >= rec_t:                        # 이번 경기에서 최고 기록을 넘은 카드: 금색 테두리 + NEW
                pulse = 0.5 + 0.5 * math.sin(t * 6.0)
                pygame.draw.rect(self.screen, _mix(C_GOLD, (255, 255, 255), 0.45 * pulse), r, 2, border_radius=10)
                pill = pygame.Rect(r.right - 38, r.y - 8, 44, 17)
                pygame.draw.rect(self.screen, C_GOLD, pill, border_radius=8)
                self._draw_text("NEW", self.font_tiny, (24, 18, 4), pill.centerx, pill.centery, "center")
        badge_y = by + 188
        if (records or ladder_clear or (ach and not self._reward_of(match)) or csum) and t >= rec_t:
            names = {"rank": "순위", "ko": "K.O.", "combo": "최대 콤보"}
            parts = []
            if csum:
                parts.append(csum[0] if self.font_small.size(csum[0])[0] < box_w - 50 else csum[1])
            if records:
                parts.append("최고 기록 갱신!  " + " · ".join(names[k] for k in records if k in names))
            if ladder_clear:
                parts.append(f"난이도 클리어!  {LADDER_NAMES.get(ladder_clear, ladder_clear)}")
            if ach and not self._reward_of(match):
                titles = {a[0]: a[1] for a in ACHIEVEMENTS}
                shown = [titles.get(x, x) for x in ach[:2]]
                parts.append("업적 달성!  " + " · ".join(shown) + (f" 외 {len(ach) - 2}개" if len(ach) > 2 else ""))
            line = "★ " + "   ★ ".join(parts)
            if self.font_small.size(line)[0] > box_w - 30:                # 한 줄에 다 안 들어가면 상세를 줄임 (기록 항목/업적 이름)
                short = []
                if records:
                    short.append("최고 기록 갱신!")
                if ladder_clear:
                    short.append(f"난이도 클리어!  {LADDER_NAMES.get(ladder_clear, ladder_clear)}")
                if ach and not self._reward_of(match):
                    short.append(f"업적 {len(ach)}개 달성!")
                if csum:
                    short.insert(0, csum[1])
                line = "★ " + "   ★ ".join(short)
            self._draw_text(line, self.font_small, C_GOLD, bx + box_w // 2, by + 178, "midtop")
        if has_line:
            badge_y = by + 178 + lh + 4
        badge_txt = f"최종 배지 Lv.{tier} (공격력 +{pct})" if tier > 0 else "최종 배지 Lv.0"
        if getattr(match, "local_assists", 0) > 0:
            badge_txt += f"   ·   K.O. 기여 {match.local_assists}"
        goal = getattr(match, "next_goal", None)
        if goal and t >= 1.2:                                            # 다음 목표: 재도전 동기를 주는 한 줄 (카드 연출이 끝난 뒤 표시)
            badge_txt += f"   ·   다음 목표: {goal}"
        self._draw_text(badge_txt, self.font_small, C_DIM, bx + box_w // 2, badge_y, "midtop")
        if loss_lines and t >= 1.2:
            for li, ln in enumerate(loss_lines):
                col = (255, 190, 150) if li == 0 else (170, 200, 235)
                while len(ln) > 8 and self.font_small.size(ln)[0] > box_w - 24:      # 패널 폭을 넘으면 끝을 줄임 (여백 확보)
                    ln = ln[:-2].rstrip(" ·(") + "…"
                self._draw_text(ln, self.font_small, col, bx + box_w // 2, badge_y + (lh + 4) * (li + 1), "midtop")
        if self._result_reward_height(match) and t >= rec_t:
            self._draw_result_rewards(match, bx, badge_y + (lh + 4) * (1 + (len(loss_lines) if loss_lines else 0)) + 4, box_w, t, rec_t)

        mx, my = pygame.mouse.get_pos()
        can_spectate = (not match.match_finished and match.alive_count > 1 and not match.local_is_alive)
        btn_y, btn_h = by + 226 + extra, 50

        self.result_restart_btn = self.result_spectate_btn = self.result_return_btn = self.result_practice_btn = None
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
            btn_w, g = 148, 10
            sbx = bx + (box_w - (btn_w * 4 + g * 3)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("spectate", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "경기 관전", "gold", "S"),
                ("practice", pygame.Rect(sbx + (btn_w + g) * 2, btn_y, btn_w, btn_h), "연습하기", "blue", "P"),
                ("return", pygame.Rect(sbx + (btn_w + g) * 3, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]
        else:
            btn_w, g = 196, 12
            sbx = bx + (box_w - (btn_w * 3 + g * 2)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("practice", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "연습하기", "blue", "P"),
                ("return", pygame.Rect(sbx + (btn_w + g) * 2, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]

        ids = [s[0] for s in specs]
        if self.result_focus_id not in ids:
            self.result_focus_id = ids[0]
        res_moved = (mx, my) != getattr(self, "_result_last_mouse", None)        # 마우스가 실제로 움직였을 때만 호버로 포커스를 옮김
        self._result_last_mouse = (mx, my)
        for bid, rect, _label, _style, _hint in specs:
            if res_moved and rect.collidepoint(mx, my):       # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮김 (이중 하이라이트 방지)
                self.result_focus_id = bid
                break
        for bid, rect, label, style, hint in specs:
            if bid == "restart":
                self.result_restart_btn = rect
            elif bid == "spectate":
                self.result_spectate_btn = rect
            elif bid == "return":
                self.result_return_btn = rect
            elif bid == "practice":
                self.result_practice_btn = rect
            self._button(rect, label, style, self.result_focus_id == bid, hint)

        self._draw_text("버튼을 클릭하거나 단축키로, ← → 와 Enter 로도 실행할 수 있습니다", self.font_tiny, C_DIM,
                        bx + box_w // 2, by + box_h - 36, "midtop")

    # ---------------------------------------------------------------- 관전 HUD
    def _render_spectator_hud(self, match, ox=0, oy=0):
        """관전 바: 미니 보드 영역(좌우)을 가리지 않도록 보드 아래 중앙 빈 공간에 2줄로 표시"""
        target_p = match.players.get(match.spectate_target_id, {})
        name = target_p.get("name", "생존자 탐색 중")
        who = (f"{target_p['trait']} 봇" if target_p.get("trait") else "봇") if target_p.get("is_ai", False) else "사람"
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
        hints = [("← →", "대상 변경"), ("클릭", "미니 보드 선택"), ("S", "결과 화면")]
        if not net_on:
            hints.append(("F", f"배속 ×{getattr(match, 'spectate_speed', 1)}"))
            hints.append(("R", "재도전"))
            hints.append(("P", "연습"))
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
