"""
Block Royale 100 - Configuration & Constants
"""

APP_VERSION = "1.4.26"          # 프로그램 버전 (메인 화면 하단, --version, error.log에 표시)

# 화면 해상도 설정
SCREEN_WIDTH = 1366
SCREEN_HEIGHT = 768
FPS = 60

# 블록 보드 규격
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
SPAWN_Y = -1                    # 새 블록이 나오는 줄: 보이는 맨 윗줄 위의 숨겨진 한 줄 (가이드라인의 '숨김 구역' 단순화). 예전에는 0이라 스택이 맨 위 두 줄에 닿으면 바로 탈락했음

# 테트로미노 모양 정의 (4x4 또는 3x3 회전 상태, SRS 표준 매트릭스)
TETROMINOES = {
    'I': [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)]
    ],
    'J': [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)]
    ],
    'L': [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)]
    ],
    'O': [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)]
    ],
    'S': [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'T': [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'Z': [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)]
    ]
}

# 피스별 고유 색상 (자체 제작 팔레트)
PIECE_COLORS = {
    'I': (255, 92, 170),   # 핑크
    'J': (150, 110, 255),  # 바이올렛
    'L': (190, 235, 70),   # 라임
    'O': (70, 215, 160),   # 민트
    'S': (90, 170, 255),   # 스카이블루
    'T': (255, 185, 60),   # 앰버
    'Z': (255, 110, 90),   # 코랄
    'G': (135, 140, 155),  # Garbage (쓰레기 라인)
    # 아래 두 색은 블록 종류가 아니라 로고(왕관) 장식용
    'Y1': (255, 206, 84),
    'Y2': (236, 150, 44),
}

PIECE_COLORS_DEFAULT = dict(PIECE_COLORS)     # 기본 팔레트 원본 (색상 모드를 되돌릴 때 사용)
# 색약 보정 팔레트: 색상뿐 아니라 밝기 차이도 크게 둬서 적녹/청황 색약에서도 블록 종류가 구분되도록 함
PIECE_COLORS_COLORBLIND = {
    'I': (86, 200, 245),   # 하늘색
    'J': (60, 100, 230),   # 진한 파랑
    'L': (240, 150, 20),   # 주황
    'O': (245, 232, 70),   # 노랑
    'S': (40, 190, 150),   # 청록
    'T': (215, 130, 185),  # 분홍 보라
    'Z': (235, 95, 35),    # 주홍
}


COLOR_MODE = {"mode": "normal"}        # 현재 색상 모드 (HUD의 위험 신호 색을 고를 때도 참조)


def is_colorblind():
    return COLOR_MODE["mode"] == "colorblind"


def apply_color_mode(mode):
    """블록 색상 팔레트를 기본/색약 보정으로 바꿈 (PIECE_COLORS 딕셔너리를 그 자리에서 갱신하므로 이미 import한 곳에도 반영)"""
    COLOR_MODE["mode"] = "colorblind" if mode == "colorblind" else "normal"
    PIECE_COLORS.update(PIECE_COLORS_DEFAULT)
    if mode == "colorblind":
        PIECE_COLORS.update(PIECE_COLORS_COLORBLIND)


# 기본 UI 테마 색상
COLOR_BG = (18, 18, 28)
COLOR_PANEL_BG = (28, 28, 44)
COLOR_PANEL_BORDER = (60, 60, 90)
COLOR_TEXT = (240, 240, 250)
COLOR_TEXT_DIM = (140, 140, 160)
COLOR_TEXT_ACCENT = (255, 215, 0)
COLOR_WARNING = (255, 75, 75)
COLOR_TARGET_LINE = (255, 50, 50, 160)
COLOR_GHOST = (80, 80, 100)

# 플레이어 이름 색상 (채팅/대기실 표시용): (이름, RGB)
NAME_COLORS = [
    ("기본", (235, 240, 252)),
    ("빨강", (255, 110, 110)),
    ("주황", (255, 170, 80)),
    ("노랑", (255, 226, 100)),
    ("연두", (170, 235, 90)),
    ("초록", (90, 225, 150)),
    ("하늘", (100, 210, 255)),
    ("파랑", (120, 150, 255)),
    ("보라", (190, 130, 255)),
    ("분홍", (255, 130, 200)),
]
NAME_COLOR_COUNT = len(NAME_COLORS)

