"""
Block Royale 100 - Settings Manager
게임 환경 설정(전체화면, 봇 지능, BGM/SFX 음량 및 활성화, 조작키 커스텀)을 관리하고 settings.json에 영구 저장합니다.
"""

import os
import re
import copy
import json
import pygame

from app_paths import data_path

SETTINGS_FILE = data_path("settings.json")

# 창 모드 해상도 옵션 ("auto" = 모니터에 맞춤). 내부 렌더링은 항상 1366x768이며 창 크기에 맞춰 확대됩니다.
RESOLUTION_OPTIONS = ["auto", "1280x720", "1366x768", "1600x900", "1920x1080", "2560x1440", "3840x2160"]

BOT_DIFFICULTY_OPTIONS = ["mixed", "easy", "normal", "hard", "master"]
BOT_DIFFICULTY_LABELS = {
    "mixed": "혼합 (배틀로얄 권장)",
    "easy": "쉬움 (입문자 / 초보)",
    "normal": "보통 (표준 대전)",
    "hard": "어려움 (베테랑 고수)",
    "master": "마스터 (초인공지능 AI)"
}

BOT_DIFFICULTY_DESCS = {
    "mixed": "초보부터 고수까지 다양한 실력의 100인 AI가 고루 섞여 등장합니다.",
    "easy": "AI의 반응 속도가 여유롭고 실수가 잦아 블록 퍼즐 입문자에게 적합합니다.",
    "normal": "자연스러운 속도와 적절한 판단력을 갖춘 균형 잡힌 표준 AI입니다.",
    "hard": "빠른 라인 빌드와 낮은 실수율을 자랑하는 강력한 토너먼트급 AI입니다.",
    "master": "인간의 한계를 넘나드는 초고속 연타와 2% 미만 오차율의 극강 AI입니다."
}

# 스테이지(인게임 전투) 배경음 세트: "random"이면 매 판 시작할 때마다 5세트 중 하나를 무작위로 고름
BGM_STAGE_SET_OPTIONS = ["random", "0", "1", "2", "3", "4"]
BGM_STAGE_SET_LABELS = {
    "random": "랜덤 (매판 다른 곡)",
    "0": "Cyber Rush (오리지널)",
    "1": "Neon Circuit",
    "2": "Pulse Overdrive",
    "3": "Chrome Requiem",
    "4": "Vector Surge",
}
BGM_STAGE_SET_DESCS = {
    "random": "경기를 시작할 때마다 5가지 세트 중 하나가 무작위로 선택됩니다.",
    "0": "오리지널 3부작: Cyber Rush → Hyperdrive Override → Apex Protocol",
    "1": "Neon Circuit → Circuit Breaker → Overclock",
    "2": "Pulse Overdrive → Redline → Terminal Velocity",
    "3": "Chrome Requiem → Ghost Protocol → Blackout Surge",
    "4": "Vector Surge → Quantum Drift → Singularity",
}

TARGET_MODE_OPTIONS = ("AUTO", "KO", "ATTACKERS", "BADGES", "RANDOM")      # config.TARGET_MODES와 같아야 함 (테스트로 확인)
SHAKE_OPTIONS = ("off", "low", "normal")
SHAKE_SCALE = {"off": 0.0, "low": 0.4, "normal": 1.0}
SHAKE_LABELS = {"off": "끔", "low": "약하게", "normal": "보통"}
RUMBLE_SCALE = {"off": 0.0, "low": 0.5, "normal": 1.0}      # 패드 진동 세기 (화면 흔들림 설정과 따로)

