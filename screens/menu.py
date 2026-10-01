"""
Block Royale 100 - 메인 메뉴 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인.
구성: 왼쪽 위 프로필 칩 · 오른쪽 위 유틸리티 알약(이동 2 + 토글 2) · 로고 · 주 카드(빠른 시작) + 보조 카드 2장 · 포커스 설명 줄 · 하단 바
포커스는 키보드/마우스가 하나의 기준(self.menu_focus)을 공유하고, 호버/포커스 강조는 색 보간으로 부드럽게 전환됨(도형만 그림, 프레임마다 Surface 생성 없음)
"""

import datetime
import time

from app_common import (
    APP_VERSION, BOT_DIFFICULTY_LABELS, C_ACCENT, C_DANGER, C_GOLD, C_GREEN, C_TEXT,
    LADDER, LADDER_MIN_PLAYERS, LADDER_NAMES, LADDER_RANK,
    NAME_COLORS, SCREEN_HEIGHT, SCREEN_WIDTH, _mix, pygame
)

CARD_BG = (22, 28, 48)
COL_SUB = (160, 172, 205)          # 보조 글자 (배경 대비 충분한 밝기)
COL_HINT = (140, 152, 185)         # 가장 어두운 글자의 하한
PILL_GAP = 10                       # 오른쪽 위 알약 사이 간격 (모두 같게)
UTIL_ROW = ["practice", "daily", "records", "settings", "toggle_sound", "toggle_fs"]

DESCRIPTIONS = {
    "quick_play": "봇과 바로 대전합니다.  ← → 로 인원, D 로 봇 난이도를 바꿀 수 있어요.",
    "host_room": "방을 열고 친구를 초대합니다. 부족한 인원은 봇이 채웁니다.",
    "join_room": "LAN에서 열린 방을 자동으로 찾거나, 호스트 IP 주소로 직접 접속합니다.",
    "match_summary": "이름, 참가 인원, 봇 난이도를 바꾸려면 Enter — 설정 화면으로 이동합니다.",
    "practice": "혼자 연습합니다. G 키로 쓰레기 줄을 받아 보고 B 키로 보드를 초기화합니다. 전적에는 기록되지 않아요.",
    "daily": "오늘의 도전: 하루에 한 번 정해지는 같은 블록 순서·같은 상대(100인, 혼합 난이도)로 내 순위를 겨룹니다.",
    "records": "지난 경기 기록과 통계를 봅니다.",
    "settings": "화면, 소리, 조작키, 게임 설정을 바꿉니다.",
    "toggle_sound": "소리를 켜고 끕니다.",
    "toggle_fs": "전체 화면과 창 모드를 전환합니다.",
    "quit_game": "게임을 종료합니다. (종료 전에 한 번 더 확인합니다)",
}


