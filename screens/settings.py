"""
Block Royale 100 - 설정 화면 (게임 / 화면 / 소리 / 조작 탭)
BlockRoyaleApp(main.py)이 상속하는 믹스인. 모든 탭이 같은 '행' 구조(왼쪽 라벨 · 오른쪽 컨트롤)와 하단 도움말 바를 쓰고,
키보드 탐색은 TAB_NAV 표 하나로 정의됨 (마우스 hit rect는 settings_buttons에 id로 등록)
"""

from app_common import (
    ACTION_NAMES,
    BGM_STAGE_SET_DESCS,
    BGM_STAGE_SET_LABELS,
    BLOCK_SKIN_DESCS,
    BLOCK_SKIN_LABELS,
    SHAKE_LABELS,
    BOT_DIFFICULTY_DESCS,
    BOT_DIFFICULTY_LABELS,
    CANVAS,
    C_ACCENT,
    C_DANGER,
    C_GOLD,
    C_GREEN,
    C_ORANGE,
    C_TEXT,
    NAME_COLORS,
    _mix,
    pygame,
    short_key_name,
    time
)

# ---- 레이아웃 (논리 좌표 1366x768 기준)
PX, PY, PW, PH = 223, 116, 920, 584          # 패널 (아래끝 700: 게임 중 하단 키 안내와 겹치지 않음)
IX, IW = PX + 28, PW - 56                     # 콘텐츠 왼쪽 x / 폭 (864)
RIGHT = IX + IW - 20                          # 컨트롤 오른쪽 끝
TOP = 198                                     # 콘텐츠 시작 y

# ---- 글자/색 위계: 라벨 17 > 값 15 > 도움말 14 > 섹션 13
COL_TEXT = (235, 240, 252)
COL_SUB = (168, 182, 212)                     # 보조 글자 (배경 대비 약 9:1)
COL_OFF = (92, 102, 128)                      # 비활성
COL_SEC = (120, 190, 235)                     # 섹션 제목
COL_ROW_HOVER = (22, 29, 50)
COL_ROW_FOCUS = (26, 38, 68)
COL_CTL_BG = (12, 15, 27)
COL_CTL_EDGE = (60, 74, 110)

TABS = [("match", "tab_match", "게임", C_GREEN), ("general", "tab_general", "화면", C_ACCENT),
        ("audio", "tab_audio", "소리", C_ORANGE), ("keys", "tab_keys", "조작", C_GOLD)]
TAB_ORDER = [t[0] for t in TABS]

# 키보드 탐색표: 탭 -> [(행 키, Enter, ←, →)]. 행 키는 화면에 그려지는 행과 도움말/포커스 표시에 쓰임
TAB_NAV = {
    "match": [("players", None, "dec_1", "inc_1"), ("diff", None, "diff_prev", "diff_next"),
              ("attack", "attack_toggle", "attack=on", "attack=off"),
              ("name", "name_edit", None, None), ("color", None, "color_prev", "color_next"),
              ("shake", None, "shake_prev", "shake_next")],
    "general": [("fs", "toggle_fs", "fs=window", "fs=full"), ("res", "res_next", "res_prev", "res_next"),
                ("mini", "mini_detail", "mini_detail=detailed", "mini_detail=simple"),
                ("block_skin", None, "skin_prev", "skin_next"),
                ("color_mode", "color_mode", "color_mode=normal", "color_mode=colorblind"),
                ("text_size", "text_size", "text_size=normal", "text_size=large")],
    "audio": [("bgm", "bgm_toggle", "bgm_dec", "bgm_inc"), ("stage_bgm", None, "stage_bgm_prev", "stage_bgm_next"),
              ("sfx", "sfx_toggle", "sfx_dec", "sfx_inc"), ("sfx_test", "sfx_test", None, None)],
}
KEY_CARDS = len(ACTION_NAMES)                 # 조작 탭: 0~8 = 키 카드, 9~11 = DAS/ARR/SDF, 12 = 프리셋
HANDLING_ROWS = ("das", "arr", "sdf")
PRESET_FOCUS = KEY_CARDS + 3

HELP = {
    "players": "한 판에 참가하는 총 인원입니다. 부족한 인원은 AI 봇이 채웁니다. 방 만들기에서는 방장이 정한 인원으로 시작합니다.",
    "attack": "배틀로얄: 줄을 지워 상대에게 쓰레기 줄을 보내 서로 공격하는 모드 · 서바이벌: 서로 공격하지 않고 각자 끝까지 버티는 모드(K.O.·배지 없음, 3분 뒤부터 쓰레기 줄이 주기적으로 올라옴). 방을 열면 호스트의 설정이 모두에게 적용됩니다.",
    "name": "채팅, 대기실 명단, 미니 보드에 표시되는 이름입니다. 클릭하거나 Enter로 수정 (최대 16자).",
    "color": "이름 색: 채팅과 대기실 명단, 미니 보드의 내 이름에 쓰입니다.",
    "shake": "공격을 받거나 K.O.가 났을 때 화면이 흔들리는 정도입니다. 멀미가 나면 '약하게'나 '끔'을 고르세요.",
    "fs": "창 모드와 전체 화면을 바꿉니다. F11 키로 언제든 전환할 수 있습니다.",
    "res": "창 크기를 고릅니다. 모니터에 들어가는 크기만 보이며 창 가장자리를 끌어서도 조절할 수 있습니다.",
    "res_off": "전체 화면에서는 모니터 해상도에 맞춰 자동으로 확대됩니다.",
    "mini": "자세히: 조작 중인 블록, 착지 위치, 홀드/다음 블록까지 표시 · 간략: 쌓인 블록만 표시해 더 깔끔하고 가볍습니다.",
    "color_mode": "색약 보정은 블록 색을 밝기 차이가 큰 팔레트로 바꿉니다.",
    "text_size": "게임 화면의 작은 글씨를 키웁니다. (메뉴 글자는 그대로입니다)",
    "block_skin": "게임 화면 블록의 모양을 바꿉니다. 색은 위의 '블록 색상' 설정을 따르며, 로고와 미니 보드는 그대로입니다.",
    "bgm": "배경음악 켜기/끄기와 음량. 생존자가 줄수록(100인 → 50인 → 20인) 곡이 더 긴박해집니다.",
    "stage_bgm": "경기 중(1/2/3단계) 배경음 세트를 고릅니다. '랜덤'이면 경기를 시작할 때마다 5가지 중 하나가 무작위로 재생됩니다.",
    "sfx": "효과음 켜기/끄기와 음량. 음량을 바꾸면 바로 들어볼 수 있습니다.",
    "sfx_test": "현재 효과음 음량으로 대표 소리를 들어봅니다.",
    "preset": "조작키 묶음을 한 번에 바꿉니다. 아래 카드를 하나라도 바꾸면 '사용자 지정'이 됩니다.",
    "cards": "카드를 클릭하거나 Enter를 누른 뒤 새 키를 누르세요. 다른 동작이 쓰던 키면 자동으로 옮겨집니다. 고정 키: ESC 일시정지/메뉴 · F11 전체화면 · M 음소거 · T 설정",
    "handling": "DAS: 키를 누른 뒤 자동 반복이 시작되기까지의 지연 · ARR: 반복 간격 (0 = 끝까지 즉시 이동) · 소프트드롭: 낙하 간격 (숫자가 작을수록 빠름)",
    "rebinding": "새 키를 누르세요  ·  ESC 취소",
}