# 블록 스킨: 게임 화면의 블록 모양 (색은 색상 모드 설정을 따름)
BLOCK_SKIN_OPTIONS = ["classic", "neon", "flat", "jelly", "pixel", "glass", "starlight", "ember", "prism"]      # pixel/glass/starlight/ember/prism은 해금 스킨 (stats_manager.SKIN_UNLOCKS)
BLOCK_SKIN_LABELS = {
    "classic": "클래식",
    "neon": "네온",
    "flat": "플랫",
    "jelly": "젤리",
    "pixel": "픽셀 (해금)",
    "glass": "유리 (해금)",
    "starlight": "별빛 (해금)",
    "ember": "불씨 (해금)",
    "prism": "프리즘 (해금)",
}
BLOCK_SKIN_DESCS = {
    "classic": "입체감 있는 기본 블록",
    "neon": "테두리가 빛나는 블록",
    "flat": "깔끔한 단색 블록",
    "jelly": "둥글고 윤기 나는 블록",
    "pixel": "8비트 느낌의 각진 픽셀 블록",
    "glass": "투명하게 비치는 유리 블록",
    "starlight": "어두운 몸통에 별이 반짝이는 블록",
    "ember": "식어 가는 숯불처럼 속에서 불씨가 타는 블록",
    "prism": "빛을 받아 면마다 밝기가 다른 보석 블록",
}

# 기본 조작키 프리셋
KEY_PRESETS = {
    "arcade": {
        "move_left": [pygame.K_LEFT],
        "move_right": [pygame.K_RIGHT],
        "soft_drop": [pygame.K_DOWN],
        "hard_drop": [pygame.K_SPACE],
        "rotate_cw": [pygame.K_UP, pygame.K_x],
        "rotate_ccw": [pygame.K_z],
        "hold": [pygame.K_c, pygame.K_LSHIFT],
        "target_cycle": [pygame.K_TAB],
        "pause": [pygame.K_p],
        "rotate_180": []
    },
    "wasd": {
        "move_left": [pygame.K_a],
        "move_right": [pygame.K_d],
        "soft_drop": [pygame.K_s],
        "hard_drop": [pygame.K_SPACE, pygame.K_w],
        "rotate_cw": [pygame.K_k, pygame.K_UP],
        "rotate_ccw": [pygame.K_j],
        "hold": [pygame.K_l, pygame.K_LSHIFT],
        "target_cycle": [pygame.K_TAB],
        "pause": [pygame.K_p],
        "rotate_180": []
    },
    # 게임패드 프리셋: 키보드는 아케이드와 같고(보조), 패드 버튼이 이 키들을 누른 것처럼 동작함. 키 안내는 패드 버튼으로 표시. 180도 회전(패드 R3)만 키 A를 배정
    "gamepad": {
        "move_left": [pygame.K_LEFT],
        "move_right": [pygame.K_RIGHT],
        "soft_drop": [pygame.K_DOWN],
        "hard_drop": [pygame.K_SPACE],
        "rotate_cw": [pygame.K_UP, pygame.K_x],
        "rotate_ccw": [pygame.K_z],
        "hold": [pygame.K_c, pygame.K_LSHIFT],
        "target_cycle": [pygame.K_TAB],
        "pause": [pygame.K_p],
        "rotate_180": [pygame.K_a]
    }
}

ACTION_NAMES = [
    ("move_left", "좌로 이동"),
    ("move_right", "우로 이동"),
    ("soft_drop", "소프트 드롭 (가속)"),
    ("hard_drop", "하드 드롭 (즉시낙하)"),
    ("rotate_cw", "시계방향 회전"),
    ("rotate_ccw", "반시계 회전"),
    ("hold", "홀드 (블록 보관)"),
    ("target_cycle", "타겟 모드 순환"),
    ("pause", "일시 정지"),
    ("rotate_180", "180도 회전 (선택)"),
]

