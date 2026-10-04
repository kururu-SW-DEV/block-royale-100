"""
설정(이니셜/반응 탭) 탐색, 크래시 처리 보조
실행: python test_settings_crash.py
"""
import os
import sys
import time
import json
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
    return app


def test_initials_setting_and_text_field():
    app = _app()
    app.settings.set("initials", "", autosave=False)
    app.player_name = "kurumi"
    assert app._initials() == "KUR"
    app.player_name = "한글이름"
    assert app._initials() == "한글이"
    app.settings.set("initials", "abc!", autosave=False)
    assert app._initials() == "ABC!"[:3] or app._initials() == "ABC"
    import settings_manager as S
    ok, v = S._valid_setting("initials", "a-b-c-d")
    assert ok and v == "ABC"
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "match", "MENU"
    app._render_settings()
    assert "initials" in app.text_rects
    app._begin_text("initials")
    for ch in "xy12":
        app._text_input_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    assert app.initials_input == "XY1", "3글자까지, 대문자"
    app._end_text()
    assert app.settings.get("initials") == "XY1" and app._initials() == "XY1"
    app._begin_text("initials")
    app.initials_input = app._auto_initials()
    app._end_text()
    assert app.settings.get("initials") == "", "이름과 같으면 자동 값으로 되돌림"
    print("  OK 이니셜")


def test_react_tab_and_keys_tab_navigation():
    import screens.settings as SS
    app = _app()
    app.state, app.previous_state = "SETTINGS", "MENU"
    assert "react" in SS.TAB_ORDER and SS.PRESET_FOCUS == SS.KEY_CARDS
    for tab in SS.TAB_ORDER:
        app.settings_tab = tab
        for f in range(8):
            app.settings_focus[tab] = f
            app._kb_nav = True
            app._render_settings()
    app.settings_tab = "react"
    app.settings_focus["react"] = 4                                # DAS 취소 줄
    before = app.settings.get("das_cancel")
    app._settings_key_nav(pygame.K_RIGHT)
    assert app.settings.get("das_cancel") != before and app.DAS_CANCEL == (not before)
    app.settings_focus["react"] = 0
    d0 = app.settings.get("das_ms")
    app._settings_key_nav(pygame.K_RIGHT)
    assert app.settings.get("das_ms") > d0
    app._reset_current_tab()
    assert app.settings.get("das_ms") == 135 and app.DAS_DELAY == 0.135
    app.settings_tab = "keys"
    app.settings_focus["keys"] = SS.KEY_CARDS - 1
    app._settings_key_nav(pygame.K_DOWN)
    assert app.settings_focus["keys"] == SS.PRESET_FOCUS
    app._settings_key_nav(pygame.K_UP)
    assert app.settings_focus["keys"] == SS.KEY_CARDS - 1
    print("  OK 반응 탭/조작 탭")


def test_v133_crash_helpers():
    import crash_log
    # 긴 로그를 자를 때 UTF-8 글자가 깨지지 않음
    big = ("한글오류 " * 40000)
    path = crash_log.log_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(big)
    crash_log.write_error("t", "x")
    with open(path, "rb") as f:
        data = f.read()
    data.decode("utf-8")                                   # 예외가 나면 잘린 글자가 남은 것
    assert len(data) < crash_log.MAX_LOG_BYTES * 2
    # 조용히 넘긴 예외는 처음 한 번만 기록
    crash_log._swallowed.clear()
    try:
        raise ValueError("boom")
    except ValueError:
        crash_log.note_swallowed("unit")
        crash_log.note_swallowed("unit")
    assert crash_log._swallowed["unit"] == 2
    with open(path, encoding="utf-8") as f:
        assert f.read().count("Swallowed exception (unit") == 1
    # 치명적 오류 직전 저장: 진행 중이던 판의 리플레이가 남음
    import replay
    old = replay.replay_path
    tmp = os.path.join(tempfile.mkdtemp(), "replays.json")
    replay.replay_path = lambda: tmp
    try:
        app = _app()
        app.start_game("SOLO", total_players=20)
        m = app.match
        m.countdown_until = 0.0
        for _ in range(4):
            m.local_engine.hard_drop()
            app._tick_game(1 / 30)
        assert len(app.replay_rec.events) >= 3, app.replay_rec.events
        crash_log.emergency_save(app)
        assert replay.load_replays(tmp), "치명적 오류 직전에 진행 중이던 판이 저장되지 않음"
    finally:
        replay.replay_path = old
    os.remove(path)


if __name__ == "__main__":
    pygame.init()
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    keep = {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in (SETTINGS_FILE, STATS_FILE)}
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL SETTINGS_CRASH TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