# 네트워크 기본 설정
DEFAULT_UDP_PORT = 19999
DISCOVERY_BROADCAST_PORT = 19998

# 배틀로얄 설정
MIN_PLAYERS = 2
MAX_PLAYERS = 100
DEFAULT_TARGET_MODE = 'AUTO'  # AUTO, KO, ATTACKERS, BADGES, RANDOM
TARGET_MODES = ['AUTO', 'KO', 'ATTACKERS', 'BADGES', 'RANDOM']

# 주간 변형 규칙: 매주 하나씩 돌아가며 규칙 하나를 바꾼 경기를 열어 준다 (오늘의 도전과 별개). 같은 주는 같은 블록 순서/상대 구성.
# 키: players(인원) / difficulty(봇 난이도) / perfect_attack(퍼펙트 클리어 공격 줄 수) / next_visible(NEXT 보이는 개수) / escalation_start(후반 증폭 시작 시각, 초)
WEEKLY_MUTATORS = (
    {"id": "elite", "name": "소수 정예", "desc": "30인 · 모두 어려움 봇", "players": 30, "difficulty": "hard"},
    {"id": "perfect", "name": "퍼펙트 폭격", "desc": "퍼펙트 클리어 공격 2배 (20줄)", "perfect_attack": 20},
    {"id": "fog", "name": "안개 속", "desc": "NEXT 블록이 1개만 보임", "next_visible": 1},
    {"id": "rush", "name": "후반 가속", "desc": "공격력 증폭이 2분부터 시작", "escalation_start": 120.0},
)


def week_key(day=None):
    """주 식별 키 'YYYYWww' (ISO 주차). day: datetime.date (없으면 오늘)"""
    import datetime
    iso = (day or datetime.date.today()).isocalendar()
    return f"{iso[0]}W{iso[1]:02d}"


def weekly_mutator(day=None):
    """그 주의 변형 규칙 dict. 기준 월요일(2026-01-05)로부터 지난 주 수로 돌아가며 정해짐 (ISO 주차 번호는 연말에 53->1로 이어져 규칙이 겹치므로 쓰지 않음)"""
    import datetime
    d = day or datetime.date.today()
    monday = d - datetime.timedelta(days=d.weekday())
    weeks = (monday - datetime.date(2026, 1, 5)).days // 7
    return WEEKLY_MUTATORS[weeks % len(WEEKLY_MUTATORS)]


def weekly_seed(key):
    """같은 주는 같은 블록 순서/상대 구성이 되도록 주 키를 정수 시드로"""
    return int(key.replace("W", ""))


# 퍼펙트 클리어(라인을 지워 보드 위 블록이 하나도 남지 않음) 보너스 공격 줄 수
PERFECT_CLEAR_ATTACK = 10

# 반격(ATTACKERS) 모드에서 나를 노리는 플레이어들에게 동시에 공격을 보낼 수 있는 최대 인원
MULTI_TARGET_MAX = 4

# 쓰레기 공격 테이블 (라인 클리어 수에 따른 쓰레기 줄 전송 수)
GARBAGE_ATTACK_TABLE = {
    1: 0,   # Single (방어만)
    2: 1,   # Double
    3: 2,   # Triple
    4: 4,   # Quad (4줄)
}

# T-스핀 공격력 테이블
TSPIN_ATTACK_TABLE = {
    0: 0,   # T-Spin 0줄 (미니)
    1: 2,   # T-Spin Single (2줄 전송)
    2: 4,   # T-Spin Double (4줄 전송)
    3: 6,   # T-Spin Triple (6줄 전송)
}

# T-스핀 Mini 공격력 테이블
TSPIN_MINI_ATTACK_TABLE = {
    0: 0,
    1: 1,
    2: 2,
}

# 락다운 1회당 보드에 올라오는 쓰레기 줄 최대 수 (초과분은 대기열 유지)
MAX_GARBAGE_PER_LOCK = 8

# 공격을 받으면 쓰레기 줄이 이 시간(초) 동안 "차징" 중이라 보드에 올라오지 않음 (그 사이에 줄을 지워 상쇄할 수 있음). 0이면 끔
GARBAGE_CHARGE_DELAY = 0.8