# 탭별 '기본값으로' 대상 설정 키
TAB_DEFAULT_KEYS = {
    "match": ["target_player_count", "bot_difficulty", "game_mode", "screen_shake"],
    "general": ["resolution", "mini_detail", "color_mode", "text_size", "block_skin"],
    "audio": ["bgm_enabled", "bgm_volume", "bgm_stage_set", "sfx_enabled", "sfx_volume"],
    "keys": ["das_ms", "arr_ms", "sdf_ms"],
}


class SettingsMixin:
    # ------------------------------------------------------------------ 이벤트
    def _handle_settings_event(self, event):
        # 1. 키 리바인딩 대기 중인 경우 키 입력 캡처
        if self.rebinding_action:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.sound_mgr.play('move')
                    self.rebinding_action = None
                else:
                    moved = self.settings.set_action_key(self.rebinding_action, event.key)
                    self.sound_mgr.play('rotate')
                    if moved:                                             # 다른 동작에 있던 키를 가져왔다면 알려 줌
                        names = dict(ACTION_NAMES)
                        kn = short_key_name(event.key)
                        parts = [f"[{names.get(a, a).split(' (')[0]}]" + ("에 이 동작의 기존 키를 넘김" if sw else "에서 해제") for a, sw in moved]
                        self.rebind_notice = (f"{kn} 키는 " + ", ".join(parts) + "했습니다", time.time() + 5.0)
                    self.rebinding_action = None
            return

        if event.type == pygame.MOUSEMOTION:
            self._kb_nav = False                                          # 마우스를 쓰면 키보드 포커스 표시를 숨김
            return

        if event.type == pygame.KEYDOWN:
            nav_keys = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_KP_ENTER)
            if event.key == pygame.K_ESCAPE:
                self.sound_mgr.play('move')
                self.settings.save()
                self.state = self.previous_state
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.key == pygame.K_TAB:
                shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                self.settings_tab = TAB_ORDER[(TAB_ORDER.index(self.settings_tab) + (-1 if shift else 1)) % len(TAB_ORDER)]
                self.rebinding_action = None
                self._kb_nav = True
                self.sound_mgr.play('move')
            elif event.key in nav_keys:
                self._kb_nav = True
                self._settings_key_nav(event.key, shift=bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT))

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._kb_nav = False
            mx, my = event.pos
            for btn_id, rect in list(self.settings_buttons.items()):
                if rect.collidepoint(mx, my):
                    if btn_id in ("bgm_bar", "sfx_bar"):                  # 슬라이더 막대를 직접 클릭하면 그 위치의 음량으로
                        self._settings_set_volume(btn_id[:3], (mx - rect.x) / max(1, rect.w))
                    else:
                        self._settings_activate(btn_id)
                    break

    def _settings_set_volume(self, which, ratio):
        value = max(0, min(100, int(round(ratio * 10)) * 10))
        if which == "bgm":
            self.settings.set("bgm_volume", value)
            self.sound_mgr.set_bgm_volume(value / 100.0)
        else:
            self.settings.set("sfx_volume", value)
            self.sound_mgr.set_sfx_volume(value / 100.0)
        self.sound_mgr.play('move')

    # ------------------------------------------------------------------ 키보드 탐색
    def _settings_focus_id(self):
        """키보드로 선택된 항목의 키 (행 키 또는 조작 탭의 카드/핸들링 ID)"""
        tab = self.settings_tab
        f = self.settings_focus.get(tab, 0)
        if tab == "keys":
            if f == PRESET_FOCUS:
                return "preset"
            if f >= KEY_CARDS:
                return "hf_" + HANDLING_ROWS[min(2, f - KEY_CARDS)]
            return "bind_" + ACTION_NAMES[f % KEY_CARDS][0]
        rows = TAB_NAV[tab]
        return rows[f % len(rows)][0]

    def _settings_key_nav(self, key, shift=False):
        tab = self.settings_tab
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        if tab == "keys":
            self._settings_key_nav_keys(key, enter)
            return
        rows = TAB_NAV[tab]
        f = self.settings_focus.get(tab, 0) % len(rows)
        if key == pygame.K_UP:
            f = (f - 1) % len(rows)
            self.sound_mgr.play('move')
        elif key == pygame.K_DOWN:
            f = (f + 1) % len(rows)
            self.sound_mgr.play('move')
        else:
            _rk, main, left, right = rows[f]
            target = main if enter else (left if key == pygame.K_LEFT else right)
            if tab == "match" and _rk == "players" and shift and not enter:     # Shift+←→ = 10명씩
                target = "dec_10" if key == pygame.K_LEFT else "inc_10"
            if target:
                self._settings_activate(target)
        self.settings_focus[tab] = f

    def _settings_key_nav_keys(self, key, enter):
        """조작 탭: 카드 3x3 + 반응 속도 3줄 + 프리셋 줄"""
        n = KEY_CARDS
        f = self.settings_focus.get("keys", 0) % (n + 4)
        moved = True
        if f == PRESET_FOCUS:                                     # 프리셋 줄: ←→로 고르고 ↓로 카드로
            if key in (pygame.K_LEFT, pygame.K_RIGHT) or enter:
                self._settings_activate("preset_arcade" if key == pygame.K_LEFT else "preset_wasd" if key == pygame.K_RIGHT else
                                        ("preset_wasd" if self.settings.get("key_preset") == "arcade" else "preset_arcade"))
                moved = False
            elif key == pygame.K_DOWN:
                f = 0
            elif key == pygame.K_UP:
                f = n + 2
        elif f >= n:                                              # 핸들링 행: ↑↓ 이동, ←→ 값 조절
            which = HANDLING_ROWS[f - n]
            if key == pygame.K_UP:
                f = f - 1 if f > n else n - 3
            elif key == pygame.K_DOWN:
                f = f + 1 if f < n + 2 else PRESET_FOCUS
            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._settings_activate(which + ("_dec" if key == pygame.K_LEFT else "_inc"))
                moved = False
        else:                                                     # 카드
            if key == pygame.K_LEFT:
                f = (f - 1) % n
            elif key == pygame.K_RIGHT:
                f = (f + 1) % n
            elif key == pygame.K_UP:
                f = PRESET_FOCUS if f < 3 else f - 3
            elif key == pygame.K_DOWN:
                f = n if f + 3 >= n else f + 3
            else:
                self._settings_activate("bind_" + ACTION_NAMES[f][0])
                moved = False
        if moved:
            self.sound_mgr.play('move')
        self.settings_focus["keys"] = f

    # ------------------------------------------------------------------ 실행 (마우스/키보드 공용)
    def _settings_activate(self, btn_id):
        """설정 화면의 버튼 하나를 실행"""
        if btn_id.startswith("tab_"):
            self.sound_mgr.play('move')
            self.settings_tab = btn_id[4:]
            self.rebinding_action = None
        elif btn_id in ("dec_10", "dec_1", "inc_1", "inc_10"):
            self.sound_mgr.play('move')
            self.adjust_player_count({"dec_10": -10, "dec_1": -1, "inc_1": 1, "inc_10": 10}[btn_id])
        elif btn_id == "name_edit":
            self._begin_text("player_name")
        elif btn_id in ("color_prev", "color_next"):
            self._set_name_color((self.name_color + (-1 if btn_id == "color_prev" else 1)) % len(NAME_COLORS))
        # 조작 탭
        elif btn_id in ("preset_arcade", "preset_wasd"):
            self.sound_mgr.play('rotate')
            self.settings.set_key_preset(btn_id[7:])
            self.rebinding_action = None
        elif btn_id.startswith("bind_"):
            self.sound_mgr.play('move')
            self.rebinding_action = btn_id[5:]
        elif btn_id in ("das_dec", "das_inc", "arr_dec", "arr_inc", "sdf_dec", "sdf_inc"):
            self.sound_mgr.play('rotate')
            self.settings.adjust_handling(btn_id[:3] + "_ms", -1 if btn_id.endswith("dec") else 1)
            self.apply_handling()
        # 화면 탭
        elif btn_id in ("toggle_fs", "fs=window", "fs=full"):
            if btn_id == "toggle_fs" or (btn_id == "fs=full") != self.is_fullscreen:
                self.sound_mgr.play('move')
                self.toggle_fullscreen()
        elif btn_id in ("res_prev", "res_next"):
            if not self.is_fullscreen:                                        # 전체 화면에서는 해상도를 고를 수 없음
                self.sound_mgr.play('rotate')
                self.change_resolution(-1 if btn_id == "res_prev" else 1)
        elif btn_id.split("=")[0] in ("mini_detail", "color_mode", "text_size"):
            name, _, value = btn_id.partition("=")
            cur = {"mini_detail": self.settings.get("mini_detail"), "color_mode": self.settings.get("color_mode"),
                   "text_size": self.settings.get("text_size")}[name]
            other = {"mini_detail": ("detailed", "simple"), "color_mode": ("normal", "colorblind"), "text_size": ("normal", "large")}[name]
            new = value if value else other[1] if cur == other[0] else other[0]      # 값이 없으면 (예전 방식) 토글
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set(name, new)
                if name == "mini_detail":
                    self.renderer.mini_detailed = (new != "simple")
                else:
                    self.apply_visual_options()
        elif btn_id in ("shake_prev", "shake_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_screen_shake(-1 if btn_id == "shake_prev" else 1)
            self.apply_gameplay_options()
        elif btn_id in ("skin_prev", "skin_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_block_skin(-1 if btn_id == "skin_prev" else 1)
            self.apply_visual_options()
        # 게임 탭
        elif btn_id in ("attack=on", "attack=off", "attack_toggle"):
            cur = "battle" if self.settings.get("game_mode") != "survival" else "survival"
            picked = btn_id.split("=")[1] if "=" in btn_id else None
            new = ("battle" if picked == "on" else "survival") if picked else ("survival" if cur == "battle" else "battle")
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("game_mode", new)
        elif btn_id in ("diff_prev", "diff_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_bot_difficulty(-1 if btn_id == "diff_prev" else 1)
            self.bot_difficulty = self.settings.get("bot_difficulty")
        # 소리 탭
        elif btn_id == "bgm_toggle":
            self.sound_mgr.play('move')
            self.sound_mgr.set_bgm_enabled(self.settings.toggle_bgm())
        elif btn_id in ("bgm_dec", "bgm_inc"):
            self.sound_mgr.play('move')
            self.sound_mgr.set_bgm_volume(self.settings.adjust_bgm_volume(-10 if btn_id == "bgm_dec" else 10) / 100.0)
        elif btn_id in ("stage_bgm_prev", "stage_bgm_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_bgm_stage_set(-1 if btn_id == "stage_bgm_prev" else 1)
        elif btn_id == "sfx_toggle":
            self.sound_mgr.set_sfx_enabled(self.settings.toggle_sfx())
            self.sound_mgr.play('move')
        elif btn_id in ("sfx_dec", "sfx_inc"):
            self.sound_mgr.set_sfx_volume(self.settings.adjust_sfx_volume(-10 if btn_id == "sfx_dec" else 10) / 100.0)
            self.sound_mgr.play('move')
        elif btn_id == "sfx_test":
            self.sound_mgr.play('clear')
        # 공통
        elif btn_id in ("reset_tab", "reset_keys"):
            self._reset_current_tab()
        elif btn_id == "reset_defaults":
            self._open_modal("환경설정을 초기화할까요?", ["해상도, 소리, 조작키, 이름 등 모든 설정이 기본값으로 돌아갑니다.", "되돌릴 수 없습니다."],
                             [("stay", "취소", "blue", "ESC"), ("reset_defaults_ok", "초기화", "red", "Y")])
        elif btn_id == "save_and_back":
            self.sound_mgr.play('move')
            self.settings.save()
            self.state = self.previous_state

    def _reset_current_tab(self):
        """현재 탭의 설정만 기본값으로 되돌림"""
        tab = self.settings_tab
        self.sound_mgr.play('clear')
        self.settings.reset_values(TAB_DEFAULT_KEYS[tab])
        if tab == "match":
            self.target_player_count = self.settings.get("target_player_count")
            self.bot_difficulty = self.settings.get("bot_difficulty")
            self.apply_gameplay_options()
        elif tab == "general":
            self.renderer.mini_detailed = self.settings.get("mini_detail") != "simple"
            self.apply_visual_options()
            if not self.is_fullscreen:
                self._apply_window_size()
        elif tab == "audio":
            self.sound_mgr.set_bgm_enabled(self.settings.get("bgm_enabled"))
            self.sound_mgr.set_sfx_enabled(self.settings.get("sfx_enabled"))
            self.sound_mgr.set_bgm_volume(self.settings.get("bgm_volume") / 100.0)
            self.sound_mgr.set_sfx_volume(self.settings.get("sfx_volume") / 100.0)
        else:
            self.settings.reset_keys_to_default()
            self.apply_handling()
            self.rebinding_action = None

    def _do_reset_defaults(self):
        self.sound_mgr.play('clear')
        self.settings.reset_to_defaults()
        self.apply_handling()
        self.renderer.mini_detailed = True
        self.apply_visual_options()
        self._end_text(commit=False)
        self.player_name = "Player_1"
        self.room_name_input = ""
        if not self.is_fullscreen:
            self._apply_window_size()
        self.bot_difficulty = self.settings.get("bot_difficulty")
        self.sound_mgr.set_bgm_enabled(self.settings.get("bgm_enabled"))
        self.sound_mgr.set_sfx_enabled(self.settings.get("sfx_enabled"))
        self.sound_mgr.set_bgm_volume(self.settings.get("bgm_volume") / 100.0)
        self.sound_mgr.set_sfx_volume(self.settings.get("sfx_volume") / 100.0)

    def _update_settings(self, dt):
        self.menu_bg.update(dt)

    # ------------------------------------------------------------------ 그리기 부품 (모든 탭 공통)
    def _s_hover(self, rect):
        mx, my = pygame.mouse.get_pos()
        return rect.collidepoint(mx, my)

    def _s_row(self, key, y, h, label, sub=None, sub_col=None):
        """설정 한 줄: 배경(마우스 올림/키보드 포커스), 왼쪽 라벨(+보조 줄). 컨트롤은 호출한 쪽이 오른쪽에 그림"""
        rect = pygame.Rect(IX, y, IW, h)
        self._row_rects[key] = rect
        focus = self._kb_nav and self._focus_key == key
        if focus:
            pygame.draw.rect(self.screen, COL_ROW_FOCUS, rect, border_radius=10)
            pygame.draw.rect(self.screen, C_ACCENT, (rect.x, rect.y + 8, 4, rect.h - 16), border_radius=2)
            pygame.draw.rect(self.screen, _mix(C_ACCENT, COL_ROW_FOCUS, 0.55), rect.inflate(-2, -2), 1, border_radius=9)
        elif self._s_hover(rect):
            pygame.draw.rect(self.screen, COL_ROW_HOVER, rect, border_radius=10)
        if sub:
            self._t(label, self.font_row, COL_TEXT, rect.x + 22, rect.y + 8)
            self._t(sub, self.font_help, sub_col or COL_SUB, rect.x + 22, rect.y + 32)
        else:
            self._t(label, self.font_row, COL_TEXT, rect.x + 22, rect.centery, "midleft")
        pygame.draw.line(self.screen, (32, 42, 68), (rect.x + 12, rect.bottom), (rect.right - 12, rect.bottom), 1)
        return rect

    def _s_section(self, title, y):
        """섹션 제목 + 오른쪽으로 이어지는 얇은 선"""
        r = self._t(title, self.font_sec, COL_SEC, IX + 22, y + 14, "midleft")
        pygame.draw.line(self.screen, (40, 58, 92), (r.right + 12, y + 14), (IX + IW - 12, y + 14), 1)

    def _s_btn(self, bid, rect, text, enabled=True, font=None, color=None):
        """작은 사각 버튼 (±, ‹ ›, 미리듣기 등). 마우스 올림 표시는 색만 바꿈 (Surface 새로 만들지 않음)"""
        rect = pygame.Rect(rect)
        if bid:
            self.settings_buttons[bid] = rect
        hov = enabled and self._s_hover(rect)
        pygame.draw.rect(self.screen, (40, 52, 86) if hov else (22, 28, 48), rect, border_radius=9)
        pygame.draw.rect(self.screen, C_ACCENT if hov else (64, 80, 120) if enabled else (40, 48, 70), rect, 1, border_radius=9)
        self._t(text, font or self.font_val, (color or COL_TEXT) if enabled else COL_OFF, rect.centerx, rect.centery, "center")

    def _s_seg(self, opts, active, right, cy, enabled=True):
        """선택 버튼(세그먼트): [(id, 라벨)]. 선택된 칸은 청록 채움 + 흰 글자"""
        widths = [max(104, self.font_val.size(lbl)[0] + 34) for _bid, lbl in opts]
        total = sum(widths)
        x = right - total
        frame = pygame.Rect(x, cy - 19, total, 38)
        pygame.draw.rect(self.screen, COL_CTL_BG, frame, border_radius=11)
        pygame.draw.rect(self.screen, COL_CTL_EDGE if enabled else (40, 48, 70), frame, 1, border_radius=11)
        for (bid, lbl), w in zip(opts, widths):
            seg = pygame.Rect(x, frame.y, w, frame.h)
            self.settings_buttons[bid] = seg
            on = (bid == active)
            if on:
                pygame.draw.rect(self.screen, _mix(COL_CTL_BG, C_ACCENT, 0.32), seg.inflate(-4, -4), border_radius=9)
                pygame.draw.rect(self.screen, C_ACCENT, seg.inflate(-4, -4), 1, border_radius=9)
            elif enabled and self._s_hover(seg):
                pygame.draw.rect(self.screen, (30, 40, 68), seg.inflate(-4, -4), border_radius=9)
            self._t(lbl, self.font_val, (255, 255, 255) if on else (COL_SUB if enabled else COL_OFF), seg.centerx, seg.centery, "center")
            x += w

    def _s_switch(self, bid, on, right, cy):
        """켜짐/꺼짐 스위치 + 상태 글자"""
        track = pygame.Rect(right - 52, cy - 14, 52, 28)
        hit = pygame.Rect(right - 130, cy - 20, 130, 40)
        self.settings_buttons[bid] = hit
        pygame.draw.rect(self.screen, (38, 150, 110) if on else (52, 60, 84), track, border_radius=14)
        kx = track.right - 14 if on else track.x + 14
        pygame.draw.circle(self.screen, (255, 255, 255) if on else (170, 180, 200), (kx, track.centery), 10)
        self._t("켜짐" if on else "꺼짐", self.font_val, (120, 235, 185) if on else COL_SUB, track.x - 12, track.centery, "midright")

    def _s_slider(self, prefix, value, color, right, cy, enabled=True):
        """[-] 막대 [+] 값%. 값 글자는 막대 밖에 두어 채움 색과 겹치지 않음. 막대를 직접 클릭해도 음량이 바뀜"""
        val_w = 56
        inc = pygame.Rect(right - val_w - 8 - 36, cy - 18, 36, 36)
        bar = pygame.Rect(inc.x - 12 - 220, cy - 4, 220, 8)
        dec = pygame.Rect(bar.x - 12 - 36, cy - 18, 36, 36)
        self._s_btn(prefix + "_dec", dec, "-", enabled)
        self._s_btn(prefix + "_inc", inc, "+", enabled)
        self.settings_buttons[prefix + "_bar"] = bar.inflate(0, 20)
        pygame.draw.rect(self.screen, (34, 42, 66), bar, border_radius=4)
        fill = pygame.Rect(bar.x, bar.y, int(bar.w * value / 100), bar.h)
        if fill.w > 0:
            pygame.draw.rect(self.screen, color if enabled else COL_OFF, fill, border_radius=4)
        pygame.draw.circle(self.screen, (255, 255, 255) if enabled else COL_OFF, (bar.x + fill.w, bar.centery), 8)
        self._t(f"{value}%", self.font_val, color if enabled else COL_OFF, right, cy, "midright")

    def _s_cycler(self, prev_id, next_id, text, right, cy, enabled=True, color=None):
        """‹ 값 › 순환 선택기"""
        nxt = pygame.Rect(right - 36, cy - 18, 36, 36)
        val = pygame.Rect(nxt.x - 8 - 240, cy - 18, 240, 36)
        prv = pygame.Rect(val.x - 8 - 36, cy - 18, 36, 36)
        self._s_btn(prev_id, prv, "‹", enabled, self.font_row)
        self._s_btn(next_id, nxt, "›", enabled, self.font_row)
        pygame.draw.rect(self.screen, COL_CTL_BG, val, border_radius=10)
        pygame.draw.rect(self.screen, COL_CTL_EDGE if enabled else (40, 48, 70), val, 1, border_radius=10)
        self._t(text, self.font_val, (color or COL_TEXT) if enabled else COL_OFF, val.centerx, val.centery, "center")

    # ------------------------------------------------------------------ 탭별 화면
    def _render_tab_match(self):
        y = TOP
        # 참가 인원
        self._s_row("players", y, 64, "참가 인원", "2 ~ 100명  ·  부족한 인원은 AI 봇이 채웁니다")
        cy = y + 32
        parts = [("dec_10", "-10", 56), ("dec_1", "-1", 46), None, ("inc_1", "+1", 46), ("inc_10", "+10", 56)]
        total = sum(p[2] if p else 110 for p in parts) + 8 * (len(parts) - 1)
        x = RIGHT - total
        for p in parts:
            if p is None:
                box = pygame.Rect(x, cy - 19, 110, 38)
                pygame.draw.rect(self.screen, COL_CTL_BG, box, border_radius=10)
                pygame.draw.rect(self.screen, C_GOLD, box, 1, border_radius=10)
                self._t(f"{self.target_player_count}명", self.font_row, C_GOLD, box.centerx, box.centery, "center")
                x += 110 + 8
            else:
                self._s_btn(p[0], pygame.Rect(x, cy - 19, p[2], 38), p[1])
                x += p[2] + 8
        y += 64
        # 봇 난이도 (설명은 현재 난이도에 따라 바뀌는 값이라 보조 줄로 유지)
        cur = self.settings.get("bot_difficulty", "mixed")
        dc = {"easy": C_GREEN, "normal": C_ACCENT, "hard": C_ORANGE, "master": C_DANGER, "mixed": C_GOLD}.get(cur, C_TEXT)
        cleared = self.stats_mgr.ladder_cleared("battle")            # 100인급 대전에서 10위 안에 들어 클리어한 난이도는 ★ 표시
        star = "  ★ 클리어" if cur in cleared else ""
        self._s_row("diff", y, 64, "AI 봇 난이도", BOT_DIFFICULTY_DESCS.get(cur, "") if not star else BOT_DIFFICULTY_DESCS.get(cur, "")[:40])
        self._s_cycler("diff_prev", "diff_next", BOT_DIFFICULTY_LABELS.get(cur, "혼합") + star, RIGHT, y + 32, color=dc)
        y += 64
        # 게임 모드: 배틀로얄(공격을 주고받음) / 서바이벌(공격 없이 각자 생존 경쟁)
        atk_on = self.settings.get("game_mode") != "survival"
        self._s_row("attack", y, 56, "게임 모드", "줄을 지워 서로 공격하는 모드" if atk_on else "서로 방해하지 않고 각자 끝까지 생존하는 모드")
        self._s_seg([("attack=on", "배틀로얄"), ("attack=off", "서바이벌")], "attack=on" if atk_on else "attack=off", RIGHT, y + 28)
        y += 56
        # 이름
        self._s_row("name", y, 56, "플레이어 이름")
        box = pygame.Rect(RIGHT - 320, y + 10, 320, 36)
        self.text_rects["player_name"] = box
        editing = (self.text_focus == "player_name")
        pygame.draw.rect(self.screen, (11, 13, 24), box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT if editing else COL_CTL_EDGE, box, 2 if editing else 1, border_radius=10)
        shown = (self.player_name_input + self.chat_comp) if editing else self.player_name
        tr = self._t(shown, self.font_val, NAME_COLORS[self.name_color][1], box.x + 14, box.centery, "midleft")
        if editing and int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_ACCENT, (tr.right + 3, box.y + 8, 2, box.h - 16))
        if not editing:
            self._t("클릭해서 수정", self.font_tiny, COL_SUB, box.right - 12, box.centery, "midright")
        y += 56
        # 이름 색
        self._s_row("color", y, 56, "이름 색")
        size, gap = 26, 8
        self.color_rects = self._draw_color_swatches(RIGHT - (size * len(NAME_COLORS) + gap * (len(NAME_COLORS) - 1)), y + 15, size=size, gap=gap)
        y += 56
        shake = self.settings.get("screen_shake", "normal")
        self._s_row("shake", y, 56, "화면 흔들림", "공격을 받거나 K.O.가 났을 때")
        self._s_cycler("shake_prev", "shake_next", SHAKE_LABELS.get(shake, "보통"), RIGHT, y + 28)

    def _render_tab_general(self):
        y = TOP
        fs = self.is_fullscreen
        size = pygame.display.get_surface().get_size() if pygame.display.get_surface() else (0, 0)
        self._s_row("fs", y, 56, "화면 모드", f"현재 {size[0]}×{size[1]}  ·  F11 키로도 전환")
        self._s_seg([("fs=window", "창 모드"), ("fs=full", "전체 화면")], "fs=full" if fs else "fs=window", RIGHT, y + 28)
        y += 56
        res = self.settings.get("resolution", "auto")
        res_label = "자동 (모니터에 맞춤)" if res == "auto" else res.replace("x", " × ") + {
            "1280x720": "  (HD)", "1920x1080": "  (FHD)", "2560x1440": "  (QHD)", "3840x2160": "  (4K)"}.get(res, "")
        self._s_row("res", y, 56, "창 해상도", "전체 화면에서는 사용하지 않습니다" if fs else None)
        self._s_cycler("res_prev", "res_next", res_label, RIGHT, y + 28, enabled=not fs)
        y += 56
        self._s_row("mini", y, 56, "미니 보드", "상대 보드에 표시할 정보의 양")
        self._s_seg([("mini_detail=detailed", "자세히"), ("mini_detail=simple", "간략")],
                    "mini_detail=simple" if self.settings.get("mini_detail") == "simple" else "mini_detail=detailed", RIGHT, y + 28)
        y += 56
        skin = self.settings.get("block_skin", "classic")
        self._s_row("block_skin", y, 56, "블록 스킨", BLOCK_SKIN_DESCS.get(skin, ""))
        self._s_cycler("skin_prev", "skin_next", BLOCK_SKIN_LABELS.get(skin, "클래식"), RIGHT, y + 28, color=C_GOLD)
        px = RIGHT - 328 - 16 - 7 * 22                            # 현재 스킨으로 그린 7종 블록 미리보기 (설명과 선택기 사이)
        for i, piece in enumerate("IOTSZJL"):
            self.screen.blit(self.renderer._cell_surface(piece, 20), (px + i * 22, y + 18))
        y += 56 + 10
        self._s_section("접근성", y)
        y += 30
        self._s_row("color_mode", y, 56, "블록 색상", "색약 보정: 밝기 차이가 큰 팔레트")
        self._s_seg([("color_mode=normal", "기본"), ("color_mode=colorblind", "색약 보정")],
                    "color_mode=colorblind" if self.settings.get("color_mode") == "colorblind" else "color_mode=normal", RIGHT, y + 28)
        y += 56
        self._s_row("text_size", y, 56, "게임 글자 크기", "게임 화면의 작은 글씨")
        self._s_seg([("text_size=normal", "보통"), ("text_size=large", "크게")],
                    "text_size=large" if self.settings.get("text_size") == "large" else "text_size=normal", RIGHT, y + 28)

    def _render_tab_audio(self):
        y = TOP
        bgm_on = bool(self.settings.get("bgm_enabled", True))
        self._s_row("bgm", y, 64, "배경음악", "생존자가 줄수록 더 긴박해집니다")
        self._s_switch("bgm_toggle", bgm_on, RIGHT - 396, y + 32)
        self._s_slider("bgm", self.settings.get("bgm_volume", 60), C_ACCENT, RIGHT, y + 32, enabled=bgm_on)
        y += 64
        cur_set = self.settings.get("bgm_stage_set", "random")
        self._s_row("stage_bgm", y, 64, "스테이지 배경음", BGM_STAGE_SET_DESCS.get(cur_set, ""))
        self._s_cycler("stage_bgm_prev", "stage_bgm_next", BGM_STAGE_SET_LABELS.get(cur_set, "랜덤"), RIGHT, y + 32, color=C_GOLD)
        y += 64
        sfx_on = bool(self.settings.get("sfx_enabled", True))
        self._s_row("sfx", y, 64, "효과음", "블록 착지, 줄 삭제, 공격 소리")
        self._s_switch("sfx_toggle", sfx_on, RIGHT - 396, y + 32)
        self._s_slider("sfx", self.settings.get("sfx_volume", 70), C_ORANGE, RIGHT, y + 32, enabled=sfx_on)
        y += 64
        self._s_row("sfx_test", y, 56, "효과음 들어보기")
        self._s_btn("sfx_test", pygame.Rect(RIGHT - 200, y + 10, 200, 36), "▶  대표 소리 재생", sfx_on)
        y += 56 + 12
        self._t("M 키로 언제든 소리를 켜고 끌 수 있습니다.", self.font_help, COL_SUB, IX + 22, y + 8)

    def _render_tab_keys(self):
        mx, my = pygame.mouse.get_pos()
        y = TOP
        cur_preset = self.settings.get("key_preset", "arcade")
        p_label = {"arcade": "아케이드 표준", "wasd": "WASD 게이머"}.get(cur_preset, "사용자 지정")
        self._s_row("preset", y, 48, "프리셋")
        self._s_seg([("preset_arcade", "아케이드 표준"), ("preset_wasd", "WASD 게이머")],
                    "preset_" + cur_preset if cur_preset in ("arcade", "wasd") else None, RIGHT - 210, y + 24)
        self._t(f"현재: {p_label}", self.font_val, C_GREEN if cur_preset in ("arcade", "wasd") else C_GOLD, RIGHT, y + 24, "midright")
        y += 48 + 8

        used = {}
        for act_id, _n in ACTION_NAMES:
            for k in self.settings.get_action_keys(act_id):
                used.setdefault(k, []).append(act_id)
        conflicts = {a for acts in used.values() if len(acts) > 1 for a in acts}

        card_w, card_h, gap = 282, 64, 9
        self._row_rects["cards"] = pygame.Rect(IX, y, IW, 3 * card_h + 2 * gap)
        focus_card = self._focus_key if self._kb_nav and self._focus_key.startswith("bind_") else None
        for i, (act_id, act_name) in enumerate(ACTION_NAMES):
            col, row = i % 3, i // 3
            rect = pygame.Rect(IX + col * (card_w + gap), y + row * (card_h + gap), card_w, card_h)
            self.settings_buttons[f"bind_{act_id}"] = rect
            rebinding = (self.rebinding_action == act_id)
            hover = rect.collidepoint(mx, my)
            is_conflict = act_id in conflicts
            focused = (focus_card == f"bind_{act_id}")
            bg = (58, 46, 20) if rebinding else ((34, 44, 72) if hover or focused else (20, 26, 46))
            edge = C_GOLD if rebinding else (C_DANGER if is_conflict else (C_ACCENT if (hover or focused) else (52, 66, 104)))
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)
            pygame.draw.rect(self.screen, edge, rect, 2 if (hover or rebinding or focused) else 1, border_radius=12)
            self._t(act_name.split(" (")[0], self.font_val, COL_TEXT, rect.x + 16, rect.y + 10)
            if rebinding:
                self._t("새 키를 누르세요…", self.font_val, C_GOLD, rect.x + 16, rect.y + 36)
                self._t("ESC 취소", self.font_tiny, COL_SUB, rect.right - 12, rect.y + 12, "topright")
            else:
                kx = rect.x + 16
                for kc in self.settings.get_action_keys(act_id)[:3]:
                    ks = self.renderer._text(short_key_name(kc), self.font_val, (225, 232, 248))
                    kr = pygame.Rect(kx, rect.y + 34, max(32, ks.get_width() + 18), 24)
                    pygame.draw.rect(self.screen, (44, 54, 86), kr, border_radius=7)
                    pygame.draw.rect(self.screen, (92, 108, 150), kr, 1, border_radius=7)
                    self.screen.blit(ks, (kr.centerx - ks.get_width() // 2, kr.centery - ks.get_height() // 2))
                    kx = kr.right + 6
                if is_conflict:
                    self._t("중복", self.font_tiny, C_DANGER, rect.right - 12, rect.y + 12, "topright")
        y += 3 * card_h + 2 * gap + 6
        # 키를 옮겼다는 알림 (몇 초간)
        notice = getattr(self, "rebind_notice", None)
        if notice and time.time() < notice[1]:
            self._t(notice[0], self.font_help, C_GOLD, IX + IW // 2, y + 8, "midtop")
        elif conflicts:
            self._t("같은 키가 여러 동작에 배정되어 있습니다. 빨간 카드를 다시 지정하세요.", self.font_help, C_DANGER, IX + IW // 2, y + 8, "midtop")
        y += 30
        self._s_section("반응 속도", y)
        y += 28
        hrow = self._s_row("handling", y, 48, "")
        group_w = IW // 3
        for gi, (key, label) in enumerate([("das", "DAS 지연"), ("arr", "ARR 반복"), ("sdf", "소프트드롭")]):
            gx = IX + gi * group_w + 12
            self._t(label, self.font_val, COL_SUB, gx + 10, y + 24, "midleft")
            dec = pygame.Rect(gx + 100, y + 8, 32, 32)
            val = pygame.Rect(dec.right + 4, y + 8, 76, 32)
            inc = pygame.Rect(val.right + 4, y + 8, 32, 32)
            self.settings_buttons["hf_" + key] = val
            self._s_btn(key + "_dec", dec, "-")
            self._s_btn(key + "_inc", inc, "+")
            pygame.draw.rect(self.screen, COL_CTL_BG, val, border_radius=8)
            pygame.draw.rect(self.screen, C_ACCENT, val, 1, border_radius=8)
            v_ms = self.settings.get(key + '_ms')
            self._t("즉시" if (key == "arr" and v_ms == 0) else f"{v_ms}ms", self.font_val, C_ACCENT, val.centerx, val.centery, "center")

    # ------------------------------------------------------------------ 전체 화면
    def _render_settings(self):
        in_game = self.previous_state == "GAME" and self.match is not None
        if in_game:
            # 게임 중 T로 연 설정: 게임 화면을 어둡게 깔고 그 위에 설정 창 (일시정지 팝업은 겹치지 않게 숨김)
            paused = self.match.is_paused
            self.match.is_paused = False
            self._render_game_frame()
            self.match.is_paused = paused
            CANVAS.overlay((4, 6, 12, 205))
        else:
            self.menu_bg.draw(self.screen)
        mx, my = pygame.mouse.get_pos()
        self.settings_buttons.clear()
        self.text_rects.clear()
        self._row_rects = {}
        self.color_rects = []
        self._kb_nav = getattr(self, "_kb_nav", False)
        if self.settings_tab not in TAB_ORDER:
            self.settings_tab = "match"
        self._focus_key = self._settings_focus_id()

        if not in_game:
            self._menu_header("게임 환경 설정", None, accent=C_ACCENT)
        else:
            self._t("환경 설정", self.font_menu, C_TEXT, IX, 80)
            self._t("게임이 일시정지된 상태입니다" if self.net_mgr.mode == "NONE" else "네트워크 게임은 설정 중에도 계속 진행됩니다",
                    self.font_help, COL_SUB, IX + 130, 90)
        self._glass((PX, PY, PW, PH), accent=(60, 120, 190), radius=18)

        # 탭 바: 선택된 탭은 옅은 채움 + 아래쪽 색 밑줄
        tab_w, tab_gap = (IW - 3 * 8) // 4, 8
        for i, (tid, bid, label, col) in enumerate(TABS):
            rect = pygame.Rect(IX + i * (tab_w + tab_gap), 132, tab_w, 44)
            self.settings_buttons[bid] = rect
            active = (self.settings_tab == tid)
            hov = rect.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _mix((18, 22, 38), col, 0.16) if active else ((26, 34, 58) if hov else (18, 22, 38)), rect, border_radius=10)
            if active:
                pygame.draw.rect(self.screen, col, (rect.x + 10, rect.bottom - 4, rect.w - 20, 3), border_radius=2)
            self._t(label, self.font_row, COL_TEXT if active else COL_SUB, rect.centerx, rect.centery - 1, "center")
        pygame.draw.line(self.screen, (50, 75, 115), (IX, 186), (IX + IW, 186), 1)

        {"match": self._render_tab_match, "general": self._render_tab_general,
         "audio": self._render_tab_audio, "keys": self._render_tab_keys}[self.settings_tab]()

        # 하단: 도움말 바 (마우스를 올린 항목, 없으면 키보드로 선택한 항목의 설명) + 키 안내
        self._render_help_bar(mx, my)

        # 하단 버튼 줄: 이 탭 기본값 · 전체 초기화 / 안내 / 완료
        reset = pygame.Rect(IX, 642, 160, 38)
        self._s_btn("reset_tab", reset, "이 탭 기본값으로", True, self.font_val, (255, 190, 200))
        full = pygame.Rect(reset.right + 8, 642, 96, 38)
        self.settings_buttons["reset_defaults"] = full
        self._t("전체 초기화", self.font_help, C_DANGER if self._s_hover(full) else COL_SUB, full.centerx, full.centery, "center")
        note = "인원·난이도·게임 모드는 다음 판부터 적용됩니다" if (in_game and self.settings_tab == "match") else "변경 사항은 즉시 적용·저장됩니다"
        self._t(note, self.font_help, COL_SUB, IX + IW // 2 + 30, 654, "midtop")
        self._t("↑↓ 이동   ←→ 조절   Enter 실행   TAB 탭   ESC 닫기", self.font_tiny, (128, 142, 175), IX + IW // 2 + 30, 673, "midtop")
        done = pygame.Rect(IX + IW - 170, 642, 170, 38)
        self.settings_buttons["save_and_back"] = done
        hov = done.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (32, 100, 130) if hov else (20, 70, 96), done, border_radius=10)
        pygame.draw.rect(self.screen, (90, 210, 255) if hov else (70, 180, 230), done, 1, border_radius=10)
        self._t("완료  (ESC)", self.font_row, (235, 250, 255), done.centerx, done.centery, "center")

    def _render_help_bar(self, mx, my):
        """하단 도움말 바: 마우스를 올린 항목(없으면 키보드로 선택한 항목)의 설명을 최대 두 줄로 표시"""
        bar = pygame.Rect(IX, 592, IW, 42)
        self._panel_flat(bar)
        key = None
        for k, r in self._row_rects.items():
            if r.collidepoint(mx, my):
                key = k
        if self.rebinding_action:
            text, col = HELP["rebinding"], C_GOLD
        else:
            if key is None and self._kb_nav:
                key = self._focus_key
            if key and key.startswith("bind_"):
                key = "cards"
            elif key and key.startswith("hf_"):
                key = "handling"
            if key == "diff":
                text = BOT_DIFFICULTY_DESCS.get(self.settings.get("bot_difficulty", "mixed"), "")
            elif key == "res" and self.is_fullscreen:
                text = HELP["res_off"]
            else:
                text = HELP.get(key or "", "")
            col = (185, 198, 225)
        if not text:
            self._t("항목에 마우스를 올리거나 ↑↓로 선택하면 설명이 여기에 표시됩니다.", self.font_help, COL_OFF, bar.x + 16, bar.centery, "midleft")
            return
        max_w = bar.w - 32
        lines, cur = [], ""
        for ch in text:                                                   # 글자 폭 기준 줄바꿈 (한글은 띄어쓰기가 드물어 글자 단위)
            if self.font_help.size(cur + ch)[0] > max_w and cur:
                lines.append(cur)
                cur = ch.lstrip()
            else:
                cur += ch
        lines.append(cur)
        if len(lines) > 2:                                                # 두 줄을 넘으면 끝을 …로
            l2 = lines[1]
            while len(l2) > 2 and self.font_help.size(l2 + "…")[0] > max_w:
                l2 = l2[:-1]
            lines = [lines[0], l2 + "…"]
        if len(lines) == 1:
            self._t(lines[0], self.font_help, col, bar.x + 16, bar.centery, "midleft")
        else:
            self._t(lines[0], self.font_help, col, bar.x + 16, bar.y + 4)
            self._t(lines[1], self.font_help, col, bar.x + 16, bar.y + 21)

    def _panel_flat(self, rect):
        """도움말 바 바탕 (해상도별로 한 번만 만들어지는 캐시 패널)"""
        self.renderer._panel(rect, border=(36, 48, 78), bg=(11, 14, 26), radius=8, alpha=255, border_w=1)