DEFAULT_SETTINGS = {
    "fullscreen": False,
    "resolution": "auto",         # 첫 실행 기본값: 자동(모니터 작업 영역에 맞춤). 예전 저장값(1280x720 등)은 그대로 유지됨
    "bot_difficulty": "mixed",
    "bgm_enabled": True,
    "bgm_volume": 60,      # 0 ~ 100
    "bgm_stage_set": "random",   # 스테이지 배경음 세트: "random" 또는 "0"~"4"
    "sfx_enabled": True,
    "sfx_volume": 70,      # 0 ~ 100
    "target_player_count": 100,
    "name_color": 0,             # 이름 색상 (config.NAME_COLORS 번호)
    "player_name": "",           # 플레이어 이름 (비어 있으면 Player_1)
    "initials": "",              # 점수표에 올릴 이니셜 3글자 (비어 있으면 이름의 앞 3글자)
    "room_name": "",             # 호스트가 정한 방 제목 (비어 있으면 "<이름>의 방")
    "last_host": "",             # 방 참가에서 마지막으로 입력한 주소 (ip 또는 ip:포트)
    "recent_hosts": [],          # 최근 접속한 주소 목록 (최신순, 최대 6개)
    "das_ms": 135,               # 좌우 이동 자동 반복 시작까지의 지연 (DAS, ms)
    "arr_ms": 33,                # 자동 반복 간격 (ARR, ms)
    "sdf_ms": 35,                # 소프트 드롭 낙하 간격 (ms, 작을수록 빠름, 0 = 즉시 바닥까지)
    "dcd_ms": 0,                 # DAS 충전 지연 (DCD, ms): 새 블록이 나온 뒤 이 시간 동안은 누르고 있던 방향키의 DAS가 다시 충전되지 않음 (0 = 끔)
    "das_cancel": False,         # 방향을 바꿀 때(한쪽 키를 떼고 반대쪽이 눌려 있을 때) DAS 충전을 취소할지
    "color_mode": "normal",      # 블록 색상: "normal"(기본) / "colorblind"(색약 보정)
    "text_size": "normal",       # 글자 크기: "normal"(보통) / "large"(크게) - 게임 화면과 메뉴/설정/로비의 작은 글씨에 적용
    "key_hints": "always",       # 게임 화면 아래 조작 안내 바: "always"(항상) / "novice"(처음 10판만) / "off"(끔)
    "language": "ko",            # 화면 글자 언어: "ko"(한국어) / "en"(English, 1단계: 메뉴·설정·HUD·결과 창 위주)
    "rule_garbage": "normal",    # 커스텀 규칙: 쓰레기 줄 배율 "half"(x0.5) / "normal"(x1) / "heavy"(x1.5)
    "rule_gravity": "normal",    # 커스텀 규칙: 내 낙하 속도 "slow"(x0.7) / "normal" / "fast"(x1.4)
    "rule_team": False,          # 커스텀 규칙: 팀전(2팀). 나와 같은 편 봇은 서로 공격하지 않고, 상대 팀이 모두 탈락하면 이김 (혼자 하는 배틀로얄만, 기록 안 함)
    "rule_badges": True,         # 커스텀 규칙: K.O. 배지 공격력 보너스 (끄면 K.O.를 해도 공격력이 오르지 않음)
    "ghost_race": False,         # 고스트 레이스: 내 최고 점수 판(저장된 리플레이)의 보드를 경기 옆에 같은 시간 흐름으로 보여 줌 (혼자 하는 경기만)
    "gamepad": True,             # 게임패드 입력 사용 (십자키/스틱/버튼을 키 입력처럼 처리)
    "announcer": False,          # 로봇 아나운서 외침 (쿼드/T-스핀/콤보/퍼펙트/TOP 10/현상금 등 큰 순간에만, 기본 끔)
    "warn_volume": 100,          # 경고음(피격 경보/심장 박동) 상대 음량 0~100 (효과음 음량에 곱해짐)
    "tips_seen": [],             # 이미 보여 준 첫 경험 팁 id 목록 (설정에서 다시 보기로 비움)
    "title": "",                 # 칭호: 달성한 업적 id 중 하나(메인 메뉴 프로필에 표시), 비어 있으면 없음
    "drill_best": 0,             # 연습 모드 압박 드릴에서 가장 오래 버틴 시간(초)
    "tips_replay": False,        # 팁 다시 보기를 눌렀다면 True: 숙련자(10판 이상)에게도 아직 안 본 팁을 보여 줌 (다 보면 꺼짐)
    "screen_flash": True,        # 큰 순간(쿼드/퍼펙트/K.O.)의 화면 번쩍임: 화면 흔들림 설정과 따로 끌 수 있음 (빛에 민감한 경우)
    "board_skyline": False,      # 메인 보드의 지형 윤곽선(쌓인 블록 윗면을 따라 밝은 선): 기본은 꺼짐
    "block_skin": "classic",     # 블록 모양: BLOCK_SKIN_OPTIONS 중 하나
    "match_log": False,          # 사람 테스트용 경기 로그를 저장할지 (경기마다 JSON 한 개, 기본 끔)
    "onboard_done": False,       # 첫 실행 기본값(50인 쉬움 봇)을 이미 적용했는지. 전적이 있는 사용자는 설정을 바꾸지 않고 표시만 함
    "coach_done": False,         # 첫 경기 코치 마크(핵심 HUD 3곳 설명)를 이미 보여줬는지
    "target_mode": "AUTO",       # 마지막으로 쓴 조준 모드 (다음 경기도 이어서 사용): TARGET_MODE_OPTIONS 중 하나
    "visual_fx": "normal",       # 빛 연출: "min"(최소: 빛 번짐/움직임/박자 연출 없음, 정지된 배경 장식만) / "normal"(보통: 빛 번짐·불씨) / "fancy"(화려하게: 박자 맞춤 맥동·더 많은 효과)
    "pad_rumble": "normal",      # 패드 진동: "off"(끔) / "low"(약하게) / "normal"(보통). 화면 흔들림을 꺼도 진동은 따로 유지할 수 있음
    "screen_shake": "normal",    # 화면 흔들림: "off"(끔) / "low"(약하게) / "normal"(보통)
    "game_mode": "battle",       # 게임 모드: "battle"(배틀로얄: 공격을 주고받음) / "survival"(서바이벌: 공격 없이 각자 생존 경쟁)
    "mini_detail": "focus",      # 미니 보드 표시: "detailed"(자세히) / "focus"(자세히 + 나를 노리는/조준/위기 카드만 또렷하게) / "simple"(간략)
    "pad_buttons": None,             # 게임패드 버튼 배치: {동작: [버튼 이름, ...]} (None이면 기본 배치. gamepad.DEFAULT_PAD_MAP)
    "key_preset": "arcade",        # "arcade"(아케이드 표준) / "wasd" / "gamepad"(게임패드) / "custom"(키를 직접 바꾼 경우)
    "custom_keys": None
}

