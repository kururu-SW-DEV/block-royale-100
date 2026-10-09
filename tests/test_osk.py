"""
화상 키보드(SteamOS/Proton에서 Steam 키보드가 안 뜰 때 게임이 직접 그리는 키보드) 테스트: 한글 조합, 글자판, 입력칸 연결, 접속 주소, 패드/마우스/물리 키보드 동작.
실행: python tests/test_osk.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from gfx import CANVAS


def _app():
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    app.settings.filepath = os.path.join(tempfile.mkdtemp(), "set.json")
    app.settings.reset_to_defaults()
    return app


def _typed(src):
    from osk import HangulComposer
    c, out = HangulComposer(), ""
    for ch in src:
        d, t = c.feed(ch)
        out = out[:len(out) - d] + t
    return out


def test_hangul_composition():
    cases = {"ㅎㅏㄴㄱㅡㄹ": "한글", "ㅇㅏㄴㄴㅕㅇ": "안녕", "ㄱㅏㅂㅅㅏ": "갑사", "ㄱㅏㅂㅅ": "값", "ㅇㅗㅏ": "와", "ㄷㅏㄹㄱㅣ": "달기",
             "ㄱㅏㅇㅏ": "가아", "ㅇㅗㅏㄴ": "완", "ㄱㅏㅏ": "가ㅏ", "ㄱㄴ": "ㄱㄴ", "ㅂㅏㅂㅗ": "바보", "ㄱㅏㄲㅏ": "가까", "ㅂㅏㅃㅏ": "바빠"}
    for src, exp in cases.items():
        assert _typed(src) == exp, (src, _typed(src), exp)
    from osk import HangulComposer
    c, out = HangulComposer(), ""
    for ch in "ㅎㅏㄴㅏ":
        d, t = c.feed(ch)
        out = out[:len(out) - d] + t
    assert out == "하나"
    seen = []
    for _ in range(4):
        r = c.backspace()
        if r:
            d, t = r
            out = out[:len(out) - d] + t
        seen.append(out)
    assert seen == ["하ㄴ", "하", "하", "하"], seen            # 지우기는 방금 친 글자 안에서만 되돌림 (앞 글자는 건드리지 않음)


def test_layouts_have_five_rows_and_function_keys():
    from osk import layout
    for page in ("en", "ko", "sym"):
        rows = layout(page)
        assert len(rows) == 5 and rows[0][-1] == "BACK" and rows[4] == ["LANG", "SYM", "SPACE", "CANCEL", "DONE"]
        assert all(isinstance(k, tuple) and len(k) == 2 or isinstance(k, str) for r in rows for k in r)
    assert [k for k in layout("en")[1]] == [(c, c.upper()) for c in "qwertyuiop"]


def _keys(app):
    app._render_osk()
    return {k if isinstance(k, str) else k[0]: rect for rect, k, r, c in app.osk["keys"]}


def _click(app, rect):
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)
    assert app._osk_event(ev)


def test_settings_name_edit_with_osk():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True                         # SteamOS/패드 환경인 것처럼
    app._begin_text("player_name")
    assert app.osk is not None and app.text_focus == "player_name"
    app.player_name_input = ""
    k = _keys(app)
    for ch in "abc":
        _click(app, _keys(app)[ch])
    assert app.player_name_input == "abc"
    _click(app, _keys(app)["SHIFT"])
    _click(app, _keys(app)["q"])
    assert app.player_name_input == "abcQ", "Shift는 한 글자만 대문자"
    _click(app, _keys(app)["q"])
    assert app.player_name_input == "abcQq"
    _click(app, _keys(app)["BACK"])
    assert app.player_name_input == "abcQ"
    _click(app, _keys(app)["LANG"])                        # 한글 자판: ㅎㅏㄴ -> 한
    assert app.osk["page"] == "ko"
    for j in "ㅎㅏㄴ":
        _click(app, _keys(app)[j])
    assert app.player_name_input == "abcQ한"
    _click(app, _keys(app)["ㅏ"])                          # 받침이 다음 글자 초성으로: 하 + 나
    assert app.player_name_input == "abcQ하나"
    _click(app, _keys(app)["BACK"])
    _click(app, _keys(app)["BACK"])
    assert app.player_name_input == "abcQ하"
    _click(app, _keys(app)["DONE"])                        # 완료: Enter와 같음 -> 이름 확정, 키보드 닫힘
    assert app.osk is None and app.text_focus is None and app.player_name.endswith("하")


def test_cancel_restores_and_physical_typing_closes_osk():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    before = app.player_name
    app._begin_text("player_name")
    _click(app, _keys(app)["z"])
    _click(app, _keys(app)["CANCEL"])
    assert app.osk is None and app.text_focus is None and app.player_name == before
    app._begin_text("player_name")
    assert app.osk is not None
    assert app._osk_event(pygame.event.Event(pygame.TEXTINPUT, text="k")) is False and app.osk is None, "물리 키보드로 치면 닫힘"
    app._end_text(commit=False)
    app._begin_text("player_name")
    assert app._osk_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a", scancode=0)) is False and app.osk is None
    app._end_text(commit=False)


def test_only_enabled_on_proton():
    import app_paths
    import screens.osk as so
    app = _app()
    assert app._osk_wanted() is False, "Windows/일반 환경에서는 켜지지 않음 (패드를 써도 마찬가지)"
    app._pad_hints_active = lambda: True
    assert app._osk_wanted() is False
    so.running_under_wine = lambda: True
    try:
        assert app._osk_wanted() is True
    finally:
        so.running_under_wine = app_paths.running_under_wine
    # 접속 화면의 버튼/패드 Y도 Proton에서만
    app.state = "JOIN_MENU"
    app._render_join_menu()
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="", scancode=0)
    ev.pad = True
    app._handle_event(ev)
    assert app.osk is None
    app._handle_join_menu_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.join_osk_btn.center, button=1))
    assert app.osk is None


def test_not_opened_without_proton_or_pad():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: False
    app._begin_text("player_name")
    assert app.osk is None
    app._end_text(commit=False)


def test_gamepad_navigation_and_buttons():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    app._begin_text("player_name")
    app.player_name_input = ""
    app._render_osk()

    def key(k, pad=True):
        ev = pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)
        ev.pad = pad
        return app._osk_event(ev)
    assert app.osk["sel"] == (1, 0)                        # 시작: q
    assert key(pygame.K_RETURN) and app.player_name_input == "q"
    assert key(pygame.K_RIGHT) and key(pygame.K_RETURN) and app.player_name_input == "qw"
    assert key(pygame.K_DOWN) and key(pygame.K_RETURN)
    assert len(app.player_name_input) == 3
    assert key(pygame.K_SPACE) and len(app.player_name_input) == 2, "패드 X = 지우기"
    assert key(pygame.K_p) and app.osk["shift"], "패드 Y = Shift"
    assert key(pygame.K_PAGEUP) and app.osk["page"] == "ko", "패드 LB = 한/영"
    assert key(pygame.K_PAGEDOWN) and app.osk["page"] == "sym", "패드 RB = 기호"
    for _ in range(12):                                    # 어느 방향으로 돌아도 키 위에 머무름
        key(pygame.K_UP)
        key(pygame.K_LEFT)
    assert any((r, c) == app.osk["sel"] for _, _, r, c in app.osk["keys"])
    assert key(pygame.K_b) is True, "그 밖의 패드 버튼은 아래 화면으로 새지 않음"
    assert key(pygame.K_ESCAPE) and app.osk is None and app.text_focus is None, "B = 닫기(입력 취소)"


def test_join_address_osk_and_pad_y():
    app = _app()
    app.state = "JOIN_MENU"
    app._osk_wanted = lambda: True
    app._render_join_menu()
    app.join_ip_input = ""
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="", scancode=0)
    ev.pad = True
    app._handle_event(ev)                                  # 패드 Y
    assert app.osk is not None and app.osk["kind"] == "join_ip" and app.join_ip_input == ""
    for ch in "192":
        _click(app, _keys(app)[ch])
    _click(app, _keys(app)["."])
    for ch in "168":
        _click(app, _keys(app)[ch])
    assert app.join_ip_input == "192.168"
    before = app.osk["page"]
    _click(app, _keys(app)["LANG"])
    assert app.osk["page"] == before, "접속 주소에는 한글 자판이 없음"
    _click(app, _keys(app)["BACK"])
    assert app.join_ip_input == "192.16"
    _click(app, _keys(app)["SYM"])
    _click(app, _keys(app)[":"])
    assert app.join_ip_input == "192.16:"
    _click(app, _keys(app)["DONE"])
    assert app.osk is None and app.state == "JOIN_MENU"
    app.state = "MENU"
    app.osk = None
    # 버튼으로도 열림
    app.state = "JOIN_MENU"
    app._render_join_menu()
    btn = app.join_osk_btn
    app._handle_join_menu_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=btn.center, button=1))
    assert app.osk is not None
    app.state = "MENU"
    app._render_osk()
    assert app.osk is None, "화면을 벗어나면 닫힘"


def test_chat_in_lobby_and_modal_close():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    app._begin_text("initials")
    assert app.osk is not None
    app._text_set("initials", "")
    _click(app, _keys(app)["a"])
    _click(app, _keys(app)["b"])
    assert app.initials_input == "AB"
    app.modal = {"title": "x", "lines": [], "buttons": []}
    app._render_osk()
    assert app.osk is None, "알림 창이 뜨면 닫힘"
    app.modal = None
    app._end_text(commit=False)


def test_translations_exist_in_english():
    import i18n
    i18n.set_language("en")
    try:
        for ko in ("지우기", "공백", "취소", "완료", "한글", "채팅", "방 제목", "플레이어 이름", "이니셜", "호스트 주소", "화상 키보드", "화상 키보드 (Y)"):
            out = i18n.tr(ko)
            assert not any("가" <= ch <= "힣" for ch in out), (ko, out)
    finally:
        i18n.set_language("ko")


def test_keys_stay_inside_panel_and_screen_and_done_closes():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    app._begin_text("room_name")
    for size in ((1366, 768), (1000, 576), (1920, 1080), (1280, 800), (800, 600)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        for page in ("en", "ko", "sym"):
            for field_kind in ("text", "join_ip"):
                app.osk["page"], app.osk["kind"] = page, field_kind
                app._render_osk() if field_kind == "text" else None
                if field_kind == "join_ip":
                    continue
                panel = app._osk_panel_rect()
                assert pygame.Rect(0, 0, 1366, 768).contains(panel), (size, panel)
                for rect, key, r, c in app.osk["keys"]:
                    assert panel.contains(rect), (size, page, key, rect, panel)             # 키가 키보드 틀 밖으로 나가지 않음
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.osk["kind"], app.osk["page"] = "text", "en"
    app.room_name_input = ""
    _click(app, _keys(app)["a"])
    _click(app, _keys(app)["DONE"])
    assert app.osk is None, "완료를 누르면 키보드가 내려감"
    app._begin_text("room_name")
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0, unicode="", scancode=0)
    ev.pad = True
    assert app.osk is not None
    assert app._osk_event(ev) and app.osk is None, "패드 Back = 완료"
    app._end_text(commit=False)


def test_render_all_pages_and_sizes():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    app._begin_text("room_name")
    for size in ((1366, 768), (1000, 576), (1920, 1080)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        for page in ("en", "ko", "sym"):
            app.osk["page"] = page
            app.osk["shift"] = page == "ko"
            app._render_osk()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    p = app._osk_panel_rect()
    assert p.left >= 0 and p.right <= 1366 and p.bottom <= 768
    app._end_text(commit=False)


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL OSK TESTS PASSED]")
