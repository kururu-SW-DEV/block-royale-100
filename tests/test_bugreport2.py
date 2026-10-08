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
    app.settings.filepath = os.path.join(tempfile.mkdtemp(), "set.json")          # 실제 settings.json과 분리하고 항상 기본값에서 시작 (사용자가 켜 둔 설정에 테스트가 좌우되지 않게)
    app.settings.reset_to_defaults()
    app.apply_visual_options()
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


def test_load_snapshot_validates_and_refills():
    e = BlockEngine(seed=1)
    snap = e.snapshot()
    f = BlockEngine(seed=2)
    f.load_snapshot(snap)
    assert len(f.next_queue) >= 5, "스냅샷은 다음 블록 3개만 담으므로 탐색용으로 채워야 함"
    bad_cases = [dict(snap, g=snap["g"][:5]), dict(snap, g=["Q" * 10] * 20), dict(snap, p=["X", 0, 3, 0]), dict(snap, n=["I", "?"])]
    before = [row[:] for row in f.grid]
    for bad in bad_cases:
        try:
            f.load_snapshot(bad)
        except ValueError:
            continue
        raise AssertionError(f"잘못된 스냅샷을 받아들임: {bad}")
    assert f.grid == before, "거부한 스냅샷이 보드를 바꿈"


def test_gamepad_remembers_devices_while_disabled():
    from gamepad import GamepadMapper
    seen = []
    m = GamepadMapper(lambda a: [], enabled=lambda: False)
    m.on_device_event = lambda e: seen.append(e.type)
    m.translate([pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)], False)
    assert seen == [pygame.JOYDEVICEADDED], "꺼 둔 동안 연결된 패드를 기억하지 못함 (나중에 켜도 안 열림)"


def test_stage_set_only_picks_finished_sets():
    from sound_fx import SoundManager
    sm = SoundManager.__new__(SoundManager)
    sm.bgm_stages = {1: ["a", "b"], 2: ["a"], 3: ["a", "b", "c"]}      # 2단계는 세트 1개만 합성 끝남
    sm.current_set_idx = 0
    assert sm._sets_ready() == 1
    for _ in range(30):
        assert sm.roll_stage_set("random") == 0
    assert sm.roll_stage_set(3) == 0
    sm.bgm_stages = {1: ["a", "b", "c", "d", "e"], 2: ["a"] * 5, 3: ["a"] * 5}
    assert sm._sets_ready() == 5 and sm.roll_stage_set(3) == 3


def test_records_digit_keys_ignored_on_replay_tab():
    app = _app()
    app.state, app.records_mode = "RECORDS", "replay"
    app.replay_view = None
    app.replay_list = []
    before = (app.records_size, app.records_diff)
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, mod=0, unicode="2"))
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode="f"))
    assert (app.records_size, app.records_diff) == before, "리플레이 탭에서 보이지 않는 필터가 바뀜"


def test_team_win_does_not_announce_final_duel_against_ally():
    app = _app()
    app.settings.set("rule_team", True)
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    me = m.local_player_id
    allies = [p for p in m.players if p != me and m.is_ally(me, p)]
    foes = [p for p in m.players if p != me and not m.is_ally(me, p)]
    assert allies and foes
    for pid in allies[1:]:
        m._eliminate_player(pid)
    for pid in foes[1:]:
        m._eliminate_player(pid)
    assert m.alive_count == 3 and not m.match_finished
    m._eliminate_player(foes[0])                                 # 마지막 적: 남는 2명은 같은 편
    assert m.match_finished and m.team_won
    assert not m._final_announced and not any("FINAL DUEL" in f["text"] for f in m.floating_texts), "아군을 상대로 결승전 연출이 나옴"
    assert m.winner_id == me
    app.settings.set("rule_team", False)


def test_lost_game_start_is_resent_to_waiting_client():
    import time
    import network as N
    host, client = N.NetworkManager(), N.NetworkManager()
    try:
        assert host.start_host(port=20977, max_players=10)
        client.start_client("127.0.0.1", 20977, "Guest")
        t0 = time.time()
        while not client.connected and time.time() - t0 < 3:
            client.client_retry_join()
            time.sleep(0.1)
        assert client.connected
        plist = [{"id": "HOST_P1", "name": "h", "is_ai": False}, {"id": client.my_player_id, "name": "Guest", "is_ai": False}]
        host.host_send_start_game(plist)
        t0 = time.time()
        while not client.game_started and time.time() - t0 < 2:
            time.sleep(0.05)
        assert client.game_started
        client.game_started = False                              # 세 번의 패킷이 모두 유실된 상황을 흉내
        client._last_ping = 0.0
        t0 = time.time()
        while not client.game_started and time.time() - t0 < 4:
            client._last_ping = 0.0
            client.client_keepalive(interval=0.0)
            time.sleep(0.2)
        assert client.game_started, "시작 신호를 다시 받지 못해 대기실에 갇힘"
    finally:
        client.stop()
        host.stop()


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
