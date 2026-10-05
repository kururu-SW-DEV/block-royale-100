"""
Block Royale 100 - 설정 화면 (게임 / 화면 / 소리 / 조작 탭)
BlockRoyaleApp(main.py)이 상속하는 믹스인. 모든 탭이 같은 '행' 구조(왼쪽 라벨 · 오른쪽 컨트롤)와 하단 도움말 바를 쓰고,
키보드 탐색은 TAB_NAV 표 하나로 정의됨 (마우스 hit rect는 settings_buttons에 id로 등록)
"""

from i18n import tr as _tr
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
        ("audio", "tab_audio", "소리", C_ORANGE), ("keys", "tab_keys", "조작", C_GOLD),
        ("react", "tab_react", "반응", (255, 150, 90)), ("rules", "tab_rules", "규칙", C_DANGER), ("help", "tab_help", "기타", C_GREEN)]
TAB_ORDER = [t[0] for t in TABS]

# 키보드 탐색표: 탭 -> [(행 키, Enter, ←, →)]. 행 키는 화면에 그려지는 행과 도움말/포커스 표시에 쓰임
TAB_NAV = {
    "match": [("language", None, "lang_prev", "lang_next"), ("players", None, "dec_1", "inc_1"), ("diff", None, "diff_prev", "diff_next"),
              ("attack", "attack_toggle", "attack=on", "attack=off"),
              ("name", "name_edit", None, None), ("color", None, "color_prev", "color_next"),
              ("shake", None, "shake_prev", "shake_next"),
              ],
    "help": [("title", None, "title_prev", "title_next"), ("rules", "open_rules", None, None), ("tips_replay", "tips_replay", None, None),
             ("matchlog", "matchlog_toggle", "matchlog=off", "matchlog=on"),
             ("ghost", "ghost_toggle", "ghost=off", "ghost=on"),
             ("update", "update_toggle", "update=off", "update=on"), ("errlog", "open_errlog", None, None)],
    "general": [("fs", "toggle_fs", "fs=window", "fs=full"), ("res", "res_next", "res_prev", "res_next"),
                ("mini", "mini_detail", "mini_detail=detailed", "mini_detail=simple"),
                ("block_skin", None, "skin_prev", "skin_next"),
                ("color_mode", "color_mode", "color_mode=normal", "color_mode=colorblind"),
                ("text_size", "text_size", "text_size=normal", "text_size=large"),
                ("key_hints", "key_hints", "key_hints_prev", "key_hints_next")],
    "rules": [("rule_garbage", None, "rg_prev", "rg_next"), ("rule_gravity", None, "rgr_prev", "rgr_next"), ("rule_badges", "rb_toggle", "rb=off", "rb=on"),
              ("rule_team", "rt_toggle", "rt=off", "rt=on")],
    "react": [("react_das", None, "das_dec", "das_inc"), ("react_arr", None, "arr_dec", "arr_inc"), ("react_sdf", None, "sdf_dec", "sdf_inc"),
              ("react_dcd", None, "dcd_dec", "dcd_inc"), ("react_dcancel", "dcancel_inc", "dcancel_dec", "dcancel_inc"),
              ("react_hpre", "hpre_inc", "hpre_dec", "hpre_inc"),
              ("gamepad", "gamepad_toggle", "gamepad=off", "gamepad=on")],
    "audio": [("bgm", "bgm_toggle", "bgm_dec", "bgm_inc"), ("stage_bgm", None, "stage_bgm_prev", "stage_bgm_next"),
              ("sfx", "sfx_toggle", "sfx_dec", "sfx_inc"), ("warn", "warn_next", "warn_prev", "warn_next"),
              ("announcer", "announcer_toggle", "announcer_toggle", "announcer_toggle"), ("sfx_test", "sfx_test", None, None)],
}
KEY_CARDS = len(ACTION_NAMES)                 # 조작 탭: 0~9 = 키 카드, 10 = 키 프리셋 (반응 속도는 별도 '반응' 탭)
PRESET_FOCUS = KEY_CARDS

HELP_SKIN_BASE = "게임 화면 블록의 모양을 바꿉니다. 색은 위의 '블록 색상' 설정을 따르며, 로고와 미니 보드는 그대로입니다."