HANDLING_LIMITS = {"das_ms": (17, 300, 10), "arr_ms": (0, 100, 5), "sdf_ms": (0, 100, 5), "dcd_ms": (0, 200, 10)}    # (최소, 최대, 큰 단계). ARR 0 = 끝까지 즉시 이동, 소프트드롭 0 = 바닥까지 즉시

# 반응 속도 프리셋: (이름, DAS, ARR, 소프트드롭, DCD, 방향 전환 시 DAS 취소). 설정 화면에서 한 번에 바꿈
HANDLING_PRESETS = [
    ("느긋", 167, 50, 60, 0, False),
    ("기본", 135, 33, 35, 0, False),
    ("빠름", 100, 17, 10, 0, True),
    ("프로", 83, 0, 0, 0, True),
]


def handling_preset_name(das, arr, sdf, dcd, cancel):
    """현재 값이 프리셋과 똑같으면 그 이름, 아니면 '사용자 지정'"""
    for name, d, a, s, c, x in HANDLING_PRESETS:
        if (d, a, s, c, x) == (das, arr, sdf, dcd, cancel):
            return name
    return "사용자 지정"


def handling_step(key, value, down):
    """DAS/ARR/소프트드롭을 한 번에 바꾸는 크기: 정밀하게 조절하는 구간은 잘게 (DAS 200ms 이하는 5, ARR/소프트드롭 10ms 이하는 1), 그 밖은 크게"""
    if key == "dcd_ms":
        return 10
    if key == "das_ms":
        return 5 if (value < 200 or (value == 200 and down)) else 10
    return 1 if (value < 10 or (value == 10 and down)) else 5


