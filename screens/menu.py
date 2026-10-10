"""
Block Royale 100 - 메인 메뉴 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인.
구성(가운데 한 열): 로고 · 주 카드(빠른 시작) · 함께하기(방 만들기/참가) · 혼자하기(연습/오늘의 도전/주간 변형) · 포커스 한 줄 설명 · 하단 줄(프로필 | 버전 | 전적·설정·소리·전체 화면·종료)
포커스는 키보드/마우스가 하나의 기준(self.menu_focus)을 공유하고, 호버/포커스 강조는 색 보간으로 부드럽게 전환됨(도형만 그림, 프레임마다 Surface 생성 없음)
"""

import datetime
import math
import time

from app_common import (
    APP_VERSION, BOT_DIFFICULTY_LABELS, C_ACCENT, C_DANGER, C_GOLD, C_GREEN, C_ORANGE, C_TEXT,
    LADDER, LADDER_MIN_PLAYERS, LADDER_NAMES, LADDER_RANK,
    CANVAS, NAME_COLORS, SCREEN_HEIGHT, SCREEN_WIDTH, _mix, pygame
)

CARD_BG = (22, 28, 48)
COL_SUB = (160, 172, 205)          # 보조 글자 (배경 대비 충분한 밝기)
COL_HINT = (140, 152, 185)         # 가장 어두운 글자의 하한
UTIL_ROW = ["records", "settings", "toggle_sound", "toggle_fs", "quit_game"]   # 하단 오른쪽 줄 (← →로 이동)
MODE_ROW = ["practice", "daily", "weekly"]                                    # 혼자하기 줄 (← →로 이동)
LAYOUT_ROWS = [["quick_play"], ["host_room", "join_room"], ["practice", "daily", "weekly"],
               ["match_summary", "records", "settings", "toggle_sound", "toggle_fs", "quit_game"]]      # 화면 배치대로의 줄 (↑↓는 줄 단위로 이동)

