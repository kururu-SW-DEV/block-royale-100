"""
Block Royale 100 - 메인 메뉴 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인.
구성: 왼쪽 위 프로필 칩 · 오른쪽 위 유틸리티 알약(이동 2 + 토글 2) · 로고 · 주 카드(빠른 시작) + 보조 카드 2장 · 포커스 설명 줄 · 하단 바
포커스는 키보드/마우스가 하나의 기준(self.menu_focus)을 공유하고, 호버/포커스 강조는 색 보간으로 부드럽게 전환됨(도형만 그림, 프레임마다 Surface 생성 없음)
"""

import datetime
import time

from app_common import (
    APP_VERSION, BOT_DIFFICULTY_LABELS, C_ACCENT, C_DANGER, C_GOLD, C_GREEN, C_ORANGE, C_TEXT,
    LADDER, LADDER_MIN_PLAYERS, LADDER_NAMES, LADDER_RANK,
    NAME_COLORS, SCREEN_HEIGHT, SCREEN_WIDTH, _mix, pygame
)

CARD_BG = (22, 28, 48)
COL_SUB = (160, 172, 205)          # 보조 글자 (배경 대비 충분한 밝기)
COL_HINT = (140, 152, 185)         # 가장 어두운 글자의 하한
PILL_GAP = 4                        # 오른쪽 위 메뉴 항목 사이 간격 (항목 안쪽 여백이 따로 있음)
UTIL_ROW = ["practice", "daily", "weekly", "records", "settings", "toggle_sound", "toggle_fs"]

DESCRIPTIONS = {
    "quick_play": "봇과 바로 대전합니다.  ← → 로 인원, D 로 봇 난이도를 바꿀 수 있어요.",
    "host_room": "방을 열고 친구를 초대합니다. 부족한 인원은 봇이 채웁니다.",
    "join_room": "LAN에서 열린 방을 자동으로 찾거나, 호스트 IP 주소로 직접 접속합니다.",
    "match_summary": "이름, 참가 인원, 봇 난이도를 바꾸려면 Enter — 설정 화면으로 이동합니다.",
    "practice": "혼자 연습합니다. G 키로 쓰레기 줄을 받아 보고 B 키로 보드를 초기화합니다. 전적에는 기록되지 않아요.",
    "weekly": "이번 주 변형 규칙: 매주 규칙 하나가 바뀐 경기를 같은 블록 순서·같은 상대로 겨룹니다. (소수 정예 / 퍼펙트 폭격 / 안개 속 / 후반 가속 순환)",
    "daily": "오늘의 도전: 하루에 한 번 정해지는 같은 블록 순서·같은 상대(100인, 혼합 난이도)로 내 순위를 겨룹니다.",
    "records": "지난 경기 기록과 통계를 봅니다.",
    "settings": "화면, 소리, 조작키, 게임 설정을 바꿉니다.",
    "toggle_sound": "소리를 켜고 끕니다.",
    "toggle_fs": "전체 화면과 창 모드를 전환합니다.",
    "quit_game": "게임을 종료합니다. (종료 전에 한 번 더 확인합니다)",
}


ATTRACT_IDLE_SECS = 25.0         # 메인 화면에서 이만큼 입력이 없으면 어트랙트 화면(봇 데모 + 점수표)이 나옴


