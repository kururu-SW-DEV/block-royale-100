"""
글꼴 고르기 테스트: OS 글꼴에 한글이 있으면 그대로 쓰고(Windows 화면 불변), 없을 때만 동봉 글꼴(assets/fonts)로 대체하며,
동봉 글꼴 파일이 없어도 예외 없이 예전처럼 동작하는지 확인한다.
실행: python tests/test_fonts.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

import font_utils


class _FakeFont:
    """한글이 있으면 글자마다 다른 그림, 없으면 모든 글자가 같은 '네모' 그림을 돌려주는 가짜 글꼴"""
    def __init__(self, hangul):
        self._h = hangul

    def render(self, text, aa, color):
        surf = pygame.Surface((8, 8), pygame.SRCALPHA)
        if self._h:
            surf.fill((200, 200, 200, 255), (0, 0, 1 + (ord(text[0]) % 7), 8))
        else:
            surf.fill((200, 200, 200, 255), (0, 0, 4, 8))
        return surf


def test_supports_hangul_detects_missing_glyphs():
    pygame.font.init()
    assert font_utils.supports_hangul(_FakeFont(True)) is True
    assert font_utils.supports_hangul(_FakeFont(False)) is False
    assert font_utils.supports_hangul(object()) is True, "알 수 없으면 OS 글꼴을 그대로 씀 (예전 동작)"
    assert font_utils.supports_hangul(pygame.font.Font(None, 20)) is False, "pygame 기본 글꼴에는 한글이 없음 (두 글자가 같은 네모로 그려짐)"
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert font_utils.supports_hangul(pygame.font.SysFont("zzz-no-such-font", 20)) is False, "OS에 없는 글꼴 이름은 기본 글꼴로 대체되어 한글이 없음"


def test_os_font_with_hangul_is_used_unchanged():
    pygame.font.init()
    orig_sys, orig_font = pygame.font.SysFont, pygame.font.Font
    made = []
    pygame.font.SysFont = lambda names, px, bold=False: _FakeFont(True)
    pygame.font.Font = lambda *a, **k: made.append(a) or _FakeFont(True)
    pref = font_utils.PREFER_BUNDLED
    font_utils.PREFER_BUNDLED = False                                  # '동봉 글꼴 우선'을 끈 경우의 동작 (OS 글꼴 우선)
    try:
        f = font_utils.make_font("malgungothic,arial", 20, True)
        f2 = font_utils.make_font("consolas", 20, True)                # 맑은 고딕이 아닌 이름은 우선 적용 대상이 아님
    finally:
        font_utils.PREFER_BUNDLED = pref
        pygame.font.SysFont, pygame.font.Font = orig_sys, orig_font
    assert isinstance(f, _FakeFont) and isinstance(f2, _FakeFont) and not made, "OS 글꼴에 한글이 있으면 동봉 글꼴을 열지 않음"


def test_default_font_is_bundled_nanum_gothic_and_other_names_keep_os_fonts():
    pygame.font.init()
    orig_sys, orig_font = pygame.font.SysFont, pygame.font.Font
    made, sysd = [], []
    pygame.font.SysFont = lambda names, px, bold=False: sysd.append(names) or _FakeFont(True)
    pygame.font.Font = lambda *a, **k: made.append(a) or _FakeFont(True)
    try:
        font_utils.make_font("malgungothic,segoeui,arial", 20, False)
        font_utils.make_font("malgungothic,segoeui,arial", 20, True)
        font_utils.make_font("consolas", 20, True)
    finally:
        pygame.font.SysFont, pygame.font.Font = orig_sys, orig_font
    assert [("Bold" in os.path.basename(a[0]), os.path.basename(a[0]).startswith("Nanum")) for a in made] == [(False, True), (True, True)], made      # 나눔(바른)고딕 보통/굵게
    assert sysd == ["consolas"], sysd


def test_bundled_font_is_used_only_when_os_font_lacks_hangul():
    pygame.font.init()
    tmp = tempfile.mkdtemp()
    fake = os.path.join(tmp, "NanumGothic-Regular.ttf")
    open(fake, "wb").write(b"x")
    orig = (pygame.font.SysFont, pygame.font.Font, font_utils.bundled_font_path)
    calls = []
    pygame.font.SysFont = lambda names, px, bold=False: _FakeFont(False)
    pygame.font.Font = lambda path, px: calls.append((path, px)) or "BUNDLED"
    font_utils.bundled_font_path = lambda bold=False: fake
    try:
        assert font_utils.make_font("malgungothic", 22, False) == "BUNDLED"
        assert calls == [(fake, 22)]
    finally:
        pygame.font.SysFont, pygame.font.Font, font_utils.bundled_font_path = orig


def test_missing_bundled_font_falls_back_to_os_font_without_crashing():
    pygame.font.init()
    d = tempfile.mkdtemp()
    os.environ["BR_DATA_DIR"] = d                                   # 경고 기록이 진짜 error.log에 남지 않게
    orig_sys, orig_path = pygame.font.SysFont, font_utils.bundled_font_path
    pygame.font.SysFont = lambda names, px, bold=False: _FakeFont(False)
    font_utils.bundled_font_path = lambda bold=False: None
    font_utils._WARNED.clear()
    try:
        f = font_utils.make_font("malgungothic", 22, False)
        assert isinstance(f, _FakeFont), "대체 글꼴이 없으면 OS 글꼴을 그대로 돌려줌 (예전 동작)"
        assert "No Korean-capable font" in open(os.path.join(d, "error.log"), encoding="utf-8").read()
        font_utils.make_font("malgungothic", 22, False)
        assert open(os.path.join(d, "error.log"), encoding="utf-8").read().count("No Korean-capable font") == 1, "한 번만 기록"
    finally:
        pygame.font.SysFont, font_utils.bundled_font_path = orig_sys, orig_path
        os.environ.pop("BR_DATA_DIR", None)


def test_bundled_paths_prefer_bold_file_and_packaging_includes_the_folder():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.isdir(os.path.join(root, "assets", "fonts")), "포장 단계(--add-data)가 실패하지 않게 폴더는 항상 있어야 함"
    bat = open(os.path.join(root, "build_exe.bat"), encoding="utf-8").read()
    assert r'--add-data "..\assets\fonts;assets\fonts"' in bat and r"if not exist assets\fonts mkdir assets\fonts" in bat
    notices = open(os.path.join(root, "THIRD_PARTY_NOTICES.md"), encoding="utf-8").read()
    assert "Nanum Barun Gothic" in notices and "Black Han Sans" in notices and "SIL Open Font License" in notices
    assert "Bold" in font_utils.BOLD_CANDIDATES[0] and "Nanum" in font_utils.REGULAR_CANDIDATES[0]


def test_hifont_still_renders_korean_with_the_real_system_font():
    import gfx
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    f = gfx.HiFont("malgungothic,segoeui,arial", 20, bold=True)
    assert f.size("한글 테스트")[0] > 20
    surf = f.render("한글 테스트", True, (255, 255, 255))
    assert surf.get_width() > 20


def test_real_bundled_nanum_gothic_is_valid_and_replaces_a_missing_os_font():
    """동봉한 나눔고딕 파일이 실제로 열리고 한글을 그리며, OS에 글꼴이 없을 때 이 글꼴로 대체됨 (Bold 포함)"""
    import warnings
    pygame.font.init()
    reg, bold = font_utils.bundled_font_path(False), font_utils.bundled_font_path(True)
    assert reg and bold and reg != bold and os.path.basename(reg).startswith("Nanum") and "Bold" in os.path.basename(bold), (reg, bold)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = font_utils.make_font("zzz-no-such-font", 24, False)
        fb = font_utils.make_font("zzz-no-such-font", 24, True)
    assert font_utils.supports_hangul(f) and font_utils.supports_hangul(fb), "OS 글꼴이 없으면 동봉 나눔고딕으로 한글이 그려짐"
    assert f.size("한글")[0] > 20
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ofl = open(os.path.join(root, "assets", "fonts", "OFL.txt"), encoding="utf-8", errors="replace").read()
    assert "SIL OPEN FONT LICENSE" in ofl.upper() and "NHN" in ofl, "라이선스 전문과 저작권 표시를 글꼴과 함께 동봉"


def test_every_symbol_in_ui_strings_exists_in_the_bundled_font():
    """화면에 나오는 글자(소스의 문자열 리터럴)에 동봉 글꼴에 없는 기호가 없어야 함 (Proton 등에서 네모로 보이지 않게)"""
    import io
    import tokenize
    pygame.font.init()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font = pygame.font.Font(font_utils.bundled_font_path(False), 24)
    tofu = pygame.image.tobytes(font.render("", True, (255, 255, 255)), "RGBA")
    missing = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("backups", "tools", "tests", "build_tmp", "release", ".git", "__pycache__", "docs", "steam")]
        for fn in files:
            if not fn.endswith(".py") or fn.startswith("make_"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                toks = list(tokenize.generate_tokens(io.StringIO(open(path, encoding="utf-8").read()).readline))
            except (tokenize.TokenError, IndentationError, UnicodeDecodeError):
                continue
            for tok in toks:
                if tok.type != tokenize.STRING:
                    continue
                for ch in tok.string:
                    o = ord(ch)
                    if o < 128 or 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or ch in " ﻿·":
                        continue
                    if pygame.image.tobytes(font.render(ch, True, (255, 255, 255)), "RGBA") == tofu:
                        missing.setdefault(ch, set()).add(os.path.relpath(path, root))
    assert not missing, {hex(ord(c)): sorted(v)[:3] for c, v in missing.items()}


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL FONT TESTS PASSED]")