def _backup_corrupt(path):
    """읽을 수 없는 저장 파일은 덮어쓰기 전에 옆에 백업해 둠 (전적/설정 영구 손실 방지)"""
    try:
        import shutil
        import time as _t
        shutil.copy2(path, f"{path}.corrupt-{int(_t.time())}")
    except Exception:
        pass


def _valid_setting(key, value):
    """저장된 설정 값이 기본값과 같은 타입/허용 범위인지 검사. 맞지 않으면 (False, None)"""
    default = DEFAULT_SETTINGS[key]
    if key == "custom_keys":
        if value is None:
            return True, None
        if isinstance(value, dict) and all(
                isinstance(k, str) and isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v)
                for k, v in value.items()):
            return True, value
        return False, None
    if key == "pad_buttons":
        return (value is None or isinstance(value, dict)), (value if (value is None or isinstance(value, dict)) else None)
    if key == "resolution":
        ok = isinstance(value, str) and (value == "auto" or re.fullmatch(r"\d{3,5}x\d{3,5}", value) is not None)
        return ok, (value if ok else None)
    if isinstance(default, bool):
        return (isinstance(value, bool), value)
    if isinstance(default, int):
        if not isinstance(value, int) or isinstance(value, bool):
            return False, None
        if key in ("bgm_volume", "sfx_volume", "warn_volume"):
            value = max(0, min(100, value))
        elif key == "target_player_count":
            value = max(2, min(100, value))
        elif key == "drill_best":
            value = max(0, min(86400, value))
        elif key == "name_color":
            from config import NAME_COLORS
            value = max(0, min(len(NAME_COLORS) - 1, value))
        elif key in HANDLING_LIMITS:
            lo, hi, _step = HANDLING_LIMITS[key]
            value = max(lo, min(hi, value))
        return True, value
    if isinstance(default, str):
        if not isinstance(value, str):
            return False, None
        if key == "bot_difficulty" and value not in BOT_DIFFICULTY_OPTIONS:
            return False, None
        if key == "bgm_stage_set" and value not in BGM_STAGE_SET_OPTIONS:
            return False, None
        if key == "game_mode" and value not in ("battle", "survival"):
            return False, None
        if key == "color_mode" and value not in ("normal", "colorblind"):
            return False, None
        if key == "text_size" and value not in ("normal", "large"):
            return False, None
        if key == "key_hints" and value not in ("always", "novice", "off"):
            return False, None
        if key == "block_skin" and value not in BLOCK_SKIN_OPTIONS:
            return False, None
        if key == "language" and value not in ("ko", "en"):
            return False, None
        if key == "rule_garbage" and value not in ("half", "normal", "heavy"):
            return False, None
        if key == "rule_gravity" and value not in ("slow", "normal", "fast"):
            return False, None
        if key == "mini_detail" and value not in ("detailed", "focus", "simple"):
            return False, None
        if key == "key_preset" and value not in ("arcade", "wasd", "gamepad", "custom"):
            return False, None
        if key == "initials":
            value = "".join(ch for ch in value if ch.isalnum())[:3].upper()
        if key == "target_mode" and value not in TARGET_MODE_OPTIONS:
            return False, None
        if key in ("screen_shake", "pad_rumble") and value not in SHAKE_OPTIONS:
            return False, None
        if key == "visual_fx" and value not in ("min", "normal", "fancy"):
            return False, None
        return True, value
    if isinstance(default, list):
        return (isinstance(value, list) and all(isinstance(x, str) for x in value)), value
    return True, value


def _bumps_keys(fn):
    """설정을 바꾸는 메서드가 끝나면 조작키 캐시를 무효화 (is_bound_key가 쓰는 '배정된 모든 키' 집합)"""
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        finally:
            self._keys_ver = getattr(self, "_keys_ver", 0) + 1
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