HELP = {
    "players": "한 판에 참가하는 총 인원입니다. 부족한 인원은 AI 봇이 채웁니다. 방 만들기에서는 방장이 정한 인원으로 시작합니다.",
    "attack": "배틀로얄: 줄을 지워 상대에게 쓰레기 줄을 보내 서로 공격하는 모드 · 서바이벌: 서로 공격하지 않고 각자 끝까지 버티는 모드(K.O.·배지 없음, 3분 뒤부터 쓰레기 줄이 주기적으로 올라옴). 방을 열면 호스트의 설정이 모두에게 적용됩니다.",
    "name": "채팅, 대기실 명단, 미니 보드에 표시되는 이름입니다. 클릭하거나 Enter로 수정 (최대 16자).",
    "color": "이름 색: 채팅과 대기실 명단, 미니 보드의 내 이름에 쓰입니다.",
    "shake": "공격을 받거나 K.O.가 났을 때 화면이 흔들리는 정도입니다. 멀미가 나면 '약하게'나 '끔'을 고르세요.",
    "tips_replay": "처음 일어나는 일(받은 공격, 역습 보너스, 첫 K.O., 후반전)에 한 번씩 뜨는 도움말 팁과 첫 판 설명 말풍선을 다음 경기부터 다시 보여 줍니다.",
    "title": "달성한 업적의 이름을 칭호로 달 수 있습니다. 메인 메뉴의 프로필에 표시됩니다. 업적은 전적 기록실의 '업적' 탭에서 확인하세요.",
    "rules": "게임의 공격표, K.O. 배지, 역습 보너스, 조준 모드, 경기 흐름을 한 화면으로 보여 줍니다. 게임 중에도 F1 키로 열 수 있습니다.",
    "ghost": "켜면 혼자 하는 경기에서 저장된 내 리플레이 중 점수가 가장 높은 판의 보드가 왼쪽 상태 칸 아래에 작게 함께 달립니다. 같은 경기 시각의 그 판 점수와의 차이도 보여 줍니다. 리플레이가 없으면 아무것도 표시되지 않습니다.",
    "gamepad": "게임패드의 십자키/왼쪽 스틱으로 이동, A 시계 회전, B 반시계 회전, X·LB 홀드, Y 180도 회전, RB 하드 드롭, Start 일시정지, Back 조준 변경. 메뉴에서는 십자키/스틱 = 방향키, A·Start = Enter, B = Esc입니다. 동작에 배정된 키를 따르며, 컨트롤러가 이상하게 동작하면 끄세요.",
    "update": "켜면 게임을 시작할 때 GitHub에서 새 버전이 있는지 한 번만 확인하고, 있으면 메인 화면에 알려 줍니다. 자동으로 내려받거나 설치하지 않으며 개인 정보는 보내지 않습니다. 기본은 꺼짐입니다.",
    "errlog": "예기치 않은 오류가 났을 때 원인을 적어 두는 error.log가 있는 폴더를 엽니다. 문제를 알릴 때 이 파일을 함께 보내 주세요.",
    "matchlog": "켜면 경기가 끝날 때마다 받은/보낸 공격, 조준 변경, 탈락 원인을 담은 기록(JSON)을 저장 폴더의 match_logs에 남깁니다. 플레이 테스트 결과를 함께 볼 때 쓰며, 기본은 꺼짐입니다.",
    "fs": "창 모드와 전체 화면을 바꿉니다. F11 키로 언제든 전환할 수 있습니다.",
    "res": "창 크기를 고릅니다. 모니터에 들어가는 크기만 보이며 창 가장자리를 끌어서도 조절할 수 있습니다.",
    "res_off": "전체 화면에서는 모니터 해상도에 맞춰 자동으로 확대됩니다.",
    "mini": "자세히: 조작 중인 블록, 착지 위치, 홀드/다음 블록까지 표시 · 집중: 자세히와 같되 나를 노리는 상대, 내 조준 대상, 위기 카드만 또렷하게 · 간략: 쌓인 블록만 표시해 더 깔끔하고 가볍습니다.",
    "color_mode": "색약 보정은 블록 색을 밝기 차이가 큰 팔레트로 바꿉니다.",
    "text_size": "게임 화면과 메뉴·설정·로비의 작은 글씨를 키웁니다. 글자가 잘려 보이면 '보통'으로 돌리세요.",
    "key_hints": "게임 화면 아래의 조작 키 안내 바입니다. '처음 10판'은 익숙해지면 저절로 사라지고, '끔'은 화면이 더 넓어 보입니다. (T 설정/ESC는 그대로 사용 가능)",
    "announcer": "쿼드·T-스핀·콤보·퍼펙트 클리어·TOP 10·결승·골든 타깃 같은 큰 순간에 짧은 로봇 목소리가 외칩니다. 합성한 소리라 발음은 어설프며, 기본은 꺼짐입니다. 효과음이 꺼져 있으면 나오지 않습니다.",
    "warn": "피격 경보음과 위기 때 나는 심장 박동 소리만 따로 줄이거나 끕니다. 효과음 음량에는 영향이 없습니다.",
    "block_skin": "게임 화면 블록의 모양을 바꿉니다. 색은 위의 '블록 색상' 설정을 따르며, 로고와 미니 보드는 그대로입니다.",
    "bgm": "배경음악 켜기/끄기와 음량. 생존자가 줄수록(100인 → 50인 → 20인) 곡이 더 긴박해집니다.",
    "stage_bgm": "경기 중(1/2/3단계) 배경음 세트를 고릅니다. '랜덤'이면 경기를 시작할 때마다 5가지 중 하나가 무작위로 재생됩니다.",
    "sfx": "효과음 켜기/끄기와 음량. 음량을 바꾸면 바로 들어볼 수 있습니다.",
    "sfx_test": "현재 효과음 음량으로 대표 소리를 들어봅니다.",
    "preset": "조작키 묶음을 한 번에 바꿉니다. 아래 카드를 하나라도 바꾸면 '사용자 지정'이 됩니다.",
    "cards": "카드를 클릭하거나 Enter를 누른 뒤 새 키를 누르세요. 다른 동작이 쓰던 키면 자동으로 옮겨집니다. 고정 키: ESC 일시정지/메뉴 · F11 전체화면 · M 음소거 · T 설정",
    "rule_garbage": "상대에게 보내는 쓰레기 줄을 모두 이 배율로 곱합니다(올림). ×0.5는 느긋한 판, ×1.5는 거친 판입니다. 기본이 아니면 커스텀 경기라 전적/점수표/경험치에 기록되지 않습니다.",
    "rule_gravity": "내 블록이 자동으로 내려오는 속도를 바꿉니다(느리게 ×0.7 속도, 빠르게 ×1.4 속도). 봇의 속도는 그대로입니다. 기본이 아니면 기록되지 않습니다.",
    "rule_team": "팀전(2팀): 나와 같은 편 봇 절반은 서로 공격하지 않고, 상대 팀을 모두 탈락시키면 이깁니다. 같은 편은 초록 테두리로 표시됩니다. 혼자 하는 배틀로얄에서만 적용되고 기록되지 않습니다(4명 이상).",
    "rule_badges": "끄면 K.O.를 해도 배지로 공격력이 오르지 않습니다(봇도 마찬가지). 기본이 아니면 기록되지 않습니다.",
    "react_das": "DAS: 방향키를 누른 뒤 자동 반복이 시작되기까지의 지연입니다. 작을수록 빠르게 움직이며, 밑의 프레임은 60fps 기준 환산값입니다.",
    "react_arr": "ARR: 자동 반복 이동의 간격입니다. 0이면 벽이나 블록에 닿을 때까지 한 번에 이동합니다.",
    "react_sdf": "소프트드롭: 아래 키를 누를 때 한 칸 내려가는 간격입니다(작을수록 빠름). 0이면 바닥까지 즉시 내려가며, 고정은 락 딜레이를 따릅니다.",
    "react_dcd": "DCD: 새 블록이 나온 뒤 이 시간 동안은 누르고 있던 방향키의 DAS가 다시 충전되지 않습니다. 방향키를 누른 채 하드 드롭할 때 새 블록이 벽으로 날아가는 것을 막아 줍니다.",
    "react_dcancel": "방향을 바꿀 때(한쪽 키를 떼고 반대쪽 키가 눌려 있을 때) DAS를 새로 충전합니다. 켜면 방향 전환 직후의 오버슈트가 줄어듭니다.",
    "react_hpre": "느긋 · 기본 · 빠름 · 프로 중에서 DAS/ARR/소프트드롭/DCD/DAS 취소를 한 번에 맞춥니다. 값을 직접 바꾸면 '사용자'로 표시됩니다.",
    "rebinding": "새 키를 누르세요  ·  ESC 취소",
}

