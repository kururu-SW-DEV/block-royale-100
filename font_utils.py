"""
Block Royale 100 - 글꼴 고르기
기본은 이전과 같이 OS에 있는 글꼴(맑은 고딕 등)을 쓴다. 그 글꼴에 한글이 없을 때(SteamOS/Proton처럼 한글 글꼴이 없는 환경)만,
게임과 함께 포장한 오픈 라이선스 글꼴(assets/fonts/ 의 나눔고딕, SIL OFL 1.1)로 바꿔 쓴다.
글꼴 파일이 없으면(저장소에 아직 넣지 않았거나 지워진 경우) 예전과 똑같이 OS 글꼴만 쓰므로 안전하다.
(Windows처럼 OS 글꼴이 있는 환경의 화면은 달라지지 않음)
"""

import os

import pygame

from app_paths import resource_path

FONT_DIR = os.path.join("assets", "fonts")
REGULAR_CANDIDATES = ("NanumGothic-Regular.ttf", "NanumGothic.ttf")
BOLD_CANDIDATES = ("NanumGothic-Bold.ttf", "NanumGothicBold.ttf")
_WARNED = set()


def bundled_font_path(bold=False):
    """동봉 글꼴 파일 경로 (없으면 None). 굵게는 굵은 글꼴 파일을 우선, 없으면 보통 파일"""
    names = (BOLD_CANDIDATES + REGULAR_CANDIDATES) if bold else REGULAR_CANDIDATES
    for n in names:
        p = resource_path(os.path.join(FONT_DIR, n))
        if os.path.exists(p):
            return p
    return None


def supports_hangul(font):
    """이 글꼴이 한글을 그릴 수 있는가. 없는 글자는 metrics가 값을 돌려주므로(측정으로 확인) 믿을 수 없어,
    서로 다른 한글 두 글자를 그려 보아 그림이 같으면(둘 다 '네모') 한글이 없는 글꼴로 본다"""
    try:
        a = pygame.image.tobytes(font.render("가", True, (255, 255, 255)), "RGBA")
        b = pygame.image.tobytes(font.render("힣", True, (255, 255, 255)), "RGBA")
        return a != b
    except Exception:
        return True                                          # 알 수 없으면 OS 글꼴을 그대로 씀 (예전 동작)


def make_font(names, px, bold=False):
    """pygame 글꼴 만들기: OS 글꼴 우선, 한글이 안 나오면 동봉 글꼴"""
    font = pygame.font.SysFont(names, px, bold=bold)
    if supports_hangul(font):
        return font
    path = bundled_font_path(bold)
    if path is not None:
        try:
            return pygame.font.Font(path, px)
        except Exception:
            pass
    if "nofont" not in _WARNED:                              # 대체할 글꼴도 없으면 한 번만 기록 (한글이 네모로 보일 수 있음)
        _WARNED.add("nofont")
        try:
            import crash_log
            crash_log.write_error("No Korean-capable font", f"names={names!r}: OS 글꼴에 한글이 없고 assets/fonts에 동봉 글꼴도 없음")
        except Exception:
            pass
    return font


# 꾸밈용 글꼴 (OFL): 제목/배너는 Black Han Sans(한글+영문), HUD 숫자는 Rajdhani Bold(영문/숫자만).
# 파일이 없거나 열 수 없으면 None -> 호출한 쪽이 기본 글꼴을 씀 (예전과 같은 화면)
DISPLAY_FACES = {"display": "BlackHanSans-Regular.ttf", "num": "Rajdhani-Bold.ttf"}
_FACE_CACHE = {}


def face_font(face, px):
    """꾸밈 글꼴(face: 'display' | 'num')을 px 크기로 열어 돌려줌. 없으면 None"""
    key = (face, px)
    if key in _FACE_CACHE:
        return _FACE_CACHE[key]
    font = None
    name = DISPLAY_FACES.get(face)
    if name:
        path = resource_path(os.path.join(FONT_DIR, name))
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, px)
            except Exception:
                font = None
    _FACE_CACHE[key] = font
    return font


def face_can_draw(face, text):
    """이 꾸밈 글꼴로 text 전체를 그릴 수 있는가 (숫자용 Rajdhani는 한글/기호가 없으므로 그런 글자가 섞이면 기본 글꼴로)"""
    if face == "num":
        return all(ord(c) < 0x2000 for c in text)
    return True