class SettingsManager:
    def __init__(self, filepath=SETTINGS_FILE):
        self.filepath = filepath
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    @_bumps_keys
    def load(self):
        """settings.json 파일에서 설정 불러오기"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        for k, v in saved.items():
                            if k in DEFAULT_SETTINGS:
                                ok, val = _valid_setting(k, v)
                                if ok:
                                    self.data[k] = val               # 타입/범위가 맞지 않는 값은 기본값 유지
                    else:
                        _backup_corrupt(self.filepath)
            except Exception as e:
                print(f"[SettingsManager] Failed to load settings: {e}. Using defaults.")
                _backup_corrupt(self.filepath)
        else:
            self.save()

    def save(self):
        """현재 설정을 settings.json에 저장"""
        try:
            tmp = self.filepath + ".tmp"                      # 임시 파일에 쓴 뒤 교체: 저장 도중 종료돼도 원본이 깨지지 않음
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            os.replace(tmp, self.filepath)
        except Exception as e:
            print(f"[SettingsManager] Failed to save settings: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    @_bumps_keys
    def set(self, key, value, autosave=True):
        self.data[key] = value
        if autosave:
            self.save()

    @_bumps_keys
    def reset_to_defaults(self):
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.save()

    def cycle_bot_difficulty(self, step=1):
        cur = self.get("bot_difficulty", "mixed")
        if cur not in BOT_DIFFICULTY_OPTIONS:
            cur = "mixed"
        idx = BOT_DIFFICULTY_OPTIONS.index(cur)
        new_idx = (idx + step) % len(BOT_DIFFICULTY_OPTIONS)
        new_diff = BOT_DIFFICULTY_OPTIONS[new_idx]
        self.set("bot_difficulty", new_diff)
        return new_diff

    def cycle_bgm_stage_set(self, step=1):
        cur = self.get("bgm_stage_set", "random")
        if cur not in BGM_STAGE_SET_OPTIONS:
            cur = "random"
        idx = BGM_STAGE_SET_OPTIONS.index(cur)
        new_idx = (idx + step) % len(BGM_STAGE_SET_OPTIONS)
        new_val = BGM_STAGE_SET_OPTIONS[new_idx]
        self.set("bgm_stage_set", new_val)
        return new_val

    def cycle_block_skin(self, step=1, available=None):
        """available: 지금 쓸 수 있는 스킨 목록 (없으면 전부). 잠긴 스킨은 건너뜀"""
        opts = [o for o in BLOCK_SKIN_OPTIONS if available is None or o in available] or ["classic"]
        cur = self.get("block_skin", "classic")
        if cur not in opts:
            cur = opts[0]
        new_val = opts[(opts.index(cur) + step) % len(opts)]
        self.set("block_skin", new_val)
        return new_val

    def cycle_visual_fx(self, step=1):
        order = ("min", "normal", "fancy")
        cur = self.get("visual_fx", "normal")
        if cur not in order:
            cur = "normal"
        new_val = order[(order.index(cur) + step) % len(order)]
        self.set("visual_fx", new_val)
        return new_val

    def cycle_pad_rumble(self, step=1):
        cur = self.get("pad_rumble", "normal")
        if cur not in SHAKE_OPTIONS:
            cur = "normal"
        new_val = SHAKE_OPTIONS[(SHAKE_OPTIONS.index(cur) + step) % len(SHAKE_OPTIONS)]
        self.set("pad_rumble", new_val)
        return new_val

    def cycle_screen_shake(self, step=1):
        cur = self.get("screen_shake", "normal")
        if cur not in SHAKE_OPTIONS:
            cur = "normal"
        new_val = SHAKE_OPTIONS[(SHAKE_OPTIONS.index(cur) + step) % len(SHAKE_OPTIONS)]
        self.set("screen_shake", new_val)
        return new_val

    def cycle_resolution(self, step=1, available=None):
        options = available or RESOLUTION_OPTIONS
        cur = self.get("resolution", "auto")
        if cur not in options:
            cur = "auto"
        new = options[(options.index(cur) + step) % len(options)]
        self.set("resolution", new)
        return new

    def adjust_bgm_volume(self, delta):
        cur = self.get("bgm_volume", 60)
        new_val = max(0, min(100, cur + delta))
        self.set("bgm_volume", new_val)
        return new_val

    def adjust_sfx_volume(self, delta):
        cur = self.get("sfx_volume", 70)
        new_val = max(0, min(100, cur + delta))
        self.set("sfx_volume", new_val)
        return new_val

    def apply_handling_preset(self, index):
        """HANDLING_PRESETS[index]의 값을 한꺼번에 적용"""
        _name, das, arr, sdf, dcd, cancel = HANDLING_PRESETS[index % len(HANDLING_PRESETS)]
        self.set("das_ms", das)
        self.set("arr_ms", arr)
        self.set("sdf_ms", sdf)
        self.set("dcd_ms", dcd)
        self.set("das_cancel", cancel)

    def cycle_handling_preset(self, direction):
        """현재 값에 맞는 프리셋 다음/이전으로 이동 (사용자 지정이면 기본에서 시작)"""
        cur = handling_preset_name(self.get("das_ms"), self.get("arr_ms"), self.get("sdf_ms"), self.get("dcd_ms"), self.get("das_cancel"))
        names = [p[0] for p in HANDLING_PRESETS]
        i = names.index(cur) if cur in names else 1
        self.apply_handling_preset(i + (1 if direction > 0 else -1))

    @_bumps_keys
    def reset_values(self, keys):
        """지정한 설정 키들만 기본값으로 되돌림 (설정 화면의 '이 탭 기본값으로')"""
        for k in keys:
            if k in DEFAULT_SETTINGS:
                self.data[k] = copy.deepcopy(DEFAULT_SETTINGS[k])
        self.save()

    def adjust_handling(self, key, direction):
        """DAS/ARR/소프트드롭 값(ms)을 한 단계 올리거나(+1) 내림(-1). 허용 범위 안으로 제한"""
        lo, hi, _big = HANDLING_LIMITS[key]
        cur = int(self.get(key))
        if key == "sdf_ms" and ((direction < 0 and cur <= 5) or (direction > 0 and cur == 0)):
            new_val = 0 if direction < 0 else 5               # 소프트드롭은 5ms 아래로 내리면 '즉시'(0)
            self.set(key, new_val)
            return new_val
        st = handling_step(key, cur, direction < 0)
        if direction > 0:
            nxt = (cur // st + 1) * st                    # 단계 눈금에 맞춰 올림 (예: 33 -> 35)
        else:
            nxt = (cur // st) * st if cur % st else cur - st
        new_val = max(lo, min(hi, nxt))
        self.set(key, new_val)
        return new_val

    def toggle_bgm(self):
        cur = self.get("bgm_enabled", True)
        self.set("bgm_enabled", not cur)
        return not cur

    def toggle_sfx(self):
        cur = self.get("sfx_enabled", True)
        self.set("sfx_enabled", not cur)
        return not cur

    def toggle_fullscreen(self):
        cur = self.get("fullscreen", False)
        self.set("fullscreen", not cur)
        return not cur

    # ----------------------------------------------------
    # 조작키 커스텀 & 프리셋 관리
    # ----------------------------------------------------
    def get_action_keys(self, action):
        """특정 액션에 매핑된 키 코드 리스트 반환"""
        custom = self.get("custom_keys")
        if custom and isinstance(custom, dict) and action in custom:
            return custom[action]
            
        preset = self.get("key_preset", "arcade")
        if preset in KEY_PRESETS and action in KEY_PRESETS[preset]:
            return KEY_PRESETS[preset][action]
            
        return KEY_PRESETS["arcade"].get(action, [])

    def is_bound_key(self, event_key, actions):
        """event_key가 actions(ACTION_NAMES 같은 (동작, 이름) 목록) 중 어느 동작에든 배정돼 있는가. 배정된 모든 키의 집합을 캐시해 키를 누를 때마다 전체 동작을 훑지 않음"""
        cache = getattr(self, "_bound_cache", None)
        ver = getattr(self, "_keys_ver", 0)
        if cache is None or cache[0] != ver or cache[1] is not actions:
            keys = set()
            for act, _n in actions:
                keys.update(self.get_action_keys(act))
            cache = self._bound_cache = (ver, actions, keys)
        return event_key in cache[2]

    def is_action_key(self, event_key, action):
        """이벤트 발생 키가 해당 액션에 할당된 키인지 검사"""
        return event_key in self.get_action_keys(action)

    @_bumps_keys
    def set_action_key(self, action, key_code):
        """특정 액션의 단축키를 새 키 코드로 변경 (커스텀 프리셋으로 전환)"""
        custom = self.get("custom_keys")
        if not custom or not isinstance(custom, dict):
            # 현재 프리셋 기반으로 복사하여 커스텀 생성
            preset = self.get("key_preset", "arcade")
            custom = {k: list(v) for k, v in KEY_PRESETS.get(preset, KEY_PRESETS["arcade"]).items()}
            
        # 새 키가 이미 다른 동작에 배정돼 있으면 그쪽에서 빼서 한 키가 두 동작을 동시에 실행하지 않게 함.
        # 그 동작이 키를 전부 잃으면 (바꾸기 전) 이 동작의 키를 넘겨줌(교환)
        old_keys = list(custom.get(action, []))
        custom[action] = [key_code]
        moved = []
        for other, keys in list(custom.items()):
            if other != action and key_code in keys:
                keys = [k for k in keys if k != key_code]
                swapped = False
                if not keys and old_keys:
                    keys = [old_keys[0]]
                    swapped = True
                custom[other] = keys
                moved.append((other, swapped))
        self.data["custom_keys"] = custom
        self.data["key_preset"] = "custom"
        self.save()
        return moved

    @_bumps_keys
    def set_key_preset(self, preset_name):
        """프리셋 변경 ('arcade' / 'wasd' / 'gamepad'). 게임패드 프리셋은 패드 입력도 켬"""
        if preset_name in KEY_PRESETS:
            self.data["key_preset"] = preset_name
            self.data["custom_keys"] = None
            if preset_name == "gamepad":
                self.data["gamepad"] = True
            self.save()

    def get_pad_map(self):
        """게임패드 버튼 배치 {동작: [버튼 이름]}: 기본 배치 위에 저장된 값을 덮어씀 (잘못된 값은 무시)"""
        from gamepad import DEFAULT_PAD_MAP, PAD_BUTTONS, PAD_REBINDABLE
        out = {a: list(v) for a, v in DEFAULT_PAD_MAP.items()}
        saved = self.get("pad_buttons")
        if isinstance(saved, dict):
            for act in PAD_REBINDABLE:
                v = saved.get(act)
                if isinstance(v, list):
                    out[act] = [n for n in v if n in PAD_BUTTONS][:3]
        return out

    def set_pad_button(self, action, name):
        """동작의 패드 버튼을 새 버튼 하나로 바꿈. 다른 동작이 쓰던 버튼이면 그쪽에서 빼 한 버튼이 두 동작을 하지 않게 함. 반환: 버튼을 빼앗긴 동작 목록"""
        from gamepad import PAD_BUTTONS, PAD_REBINDABLE
        if action not in PAD_REBINDABLE or name not in PAD_BUTTONS:
            return []
        m = self.get_pad_map()
        moved = [a for a, names in m.items() if a != action and name in names]
        for a in moved:
            m[a] = [n for n in m[a] if n != name]
        m[action] = [name]
        self.data["pad_buttons"] = {a: list(v) for a, v in m.items() if a in PAD_REBINDABLE}
        self.save()
        return moved

    def reset_pad_buttons(self):
        self.data["pad_buttons"] = None
        self.save()

    @_bumps_keys
    def reset_keys_to_default(self):
        """조작키를 아케이드 표준 기본값으로 초기화"""
        self.set_key_preset("arcade")
        self.data["pad_buttons"] = None                  # 패드 버튼 배치도 기본으로
        self.save()