class MenuMixin:
    MENU_FOCUS_ORDER = ["quick_play", "host_room", "join_room", "match_summary",
                        "practice", "daily", "records", "settings", "toggle_sound", "toggle_fs", "quit_game"]

    # ------------------------------------------------------------------ 상태 갱신
    def _menu_focus_id(self):
        return self.MENU_FOCUS_ORDER[self.menu_focus % len(self.MENU_FOCUS_ORDER)]

    def _set_menu_focus(self, bid, sound=True):
        idx = self.MENU_FOCUS_ORDER.index(bid)
        if idx != self.menu_focus:
            self.menu_focus = idx
            if sound:
                self.sound_mgr.play('move')

    def _update_menu(self, dt):
        self.menu_bg.update(dt)
        if not self._menu_active:                          # 메뉴에 들어올 때마다 카드 등장 연출을 처음부터
            self._menu_active = True
            self._menu_intro_t = 0.0
        self._menu_intro_t += dt
        fid = self._menu_focus_id()
        k = min(1.0, dt * 12.0)
        for bid in self.MENU_FOCUS_ORDER:                  # 강조 정도를 목표값(포커스면 1)으로 부드럽게 접근
            cur = self._menu_hl.get(bid, 1.0 if bid == fid else 0.0)
            self._menu_hl[bid] = cur + ((1.0 if bid == fid else 0.0) - cur) * k

    # ------------------------------------------------------------------ 실행/이벤트
    def _menu_adjust_players(self, delta):
        self.adjust_player_count(delta)
        self.sound_mgr.play('rotate')
        self._menu_flash = time.time()                     # 숫자가 바뀐 순간 잠깐 금색으로

    def _menu_activate(self, btn_id):
        """메인 메뉴 항목 실행 (키보드/마우스 공용)"""
        if btn_id == "toggle_sound":
            self.toggle_mute()
            return
        if btn_id == "toggle_fs":
            self.sound_mgr.play('move')
            self.toggle_fullscreen()
            return
        self.sound_mgr.play('move')
        if btn_id == "quick_play":
            self.start_game(mode="SOLO", total_players=self.target_player_count)
        elif btn_id == "host_room":
            if self._start_host_room():
                self.state = "HOST_LOBBY"
        elif btn_id == "join_room":
            self._enter_join_menu()
        elif btn_id == "practice":
            self.start_game(mode="SOLO", practice=True)
        elif btn_id == "daily":
            self.start_game(mode="SOLO", daily=datetime.date.today().strftime("%Y%m%d"))
        elif btn_id == "records":
            self.records_mode = "survival" if self.settings.get("game_mode") == "survival" else "battle"   # 현재 게임 모드의 전적을 먼저 보여줌
            self.records_scroll = 0
            self.previous_state = "MENU"
            self.state = "RECORDS"
        elif btn_id == "settings":
            self.previous_state = "MENU"
            self.state = "SETTINGS"
        elif btn_id == "match_summary":
            self.previous_state = "MENU"
            self.settings_tab = "match"
            self.state = "SETTINGS"
        elif btn_id == "quit_game":
            self._confirm_quit_app()

    def _handle_menu_event(self, event):
        if event.type == pygame.KEYDOWN:
            k = event.key
            self._menu_kb = True
            shift = bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
            fid = self._menu_focus_id()
            n = len(self.MENU_FOCUS_ORDER)
            if k == pygame.K_ESCAPE:
                self._confirm_quit_app()
            elif k in (pygame.K_1, pygame.K_KP1):
                self._menu_activate("quick_play")
            elif k in (pygame.K_2, pygame.K_KP2):
                self._menu_activate("host_room")
            elif k in (pygame.K_3, pygame.K_KP3):
                self._menu_activate("join_room")
            elif k in (pygame.K_4, pygame.K_KP4, pygame.K_s, pygame.K_o):
                self._menu_activate("settings")
            elif k in (pygame.K_r, pygame.K_KP5):
                self._menu_activate("records")
            elif k == pygame.K_p:
                self._menu_activate("practice")
            elif k == pygame.K_c:
                self._menu_activate("daily")
            elif k == pygame.K_UP or (k == pygame.K_TAB and shift):
                self.menu_focus = (self.menu_focus - 1) % n
                self.sound_mgr.play('move')
            elif k in (pygame.K_DOWN, pygame.K_TAB):
                self.menu_focus = (self.menu_focus + 1) % n
                self.sound_mgr.play('move')
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._menu_activate(fid)
            elif k in (pygame.K_LEFT, pygame.K_RIGHT):
                step = -1 if k == pygame.K_LEFT else 1
                if fid in ("quick_play", "match_summary"):         # 인원 조절은 빠른 시작/프로필에 포커스가 있을 때만
                    self._menu_adjust_players(step * (10 if shift else 1))
                elif fid == "host_room" and step > 0:
                    self._set_menu_focus("join_room")
                elif fid == "join_room" and step < 0:
                    self._set_menu_focus("host_room")
                elif fid in UTIL_ROW:
                    self._set_menu_focus(UTIL_ROW[(UTIL_ROW.index(fid) + step) % len(UTIL_ROW)])
            elif k == pygame.K_d:
                self.sound_mgr.play('rotate')
                self.settings.cycle_bot_difficulty(1)
                self.bot_difficulty = self.settings.get("bot_difficulty")
                self._menu_flash = time.time()
        elif event.type == pygame.MOUSEMOTION:
            self._menu_kb = False
            for bid in self.MENU_FOCUS_ORDER:
                rect = self.menu_buttons.get(bid)
                if rect and rect.collidepoint(event.pos):
                    self._set_menu_focus(bid, sound=False)
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._menu_kb = False
            self._menu_press = None
            for bid, rect in self.menu_buttons.items():
                if rect.collidepoint(event.pos):
                    self._menu_press = bid                    # 누른 순간은 눌림 표시만, 같은 버튼 위에서 뗄 때 실행
                    if bid in self.MENU_FOCUS_ORDER:
                        self._set_menu_focus(bid, sound=False)
                    break
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            press, self._menu_press = self._menu_press, None
            rect = self.menu_buttons.get(press) if press else None
            if rect and rect.collidepoint(event.pos):
                self._menu_activate(press)

    # ------------------------------------------------------------------ 그리기 부품
    def _menu_fit(self, text, font, max_w):
        """글자 폭이 max_w를 넘으면 끝을 자르고 ..."""
        if font.size(text)[0] <= max_w:
            return text
        while len(text) > 1 and font.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."

    def _menu_glow(self, rect, accent, t):
        """포커스 카드 바깥의 은은한 빛: 크기/색별로 한 번만 만든 오버레이의 투명도만 조절"""
        if t <= 0.03:
            return
        w, h = rect.w, rect.h

        def build(surf):
            pygame.draw.rect(surf, (*accent, 255), (0, 0, w + 16, h + 16), border_radius=16)
        self.renderer._blit_overlay(("mcglow", w, h, accent), (w + 16, h + 16), build, (rect.x - 8, rect.y - 8), alpha=int(70 * t))

    def _menu_focus_ring(self, rect, accent, bg, radius):
        """키보드로 이동했을 때만 보이는 바깥 링 (마우스 호버와 구분)"""
        if self._menu_kb:
            pygame.draw.rect(self.screen, _mix(accent, bg, 0.45), rect.inflate(10, 10), 1, border_radius=radius + 4)

    def _menu_slide(self, index):
        """카드 등장 연출: 위치는 처음부터 최종 자리에 두고 그릴 때만 아래에서 살짝 올라옴"""
        p = max(0.0, min(1.0, (self._menu_intro_t - (0.08 + index * 0.07)) / 0.4))
        return int(round(16 * (1.0 - p) ** 3))

    def _menu_glyph(self, kind, x, y, accent, big):
        """카드 왼쪽의 작은 그림: 블록 셀(캐시된 셀 그림)과 선으로만 그림"""
        r = self.renderer
        if kind == "quick":                                # 쌓인 블록 위로 떨어지는 T
            cs = 17 if big else 12
            stack = [(0, 3, 'L'), (1, 3, 'L'), (2, 3, 'J'), (3, 3, 'J'), (0, 2, 'L'), (3, 2, 'J')]
            fall = [(1, 0, 'T'), (0, 1, 'T'), (1, 1, 'T'), (2, 1, 'T')]
            for cx_, cy_, ch in stack + fall:
                r._draw_cell(x + cx_ * cs, y + cy_ * cs, cs, ch)
        elif kind == "host":                               # O 블록 + 퍼져 나가는 신호
            cs = 15
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                r._draw_cell(x + 2 + dx * cs, y + 14 + dy * cs, cs, 'O')
            for rad in (7, 12):
                pygame.draw.circle(self.screen, _mix(accent, CARD_BG, 0.25 if rad == 7 else 0.55), (x + 40, y + 8), rad, 2)
        else:                                              # L 블록 + 접속 화살표
            cs = 14
            for dx, dy in ((0, 0), (0, 1), (1, 1), (2, 1)):
                r._draw_cell(x + 2 + dx * cs, y + 16 + dy * cs, cs, 'L')
            ax, ay = x + 6, y + 6
            pygame.draw.line(self.screen, accent, (ax, ay), (ax + 30, ay), 3)
            pygame.draw.line(self.screen, accent, (ax + 30, ay), (ax + 22, ay - 7), 3)
            pygame.draw.line(self.screen, accent, (ax + 30, ay), (ax + 22, ay + 7), 3)

    def _menu_card(self, bid, rect, kind, accent, title, desc, key, chip, chip_col, hero, index):
        rect = pygame.Rect(rect)
        self.menu_buttons[bid] = rect                       # 클릭 영역은 처음부터 최종 위치
        t = self._menu_hl.get(bid, 1.0 if self._menu_focus_id() == bid else 0.0)
        pressed = (self._menu_press == bid)
        dr = rect.move(0, self._menu_slide(index) + (2 if pressed else 0))
        self._menu_glow(dr, accent, t)
        base = (0.14 if hero else 0.05) + (0.10 if hero else 0.11) * t + (0.06 if pressed else 0.0)
        bg = _mix(CARD_BG, accent, base)
        edge = accent if hero else _mix(_mix(accent, CARD_BG, 0.6), accent, t)
        pygame.draw.rect(self.screen, bg, dr, border_radius=14 if hero else 12)
        pygame.draw.rect(self.screen, edge, dr, 2 if (hero or t > 0.5) else 1, border_radius=14 if hero else 12)
        if t > 0.5:
            self._menu_focus_ring(dr, accent, bg, 14 if hero else 12)
        gx, gy = (dr.x + 24, dr.y + 18) if hero else (dr.x + 18, dr.y + 20)
        self._menu_glyph(kind, gx, gy, accent, hero)
        tx = dr.x + (116 if hero else 84)
        badge_w = 46
        if hero:
            self._t(title, self.font_hero, C_TEXT, tx, dr.y + 18)
            self._t(self._menu_fit(desc, self.font_help, dr.w - (tx - dr.x) - badge_w - 34), self.font_help, COL_SUB, tx, dr.y + 58)
        else:
            self._t(title, self.font_menu, C_TEXT, tx, dr.y + 14)
            self._t(self._menu_fit(desc, self.font_help, dr.w - (tx - dr.x) - badge_w - 24), self.font_help, COL_SUB, tx, dr.y + 44)
        kr = pygame.Rect(dr.right - 20 - 34, dr.y + 14, 34, 26)
        pygame.draw.rect(self.screen, accent, kr, border_radius=7)
        self._t(key, self.font_mid, (12, 16, 28), kr.centerx, kr.centery, "center")
        if hero:
            self._t("Enter  >", self.font_small, accent, dr.right - 20, dr.y + 52, "topright")
        if chip:                                            # 실시간 정보 칩 (카드 오른쪽 아래)
            maxw = dr.w - (tx - dr.x) - 30
            s = self._menu_fit(chip, self.font_small, maxw)
            cy = dr.bottom - (18 if hero else 14)
            tr = self._t(s, self.font_small, chip_col, dr.right - 22, cy, "midright")
            pygame.draw.circle(self.screen, chip_col, (tr.x - 9, cy), 3)

    def _menu_pill(self, bid, right, y, label, key, tint, dot=None):
        """오른쪽 위 알약 하나 (오른쪽 끝 기준으로 폭을 계산해 그리고 왼쪽 끝 x를 반환)"""
        lw = self.font_small.size(label)[0]
        kw = self.font_tiny.size(key)[0] + 12
        w = 18 + (14 if dot else 0) + lw + 10 + kw + 10
        rect = pygame.Rect(right - w, y, w, 36)
        self.menu_buttons[bid] = rect
        t = self._menu_hl.get(bid, 1.0 if self._menu_focus_id() == bid else 0.0)
        pressed = (self._menu_press == bid)
        bg = _mix((22, 28, 48), (36, 46, 76), t)
        pygame.draw.rect(self.screen, bg if not pressed else (44, 56, 90), rect, border_radius=18)
        edge = _mix(_mix((56, 70, 108), tint, 0.3), tint, t)
        pygame.draw.rect(self.screen, edge, rect, 1, border_radius=18)
        if t > 0.5:
            self._menu_focus_ring(rect, tint, bg, 18)
        x = rect.x + 16
        if dot:
            pygame.draw.circle(self.screen, dot, (x + 4, rect.centery), 4)
            x += 14
        self._t(label, self.font_small, C_TEXT if t > 0.5 else (200, 210, 232), x, rect.centery, "midleft")
        kr = pygame.Rect(rect.right - 10 - kw, rect.centery - 9, kw, 18)
        pygame.draw.rect(self.screen, (36, 44, 70), kr, border_radius=5)
        pygame.draw.rect(self.screen, (78, 92, 132), kr, 1, border_radius=5)
        self._t(key, self.font_tiny, (215, 225, 245), kr.centerx, kr.centery, "center")
        return rect.x

    def _menu_profile_chip(self):
        rect = pygame.Rect(24, 18, 364, 44)
        self.menu_buttons['match_summary'] = rect
        t = self._menu_hl.get('match_summary', 1.0 if self._menu_focus_id() == 'match_summary' else 0.0)
        bg = _mix((20, 26, 46), (30, 40, 68), t)
        pygame.draw.rect(self.screen, bg, rect, border_radius=22)
        pygame.draw.rect(self.screen, _mix((60, 74, 110), C_ACCENT, t), rect, 1, border_radius=22)
        if t > 0.5:
            self._menu_focus_ring(rect, C_ACCENT, bg, 22)
        col = NAME_COLORS[self.name_color][1]
        pygame.draw.circle(self.screen, col, (rect.x + 26, rect.centery), 8)
        name = self._menu_fit(self.player_name, self.font_mid, 118)
        self._t(name, self.font_mid, col, rect.x + 44, rect.centery, "midleft")
        diff = BOT_DIFFICULTY_LABELS.get(self.settings.get("bot_difficulty", "mixed"), "혼합").split(" (")[0]
        flash = (time.time() - self._menu_flash) < 0.35
        self._t(f"{self.target_player_count}명 · {diff}" + (" · 서바이벌" if self.settings.get("game_mode") == "survival" else " · 배틀로얄"), self.font_small, C_GOLD if flash else COL_SUB, rect.right - 36, rect.centery, "midright")
        self._t(">", self.font_mid, C_ACCENT if t > 0.5 else COL_HINT, rect.right - 20, rect.centery, "midright")

    # ------------------------------------------------------------------ 화면
    def _render_menu(self):
        self.menu_bg.draw(self.screen)
        self.menu_buttons.clear()
        cx = SCREEN_WIDTH // 2

        # 1. 왼쪽 위 프로필 칩 + 오른쪽 위 유틸리티 (이동 2 + 토글 2)
        self._menu_profile_chip()
        snd_on = self.sound_mgr.enabled
        x = SCREEN_WIDTH - 24
        x = self._menu_pill("toggle_fs", x, 18, "창 모드" if self.is_fullscreen else "전체 화면", "F11", C_ACCENT) - PILL_GAP
        x = self._menu_pill("toggle_sound", x, 18, "소리 켜짐" if snd_on else "소리 꺼짐", "M",
                            C_GREEN if snd_on else C_DANGER, dot=C_GREEN if snd_on else (110, 120, 150)) - PILL_GAP
        x = self._menu_pill("settings", x, 18, "설정", "S", C_ACCENT) - PILL_GAP
        x = self._menu_pill("records", x, 18, "전적", "R", C_GOLD) - PILL_GAP
        today = datetime.date.today().strftime("%Y%m%d")
        done = self.stats_mgr.daily_best(today) > 0                                  # 오늘의 도전을 이미 했으면 점 없음, 아직이면 초록 점
        x = self._menu_pill("daily", x, 18, "오늘의 도전", "C", C_GREEN, dot=None if done else C_GREEN) - PILL_GAP
        self._menu_pill("practice", x, 18, "연습", "P", C_ACCENT)

        # 2. 로고 + 한 줄 소개
        logo_top = 100
        logo_h = self.logo.draw(self.screen, cx, logo_top)
        self._t("100인 배틀로얄  ·  AI 봇 대전  ·  LAN 멀티", self.font_info, (165, 178, 212), cx, logo_top + logo_h + 2, "midtop")

        # 3. 주 카드(빠른 시작) + 보조 카드 2장. 카드 안 실시간 정보는 이미 있는 데이터(전적/발견된 방/IP)만 사용
        by = logo_top + logo_h + 50                # 로고/소개 줄과 카드 사이에 여유를 둠
        sm = self.stats_mgr.get_summary("survival" if self.settings.get("game_mode") == "survival" else "battle")
        recent = sm.get("recent_matches") or []
        if sm["total_games"] == 0:
            quick_chip, quick_col = "처음이라면 여기서 시작하세요", C_GREEN
        else:
            last = recent[-1] if recent else None
            quick_chip = (f"다시 하기 · 지난 경기 {last.get('rank', '?')}위/{last.get('total_players', '?')} · 최고 {sm['best_rank_str']}"
                          if last else f"최고 순위 {sm['best_rank_str']}")
            quick_col = C_ACCENT
        rooms = len(self.net_mgr.discovered_rooms)
        join_chip, join_col = (f"LAN 방 {rooms}개 발견", C_GOLD) if rooms else ("IP 직접 접속도 가능", COL_HINT)
        n = self.target_player_count
        atk_off = self.settings.get("game_mode") == "survival"
        self._menu_card("quick_play", (cx - 320, by, 640, 104), "quick", C_ACCENT, "빠른 시작",
                        (f"봇 {max(0, n - 1)}명과 서바이벌  ·  {n}인 (공격 없음)" if atk_off else f"봇 {max(0, n - 1)}명과 바로 대전  ·  {n}인 배틀로얄"),
                        "1", quick_chip, quick_col, True, 0)
        self._menu_card("host_room", (cx - 320, by + 116, 314, 88), "host", C_GREEN, "방 만들기",
                        "친구를 초대해 함께", "2", f"내 IP {self.local_ip}", COL_SUB, False, 1)
        self._menu_card("join_room", (cx + 6, by + 116, 314, 88), "join", C_GOLD, "방 참가하기",
                        "LAN 검색 · IP 접속", "3", join_chip, join_col, False, 2)

        # 4. 포커스된 항목의 한 줄 설명 (세 모드의 차이는 여기서 설명)
        fid = self._menu_focus_id()
        desc = DESCRIPTIONS.get(fid, "")
        if fid == "quick_play":
            desc = f"봇 {max(0, n - 1)}명과 바로 대전합니다.  ← → 로 인원, D 로 봇 난이도를 바꿀 수 있어요."
            if self.settings.get("game_mode") != "survival":
                nxt = next((d for d in LADDER if d not in self.stats_mgr.ladder_cleared()), None)
                if nxt:                                                  # 보이지 않던 보상(난이도 사다리 ★)을 메뉴에서 알려 줌
                    desc += f"   ★ 다음 도전: {LADDER_NAMES[nxt]} 봇 {LADDER_MIN_PLAYERS}인↑에서 {LADDER_RANK}위 안"
        self._t(self._menu_fit(desc, self.font_help, 900), self.font_help, COL_SUB, cx, by + 226, "midtop")

        # 5. 하단 바: 버전 · 키 안내 · 게임 종료
        self._t(f"v{APP_VERSION}", self.font_tiny, COL_HINT, 24, SCREEN_HEIGHT - 42, "topleft")
        self._keycap_row([("↑↓←→", "이동"), ("Enter", "선택"), ("R", "전적"), ("S", "설정"), ("Esc", "종료")],
                         cx, SCREEN_HEIGHT - 42, gap=20, font=self.font_small, label_col=COL_SUB)
        quit_r = pygame.Rect(SCREEN_WIDTH - 24 - 112, SCREEN_HEIGHT - 50, 112, 34)
        self.menu_buttons['quit_game'] = quit_r
        t = self._menu_hl.get('quit_game', 1.0 if fid == 'quit_game' else 0.0)
        pressed = (self._menu_press == 'quit_game')
        pygame.draw.rect(self.screen, _mix((22, 28, 48), (52, 30, 40), t) if not pressed else (60, 34, 46), quit_r, border_radius=17)
        pygame.draw.rect(self.screen, _mix(_mix((56, 70, 108), C_DANGER, 0.45), C_DANGER, t), quit_r, 1, border_radius=17)
        if t > 0.5:
            self._menu_focus_ring(quit_r, C_DANGER, (22, 28, 48), 17)
        self._t("게임 종료", self.font_small, C_TEXT if t > 0.5 else (200, 210, 232), quit_r.centerx, quit_r.centery, "center")