# 탭별 '기본값으로' 대상 설정 키
TAB_DEFAULT_KEYS = {
    "match": ["target_player_count", "bot_difficulty", "game_mode", "screen_shake", "language"],
    "help": ["match_log", "update_check", "ghost_race"],
    "general": ["resolution", "mini_detail", "color_mode", "text_size", "block_skin", "key_hints"],
    "audio": ["bgm_enabled", "bgm_volume", "bgm_stage_set", "sfx_enabled", "sfx_volume", "warn_volume", "announcer"],
    "keys": [],
    "react": ["das_ms", "arr_ms", "sdf_ms", "dcd_ms", "das_cancel", "gamepad"],
    "rules": ["rule_garbage", "rule_gravity", "rule_badges", "rule_team"],
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
                elif event.key in (pygame.K_m, pygame.K_F11):                  # 음소거/전체 화면은 앱이 먼저 가로채므로 조작키로 쓸 수 없음
                    self.sound_mgr.play('move')
                    self.rebind_notice = (f"{short_key_name(event.key)} 키는 {'음소거' if event.key == pygame.K_m else '전체 화면'} 전용이라 조작키로 쓸 수 없습니다", time.time() + 5.0)
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
            drag = getattr(self, "_vol_drag", None)
            if drag and event.buttons[0]:                                  # 음량 막대를 누른 채 끌면 따라 움직임
                which, rect = drag
                self._settings_set_volume(which, (event.pos[0] - rect.x) / max(1, rect.w), only_if_changed=True)
            elif drag:
                self._vol_drag = None
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._vol_drag = None
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
                        self._vol_drag = (btn_id[:3], rect.copy())
                    else:
                        self._settings_activate(btn_id)
                    break

    def _settings_set_volume(self, which, ratio, only_if_changed=False):
        value = max(0, min(100, int(round(ratio * 10)) * 10))
        if only_if_changed and self.settings.get("bgm_volume" if which == "bgm" else "sfx_volume") == value:
            return
        if which == "bgm":
            self.settings.set("bgm_volume", value)
            self.sound_mgr.set_bgm_volume(value / 100.0)
        else:
            self.settings.set("sfx_volume", value)
            self.sound_mgr.set_sfx_volume(value / 100.0)
        self.sound_mgr.play('move')

    def _open_error_log_folder(self):
        """error.log가 있는 폴더를 탐색기로 엶 (파일이 아직 없어도 폴더는 열림). 실패해도 게임에는 영향 없음"""
        try:
            import os
            from crash_log import log_path
            folder = os.path.dirname(os.path.abspath(log_path()))
            if hasattr(os, "startfile"):
                os.startfile(folder)
        except Exception:
            pass

    # ------------------------------------------------------------------ 키보드 탐색
    def _settings_focus_id(self):
        """키보드로 선택된 항목의 키 (행 키 또는 조작 탭의 카드/핸들링 ID)"""
        tab = self.settings_tab
        f = self.settings_focus.get(tab, 0)
        if tab == "keys":
            if f == PRESET_FOCUS:
                return "preset"
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
        """조작 탭: 키 카드 3열 + 프리셋 줄 (반응 속도는 '반응' 탭)"""
        n = KEY_CARDS
        f = self.settings_focus.get("keys", 0) % (n + 1)
        moved = True
        if f == PRESET_FOCUS:                                     # 프리셋 줄: ←→로 고르고 ↓로 카드로
            if key in (pygame.K_LEFT, pygame.K_RIGHT) or enter:
                self._settings_activate("preset_arcade" if key == pygame.K_LEFT else "preset_wasd" if key == pygame.K_RIGHT else
                                        ("preset_wasd" if self.settings.get("key_preset") == "arcade" else "preset_arcade"))
                moved = False
            elif key == pygame.K_DOWN:
                f = 0
            elif key == pygame.K_UP:
                f = n - 1
        else:                                                     # 카드
            if key == pygame.K_LEFT:
                f = (f - 1) % n
            elif key == pygame.K_RIGHT:
                f = (f + 1) % n
            elif key == pygame.K_UP:
                f = PRESET_FOCUS if f < 3 else f - 3
            elif key == pygame.K_DOWN:
                f = PRESET_FOCUS if f + 3 >= n else f + 3
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
        elif btn_id in ("das_dec", "das_inc", "arr_dec", "arr_inc", "sdf_dec", "sdf_inc", "dcd_dec", "dcd_inc"):
            self.sound_mgr.play('rotate')
            self.settings.adjust_handling(btn_id[:-4] + "_ms", -1 if btn_id.endswith("dec") else 1)
            self.apply_handling()
        elif btn_id in ("dcancel_dec", "dcancel_inc"):
            self.sound_mgr.play('rotate')
            self.settings.set("das_cancel", not self.settings.get("das_cancel"))
            self.apply_handling()
        elif btn_id in ("hpre_dec", "hpre_inc"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_handling_preset(-1 if btn_id.endswith("dec") else 1)
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
            other = {"mini_detail": ("detailed", "focus", "simple"), "color_mode": ("normal", "colorblind"), "text_size": ("normal", "large")}[name]
            new = value if value else other[(other.index(cur) + 1) % len(other)] if cur in other else other[0]      # 값이 없으면 (Enter) 다음 선택지로 순환
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set(name, new)
                if name == "mini_detail":
                    self.renderer.mini_detailed = (new != "simple")
                    self.renderer.mini_focus = (new == "focus")
                else:
                    self.apply_visual_options()
        elif btn_id in ("key_hints_prev", "key_hints_next", "key_hints"):
            opts = ("always", "novice", "off")
            cur = self.settings.get("key_hints", "always")
            i = opts.index(cur) if cur in opts else 0
            new = opts[(i + (-1 if btn_id == "key_hints_prev" else 1)) % len(opts)]
            self.sound_mgr.play('rotate')
            self.settings.set("key_hints", new)
        elif btn_id == "announcer_toggle":
            new = not self.settings.get("announcer", False)
            self.settings.set("announcer", new)
            self.sound_mgr.set_announcer(new)
            self.sound_mgr.play('rotate')
            if new:
                self.sound_mgr.play('vo_quad')
        elif btn_id in ("warn_prev", "warn_next"):
            opts = (100, 50, 0)
            cur = self.settings.get("warn_volume", 100)
            i = opts.index(cur) if cur in opts else 0
            new = opts[(i + (-1 if btn_id == "warn_prev" else 1)) % len(opts)]
            self.settings.set("warn_volume", new)
            self.sound_mgr.set_warn_scale(new / 100.0)
            self.sound_mgr.play('hit_2')
        elif btn_id in ("title_prev", "title_next"):
            ids = [""] + self.stats_mgr.achievements_done()
            cur = self.settings.get("title", "")
            i = ids.index(cur) if cur in ids else 0
            self.sound_mgr.play('rotate')
            self.settings.set("title", ids[(i + (-1 if btn_id == "title_prev" else 1)) % len(ids)])
        elif btn_id == "open_rules":
            self._open_rules()
        elif btn_id == "tips_replay":
            self.sound_mgr.play('rotate')
            if self.settings.get("tips_replay"):                         # 켜져 있으면 다시 눌러 끔: 첫 판 설명은 켜기 전 상태로 되돌림
                self.settings.set("tips_replay", False, autosave=False)
                self.settings.set("coach_done", bool(getattr(self, "_coach_done_before_replay", True)))
            else:
                self._coach_done_before_replay = bool(self.settings.get("coach_done"))
                self.settings.set("tips_seen", [], autosave=False)
                self.settings.set("tips_replay", True, autosave=False)
                self.settings.set("coach_done", False)
            self.tips_replay_notice_until = time.time() + 3.0
        elif btn_id in ("shake_prev", "shake_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_screen_shake(-1 if btn_id == "shake_prev" else 1)
            self.apply_gameplay_options()
        elif btn_id in ("skin_prev", "skin_next"):
            self.sound_mgr.play('rotate')
            self.settings.cycle_block_skin(-1 if btn_id == "skin_prev" else 1, available=__import__("stats_manager").unlocked_skin_ids(self.stats_mgr.data))      # 잠긴 스킨은 건너뜀
            self.apply_visual_options()
        # 게임 탭
        elif btn_id in ("attack=on", "attack=off", "attack_toggle"):
            cur = "battle" if self.settings.get("game_mode") != "survival" else "survival"
            picked = btn_id.split("=")[1] if "=" in btn_id else None
            new = ("battle" if picked == "on" else "survival") if picked else ("survival" if cur == "battle" else "battle")
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("game_mode", new)
        elif btn_id in ("rt=on", "rt=off", "rt_toggle"):
            self.sound_mgr.play('rotate')
            cur = bool(self.settings.get("rule_team", False))
            self.settings.set("rule_team", (btn_id.endswith("=on")) if "=" in btn_id else (not cur))
        elif btn_id in ("lang_prev", "lang_next", "lang=ko", "lang=en"):
            import i18n
            cur = self.settings.get("language", "ko")
            new = btn_id[5:] if "=" in btn_id else ("en" if cur == "ko" else "ko")
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("language", new)
                i18n.set_language(new)
                self.renderer.clear_visual_caches()                        # 번역된 글자 이미지 캐시를 비워 새 언어로 다시 그림
        elif btn_id in ("rg_prev", "rg_next", "rgr_prev", "rgr_next", "rb=on", "rb=off", "rb_toggle"):
            self.sound_mgr.play('rotate')
            if btn_id.startswith("rg_"):
                opts = ("half", "normal", "heavy")
                cur = self.settings.get("rule_garbage", "normal")
                self.settings.set("rule_garbage", opts[(opts.index(cur) + (-1 if btn_id == "rg_prev" else 1)) % 3])
            elif btn_id.startswith("rgr_"):
                opts = ("slow", "normal", "fast")
                cur = self.settings.get("rule_gravity", "normal")
                self.settings.set("rule_gravity", opts[(opts.index(cur) + (-1 if btn_id == "rgr_prev" else 1)) % 3])
            else:
                cur = bool(self.settings.get("rule_badges", True))
                self.settings.set("rule_badges", (btn_id.endswith("=on")) if "=" in btn_id else (not cur))
        elif btn_id in ("gamepad=on", "gamepad=off", "gamepad_toggle"):
            cur = bool(self.settings.get("gamepad", True))
            new = (btn_id.endswith("=on")) if "=" in btn_id else (not cur)
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("gamepad", new)
        elif btn_id in ("ghost=on", "ghost=off", "ghost_toggle"):
            cur = bool(self.settings.get("ghost_race", False))
            new = (btn_id.endswith("=on")) if "=" in btn_id else (not cur)
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("ghost_race", new)
        elif btn_id in ("update=on", "update=off", "update_toggle"):
            cur = bool(self.settings.get("update_check", False))
            new = (btn_id.endswith("=on")) if "=" in btn_id else (not cur)
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("update_check", new)
                if new:
                    self._start_update_check()
        elif btn_id == "open_errlog":
            self.sound_mgr.play('move')
            self._open_error_log_folder()
        elif btn_id in ("matchlog=on", "matchlog=off", "matchlog_toggle"):
            cur = bool(self.settings.get("match_log", False))
            new = (btn_id.endswith("=on")) if "=" in btn_id else (not cur)
            if new != cur:
                self.sound_mgr.play('rotate')
                self.settings.set("match_log", new)
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

    def _sync_language_and_audio(self):
        """초기화로 바뀐 언어/소리 설정을 실행 중인 상태(번역·사운드 매니저)에 즉시 반영"""
        import i18n
        i18n.set_language(self.settings.get("language", "ko"))
        self.renderer.clear_visual_caches()                              # 번역된 글자 이미지 캐시를 비워 새 언어로 다시 그림
        self.sound_mgr.set_warn_scale(self.settings.get("warn_volume", 100) / 100.0)
        self.sound_mgr.set_announcer(self.settings.get("announcer", False))

    def _reset_current_tab(self):
        """현재 탭의 설정만 기본값으로 되돌림"""
        tab = self.settings_tab
        self.sound_mgr.play('clear')
        self.settings.reset_values(TAB_DEFAULT_KEYS[tab])
        if tab == "match":
            self.target_player_count = self.settings.get("target_player_count")
            self.bot_difficulty = self.settings.get("bot_difficulty")
            self.apply_gameplay_options()
            self._sync_language_and_audio()
        elif tab == "general":
            self.renderer.mini_detailed = self.settings.get("mini_detail") != "simple"
            self.renderer.mini_focus = self.settings.get("mini_detail") == "focus"
            self.apply_visual_options()
            if not self.is_fullscreen:
                self._apply_window_size()
        elif tab == "audio":
            self.sound_mgr.set_bgm_enabled(self.settings.get("bgm_enabled"))
            self.sound_mgr.set_sfx_enabled(self.settings.get("sfx_enabled"))
            self.sound_mgr.set_bgm_volume(self.settings.get("bgm_volume") / 100.0)
            self.sound_mgr.set_sfx_volume(self.settings.get("sfx_volume") / 100.0)
            self._sync_language_and_audio()
        elif tab == "react":
            self.apply_handling()
        elif tab == "keys":                                              # 조작키는 '조작' 탭에서만 초기화 (규칙/기타 탭에서 눌러도 키 설정이 날아가지 않게)
            self.settings.reset_keys_to_default()
            self.apply_handling()
            self.rebinding_action = None

    def _do_reset_defaults(self):
        self.sound_mgr.play('clear')
        self.settings.reset_to_defaults()
        self.apply_handling()
        self.renderer.mini_detailed = True
        self.renderer.mini_focus = True
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
        self._sync_language_and_audio()
        self.target_player_count = self.settings.get("target_player_count")
        try:
            self.name_color = max(0, min(len(NAME_COLORS) - 1, int(self.settings.get("name_color", 0))))
        except (TypeError, ValueError):
            self.name_color = 0
        self.net_mgr.my_color = self.name_color

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
            from i18n import tr
            sub = tr(sub)                                       # 번역한 글자로 길이를 재고 줄임 (자른 한국어는 번역표와 맞지 않으므로)
            max_sub = 470                                       # 오른쪽 컨트롤과 겹치지 않게 긴 보조 줄은 줄임표로 (글자 크기 '크게'에서도)
            while len(sub) > 4 and self.font_help.size(sub)[0] > max_sub:
                sub = sub[:-2].rstrip(" ,·") + "…"
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
        lang = self.settings.get("language", "ko")
        self._s_row("language", y, 52, "언어 / Language", "The whole UI switches language; a few names (e.g. in saved data) stay as they were" if lang == "en" else "화면의 글이 모두 바뀝니다 (저장된 데이터 속 이름 등 일부는 그대로)")
        self._s_seg([("lang=ko", "한국어"), ("lang=en", "English")], "lang=" + lang, RIGHT, y + 26)
        y += 52
        # 참가 인원
        self._s_row("players", y, 56, "참가 인원", "2 ~ 100명  ·  부족한 인원은 AI 봇이 채웁니다")
        cy = y + 28
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
        y += 56
        # 봇 난이도 (설명은 현재 난이도에 따라 바뀌는 값이라 보조 줄로 유지)
        cur = self.settings.get("bot_difficulty", "mixed")
        dc = {"easy": C_GREEN, "normal": C_ACCENT, "hard": C_ORANGE, "master": C_DANGER, "mixed": C_GOLD}.get(cur, C_TEXT)
        cleared = self.stats_mgr.ladder_cleared("battle")            # 100인급 대전에서 10위 안에 들어 클리어한 난이도는 ★ 표시
        star = "  ★ 클리어" if cur in cleared else ""
        self._s_row("diff", y, 56, "AI 봇 난이도", BOT_DIFFICULTY_DESCS.get(cur, "") if not star else __import__("i18n").tr(BOT_DIFFICULTY_DESCS.get(cur, ""))[:40])
        self._s_cycler("diff_prev", "diff_next", BOT_DIFFICULTY_LABELS.get(cur, "혼합") + star, RIGHT, y + 28, color=dc)
        y += 56
        # 게임 모드: 배틀로얄(공격을 주고받음) / 서바이벌(공격 없이 각자 생존 경쟁)
        atk_on = self.settings.get("game_mode") != "survival"
        self._s_row("attack", y, 52, "게임 모드", "줄을 지워 서로 공격하는 모드" if atk_on else "서로 방해하지 않고 각자 끝까지 생존하는 모드")
        self._s_seg([("attack=on", "배틀로얄"), ("attack=off", "서바이벌")], "attack=on" if atk_on else "attack=off", RIGHT, y + 26)
        y += 52
        # 이름
        self._s_row("name", y, 52, "플레이어 이름 · 이니셜")
        ini_box = pygame.Rect(RIGHT - 232 - 12 - 84, y + 8, 84, 36)                 # 점수표에 올릴 이니셜 3글자 (이름 입력칸 왼쪽)
        self.text_rects["initials"] = ini_box
        ini_edit = (self.text_focus == "initials")
        pygame.draw.rect(self.screen, (11, 13, 24), ini_box, border_radius=10)
        pygame.draw.rect(self.screen, C_GOLD if ini_edit else COL_CTL_EDGE, ini_box, 2 if ini_edit else 1, border_radius=10)
        ini_txt = (getattr(self, "initials_input", "") + self.chat_comp) if ini_edit else self._initials()
        itr = self._t(ini_txt, self.font_val, C_GOLD, ini_box.centerx, ini_box.centery, "center")
        if ini_edit and int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_GOLD, (itr.right + 3, ini_box.y + 8, 2, ini_box.h - 16))
        box = pygame.Rect(RIGHT - 232, y + 8, 232, 36)
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
        if not ini_edit:
            self._t("이니셜", self.font_tiny, COL_SUB, ini_box.centerx, ini_box.y - 2, "midbottom")
        y += 52
        # 이름 색
        self._s_row("color", y, 52, "이름 색")
        size, gap = 26, 8
        self.color_rects = self._draw_color_swatches(RIGHT - (size * len(NAME_COLORS) + gap * (len(NAME_COLORS) - 1)), y + 13, size=size, gap=gap)
        y += 52
        shake = self.settings.get("screen_shake", "normal")
        self._s_row("shake", y, 52, "화면 흔들림", "쿼드/피격/K.O. 흔들림, 큰 순간의 번쩍임 (끔: 둘 다 없음)")
        self._s_cycler("shake_prev", "shake_next", SHAKE_LABELS.get(shake, "보통"), RIGHT, y + 26)
        y += 52
    def _render_tab_help(self):
        y = TOP
        done_ids = self.stats_mgr.achievements_done()
        cur_title = self.settings.get("title", "")
        title_name = next((a[1] for a in __import__("stats_manager").ACHIEVEMENTS if a[0] == cur_title and cur_title in done_ids), "없음")
        self._s_row("title", y, 50, "칭호", f"달성한 업적 {len(done_ids)}개 중에서 선택 (메인 메뉴 프로필에 표시)")
        self._s_cycler("title_prev", "title_next", title_name, RIGHT, y + 25, enabled=bool(done_ids), color=C_GOLD)
        y += 50
        self._s_row("rules", y, 50, "규칙 요약 보기", "공격표 · 배지 · 역습 보너스 · 조준 모드 (게임 어디서든 F1)")
        self._s_btn("open_rules", pygame.Rect(RIGHT - 200, y + 7, 200, 36), "규칙 카드 열기", True)
        y += 50
        tips_on = bool(self.settings.get("tips_replay"))                  # 켜 두면 다음 경기부터 팁이 다시 나옴 (다 본 뒤 저절로 꺼짐)
        self._s_row("tips_replay", y, 50, "도움말 팁 다시 보기", "다음 경기부터 팁과 첫 판 설명을 다시 표시 (켠 뒤 다시 누르면 끔)" if tips_on else "첫 판 설명과 상황별 팁을 다음 경기부터 다시 표시")
        self._s_btn("tips_replay", pygame.Rect(RIGHT - 200, y + 7, 200, 36), "켜짐 · 누르면 끔" if tips_on else "다시 보기", True, color=C_GREEN if tips_on else None)
        y += 50
        log_on = bool(self.settings.get("match_log", False))
        self._s_row("matchlog", y, 50, "경기 기록 저장", "테스트용: 경기마다 JSON 기록을 남김")
        self._s_seg([("matchlog=off", "끔"), ("matchlog=on", "켜기")], "matchlog=on" if log_on else "matchlog=off", RIGHT, y + 25)
        y += 50
        gh_on = bool(self.settings.get("ghost_race", False))
        from replay import load_replays_cached, best_replay
        _b = best_replay(load_replays_cached(), mode="battle")
        self._s_row("ghost", y, 50, "고스트 레이스", (f"내 최고 판({_b['score']:,}점)이 경기 옆에 함께 달립니다 (혼자 하는 경기)" if _b else "내 최고 판이 경기 옆에 함께 달립니다 (아직 저장된 리플레이 없음)"))
        self._s_seg([("ghost=off", "끔"), ("ghost=on", "켜기")], "ghost=on" if gh_on else "ghost=off", RIGHT, y + 25)
        y += 50
        up_on = bool(self.settings.get("update_check", False))
        upd = self.update_info()
        self._s_row("update", y, 50, "업데이트 확인", f"새 버전 {upd['tag']} 이(가) 있습니다" if upd else "시작할 때 새 버전이 있는지 한 번 확인 (자동 설치 없음)")
        self._s_seg([("update=off", "끔"), ("update=on", "켜기")], "update=on" if up_on else "update=off", RIGHT, y + 25)
        y += 50
        self._s_row("errlog", y, 50, "오류 기록", "문제를 알릴 때 error.log를 함께 보내 주세요")
        self._s_btn("open_errlog", pygame.Rect(RIGHT - 200, y + 7, 200, 36), "error.log 폴더 열기", True)
        y += 50 + 10
        self._t("F1: 규칙 요약  ·  T: 게임 중 설정  ·  M: 소리 켜고 끄기  ·  F11: 전체 화면", self.font_help, COL_SUB, IX + 22, y)

    def _render_tab_general(self):
        y = TOP
        fs = self.is_fullscreen
        size = pygame.display.get_surface().get_size() if pygame.display.get_surface() else (0, 0)
        self._s_row("fs", y, 52, "화면 모드", f"현재 {size[0]}×{size[1]}  ·  F11 키로도 전환")
        self._s_seg([("fs=window", "창 모드"), ("fs=full", "전체 화면")], "fs=full" if fs else "fs=window", RIGHT, y + 26)
        y += 52
        res = self.settings.get("resolution", "auto")
        res_label = "자동 (모니터에 맞춤)" if res == "auto" else res.replace("x", " × ") + {
            "1280x720": "  (HD)", "1920x1080": "  (FHD)", "2560x1440": "  (QHD)", "3840x2160": "  (4K)"}.get(res, "")
        self._s_row("res", y, 52, "창 해상도", "전체 화면에서는 사용하지 않습니다" if fs else None)
        self._s_cycler("res_prev", "res_next", res_label, RIGHT, y + 26, enabled=not fs)
        y += 52
        self._s_row("mini", y, 52, "미니 보드", "상대 보드에 표시할 정보의 양")
        self._s_seg([("mini_detail=detailed", "자세히"), ("mini_detail=focus", "집중"), ("mini_detail=simple", "간략")],
                    "mini_detail=" + (self.settings.get("mini_detail") if self.settings.get("mini_detail") in ("detailed", "focus", "simple") else "focus"), RIGHT, y + 26)
        y += 52
        skin = self.settings.get("block_skin", "classic")
        _sm = __import__("stats_manager")
        if skin not in _sm.unlocked_skin_ids(self.stats_mgr.data):
            skin = "classic"                                                 # 저장된 스킨이 (전적 초기화 등으로) 잠겼다면 기본으로 표시
        locked = _sm.locked_skin_hints(self.stats_mgr.data)
        HELP["block_skin"] = _tr(HELP_SKIN_BASE) + (_tr("  잠긴 스킨: ") + ", ".join(f"{_tr(BLOCK_SKIN_LABELS[s].split(' (')[0])}({_tr(d)})" for s, d in locked) if locked else "")
        self._s_row("block_skin", y, 52, "블록 스킨", BLOCK_SKIN_DESCS.get(skin, ""))
        self._s_cycler("skin_prev", "skin_next", BLOCK_SKIN_LABELS.get(skin, "클래식"), RIGHT, y + 26, color=C_GOLD)
        px = RIGHT - 328 - 16 - 7 * 22                            # 현재 스킨으로 그린 7종 블록 미리보기 (설명과 선택기 사이)
        for i, piece in enumerate("IOTSZJL"):
            self.screen.blit(self.renderer._cell_surface(piece, 20), (px + i * 22, y + 16))
        y += 52
        self._s_section("접근성", y)
        y += 24
        self._s_row("color_mode", y, 52, "블록 색상", "색약 보정: 밝기 차이가 큰 팔레트")
        self._s_seg([("color_mode=normal", "기본"), ("color_mode=colorblind", "색약 보정")],
                    "color_mode=colorblind" if self.settings.get("color_mode") == "colorblind" else "color_mode=normal", RIGHT, y + 26)
        y += 52
        self._s_row("text_size", y, 52, "글자 크기", "게임·메뉴·설정의 작은 글씨")
        self._s_seg([("text_size=normal", "보통"), ("text_size=large", "크게")],
                    "text_size=large" if self.settings.get("text_size") == "large" else "text_size=normal", RIGHT, y + 26)
        y += 52
        kh = self.settings.get("key_hints", "always")
        self._s_row("key_hints", y, 52, "조작 안내 바", "게임 화면 아래 키 안내")
        self._s_cycler("key_hints_prev", "key_hints_next", {"always": "항상 표시", "novice": "처음 10판만", "off": "끔"}.get(kh, "항상 표시"), RIGHT, y + 26)

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
        y += 56
        wv = self.settings.get("warn_volume", 100)
        self._s_row("warn", y, 56, "경고음 크기", "피격 경보 · 심장 박동")
        self._s_cycler("warn_prev", "warn_next", {100: "보통", 50: "작게", 0: "끔"}.get(wv, "보통"), RIGHT, y + 28, enabled=sfx_on)
        y += 56
        self._s_row("announcer", y, 52, "아나운서 콜", "큰 순간에 로봇 목소리 외침 (합성음)")
        self._s_switch("announcer_toggle", bool(self.settings.get("announcer", False)), RIGHT - 70, y + 26)
        y += 52 + 8
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

        card_w, card_h, gap = 282, 54, 7
        n_rows = (len(ACTION_NAMES) + 2) // 3
        self._row_rects["cards"] = pygame.Rect(IX, y, IW, n_rows * card_h + (n_rows - 1) * gap)
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
            self._t(act_name.split(" (")[0], self.font_val, COL_TEXT, rect.x + 16, rect.y + 6)
            if rebinding:
                self._t("새 키를 누르세요…", self.font_val, C_GOLD, rect.x + 16, rect.y + 28)
                self._t("ESC 취소", self.font_tiny, COL_SUB, rect.right - 12, rect.y + 12, "topright")
            else:
                kx = rect.x + 16
                if not self.settings.get_action_keys(act_id):
                    self._t("지정 안 됨 (클릭해서 지정)", self.font_tiny, COL_OFF, rect.x + 16, rect.y + 39, "midleft")
                for kc in self.settings.get_action_keys(act_id)[:3]:
                    ks = self.renderer._text(short_key_name(kc), self.font_val, (225, 232, 248))
                    kr = pygame.Rect(kx, rect.y + 28, max(32, ks.get_width() + 18), 22)
                    pygame.draw.rect(self.screen, (44, 54, 86), kr, border_radius=7)
                    pygame.draw.rect(self.screen, (92, 108, 150), kr, 1, border_radius=7)
                    self.screen.blit(ks, (kr.centerx - ks.get_width() // 2, kr.centery - ks.get_height() // 2))
                    kx = kr.right + 6
                if is_conflict:
                    self._t("중복", self.font_tiny, C_DANGER, rect.right - 12, rect.y + 12, "topright")
        y += n_rows * card_h + (n_rows - 1) * gap + 6
        # 키를 옮겼다는 알림 (몇 초간)
        notice = getattr(self, "rebind_notice", None)
        if notice and time.time() < notice[1]:
            self._t(notice[0], self.font_help, C_GOLD, IX + IW // 2, y + 8, "midtop")
        elif conflicts:
            self._t("같은 키가 여러 동작에 배정되어 있습니다. 빨간 카드를 다시 지정하세요.", self.font_help, C_DANGER, IX + IW // 2, y + 8, "midtop")
        y += 22
        self._t("반응 속도(DAS · ARR · 소프트드롭 · DCD · 프리셋)는 위쪽의 '반응' 탭에서 바꿉니다.", self.font_help, COL_SUB, IX + IW // 2, y + 6, "midtop")

    def _render_tab_rules(self):
        """규칙 탭(커스텀 규칙): 혼자 하는 배틀로얄에서 쓰레기 배율 / 내 낙하 속도 / 배지를 바꿈. 기본이 아니면 기록되지 않는 경기가 됨"""
        st = self.settings
        y = TOP
        g, v, b = st.get("rule_garbage", "normal"), st.get("rule_gravity", "normal"), bool(st.get("rule_badges", True))
        self._s_row("rule_garbage", y, 56, "쓰레기 줄 배율", "상대에게 보내는 쓰레기 줄에 곱함 (올림)")
        self._s_cycler("rg_prev", "rg_next", {"half": "×0.5 (느긋하게)", "normal": "×1 (기본)", "heavy": "×1.5 (거칠게)"}[g], RIGHT, y + 28, color=C_ACCENT if g != "normal" else None)
        y += 56
        self._s_row("rule_gravity", y, 56, "내 낙하 속도", "블록이 자동으로 내려오는 속도 (봇은 그대로)")
        self._s_cycler("rgr_prev", "rgr_next", {"slow": "느리게 (×0.7)", "normal": "기본", "fast": "빠르게 (×1.4)"}[v], RIGHT, y + 28, color=C_ACCENT if v != "normal" else None)
        y += 56
        self._s_row("rule_badges", y, 56, "K.O. 배지 보너스", "끄면 K.O.를 해도 공격력이 오르지 않음")
        self._s_seg([("rb=on", "켜기"), ("rb=off", "끔")], "rb=on" if b else "rb=off", RIGHT, y + 28)
        y += 56
        team = bool(st.get("rule_team", False))
        self._s_row("rule_team", y, 56, "팀전 (2팀)", "같은 편은 공격하지 않고 상대 팀을 모두 탈락시키면 승리")
        self._s_seg([("rt=off", "끔"), ("rt=on", "켜기")], "rt=on" if team else "rt=off", RIGHT, y + 28)
        y += 56 + 12
        custom = (g, v, b) != ("normal", "normal", True) or team
        self._t("커스텀 경기: 전적 · 점수표 · 경험치에 기록되지 않습니다 (혼자 하는 배틀로얄에만 적용)" if custom else
                "모두 기본값입니다. 바꾸면 '커스텀 경기'가 되어 기록되지 않습니다 (혼자 하는 배틀로얄에만 적용)",
                self.font_help, C_GOLD if custom else COL_SUB, IX + 22, y)

    def _render_tab_react(self):
        """반응 탭: DAS/ARR/소프트드롭/DCD/DAS 취소/프리셋을 다른 탭과 같은 '행' 모양(라벨 + 설명 + 값 조절)으로"""
        from settings_manager import handling_preset_name
        st = self.settings
        y = TOP
        das, arr, sdf, dcd = st.get("das_ms"), st.get("arr_ms"), st.get("sdf_ms"), st.get("dcd_ms")
        cancel = bool(st.get("das_cancel"))
        cur_name = handling_preset_name(das, arr, sdf, dcd, cancel)
        rows = [
            ("react_das", "DAS 지연", f"누른 뒤 자동 반복까지 · 약 {das * 0.06:.1f}프레임 (60fps 기준)", "das_dec", "das_inc", f"{das}ms"),
            ("react_arr", "ARR 반복", "자동 반복 간격 · " + ("벽까지 즉시 이동" if arr == 0 else f"약 {arr * 0.06:.1f}프레임"), "arr_dec", "arr_inc", "즉시" if arr == 0 else f"{arr}ms"),
            ("react_sdf", "소프트드롭", "아래 키를 누를 때 내려가는 간격 · " + ("바닥까지 즉시" if sdf == 0 else "숫자가 작을수록 빠름"), "sdf_dec", "sdf_inc", "즉시" if sdf == 0 else f"{sdf}ms"),
            ("react_dcd", "DCD 지연", "새 블록 뒤 DAS 재충전을 막는 시간 (오버슈트 방지)", "dcd_dec", "dcd_inc", "끔" if dcd == 0 else f"{dcd}ms"),
            ("react_dcancel", "방향 전환 시 DAS 취소", "방향을 바꿀 때 DAS를 새로 충전", "dcancel_dec", "dcancel_inc", "켬" if cancel else "끔"),
            ("react_hpre", "반응 프리셋", "느긋 · 기본 · 빠름 · 프로를 한 번에 적용", "hpre_dec", "hpre_inc", "사용자" if cur_name == "사용자 지정" else cur_name),
        ]
        for key, label, desc, dec, inc, text in rows:
            self._s_row(key, y, 56, label, desc)
            on_col = C_ACCENT if text not in ("끔", "사용자") else COL_SUB
            self._s_cycler(dec, inc, text, RIGHT, y + 28, color=on_col)
            y += 56
        pad_on = bool(self.settings.get("gamepad", True))
        npad = len(self.gamepad.joys) + len(self.gamepad.ctrls)
        self._s_row("gamepad", y, 50, "게임패드", f"연결된 컨트롤러 {npad}개  ·  십자키/스틱 이동, A·B 회전" if npad else "연결된 컨트롤러 없음  ·  연결하면 바로 사용할 수 있습니다")
        self._s_seg([("gamepad=off", "끔"), ("gamepad=on", "켜기")], "gamepad=on" if pad_on else "gamepad=off", RIGHT, y + 25)
        y += 50

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
        tab_w, tab_gap = (IW - (len(TABS) - 1) * 8) // len(TABS), 8
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
         "audio": self._render_tab_audio, "keys": self._render_tab_keys, "react": self._render_tab_react, "rules": self._render_tab_rules, "help": self._render_tab_help}[self.settings_tab]()

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
                key = "react_das"
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
        from i18n import tr
        text = tr(text)                                                    # 번역한 글자로 나눔
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