class MenuMixin:
    def _attract_on(self):
        """메인 화면에서 한참 입력이 없을 때만 켜짐 (알림 창/규칙 창이 떠 있으면 켜지 않음)"""
        return (self.state == "MENU" and self.modal is None and not self.rules_open
                and time.time() - getattr(self, "_idle_t", time.time()) > ATTRACT_IDLE_SECS)

    def _attract_reset(self):
        self._idle_t = time.time()
        self._attract = None

    def _render_attract(self, dt):
        """어트랙트 화면: 어둡게 덮고 양옆에서 봇 두 대가 실제로 플레이하는 데모, 가운데에 점수표 TOP 5와 PRESS ANY KEY. 아무 키나 누르면 메인으로 돌아옴"""
        from ai_bot import AIBot
        t_now = time.time()
        demo = getattr(self, "_attract", None)
        if demo is None:
            demo = self._attract = {"t0": t_now, "bots": [AIBot("DEMO_A", "demo", "normal"), AIBot("DEMO_B", "demo", "hard")], "dead_t": [0.0, 0.0]}
        for i, bot in enumerate(demo["bots"]):
            if bot.engine.game_over:                                   # 끝나면 잠깐 뒤 새 판
                if not demo["dead_t"][i]:
                    demo["dead_t"][i] = t_now
                elif t_now - demo["dead_t"][i] > 1.5:
                    demo["bots"][i] = AIBot(bot.bot_id, "demo", bot.difficulty)
                    demo["dead_t"][i] = 0.0
                continue
            bot.update(min(dt, 0.05))
        CANVAS_overlay = self.screen.overlay if hasattr(self.screen, "overlay") else None
        if CANVAS_overlay:
            CANVAS_overlay((4, 6, 14, 255))
        cs = 20
        for i, bot in enumerate(demo["bots"]):
            bx = 150 if i == 0 else SCREEN_WIDTH - 150 - cs * 10
            by = 150
            pygame.draw.rect(self.screen, (10, 12, 22), (bx - 4, by - 4, cs * 10 + 8, cs * 20 + 8), border_radius=8)
            pygame.draw.rect(self.screen, (60, 74, 112), (bx - 4, by - 4, cs * 10 + 8, cs * 20 + 8), 2, border_radius=8)
            eng = bot.engine
            for y in range(20):
                for x in range(10):
                    piece = eng.grid[y][x]
                    if piece:
                        self.renderer._draw_cell(bx + x * cs, by + y * cs, cs, piece)
            if eng.current_piece and not eng.game_over:
                for px, py in eng._get_blocks(eng.current_piece, eng.current_rot, eng.current_x, eng.current_y):
                    if 0 <= py < 20:
                        self.renderer._draw_cell(bx + px * cs, by + py * cs, cs, eng.current_piece)
            self._t(f"SCORE {eng.score:,}", self.font_small, C_GOLD, bx + cs * 5, by + cs * 20 + 14, "center")
        # 가운데: 제목 + 점수표 TOP 5
        cx = SCREEN_WIDTH // 2
        self._t("BLOCK ROYALE 100", self.renderer.font_title, C_GOLD, cx, 110, "center")
        hs = self.stats_mgr.data.get("hiscores", {})
        rows = sorted([e for lst in hs.values() for e in lst], key=lambda e: -e["score"])[:5]
        self._t("HIGH SCORES", self.font_mid, C_TEXT, cx, 190, "center")
        for i in range(5):
            y = 232 + i * 40
            col = (255, 215, 90) if i == 0 else C_TEXT
            if i < len(rows):
                e = rows[i]
                self._t(f"{i + 1}", self.font_mid, col, cx - 200, y, "center")
                self._t(e["ini"], self.font_mid, col, cx - 120, y, "center")
                self._t(f"{e['score']:,}", self.font_mid, col, cx + 60, y, "midright")
                self._t(f"{e['rank']}위/{e['total']}", self.font_small, COL_SUB, cx + 190, y, "center")
            else:
                self._t(f"{i + 1}   - - -", self.font_mid, (80, 90, 120), cx - 40, y, "center")
        pulse = 0.5 + 0.5 * abs(((t_now - demo["t0"]) % 1.6) / 0.8 - 1.0)             # 1.6초 주기로 천천히 깜빡임 (초당 1회 미만)
        self._t("PRESS ANY KEY", self.renderer.font_title, _mix((90, 110, 150), (255, 255, 255), pulse), cx, 470, "center")
        self._t("메인 화면으로 돌아가려면 아무 키나 누르세요", self.font_small, COL_SUB, cx, 515, "center")


    MENU_FOCUS_ORDER = ["quick_play", "host_room", "join_room", "match_summary",
                        "practice", "daily", "weekly", "records", "settings", "toggle_sound", "toggle_fs", "quit_game"]

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
        if btn_id == "update_skip":
            upd = self.update_info()
            if upd:
                self.settings.set("update_skip", upd["tag"])
            return
        if btn_id == "update":
            upd = self.update_info()
            if upd:
                try:
                    import webbrowser
                    webbrowser.open(upd["url"])
                except Exception:
                    pass
            return
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
        elif btn_id == "weekly":
            self.start_game(mode="SOLO", weekly=True)
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
            elif k == pygame.K_w:
                self._menu_activate("weekly")
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
        """글자 폭이 max_w를 넘으면 끝을 자르고 ... (번역한 글자로)"""
        from i18n import tr
        text = tr(text)
        if font.size(text)[0] <= max_w:
            return text
        while len(text) > 1 and font.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."


    def _menu_focus_ring(self, rect, accent, bg, radius):
        """(쓰지 않음) 예전에는 키보드로 이동했을 때 카드 바깥에 링을 그렸으나, 카드 테두리와 겹쳐 이중 테두리로 보였다. 포커스는 카드/항목 자체의 색과 강조선·밑줄로 표시한다"""
        return

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
        """메뉴 카드: 평평한 면 + 1px 테두리. 선택/포커스는 왼쪽 강조선과 면 밝기로만 표시 (바깥 빛 없음 -> 이웃 카드와 겹치지 않음)"""
        rect = pygame.Rect(rect)
        self.menu_buttons[bid] = rect                       # 클릭 영역은 처음부터 최종 위치
        t = self._menu_hl.get(bid, 1.0 if self._menu_focus_id() == bid else 0.0)
        pressed = (self._menu_press == bid)
        dr = rect.move(0, self._menu_slide(index) + (1 if pressed else 0))
        radius = 10
        bg = _mix(CARD_BG, accent, 0.025 + 0.08 * t + (0.04 if pressed else 0.0))          # 강조는 포커스된 카드 하나에만 (빠른 시작도 예외 없음)
        edge = _mix((50, 62, 94), accent, 0.9 * t)
        pygame.draw.rect(self.screen, bg, dr, border_radius=radius)
        pygame.draw.rect(self.screen, edge, dr, 1, border_radius=radius)
        if t > 0.5:                                          # 포커스: 왼쪽 강조선 + 강조 테두리 (바깥 링은 이중 테두리처럼 보여 쓰지 않음)
            pygame.draw.rect(self.screen, accent, (dr.x + 1, dr.y + 16, 3, dr.h - 32), border_radius=2)
        gx, gy = (dr.x + 28, dr.y + 22) if hero else (dr.x + 22, dr.y + 22)
        self._menu_glyph(kind, gx, gy, accent, hero)
        tx = dr.x + (118 if hero else 88)
        kr = pygame.Rect(dr.right - 18 - 26, dr.y + 14, 26, 22)                      # 번호 키: 속 빈 키캡 (패드로 할 때는 숨김)
        if not self.renderer.pad_ui:
            pygame.draw.rect(self.screen, _mix(edge, CARD_BG, 0.2), kr, 1, border_radius=6)
            self._t(key, self.font_small, COL_SUB if t < 0.5 else C_TEXT, kr.centerx, kr.centery, "center")
        if hero:
            self._t(title, self.font_hero, C_TEXT, tx, dr.y + 16)
            self._t(self._menu_fit(desc, self.font_help, dr.w - (tx - dr.x) - 70), self.font_help, COL_SUB, tx, dr.y + 54)
            self._t("A  >" if self.renderer.pad_ui else "Enter  >", self.font_small, accent, dr.right - 20, dr.bottom - 18, "midright")
        else:
            self._t(title, self.font_menu, C_TEXT, tx, dr.y + 14)
            self._t(self._menu_fit(desc, self.font_help, dr.w - (tx - dr.x) - 56), self.font_help, COL_SUB, tx, dr.y + 42)
        if chip:                                            # 실시간 정보 한 줄 (설명 아래, 왼쪽 맞춤)
            maxw = dr.w - (tx - dr.x) - (110 if hero else 24)
            cs = self._menu_fit(chip, self.font_small, maxw)
            cy = dr.bottom - (18 if hero else 16)
            pygame.draw.circle(self.screen, chip_col, (tx + 3, cy), 3)
            self._t(cs, self.font_small, chip_col, tx + 14, cy, "midleft")

    def _menu_pill(self, bid, right, y, label, key, tint, dot=None):
        """오른쪽 위 메뉴 항목 하나 (테두리 없는 글자 + 작은 키 표시, 포커스/호버는 밑줄). 오른쪽 끝 기준으로 폭을 계산해 그리고 왼쪽 끝 x를 반환"""
        if self.renderer.pad_ui:
            key = ""                                          # 패드로 할 때는 단축키 글자(P/C/W/R/S/M/F11)를 숨김: 십자키로 골라 A로 실행
        lw = self.font_small.size(label)[0]
        kw = self.font_tiny.size(key)[0] if key else 0
        w = 8 + (14 if dot else 0) + lw + (8 + kw if key else 0) + 8
        rect = pygame.Rect(right - w, y, w, 36)
        self.menu_buttons[bid] = rect
        t = self._menu_hl.get(bid, 1.0 if self._menu_focus_id() == bid else 0.0)
        pressed = (self._menu_press == bid)
        x = rect.x + 8
        if dot:
            pygame.draw.circle(self.screen, dot, (x + 3, rect.centery), 3)
            x += 14
        col = _mix((176, 188, 218), C_TEXT, 1.0 if pressed else t)
        self._t(label, self.font_small, col, x, rect.centery, "midleft")
        if key:
            self._t(key, self.font_tiny, _mix((104, 116, 150), C_TEXT, 0.5 * t), x + lw + 8, rect.centery + 1, "midleft")
        if t > 0.05:                                         # 밑줄: 호버/포커스 때 왼쪽에서 오른쪽으로 차오름
            ul = int((lw + 8 + kw) * min(1.0, t))
            pygame.draw.rect(self.screen, C_ACCENT, (rect.x + 8 + (14 if dot else 0), rect.bottom - 5, ul, 2), border_radius=1)
        if t > 0.5:
            self._menu_focus_ring(rect, tint, (10, 14, 28), 8)
        return rect.x

    def _menu_profile_chip(self):
        # 칩 폭: 영어처럼 요약("100 players · Easy · Battle Royale")이 길면 이름/칭호와 겹치지 않게 늘림 (위쪽 메뉴 항목과 부딪히지 않는 470px까지)
        from i18n import tr as _tr
        _diff = BOT_DIFFICULTY_LABELS.get(self.settings.get("bot_difficulty", "mixed"), "혼합").split(" (")[0]
        _sum = f"{self.target_player_count}명 · {_diff}" + (" · 서바이벌" if self.settings.get("game_mode") == "survival" else " · 배틀로얄")
        _need = 14 + 40 + 10 + 110 + 8 + 120 + 14 + self.font_small.size(_tr(_sum))[0] + 36
        rect = pygame.Rect(24, 18, max(364, min(470, _need)), 44)
        self.menu_buttons['match_summary'] = rect
        t = self._menu_hl.get('match_summary', 1.0 if self._menu_focus_id() == 'match_summary' else 0.0)
        bg = _mix((14, 19, 36), (26, 34, 60), t)
        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        pygame.draw.rect(self.screen, _mix((44, 56, 88), C_ACCENT, 0.7 * t), rect, 1, border_radius=10)
        if t > 0.5:
            self._menu_focus_ring(rect, C_ACCENT, bg, 10)
        col = NAME_COLORS[self.name_color][1]
        lv = self.stats_mgr.level()[0]                           # 레벨: 이름 색의 작은 글자 (배지 테두리 없이)
        lv_txt = f"Lv.{lv}"
        lr = self._t(lv_txt, self.font_tiny, col, rect.x + 14, rect.centery, "midleft")
        name = self._menu_fit(self.player_name, self.font_mid, 110)
        nr = self._t(name, self.font_mid, C_TEXT, lr.right + 10, rect.centery, "midleft")
        diff = BOT_DIFFICULTY_LABELS.get(self.settings.get("bot_difficulty", "mixed"), "혼합").split(" (")[0]
        flash = (time.time() - self._menu_flash) < 0.35
        sr = self._t(f"{self.target_player_count}명 · {diff}" + (" · 서바이벌" if self.settings.get("game_mode") == "survival" else " · 배틀로얄"), self.font_small, C_GOLD if flash else COL_SUB, rect.right - 36, rect.centery, "midright")
        title_id = self.settings.get("title", "")
        title_txt = next((a[1] for a in __import__("stats_manager").ACHIEVEMENTS if a[0] == title_id and title_id in self.stats_mgr.achievements_done()), "")
        if not title_txt:                                       # 고른 업적 칭호가 없으면 레벨 칭호 (Lv.5 이상)
            title_txt = __import__("stats_manager").level_title(lv)
        if title_txt:                                           # 칭호: 이름과 오른쪽 요약 사이의 남는 폭 안에서만 (영어는 요약이 길어 겹치던 문제). 폭이 너무 좁으면 칭호는 생략
            room = sr.left - 12 - (nr.right + 8)
            if room >= 48:
                self._t(self._menu_fit(title_txt, self.font_tiny, min(130, room)), self.font_tiny, C_GOLD, nr.right + 8, rect.centery + 1, "midleft")
        self._t(">", self.font_mid, C_ACCENT if t > 0.5 else COL_HINT, rect.right - 20, rect.centery, "midright")

    # ------------------------------------------------------------------ 화면
    def _render_menu(self):
        self.menu_bg.draw(self.screen)
        self.menu_buttons.clear()
        cx = SCREEN_WIDTH // 2

        def _scrim(surf):                                  # 아래쪽으로 갈수록 어두워지는 막: 떨어지는 배경 블록이 카드/글자 뒤에서 읽기를 방해하지 않게
            h = surf.get_height()
            for yy in range(h):
                pygame.draw.line(surf, (6, 9, 20, int(190 * (yy / h) ** 1.3)), (0, yy), (surf.get_width(), yy))
        self.renderer._blit_overlay(("menu_scrim",), (SCREEN_WIDTH, 440), _scrim, (0, SCREEN_HEIGHT - 440))

        def _scrim_top(surf):                              # 위쪽 메뉴 줄 뒤도 같은 이유로 살짝 어둡게
            h = surf.get_height()
            for yy in range(h):
                pygame.draw.line(surf, (6, 9, 20, int(200 * (1.0 - yy / h) ** 1.5)), (0, yy), (surf.get_width(), yy))
        self.renderer._blit_overlay(("menu_scrim_top",), (SCREEN_WIDTH, 96), _scrim_top, (0, 0))

        # 1. 왼쪽 위 프로필 칩 + 오른쪽 위 유틸리티 (이동 2 + 토글 2)
        self._menu_profile_chip()
        snd_on = self.sound_mgr.enabled
        x = SCREEN_WIDTH - 24
        x = self._menu_pill("toggle_fs", x, 18, "창 모드" if self.is_fullscreen else "전체 화면", "F11", C_ACCENT) - PILL_GAP
        x = self._menu_pill("toggle_sound", x, 18, "소리 켜짐" if snd_on else "소리 꺼짐", "M",
                            C_GREEN if snd_on else C_DANGER, dot=C_GREEN if snd_on else (110, 120, 150)) - PILL_GAP
        x = self._menu_pill("settings", x, 18, "설정", "S", C_ACCENT) - PILL_GAP
        x = self._menu_pill("records", x, 18, "전적", "R", C_GOLD) - PILL_GAP
        wk_done = self.stats_mgr.weekly_best(__import__("config").week_key()) > 0
        x = self._menu_pill("weekly", x, 18, "주간 변형", "W", C_ORANGE, dot=None if wk_done else C_ORANGE) - PILL_GAP
        today = datetime.date.today().strftime("%Y%m%d")
        done = self.stats_mgr.daily_best(today) > 0                                  # 오늘의 도전을 이미 했으면 점 없음, 아직이면 초록 점
        n_star = self.stats_mgr.daily_stars_today(today)
        x = self._menu_pill("daily", x, 18, f"오늘의 도전 ★{n_star}/3" if n_star else "오늘의 도전", "C", C_GREEN, dot=None if (done or n_star) else C_GREEN) - PILL_GAP
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
        diff_short = BOT_DIFFICULTY_LABELS.get(self.bot_difficulty, "혼합").split(" (")[0] + " 봇"      # 어떤 난이도로 시작하는지 카드에서 바로 보이게
        self._menu_card("quick_play", (cx - 320, by, 640, 112), "quick", C_ACCENT, "빠른 시작",
                        (f"봇 {max(0, n - 1)}명과 서바이벌  ·  {n}인 (공격 없음)  ·  {diff_short}" if atk_off else f"봇 {max(0, n - 1)}명과 바로 대전  ·  {n}인 배틀로얄  ·  {diff_short}"),
                        "1", quick_chip, quick_col, True, 0)
        self._menu_card("host_room", (cx - 320, by + 126, 313, 92), "host", C_GREEN, "방 만들기",
                        "친구를 초대해 함께", "2", f"내 IP {self.local_ip}", COL_SUB, False, 1)
        self._menu_card("join_room", (cx + 7, by + 126, 313, 92), "join", C_GOLD, "방 참가하기",
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
        self._t(self._menu_fit(desc, self.font_help, 900), self.font_help, COL_SUB, cx, by + 238, "midtop")
        games_all = self.stats_mgr.data.get("total_games", 0)
        n_prac = len(self.stats_mgr.ch()["practice"]["done"])
        if games_all < 3 and not (n_prac >= 3 and games_all >= 1):              # 처음 몇 판: 입문 순서를 체크리스트로 (연습 기초 과제 3개 -> 첫 경기)
            g = f"처음이라면  {'■' if n_prac >= 3 else '□'} ① 연습 기초 과제 3개 ({min(n_prac, 3)}/3)   {'■' if games_all >= 1 else '□'} ② 첫 경기 끝까지 해 보기"
            self._t(self._menu_fit(g, self.font_help, 900), self.font_help, C_GOLD if n_prac < 3 else COL_HINT, cx, by + 262, "midtop")

        # 5. 하단 바: 버전 · 키 안내 · 게임 종료
        vr = self._t(f"v{APP_VERSION}", self.font_tiny, COL_HINT, 24, SCREEN_HEIGHT - 42, "topleft")
        upd = self.update_info()
        if upd:                                                          # 새 버전 알림: 누르면 릴리스 페이지가 브라우저에서 열림 (자동 설치 없음)
            label = f"새 버전 {upd['tag']} 받기"
            tw = self.font_tiny.size(label)[0]
            ur = pygame.Rect((vr.right if vr is not None else 60) + 12, SCREEN_HEIGHT - 46, tw + 24, 24)
            self.menu_buttons["update"] = ur
            hov = ur.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, _mix((22, 28, 48), C_GOLD, 0.30 if hov else 0.16), ur, border_radius=12)
            pygame.draw.rect(self.screen, C_GOLD, ur, 1, border_radius=12)
            self._t(label, self.font_tiny, C_GOLD, ur.centerx, ur.centery, "center")
            sk = pygame.Rect(ur.right + 8, ur.y, self.font_tiny.size("건너뛰기")[0] + 20, 24)                 # 이 버전 건너뛰기
            self.menu_buttons["update_skip"] = sk
            pygame.draw.rect(self.screen, (60, 70, 100) if sk.collidepoint(pygame.mouse.get_pos()) else (36, 44, 70), sk, 1, border_radius=12)
            self._t("건너뛰기", self.font_tiny, COL_SUB, sk.centerx, sk.centery, "center")
            from update_check import breaks_lan                                                              # 무엇이 바뀌었나 요약 + LAN 경고 (왼쪽 아래 빈 자리)
            ly = SCREEN_HEIGHT - 66
            lines = [(x, COL_HINT) for x in (upd.get("summary") or [])]
            if breaks_lan(upd["tag"]):
                lines.append(("LAN 멀티: 상대도 같은 버전 필요", C_ORANGE))
            for ln, col in lines[-3:][::-1]:
                self._t(self._menu_fit(ln, self.font_tiny, 262), self.font_tiny, col, 24, ly, "bottomleft")           # 가운데 안내 줄(x 300~)과 겹치지 않는 폭
                ly -= 17
        self._keycap_row([("↑↓←→", "이동"), ("Enter", "선택"), ("R", "전적"), ("S", "설정"), ("F1", "규칙"), ("Esc", "종료")],
                         cx, SCREEN_HEIGHT - 42, gap=20, font=self.font_small, label_col=COL_SUB)
        quit_r = pygame.Rect(SCREEN_WIDTH - 24 - 112, SCREEN_HEIGHT - 50, 112, 34)
        self.menu_buttons['quit_game'] = quit_r
        t = self._menu_hl.get('quit_game', 1.0 if fid == 'quit_game' else 0.0)
        pressed = (self._menu_press == 'quit_game')
        pygame.draw.rect(self.screen, _mix((14, 19, 36), (52, 30, 40), t) if not pressed else (60, 34, 46), quit_r, border_radius=10)
        pygame.draw.rect(self.screen, _mix(_mix((50, 62, 94), C_DANGER, 0.2), C_DANGER, t), quit_r, 1, border_radius=10)
        if t > 0.5:
            self._menu_focus_ring(quit_r, C_DANGER, (22, 28, 48), 10)
        self._t("게임 종료", self.font_small, C_TEXT if t > 0.5 else (200, 210, 232), quit_r.centerx, quit_r.centery, "center")
