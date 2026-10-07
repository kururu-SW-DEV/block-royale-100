"""
BUG_REPORT.md(다른 AI가 쓴 보고서, 2026-10-07)의 항목을 코드로 재현해 확인하고 고친 것의 회귀 테스트
- A-2 탑아웃 쓰레기 기록, A-6 충전 중인 묶음 뒤의 즉시 쓰레기, B-1 최종 순위표 포커스/Enter, B-3 관전 중 일시정지 입력,
  B-4 텍스트 입력칸 재클릭/다른 칸 클릭
실행: python tests/test_bugreport2.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from block_engine import BlockEngine


def test_garbage_topout_records_only_pushed_rows():
    e = BlockEngine(seed=1)
    e.replay_log = []
    e.grid[0][4] = "J"                                           # 맨 위 줄이 이미 차 있으면 한 줄도 올라오지 못함
    before = e.garbage_pushed_total
    e._push_garbage(3)
    assert e.game_over
    assert e.garbage_pushed_total == before, "올라오지 못한 줄이 통계에 들어감"
    assert not [ev for ev in e.replay_log if ev["k"] == "G"], "올라오지 못한 줄이 리플레이에 기록됨"
    e2 = BlockEngine(seed=1)
    e2.replay_log = []
    e2.grid[1][4] = "J"                                          # 한 줄은 올라오고 두 번째에서 탑아웃
    e2._push_garbage(3)
    g = [ev for ev in e2.replay_log if ev["k"] == "G"]
    assert e2.game_over and len(g) == 1 and g[0]["n"] == 1 and len(g[0]["h"]) == 1, g
    assert e2.garbage_pushed_total == 1


def test_instant_garbage_not_blocked_by_charging_batch():
    e = BlockEngine(seed=1)
    e.queue_garbage(2)                                           # 충전 중 (0.8초 뒤에 올라옴)
    e.queue_garbage(3, instant=True)
    assert e.ready_garbage == 3
    groups = e._take_garbage(10, ready_only=True)
    assert sum(groups) == 3, groups
    assert e.incoming_garbage == 2, "충전 중이던 묶음은 남아 있어야 함"


def _app():
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    return app


def _key(app, key):
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))


def test_standings_focus_and_enter_do_not_exit_to_menu():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0                                          # 첫 경기 코치 마크가 Enter를 먼저 소비하지 않게
    app.state = "GAME"
    m.match_finished = True
    app.result_lock_until = 0.0
    calls = []
    app._restart_after_match = lambda: calls.append("restart")
    app._practice_after_match = lambda: calls.append("practice")
    app._request_menu_exit = lambda: calls.append("menu")
    app.renderer.result_focus_id = "restart"
    _key(app, pygame.K_RETURN)
    assert calls == ["restart"], f"Enter가 기본 포커스(재도전) 대신 {calls}를 실행"
    _key(app, pygame.K_RIGHT)
    assert app.renderer.result_focus_id == "practice"
    _key(app, pygame.K_SPACE)
    assert calls[-1] == "practice", calls
    _key(app, pygame.K_RIGHT)
    _key(app, pygame.K_RETURN)
    assert calls[-1] == "menu", calls
    import time
    app.result_lock_until = time.time() + 5                     # 세리머니 동안은 모두 무시
    n = len(calls)
    _key(app, pygame.K_RETURN)
    _key(app, pygame.K_r)
    assert len(calls) == n, calls


def test_pause_while_spectating_is_handled_by_pause_menu():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0                                          # 첫 경기 코치 마크가 Enter를 먼저 소비하지 않게
    app.state = "GAME"
    m.local_is_alive = False
    m.is_spectating = True
    app.is_paused = m.is_paused = True
    calls = []
    app._practice_after_match = lambda: calls.append("practice")
    app._restart_after_match = lambda: calls.append("restart")
    pk = app.settings.get_action_keys("pause")[0]
    _key(app, pygame.K_s)                                        # 일시정지 중 S는 관전을 끄면 안 됨
    assert m.is_spectating, "일시정지 창이 떠 있는데 S가 관전을 껐음"
    _key(app, pk)                                                # 일시정지 키는 연습 모드가 아니라 일시정지 해제
    assert not calls, calls
    assert not app.is_paused and not m.is_paused


def test_text_field_click_keeps_typing_and_commits_on_switch():
    app = _app()
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "match", "MENU"
    app.text_rects = {"player_name": pygame.Rect(100, 100, 200, 40), "initials": pygame.Rect(100, 200, 200, 40)}
    app.color_rects = [pygame.Rect(400, 100, 30, 30)]
    app._begin_text("player_name")
    app.player_name_input = "Hello"
    click = lambda pos: app._text_input_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    click((150, 120))                                            # 편집 중인 칸을 다시 클릭
    assert app.text_focus == "player_name" and app.player_name_input == "Hello", "재클릭이 입력을 지움"
    click((150, 220))                                            # 다른 칸 클릭: 이름이 확정돼야 함
    assert app.player_name == "Hello", f"다른 칸을 눌렀더니 이름이 저장되지 않음: {app.player_name!r}"
    assert app.text_focus == "initials"
    app._end_text(commit=False)
    app._begin_text("player_name")
    app.player_name_input = "World"
    click((410, 110))                                            # 색 칩 클릭도 확정
    assert app.player_name == "World", app.player_name


def test_english_strings_from_report_are_translated():
    import re
    import i18n
    i18n.set_language("en")
    try:
        for ko in ("느긋", "빠름", "프로", "Cyber Rush (오리지널)", "드릴 60초", "마스터 클리어! 모든 난이도 클리어", "★ B2B x2 쿼드! ★",
                   "Bot_07 연결 끊김 · 봇이 대신 플레이", "★ 새 스킨 해금!  Neon", "시스템", "(사람)",
                   "오리지널 3부작: Cyber Rush → Hyperdrive Override → Apex Protocol", "업적 달성!  Test 외 3개", "★ 업적 달성!  Test 외 3개"):
            out = i18n.tr(ko)
            assert not re.search("[가-힣]", out), f"영어에서 한글이 남음: {ko!r} -> {out!r}"
    finally:
        i18n.set_language("ko")


def test_replay_keeps_block_locked_before_first_update():
    from replay import ReplayRecorder
    e = BlockEngine(seed=2)
    e.replay_log = []                                            # 경기 시작과 함께 기록을 켜 둔 상태
    e.replay_log.append({"k": "L", "p": "O", "c": [[4, 19]], "r": [], "s": 0})
    rec = ReplayRecorder()
    rec.update(e, 0.0)                                           # 첫 update에서 이미 쌓인 사건을 버리면 안 됨
    assert [ev["k"] for ev in rec.events] == ["L"], rec.events


def test_validation_of_report_settings():
    from settings_manager import _valid_setting
    assert _valid_setting("drill_best", -5) == (True, 0)
    assert _valid_setting("pad_buttons", 7)[0] is False and _valid_setting("pad_buttons", None)[0]
    assert _valid_setting("resolution", "auto")[0] and _valid_setting("resolution", "1920x1080")[0]
    assert not _valid_setting("resolution", "banana")[0]


def test_modifier_keys_do_not_start_or_close_cards():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.rules_open = True
    app._handle_rules_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=0, unicode=""))
    assert app.rules_open, "Shift 하나로 규칙 카드가 닫힘"
    app._handle_rules_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a"))
    assert not app.rules_open


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
        print("[ALL BUGREPORT2 TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