# 쓰레기 줄의 구멍 위치: 한 번에 올라오는 묶음 안에서 다음 줄로 넘어갈 때 구멍이 다른 칸으로 옮겨질 확률
GARBAGE_MESSINESS = 0.25

# 한 플레이어에게 쌓여 있을 수 있는 대기 쓰레기 줄 수의 상한 (블록 3번 고정분). 이미 탈락이 확정된 상대에게 100줄씩 쌓이는 것을 막음: 초과분은 버려짐
MAX_INCOMING_GARBAGE = 24

# 연속 콤보 보너스 테이블
COMBO_BONUS = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 5]

# K.O. 배지(Badge) 공격력 증폭 테이블: (필요 KO 수, 공격력 증가율)
BADGE_TIERS = [
    (0, 0.00),   # 0단계: 0% 보너스
    (2, 0.25),   # 1단계 (2 K.O.): +25% 공격력 증가
    (4, 0.50),   # 2단계 (4 K.O.): +50% 공격력 증가
    (8, 0.75),   # 3단계 (8 K.O.): +75% 공격력 증가
    (16, 1.00),  # 4단계 (16 K.O.): +100% 공격력 증가 (공격력 2배)
]

# 봇 이름: "번개여우"처럼 형용+동물 2글자씩 100개 조합을 한 번 섞어 둔 고정 목록 (같은 번호 봇은 로비/경기/멀티플레이에서 같은 이름)
BOT_NAME_ADJ = ("번개", "새벽", "노을", "폭풍", "안개", "달빛", "별빛", "바람", "얼음", "불꽃")
BOT_NAME_NOUN = ("여우", "늑대", "고래", "까치", "수달", "사자", "거북", "참새", "매미", "토끼")


BOT_NAME_ADJ_EN = ("Bolt", "Dawn", "Dusk", "Storm", "Mist", "Moon", "Star", "Wind", "Ice", "Flame")      # 영어 UI용 (한국어 목록과 같은 순서)
BOT_NAME_NOUN_EN = ("Fox", "Wolf", "Whale", "Magpie", "Otter", "Lion", "Turtle", "Sparrow", "Cicada", "Rabbit")


def _build_bot_names():
    import random as _r
    pairs = [(i, j) for i in range(len(BOT_NAME_ADJ)) for j in range(len(BOT_NAME_NOUN))]
    _r.Random(2026).shuffle(pairs)
    return (tuple(BOT_NAME_ADJ[i] + BOT_NAME_NOUN[j] for i, j in pairs),
            tuple(BOT_NAME_ADJ_EN[i] + BOT_NAME_NOUN_EN[j] for i, j in pairs))


BOT_NAMES, BOT_NAMES_EN = _build_bot_names()      # 같은 번호는 언어가 달라도 같은 조합 (경기를 만들 때의 언어로 이름이 정해짐)


def bot_display_name(idx):
    """봇 번호(1부터)에 대응하는 표시 이름 (영어 UI면 영어 이름). 100개가 넘어가면 번호를 덧붙여 중복을 막음"""
    try:
        import i18n
        names = BOT_NAMES_EN if i18n.language() == "en" else BOT_NAMES
    except Exception:
        names = BOT_NAMES
    n = len(names)
    base = names[(idx - 1) % n]
    return base if idx <= n else f"{base}{(idx - 1) // n + 1}"


# 봇 성향: 조준 방식만 달라짐 (평가/탐색은 그대로라 CPU 부담 없음). 반격형은 나를 노리는 상대에게 자주 되갚고, 저격형은 되갚지 않고 탈락 직전 상대를 노림
BOT_TRAITS = ("반격형", "저격형", "균형형")
BOT_TRAIT_WEIGHTS = (2, 2, 4)

# 다수 공격자(Attacker) 타겟팅 방어/반격 보너스
ATTACKER_BONUS = {
    0: 0, 1: 0,
    2: 1,   # 2명에게 조준당할 시: +1줄 반격 보너스
    3: 3,   # 3명에게 조준당할 시: +3줄 반격 보너스
    4: 5,   # 4명에게 조준당할 시: +5줄 반격 보너스
    5: 7,   # 5명: +7줄
    6: 9    # 6명 이상: +9줄 (역전의 일격)
}