CAPTIONS = {                       # 포커스된 항목의 한 줄 설명 (상태 값이 있으면 그쪽이 우선)
    "quick_play": "봇과 바로 대전합니다",
    "host_room": "방을 열고 친구를 초대합니다. 빈 자리는 봇이 채웁니다",
    "join_room": "LAN에서 방을 찾거나 IP로 직접 접속합니다",
    "practice": "혼자 자유롭게 연습합니다. 전적에는 남지 않아요",
    "daily": "하루 한 번, 모두 같은 블록 순서로 순위를 겨룹니다",
    "weekly": "매주 규칙 하나가 바뀐 경기로 겨룹니다",
    "match_summary": "이름 · 인원 · 봇 난이도 설정",
    "records": "지난 경기 기록과 통계를 봅니다.",
    "settings": "화면, 소리, 조작키, 게임 설정을 바꿉니다.",
    "quit_game": "게임 종료",
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


    MENU_FOCUS_ORDER = ["quick_play", "host_room", "join_room", "practice", "daily", "weekly",
                        "match_summary", "records", "settings", "toggle_sound", "toggle_fs", "quit_game"]

    # ------------------------------------------------------------------ 상태 갱신
    def _menu_visible_ids(self):
        """실제로 화면에 그려지는 항목 id (Proton에서는 전체 화면 버튼이 없음: 보이지 않는 항목에 포커스가 멈추지 않게)"""
        from app_paths import running_under_wine
        return [b for b in self.MENU_FOCUS_ORDER if not (b == "toggle_fs" and running_under_wine())]

    def _menu_move_vertical(self, step):
        """↑↓: 화면 배치대로 한 줄 위/아래로 (같은 가로 위치에 가장 가까운 항목, 비슷하면 왼쪽). 위치를 모르면 목록 순서대로"""
        vis = set(self._menu_visible_ids())
        rows = [[b for b in row if b in vis] for row in LAYOUT_ROWS]
        rows = [r for r in rows if r]
        fid = self._menu_focus_id()
        cur = next((i for i, r in enumerate(rows) if fid in r), None)
        rect = self.menu_buttons.get(fid)
        if cur is None or rect is None:
            self._menu_step_focus(step)
            return
        target = rows[(cur + step) % len(rows)]
        cands = [(round(abs(self.menu_buttons[b].centerx - rect.centerx) / 40), i, b) for i, b in enumerate(target) if b in self.menu_buttons]
        if not cands:
            self._menu_step_focus(step)
            return
        self.menu_focus = self.MENU_FOCUS_ORDER.index(min(cands)[2])

    def _menu_step_focus(self, step):
        vis = self._menu_visible_ids()
        cur = self._menu_focus_id()
        i = vis.index(cur) if cur in vis else 0
        self.menu_focus = self.MENU_FOCUS_ORDER.index(vis[(i + step) % len(vis)])

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
        self.renderer.release_scene_caches()               # 메뉴로 돌아오면 우승 광선/박자 변형 같은 전체 화면 캐시를 비움
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

    def _menu_cycle_difficulty(self):
        self.sound_mgr.play('rotate')
        self.settings.cycle_bot_difficulty(1)
        self.bot_difficulty = self.settings.get("bot_difficulty")
        self._menu_flash = time.time()

    def _menu_activate(self, btn_id):
        """메인 메뉴 항목 실행 (키보드/마우스 공용)"""
        if btn_id == "toggle_sound":
            self.toggle_mute()
            return
        if btn_id in ("qp_minus", "qp_plus"):                # 빠른 시작 카드 안의 ‹ › : 인원 -1/+1 (게임을 시작하지 않음)
            self._menu_adjust_players(-1 if btn_id == "qp_minus" else 1)
            return
        if btn_id == "qp_diff":                              # 빠른 시작 카드의 인원 · 난이도 글자: 봇 난이도 순환
            self._menu_cycle_difficulty()
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
            elif k == pygame.K_UP:
                self._menu_move_vertical(-1)
                self.sound_mgr.play('move')
            elif k == pygame.K_DOWN:
                self._menu_move_vertical(1)
                self.sound_mgr.play('move')
            elif k == pygame.K_TAB and shift:
                self._menu_step_focus(-1)
                self.sound_mgr.play('move')
            elif k == pygame.K_TAB:
                self._menu_step_focus(1)
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
                elif fid in UTIL_ROW or fid in MODE_ROW:
                    row = [b for b in (UTIL_ROW if fid in UTIL_ROW else MODE_ROW) if b in self._menu_visible_ids()]
                    self._set_menu_focus(row[(row.index(fid) + step) % len(row)])
            elif k == pygame.K_d:
                self._menu_cycle_difficulty()
        elif event.type == pygame.MOUSEMOTION:
            self._menu_mouse = event.pos                       # 빠른 시작 카드의 설정 단추 호버 표시용
            if getattr(event, "rel", (1, 1)) == (0, 0):
                return                                         # 창 포커스 복귀/화면 전환 때 생기는 '움직이지 않은' 이벤트로 포커스가 바뀌지 않게
            self._menu_kb = False
            for bid in self.MENU_FOCUS_ORDER:
                rect = self.menu_buttons.get(bid)
                if rect and rect.collidepoint(event.pos):
                    self._set_menu_focus(bid, sound=False)
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._menu_kb = False
            self._menu_press = None
            for bid, rect in sorted(self.menu_buttons.items(), key=lambda kv: 0 if kv[0].startswith("qp_") else 1):      # 카드 안의 작은 버튼이 카드보다 먼저
                if rect.collidepoint(event.pos):
                    self._menu_press = bid                    # 누른 순간은 눌림 표시만, 같은 버튼 위에서 뗄 때 실행
                    if bid in self.MENU_FOCUS_ORDER:
                        self._set_menu_focus(bid, sound=False)
                    break
        elif event.type == pygame.MOUSEWHEEL:
            r = self.menu_buttons.get("quick_play")
            if r is not None and r.collidepoint(pygame.mouse.get_pos()) and getattr(event, "y", 0):
                self._set_menu_focus("quick_play", sound=False)
                self._menu_adjust_players(1 if event.y > 0 else -1)          # 빠른 시작 카드 위에서 휠: 인원 조절
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

    # ------------------------------------------------------------------ 가운데 한 열 (v1.4.27 메인 화면: 로고 → 빠른 시작 → 함께하기/혼자하기 → 한 줄 설명 → 하단 줄)
    COL_X, COL_W = 313, 740                        # 가운데 열 (논리 좌표 1366x768): 로고와 비슷한 폭
    BAR_Y, BAR_H = 708, 36                         # 하단 줄 (프로필 · 전적/설정/소리/전체 화면/종료)
    MENU_KEYS = {"quick_play": "1", "host_room": "2", "join_room": "3", "practice": "P", "daily": "C", "weekly": "W"}

    def _menu_bg_fx(self):
        """메인 화면 배경의 빛 연출 설정을 반영 (visual_fx / 화면 흔들림 / 번쩍임 / 메뉴 BGM 박자 / 마우스 위치)"""
        from app_common import SHAKE_SCALE
        from ui_glow import FX_NAMES
        mode = FX_NAMES.get(self.settings.get("visual_fx", "normal"), 1)
        motion = SHAKE_SCALE.get(self.settings.get("screen_shake"), 1.0) > 0
        flash_ok = bool(self.settings.get("screen_flash", True))
        beat = self.sound_mgr.beat_phase() if mode else None
        mouse = CANVAS.to_logical(pygame.mouse.get_pos()) if (mode and motion and not self.renderer.pad_ui) else None
        self.menu_bg.set_fx(mode, motion, flash_ok, beat, mouse)

    def _menu_hl_t(self, bid):
        return self._menu_hl.get(bid, 1.0 if self._menu_focus_id() == bid else 0.0)

    def _menu_glyph(self, kind, x, y, accent, cs):
        """카드 왼쪽 그림: 블록 셀(캐시된 셀 그림)과 선으로만 그림. (x, y)는 그림 영역 왼쪽 위, cs는 셀 크기"""
        r = self.renderer
        cell = lambda cx_, cy_, ch: r._draw_cell(x + cx_ * cs, y + cy_ * cs, cs, ch)
        dim = _mix(accent, CARD_BG, 0.45)
        if kind == "quick":                                # 쌓인 블록 위로 떨어지는 T
            for cx_, cy_, ch in ((0, 3, 'L'), (1, 3, 'L'), (2, 3, 'J'), (3, 3, 'J'), (0, 2, 'L'), (3, 2, 'J'),
                                 (1, 0, 'T'), (0, 1, 'T'), (1, 1, 'T'), (2, 1, 'T')):
                cell(cx_, cy_, ch)
        elif kind == "host":                               # O 블록 + 퍼져 나가는 신호
            for dx, dy in ((0, 1), (1, 1), (0, 2), (1, 2)):
                cell(dx, dy, 'O')
            for rad in (int(cs * 0.6), int(cs * 1.05)):
                pygame.draw.circle(self.screen, accent if rad < cs else dim, (x + cs * 3, y + cs // 2 + 2), rad, 2)
        elif kind == "join":                               # L 블록 + 접속 화살표
            for dx, dy in ((0, 1), (0, 2), (1, 2), (2, 2)):
                cell(dx, dy, 'L')
            ay, ax = y + cs // 2, x + 2
            pygame.draw.line(self.screen, accent, (ax, ay), (ax + cs * 3, ay), 3)
            pygame.draw.lines(self.screen, accent, False, [(ax + cs * 3 - 7, ay - 6), (ax + cs * 3, ay), (ax + cs * 3 - 7, ay + 6)], 3)
        elif kind == "practice":                           # S 블록 + 아래 고스트(떨어질 자리) 윤곽
            for dx, dy in ((1, 0), (2, 0), (0, 1), (1, 1)):
                cell(dx, dy, 'S')
            for dx, dy in ((1, 2), (2, 2), (0, 3), (1, 3)):
                pygame.draw.rect(self.screen, dim, (x + dx * cs + 1, y + dy * cs + 1, cs - 2, cs - 2), 1, border_radius=2)
        elif kind == "daily":                              # 달력: 머리띠 + 날짜 칸, 오늘 칸만 블록
            w_, h_ = cs * 3 + 6, cs * 3 + 4
            pygame.draw.rect(self.screen, dim, (x, y + 2, w_, h_), 2, border_radius=4)
            pygame.draw.rect(self.screen, accent, (x + 2, y + 4, w_ - 4, 5), border_radius=2)
            for i in range(6):
                gx, gy = x + 4 + (i % 3) * cs, y + 12 + (i // 3) * cs
                if i == 4:
                    r._draw_cell(gx, gy, cs - 2, 'O')
                else:
                    pygame.draw.rect(self.screen, _mix(CARD_BG, accent, 0.25), (gx + 2, gy + 2, cs - 6, cs - 6), border_radius=2)
        else:                                              # 주간 변형: Z 블록 + 돌아가는 화살표 (규칙이 바뀜)
            for dx, dy in ((0, 1), (1, 1), (1, 2), (2, 2)):
                cell(dx, dy, 'Z')
            ccx, ccy, rad = x + cs * 3, y + cs // 2 + 1, cs * 0.75
            pts = [(ccx + rad * math.cos(a), ccy + rad * math.sin(a)) for a in [math.radians(d) for d in range(-200, 70, 30)]]
            pygame.draw.lines(self.screen, accent, False, pts, 2)
            ex, ey = pts[-1]
            pygame.draw.lines(self.screen, accent, False, [(ex - 6, ey - 1), (ex, ey), (ex + 1, ey - 6)], 2)

    def _menu_card(self, bid, rect, kind, accent, title, status, status_col, index, hero=False):
        """메뉴 카드 (글자 층은 그림 + 제목 + 상태 한 줄까지): 평평한 면 + 1px 테두리, 포커스는 왼쪽 강조선·면 밝기·테두리 색으로만"""
        from i18n import tr
        rect = pygame.Rect(rect)
        self.menu_buttons[bid] = rect                       # 클릭 영역은 처음부터 최종 위치
        t = self._menu_hl_t(bid)
        pressed = (self._menu_press == bid)
        dr = rect.move(0, self._menu_slide(index) + (1 if pressed else 0))
        bg = _mix(CARD_BG, accent, (0.07 if hero else 0.02) + 0.09 * t + (0.04 if pressed else 0.0))
        edge = _mix(_mix((50, 62, 94), accent, 0.35 if hero else 0.0), accent, 0.9 * t)
        pygame.draw.rect(self.screen, bg, dr, border_radius=12 if hero else 10)
        pygame.draw.rect(self.screen, edge, dr, 1, border_radius=12 if hero else 10)
        if t > 0.05:                                         # 포커스: 왼쪽 강조선 (위아래로 자라남)
            hh = int((dr.h - 28) * min(1.0, t))
            pygame.draw.rect(self.screen, accent, (dr.x + 1, dr.centery - hh // 2, 3, hh), border_radius=2)
        cs = 16 if hero else 11
        gh = cs * 4 if kind in ("quick", "practice") else cs * 3 + 2
        gx = dr.x + (30 if hero else 18)
        self._menu_glyph(kind, gx, dr.centery - gh // 2, accent, cs)
        tx = gx + (cs * 4 + 26 if hero else cs * 4 + 12)
        room = dr.right - 12 - tx
        tw = self.font_menu.size(tr(title))[0]
        font = self.font_menu if tw <= room - 26 or hero else self.font_mid      # 영어 긴 이름은 한 단계 작은 글꼴 (자르지 않음)
        key = self.MENU_KEYS.get(bid)
        if key and not self.renderer.pad_ui and (hero or font.size(tr(title))[0] <= room - 26):    # 번호 키: 오른쪽 위 모서리에 작게 (패드 UI이거나 제목과 닿으면 숨김)
            kr = pygame.Rect(dr.right - 10 - 20, dr.y + 9, 20, 18)
            pygame.draw.rect(self.screen, _mix(edge, bg, 0.3), kr, 1, border_radius=5)
            self._t(key, self.font_tiny, _mix(COL_HINT, C_TEXT, t), kr.centerx, kr.centery, "center")
        if hero:
            pcx, pcy = dr.right - 62, dr.centery + 4                  # 오른쪽 재생 단추: 동그라미 + 채운 삼각형 (polygon 대신 가로줄로 채움)
            pygame.draw.circle(self.screen, _mix(bg, accent, 0.18 + 0.82 * t), (pcx, pcy), 22)
            tri = _mix(accent, C_TEXT, 0.4) if t < 0.5 else (12, 18, 34)
            for i in range(17):
                pygame.draw.line(self.screen, tri, (pcx - 5, pcy - 8 + i), (pcx - 5 + int(15 * (1 - abs(i - 8) / 8)), pcy - 8 + i), 2)
            self._t(title, self.font_hero, C_TEXT, tx, dr.y + 20)
            self._t(status, self.font_small, _mix(COL_SUB, C_TEXT, t), tx + 2, dr.y + 64, "midleft")          # 게임 방식(배틀로얄/서바이벌)만 제목 아래에
            self._menu_quick_chips(dr, pcx - 22 - 18, accent, bg, t)
            return
        self._t(title, font, C_TEXT, tx, dr.y + 12)
        if status:                                           # 상태 한 줄 (글자가 길면 한 단계 작은 글꼴, 그래도 모자라면 숨김)
            sf = next((f for f in (self.font_small, self.font_tiny) if f.size(tr(status))[0] <= room - 12), None)
            if sf:
                cy = dr.bottom - 17
                pygame.draw.circle(self.screen, status_col, (tx + 3, cy), 3)
                self._t(status, sf, status_col, tx + 12, cy, "midleft")

    def _menu_quick_chips(self, dr, right, accent, card_bg, t):
        """빠른 시작 카드 오른쪽의 설정 단추 두 개 (전에는 제목 아래 작은 글씨 한 줄): 인원 [‹ 50명 ›] · 봇 난이도 [쉬움].
        큰 글꼴과 넉넉한 누름 영역. ‹ › 는 인원 -1/+1, 난이도 단추는 누를 때마다 순환 (D 키와 같음). 카드 위 휠도 인원 조절"""
        from i18n import tr
        flash = (time.time() - self._menu_flash) < 0.35
        diff = tr(BOT_DIFFICULTY_LABELS.get(self.bot_difficulty, "혼합").split(" (")[0])
        n_txt = tr(f"{self.target_player_count}명")
        ch = 46
        cy = dr.centery + 2
        mp = getattr(self, "_menu_mouse", (-999, -999))
        chip_bg = _mix(card_bg, (8, 12, 26), 0.45)

        def chip(rect, bid):
            self.menu_buttons[bid] = rect
            hov = rect.collidepoint(mp)
            pressed = self._menu_press == bid
            fill = _mix(chip_bg, accent, 0.22 if pressed else (0.12 if hov else 0.0))
            pygame.draw.rect(self.screen, fill, rect, border_radius=10)
            pygame.draw.rect(self.screen, _mix((62, 76, 112), accent, 0.85 if hov else 0.0), rect, 1, border_radius=10)
            return hov

        dw = max(100, self.font_menu.size(diff)[0] + 36)
        dr_ = pygame.Rect(right - dw, cy - ch // 2, dw, ch)
        hov = chip(dr_, "qp_diff")
        self._t(diff, self.font_menu, C_TEXT if hov else _mix(COL_SUB, C_TEXT, 0.8), dr_.centerx, dr_.centery, "center")
        pw = max(172, self.font_menu.size(n_txt)[0] + 2 * 44 + 12)
        pr = pygame.Rect(dr_.x - 12 - pw, cy - ch // 2, pw, ch)
        pygame.draw.rect(self.screen, chip_bg, pr, border_radius=10)
        pygame.draw.rect(self.screen, (62, 76, 112), pr, 1, border_radius=10)
        for bid, side in (("qp_minus", -1), ("qp_plus", 1)):
            br = pygame.Rect(pr.x if side < 0 else pr.right - 44, pr.y, 44, ch)
            self.menu_buttons[bid] = br
            hov_b = br.collidepoint(mp)
            if hov_b or self._menu_press == bid:
                pygame.draw.rect(self.screen, _mix(chip_bg, accent, 0.28 if self._menu_press == bid else 0.16), br.inflate(-4, -4), border_radius=8)
            ax = br.centerx + (-2 if side < 0 else 2)
            ac = C_TEXT if hov_b else _mix(COL_HINT, accent, 0.6)
            pygame.draw.lines(self.screen, ac, False, [(ax + 5 * -side, pr.centery - 9), (ax - 5 * -side, pr.centery), (ax + 5 * -side, pr.centery + 9)], 3)
        self._t(n_txt, self.font_menu, C_GOLD if flash else C_TEXT, pr.centerx, pr.centery, "center")

    def _menu_ghost(self, bid, rect, accent=C_ACCENT):
        """하단 줄 버튼: 평소에는 테두리 없이 글자/아이콘만, 포커스·호버일 때만 면이 드러남"""
        rect = pygame.Rect(rect)
        self.menu_buttons[bid] = rect
        t = self._menu_hl_t(bid)
        pressed = (self._menu_press == bid)
        if t > 0.03 or pressed:
            pygame.draw.rect(self.screen, _mix((10, 14, 28), _mix((26, 34, 60), accent, 0.12), 1.0 if pressed else t), rect, border_radius=9)
            pygame.draw.rect(self.screen, _mix((10, 14, 28), accent, 0.75 * t), rect, 1, border_radius=9)
        return t, _mix((170, 182, 212), C_TEXT, 1.0 if pressed else t)

    def _menu_text_btn(self, bid, right, label, accent=C_ACCENT):
        """하단 줄 글자 버튼: 오른쪽 끝 기준, 왼쪽 끝 x를 반환"""
        from i18n import tr
        w = self.font_small.size(tr(label))[0] + 28
        rect = pygame.Rect(right - w, self.BAR_Y, w, self.BAR_H)
        _t, col = self._menu_ghost(bid, rect, accent)
        self._t(label, self.font_small, col, rect.centerx, rect.centery, "center")
        return rect.x

    def _menu_icon(self, bid, right, kind):
        """글자 없는 아이콘 버튼 (소리 / 전체 화면): 이름은 포커스 시 설명 줄에 나옴"""
        rect = pygame.Rect(right - self.BAR_H, self.BAR_Y, self.BAR_H, self.BAR_H)
        _t, col = self._menu_ghost(bid, rect)
        cx_, cy_ = rect.center
        if kind == "sound":
            on = self.sound_mgr.enabled
            c = col if on else (120, 128, 150)
            cx_ -= 3
            pygame.draw.lines(self.screen, c, True, [(cx_ - 8, cy_ - 3), (cx_ - 4, cy_ - 3), (cx_ + 1, cy_ - 8), (cx_ + 1, cy_ + 8), (cx_ - 4, cy_ + 3), (cx_ - 8, cy_ + 3)], 2)
            if on:
                for rad in (5, 9):                                         # 소리 물결 2줄 (호 대신 짧은 꺾은선)
                    pts = [(cx_ + 3 + rad * math.cos(a), cy_ + rad * math.sin(a)) for a in (-0.9, -0.45, 0.0, 0.45, 0.9)]
                    pygame.draw.lines(self.screen, c, False, pts, 2)
            else:
                pygame.draw.line(self.screen, C_DANGER, (cx_ + 5, cy_ - 4), (cx_ + 12, cy_ + 4), 2)
                pygame.draw.line(self.screen, C_DANGER, (cx_ + 12, cy_ - 4), (cx_ + 5, cy_ + 4), 2)
        else:
            s = 7
            for sx_, sy_ in ((-1, -1), (1, -1), (-1, 1), (1, 1)):          # 모서리 꺾쇠 4개
                px, py = cx_ + sx_ * s, cy_ + sy_ * s
                pygame.draw.line(self.screen, col, (px, py), (px - sx_ * 5, py), 2)
                pygame.draw.line(self.screen, col, (px, py), (px, py - sy_ * 5), 2)
        return rect.x

    def _menu_profile(self):
        """하단 왼쪽 프로필 (한 곳에만): 레벨 배지 + 이름. 누르면 경기 설정"""
        lv_txt = f"Lv.{self.stats_mgr.level()[0]}"
        name = self.player_name
        while len(name) > 1 and self.font_mid.size(name)[0] > 200:          # 아주 긴 이름은 글자를 줄임 (말줄임표 없이)
            name = name[:-1]
        bw = self.font_tiny.size(lv_txt)[0] + 14
        rect = pygame.Rect(24, self.BAR_Y, 12 + bw + 10 + self.font_mid.size(name)[0] + 16, self.BAR_H)
        _t, col = self._menu_ghost("match_summary", rect)
        badge = pygame.Rect(rect.x + 12, rect.centery - 10, bw, 20)
        ncol = NAME_COLORS[self.name_color][1]
        pygame.draw.rect(self.screen, _mix(CARD_BG, ncol, 0.25), badge, border_radius=6)
        self._t(lv_txt, self.font_tiny, ncol, badge.centerx, badge.centery, "center")
        self._t(name, self.font_mid, col, badge.right + 10, rect.centery, "midleft")

    def _render_menu(self):
        self._menu_bg_fx()                                 # 메인 화면만 빛 연출(박자 맞춤/시차/빛 띠/로고 후광)을 켬
        self.menu_bg.draw(self.screen)
        self.menu_buttons.clear()
        cx = SCREEN_WIDTH // 2
        from i18n import tr as _tr

        def _scrim(surf):                                  # 아래쪽으로 갈수록 어두워지는 막: 떨어지는 배경 블록이 카드/글자 뒤에서 읽기를 방해하지 않게
            h = surf.get_height()
            for yy in range(h):
                pygame.draw.line(surf, (6, 9, 20, int(190 * (yy / h) ** 1.3)), (0, yy), (surf.get_width(), yy))
        self.renderer._blit_overlay(("menu_scrim",), (SCREEN_WIDTH, 440), _scrim, (0, SCREEN_HEIGHT - 440))

        # 1. 로고
        logo_top = 64                                      # 로고가 화면 맨 위에 붙어 불안해 보이지 않게 위쪽 여백을 둠 (아래쪽 여백과 비슷하게)
        logo_h = self.logo.draw(self.screen, cx, logo_top)
        y0 = min(logo_top + logo_h + 18, 386)

        # 2. 상태 값 (이미 있는 데이터만)
        n = self.target_player_count
        atk_off = self.settings.get("game_mode") == "survival"
        diff = BOT_DIFFICULTY_LABELS.get(self.bot_difficulty, "혼합").split(" (")[0]
        summary = _tr("서바이벌" if atk_off else "배틀로얄")                  # 인원/난이도는 카드 오른쪽 단추로 옮김 (_menu_quick_chips)
        wk_best = self.stats_mgr.weekly_best(__import__("config").week_key())
        today = datetime.date.today().strftime("%Y%m%d")
        day_best = self.stats_mgr.daily_best(today)
        n_star = self.stats_mgr.daily_stars_today(today)
        rooms = len(self.net_mgr.discovered_rooms)
        n_prac = len(self.stats_mgr.ch()["practice"]["done"])

        # 3. 주 행동 + 카테고리 두 묶음 (함께하기 2장 · 혼자하기 3장, 카드 칸은 같은 폭/끝선)
        x0, w = self.COL_X, self.COL_W
        self._menu_card("quick_play", (x0, y0, w, 88), "quick", C_ACCENT, "빠른 시작", summary, COL_SUB, 0, hero=True)
        gap, ch_, head = 12, 72, 0                 # 카테고리 틀/이름 없이 카드만 두 줄 (함께하기 2장 · 혼자하기 3장)
        fh = ch_
        ix, iw = x0, w
        y1 = y0 + 88 + 12
        cw2 = (iw - gap) // 2
        self._menu_card("host_room", (ix, y1 + head, cw2, ch_), "host", C_GREEN, "방 만들기", f"내 IP {self.local_ip}", COL_SUB, 1)
        self._menu_card("join_room", (ix + cw2 + gap, y1 + head, iw - cw2 - gap, ch_), "join", C_GOLD, "방 참가하기",
                        f"LAN 방 {rooms}개 발견" if rooms else "IP 직접 접속도 가능", C_GOLD if rooms else COL_SUB, 2)
        y2 = y1 + fh + 12
        cw3 = (iw - 2 * gap) // 3
        self._menu_card("practice", (ix, y2 + head, cw3, ch_), "practice", C_ACCENT, "연습",
                        f"완료한 과제 {n_prac}개" if n_prac else "전적에 남지 않음", COL_SUB, 3)
        self._menu_card("daily", (ix + cw3 + gap, y2 + head, cw3, ch_), "daily", C_GREEN, "오늘의 도전",
                        f"★{n_star}/3 · 최고 {day_best}위" if day_best else "오늘 아직 안 함", COL_SUB if day_best else C_GREEN, 4)
        self._menu_card("weekly", (ix + 2 * (cw3 + gap), y2 + head, iw - 2 * (cw3 + gap), ch_), "weekly", C_ORANGE, "주간 변형",
                        f"이번 주 최고 {wk_best}위" if wk_best else "이번 주 아직 안 함", COL_SUB if wk_best else C_ORANGE, 5)

        # 4. 한 줄 설명: 포커스된 항목 하나만 (실시간 상태는 카드 안에 있음)
        fid = self._menu_focus_id()
        cap, ccol = CAPTIONS.get(fid, ""), COL_SUB
        if fid == "quick_play":
            nxt = None if atk_off else next((d for d in LADDER if d not in self.stats_mgr.ladder_cleared()), None)
            ob = self.stats_mgr.onboarding_next()
            if ob is not None:                                       # 입문 미션: 처음 하는 사람이 다음에 할 일 한 가지를 순서대로
                cap, ccol = f"입문 미션 {ob[0]}/{ob[1]} · {ob[2]}", C_GREEN
            elif nxt:                                                # 보이지 않던 보상(난이도 사다리 ★)을 알려 줌
                cap, ccol = f"★ 다음 도전: {LADDER_NAMES[nxt]} 봇 {LADDER_MIN_PLAYERS}인↑에서 {LADDER_RANK}위 안", C_GOLD
        elif fid == "toggle_sound":
            cap = "소리 켜짐" if self.sound_mgr.enabled else "소리 꺼짐"
        elif fid == "toggle_fs":
            cap = "창 모드" if self.is_fullscreen else "전체 화면"
        if fid in self.MENU_FOCUS_ORDER[:6]:                 # 가운데 열 항목: 열 바로 아래 가운데
            y = y2 + fh + 24
            for line in self._wrap_text(cap, self.font_help, w)[:2]:
                self._t(line, self.font_help, ccol, cx, y, "midtop")
                y += 20
            if fid == "quick_play":                              # 인원 · 난이도를 바꾸는 방법 (D 키는 전에는 화면 어디에도 안내가 없었음)
                self._t("← → 인원  ·  D 난이도  ·  클릭/휠도 가능" if not self.renderer.pad_ui else "← → 인원", self.font_tiny, COL_HINT, cx, y + 2, "midtop")

        # 5. 하단 줄: 왼쪽 프로필, 가운데 버전, 오른쪽 전적 · 설정 · 소리 · 전체 화면 · 게임 종료
        self._menu_profile()
        if self.renderer.pad_ui:
            self._t(f"v{APP_VERSION}", self.font_tiny, COL_HINT, cx, self.BAR_Y + self.BAR_H // 2, "center")
        else:                                              # 규칙 카드(F1) 안내: 새로 시작한 사람이 키를 알 수 있게 하단 가운데에 한 쌍만 (패드에는 F1 버튼이 없어 숨김)
            self._keycap_row([("F1", "규칙")], cx - 34, self.BAR_Y + self.BAR_H // 2 - 10, gap=0, font=self.font_tiny, label_col=COL_HINT)
            self._t(f"v{APP_VERSION}", self.font_tiny, COL_HINT, cx + 40, self.BAR_Y + self.BAR_H // 2 - 1, "midleft")
        from app_paths import running_under_wine
        x = self._menu_text_btn("quit_game", SCREEN_WIDTH - 24, "게임 종료", C_DANGER) - 14
        if not running_under_wine():                       # Proton에서는 전체 화면 전환이 없음 (입력이 막힘)
            x = self._menu_icon("toggle_fs", x, "fs") - 4
        x = self._menu_icon("toggle_sound", x, "sound") - 4
        x = self._menu_text_btn("settings", x, "설정 (Start)" if self.renderer.pad_ui else "설정") - 4
        self._menu_text_btn("records", x, "전적", C_GOLD)
        r = self.menu_buttons.get(fid)
        if r and fid not in self.MENU_FOCUS_ORDER[:6] and fid != "quit_game":      # 하단 줄 항목: 그 버튼 바로 위에 작게 (화면 밖으로 나가지 않게)
            tw = self.font_help.size(_tr(cap))[0]
            tx = max(24 + tw // 2, min(SCREEN_WIDTH - 24 - tw // 2, r.centerx))
            self._t(cap, self.font_help, COL_SUB, tx, r.y - 10, "midbottom")
