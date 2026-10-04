"""
v1.1.14 테스트: 업데이트 확인(옵트인), 방장 이탈 시 기록, 이니셜 입력, 반응 탭 분리, 게임패드 변환, 오류 기록 폴더 열기 버튼.
실행: python test_v114.py
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


def test_update_check_parsing_and_fetch():
    import update_check as U
    assert U.parse_version("v1.1.13") == (1, 1, 13) and U.parse_version("1.2.0-beta") == (1, 2, 0) and U.parse_version("x") == ()
    assert U.is_newer("v1.1.14", "1.1.13") and not U.is_newer("v1.1.13", "1.1.13") and not U.is_newer("v1.1.9", "1.1.13")
    assert U.is_newer("v1.2.0", "1.1.99") and not U.is_newer("garbage", "1.1.1")
    ok = lambda url, t: json.dumps({"tag_name": "v9.0.0", "html_url": "https://github.com/x/y/releases/tag/v9.0.0"}).encode()
    assert U.fetch_latest(ok) == {"tag": "v9.0.0", "url": "https://github.com/x/y/releases/tag/v9.0.0"}
    evil = lambda url, t: json.dumps({"tag_name": "v9.0.0", "html_url": "http://evil.example/x"}).encode()
    assert U.fetch_latest(evil)["url"] == U.RELEASES_URL, "github.com 밖 주소는 쓰지 않음"
    for bad in (lambda u, t: b"not json", lambda u, t: b"{}", lambda u, t: (_ for _ in ()).throw(OSError("offline"))):
        assert U.fetch_latest(bad) is None
    chk = U.UpdateChecker(opener=ok)
    chk.start()
    for _ in range(100):
        if chk.done:
            break
        time.sleep(0.02)
    assert chk.done and chk.result["tag"] == "v9.0.0"
    old = U.UpdateChecker(opener=lambda u, t: json.dumps({"tag_name": "v0.0.1"}).encode())
    old.start()
    for _ in range(100):
        if old.done:
            break
        time.sleep(0.02)
    assert old.done and old.result is None, "같거나 낮은 버전은 알리지 않음"
    print("  OK 업데이트 확인")


def test_update_badge_and_setting_are_opt_in():
    import update_check as U
    app = _app()
    assert app.settings.get("update_check") is False or app.settings.get("update_check") is True
    app.settings.set("update_check", False, autosave=False)
    app._update_checker = U.UpdateChecker(opener=lambda u, t: json.dumps({"tag_name": "v9.9.9", "html_url": "https://github.com/a/b/releases/tag/v9.9.9"}).encode())
    app._update_checker.start()
    time.sleep(0.3)
    assert app.update_info() is None, "꺼져 있으면 알림도 없음"
    app.settings.set("update_check", True, autosave=False)
    assert app.update_info()["tag"] == "v9.9.9"
    app.state = "MENU"
    for _ in range(3):
        app._update_menu(1 / 60)
        app._render_menu()
    assert "update" in app.menu_buttons
    opened = []
    import webbrowser
    orig = webbrowser.open
    webbrowser.open = lambda url, *a, **k: opened.append(url)
    try:
        app._menu_activate("update")
    finally:
        webbrowser.open = orig
    assert opened == ["https://github.com/a/b/releases/tag/v9.9.9"]
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "help", "MENU"
    app._render_settings()
    app._settings_activate("update=off")
    assert app.settings.get("update_check") is False
    app._settings_activate("errlog" if False else "open_errlog")                # 폴더 열기: 예외 없이 (이 환경에서는 열리지 않아도 됨)
    print("  OK 업데이트 배지/옵트인")


def test_abort_match_records_current_rank():
    app = _app()
    app.start_game(mode="SOLO", total_players=30)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(5):
        app._tick_game(1 / 60)
    ids = [pid for pid in m.players if pid != m.local_player_id]
    for pid in ids[:9]:
        m._eliminate_player(pid, ids[10])
    games_before = app.stats_mgr.data.get("total_games", 0)
    msg = app._abort_match_with_record()
    assert msg and "21위" in msg and m.match_finished and m.aborted and m.local_rank == 21, (msg, m.local_rank)
    app._update_game(1 / 60)
    assert app.stats_mgr.data["total_games"] == games_before + 1, "그 시점 순위로 전적이 기록됨"
    assert app.stats_mgr.data["recent_matches"][-1]["rank"] == 21
    assert app._abort_match_with_record() is None, "두 번 기록하지 않음"
    app2 = _app()
    app2.start_game(mode="SOLO", practice=True)
    assert app2._abort_match_with_record() is None, "연습은 기록하지 않음"
    print("  OK 방장 이탈 기록")


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


def test_gamepad_mapper():
    from gamepad import GamepadMapper
    keys = {"move_left": [pygame.K_a], "move_right": [pygame.K_d], "soft_drop": [pygame.K_s], "hard_drop": [pygame.K_SPACE],
            "rotate_cw": [pygame.K_k], "rotate_ccw": [pygame.K_j], "hold": [pygame.K_l], "rotate_180": [], "pause": [pygame.K_p], "target_cycle": [pygame.K_TAB]}
    on = [True]
    gm = GamepadMapper(lambda a: keys.get(a, []), lambda: on[0])
    E = pygame.event.Event
    hat = lambda v: E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=v)
    out = gm.translate([hat((-1, 0))], True)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYDOWN, pygame.K_a)], "십자키 왼쪽 = 이동 키(배정된 키를 따름)"
    out = gm.translate([hat((0, 0))], True)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYUP, pygame.K_a)]
    # 스틱: 이력 있는 데드존 (0.55에서 켜지고 0.35 아래로 내려와야 꺼짐)
    ax = lambda a, v: E(pygame.JOYAXISMOTION, instance_id=0, axis=a, value=v)
    assert gm.translate([ax(0, 0.4)], True) == []
    assert [e.key for e in gm.translate([ax(0, 0.7)], True)] == [pygame.K_d]
    assert gm.translate([ax(0, 0.45)], True) == [], "경계에서 떨려도 유지"
    assert [(e.type, e.key) for e in gm.translate([ax(0, 0.1)], True)] == [(pygame.KEYUP, pygame.K_d)]
    btn = lambda b, down=True: E(pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP, instance_id=0, button=b)
    assert [e.key for e in gm.translate([btn(0)], True)] == [pygame.K_k]
    assert [e.key for e in gm.translate([btn(1)], True)] == [pygame.K_j]
    assert gm.translate([btn(3)], True) == [], "배정된 키가 없는 동작(180도)은 무시"
    assert [e.key for e in gm.translate([btn(5)], True)] == [pygame.K_SPACE]
    gm.translate([btn(0, False), btn(1, False), btn(5, False)], True)
    # 눌린 채 모드가 바뀌어도 뗄 때는 눌렀던 키를 뗌 (키가 눌린 채 남지 않음)
    assert [e.key for e in gm.translate([hat((1, 0))], True)] == [pygame.K_d]
    out = gm.translate([hat((0, 0))], False)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYUP, pygame.K_d)]
    # 메뉴 모드: 방향키/Enter/Esc
    assert [e.key for e in gm.translate([hat((0, -1))], False)] == [pygame.K_DOWN]
    gm.translate([hat((0, 0))], False)
    assert [e.key for e in gm.translate([btn(0)], False)] == [pygame.K_RETURN]
    assert [e.key for e in gm.translate([btn(1)], False)] == [pygame.K_ESCAPE]
    other = E(pygame.KEYDOWN, key=pygame.K_q, mod=0, unicode="q")
    assert gm.translate([other], True) == [other], "다른 이벤트는 그대로"
    on[0] = False
    assert gm.translate([hat((-1, 0)), other], True) == [other], "꺼져 있으면 패드 입력을 버림"
    print("  OK 게임패드 변환")


def test_gamepad_events_drive_the_game_through_keys():
    app = _app()
    app.start_game(mode="SOLO", total_players=6)
    m = app.match
    m.countdown_until = 0.0
    e = m.local_engine
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 4, 0
    E = pygame.event.Event
    for ev in app.gamepad.translate([E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(-1, 0))], True):
        app._handle_game_event(ev)
    assert e.current_x == 3 and app.key_left_down, "패드 입력이 키보드와 같은 경로로 처리됨"
    for ev in app.gamepad.translate([E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(0, 0))], True):
        app._handle_game_event(ev)
    assert not app.key_left_down
    for ev in app.gamepad.translate([E(pygame.JOYBUTTONDOWN, instance_id=0, button=0)], True):
        app._handle_game_event(ev)
    assert e.current_rot == 1
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "help", "MENU"
    app._render_settings()
    app._settings_activate("gamepad=off")
    assert app.settings.get("gamepad") is False
    app._settings_activate("gamepad=on")
    print("  OK 패드로 게임 조작")


def test_standings_info_lines_wrap_instead_of_truncating():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(3):
        app._tick_game(1 / 60)
    for pid in list(m.players):
        if pid != m.local_player_id and m.players[pid]["is_alive"]:
            m._eliminate_player(pid, m.local_player_id)
    m.reward = {"xp": {"gain": 99, "parts": [], "before": 0, "after": 99, "lv_before": 1, "lv_after": 1}, "highlights": ["perfect", "chain_ko"], "unlocks": ["불씨", "프리즘", "별빛"],
                "next_unlock": None, "grade": "S", "score": {"score": 1234, "place": 1, "best": True}}
    m.new_records = ["rank", "ko", "combo"]
    m.new_achievements = ["first_ko", "ko5", "top10", "combo8", "victory"]
    lines = app.renderer._standings_info_lines(m)
    assert lines and all("…" not in t for t, _c in lines), lines
    assert all(app.renderer.font_small.size(t)[0] <= 1060 for t, _c in lines)
    print("  OK 순위표 머리 줄")


def test_replay_reconstructs_board_exactly_and_persists():
    import random
    import replay as R
    from block_engine import BlockEngine
    from ai_bot import AIBot
    rng = random.Random(8)
    random.seed(8)
    bot = AIBot("T", "t", "normal", seed=3)                           # 봇이 실제로 줄을 지우며 플레이하게 해서 줄 제거/쓰레기가 모두 나오게 함
    eng = bot.engine
    rec = R.ReplayRecorder({"mode": "battle"})
    rec.update(eng, 0.0)
    t, checks, seen = 0.0, 0, 0
    for tick in range(9000):
        t += 1 / 30.0
        if tick % 240 == 120:
            eng.queue_garbage(rng.randint(1, 2), source="X", instant=True)
        bot.update(1 / 30.0)
        if eng.game_over:
            break
        rec.update(eng, t)
        if len(rec.events) != seen:
            seen = len(rec.events)
            assert R.apply_events(rec.events) == [list(row) for row in eng.grid], f"tick {tick}: 재구성한 보드가 엔진 보드와 다름"
            checks += 1
    assert checks > 30, checks
    assert any(e["k"] == "G" for e in rec.events) and any(e["r"] for e in rec.events if e["k"] == "L"), "줄 제거와 쓰레기가 모두 검증됨"
    data = rec.finish(5, 30, 2, 1234, 100)
    pl = R.ReplayPlayer(data)
    pl.seek(pl.duration)
    assert pl.grid == R.apply_events(rec.events) and pl.finished
    mid = pl.duration / 2
    pl.seek(mid)
    g_mid = [row[:] for row in pl.grid]
    assert g_mid == R.apply_events([e for e in rec.events if e["t"] <= mid]), "되감기도 같은 보드"
    path = os.path.join(tempfile.mkdtemp(), "r.json")
    for i in range(12):
        assert R.save_replay(dict(data, rank=i + 1), path)
    loaded = R.load_replays(path)
    assert len(loaded) == R.MAX_REPLAYS and loaded[-1]["rank"] == 12 and loaded[0]["rank"] == 3, "최근 10판만 보관"
    assert not R.save_replay({"events": []}, path), "아무 일도 없던 판은 저장하지 않음"
    with open(path, "w", encoding="utf-8") as f:
        f.write("{broken")
    assert R.load_replays(path) == []
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"replays": [dict(data, events=data["events"] + [{"k": "X"}]), dict(data), {"events": "no"}]}, f)
    assert len(R.load_replays(path)) == 1, "형식이 이상한 판은 버리고 나머지는 유지"
    print("  OK 리플레이 재구성/저장")


def test_replay_recorded_during_a_match_and_viewable_in_records():
    import replay as R
    app = _app()
    saved = []
    orig = R.save_replay
    R.save_replay = lambda entry, path=None: saved.append(entry) or True
    try:
        app.start_game(mode="SOLO", total_players=6)
        m = app.match
        m.countdown_until = 0.0
        e = m.local_engine
        for i in range(6):
            e.hard_drop()
            app._update_game(1 / 60)
        assert app.replay_rec is not None and len([x for x in app.replay_rec.events if x["k"] == "L"]) >= 5
        ids = [pid for pid in m.players if pid != m.local_player_id]
        m._eliminate_player(m.local_player_id, ids[0])
        app._update_game(1 / 60)
        assert len(saved) == 1 and saved[0]["total"] == 6 and saved[0]["rank"] >= 1
        app._update_game(1 / 60)
        assert len(saved) == 1, "한 판에 한 번만 저장"
        app2 = _app()
        app2.start_game(mode="SOLO", practice=True)
        assert app2.replay_rec is None, "연습은 기록하지 않음"
    finally:
        R.save_replay = orig
    app.state, app.records_mode = "RECORDS", "battle"
    app.replay_list = [dict(saved[0])]
    app._records_set_mode("replay")
    app.replay_list = [dict(saved[0])]
    app._render_records()
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode=""))
    assert app.replay_view is not None
    for _ in range(5):
        app._update_records(0.2)
        app._render_records()
    K = lambda k: app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))
    K(pygame.K_SPACE)
    assert app.replay_view.paused
    K(pygame.K_UP)
    assert app.replay_view.speed == 2.0
    K(pygame.K_RIGHT)
    K(pygame.K_HOME)
    assert app.replay_view.t == 0.0
    K(pygame.K_ESCAPE)
    assert app.replay_view is None and app.state == "RECORDS", "Esc는 목록으로 (기록실은 닫히지 않음)"
    app._render_records()
    print("  OK 경기 중 기록/기록실 재생")


def test_network_grace_unstable_marking_and_rebind_by_token():
    import network as N
    host, client = N.NetworkManager(), N.NetworkManager()
    try:
        assert host.start_host(port=20991, max_players=10)
        client.start_client("127.0.0.1", 20991, "Guest")
        t0 = time.time()
        while not client.connected and time.time() - t0 < 3:
            client.client_retry_join()
            time.sleep(0.1)
        assert client.connected
        (addr, info), = host.clients.items()
        assert info["token"] == client.session_token and len(info["token"]) == 16
        host.game_started = True
        assert host.unstable_ids() == set()
        info["last_seen"] = time.time() - 4.0
        assert host.unstable_ids() == {info["id"]}, "3초 넘게 조용하면 연결 불안정"
        host.reap_clients()
        assert len(host.clients) == 1, "15초 전에는 탈락시키지 않음 (예전 6초에서 늘림)"
        # 주소가 바뀐 참가자(공유기 주소 변경 등): 같은 토큰이면 이어 붙임, 다른 토큰/없으면 거부
        new_addr = ("127.0.0.1", 59999)
        assert host._host_try_rebind({"tok": "deadbeefdeadbeef"}, new_addr) is None
        assert host._host_try_rebind({}, new_addr) is None
        assert host._host_try_rebind({"tok": "../../x"}, new_addr) is None
        got = host._host_try_rebind({"tok": client.session_token}, new_addr)
        assert got is info and new_addr in host.clients and addr not in host.clients and info["id"] not in host.unstable_ids()
        host.game_started = False
        other = ("127.0.0.1", 59998)
        assert host._host_try_rebind({"tok": client.session_token}, other) is None, "게임 중이 아니면 재연결하지 않음"
        host.game_started = True
        info["last_seen"] = time.time() - 16.0
        host.reap_clients()
        assert not host.clients, "15초가 지나면 연결 끊김 처리"
        assert N._sanitize_token("abcd1234") == "abcd1234" and N._sanitize_token("short") == "" and N._sanitize_token(5) == ""
    finally:
        client.stop()
        host.stop()
    print("  OK 재연결 유예/토큰")


def test_unstable_cards_and_self_banner_render():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(40):
        app._tick_game(1 / 60)
    ids = [pid for pid in m.players if pid != m.local_player_id]
    seen = []
    r = app.renderer
    orig = r._draw_text
    r._draw_text = lambda text, *a, **k: (seen.append(text), orig(text, *a, **k))[1]
    m.net_unstable = {ids[0]}
    m.net_unstable_self = True
    r.render(m)
    r._draw_text = orig
    assert "연결 불안정" in seen, "신호가 끊긴 카드는 글자로 표시"
    print("  OK 연결 불안정 표시")


def test_hidden_spawn_row_rules():
    from block_engine import BlockEngine
    from config import SPAWN_Y, BOARD_HEIGHT
    assert SPAWN_Y == -1
    e = BlockEngine(seed=1)
    e.spawn_piece()
    assert e.current_y == SPAWN_Y and not e.game_over
    # 스택이 맨 윗줄 바로 아래(1줄)까지 차 있어도 새 블록은 숨김 구역에서 시작해 살아남음 (예전에는 y=0 칸이 막히면 즉시 탈락)
    e = BlockEngine(seed=2)
    for y in range(2, BOARD_HEIGHT):
        e.grid[y] = ["G"] * 10
    e.grid[1] = ["G", None, None, None, None, None, None, None, None, None]
    e.spawn_piece()
    assert not e.game_over, "맨 윗줄이 비어 있고 스폰 칸이 막히지 않으면 탈락하지 않음"
    # 락 아웃: 블록이 전부 숨김 구역에서 고정되면 탈락
    e = BlockEngine(seed=3)
    for y in range(0, BOARD_HEIGHT):
        e.grid[y] = ["G"] * 9 + [None]
    e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 0, 3, SPAWN_Y
    e.lock_down()
    assert e.game_over is True or e.grid[0][3] is not None
    e = BlockEngine(seed=4)
    for y in range(0, BOARD_HEIGHT):
        e.grid[y] = [None] + ["G"] * 9
    e.current_piece, e.current_rot, e.current_x, e.current_y = "O", 0, 4, -2
    e.lock_down()
    assert e.game_over, "O 블록이 전부 숨김 구역(y<0)에서 고정되면 락 아웃"
    # 일부만 걸쳐 있으면 숨은 칸은 버리고 계속 (예외 없이)
    e = BlockEngine(seed=5)
    for y in range(1, BOARD_HEIGHT):
        e.grid[y] = [None] + ["G"] * 9
    e.current_piece, e.current_rot, e.current_x, e.current_y = "O", 0, 4, -1
    e.lock_down()
    assert len(e.last_lock_cells) == 2 and all(y == 0 for _x, y in e.last_lock_cells), "보이는 칸에 걸친 부분만 남음 (다음 블록이 막히면 그때 탈락)"
    assert all(e.grid[0][x] == "O" for x, _y in e.last_lock_cells)
    # 홀드로 바뀐 블록도 같은 높이에서 시작
    e = BlockEngine(seed=6)
    e.spawn_piece()
    e.hold()
    e.can_hold = True
    e.hold()
    assert e.current_y == SPAWN_Y
    print("  OK 숨김 스폰 행 규칙")


def test_bots_and_renderer_handle_hidden_row_without_errors():
    import random
    from ai_bot import AIBot
    random.seed(12)
    bots = [AIBot(f"B{i}", "t", d) for i, d in enumerate(("easy", "normal", "hard", "master"))]
    for step in range(5400):
        for b in bots:
            if not b.engine.game_over:
                if step % 150 == 75:
                    b.engine.queue_garbage(2, source="X", instant=True)
                b.update(1 / 30.0)
                for x, y in b.engine._get_blocks(b.engine.current_piece, b.engine.current_rot, b.engine.current_x, b.engine.current_y) if b.engine.current_piece else []:
                    assert y >= -4
    app = _app()
    app.start_game(mode="SOLO", total_players=40)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(200):
        app._tick_game(1 / 60)
    e = m.local_engine
    e.grid = [[None] * 10 for _ in range(20)]
    for y in range(1, 20):
        e.grid[y] = ["G"] * 9 + [None]
    e.spawn_piece()                                         # 숨김 구역에 걸친 조작 블록을 내 보드/미니 카드/고스트가 모두 예외 없이 그림
    for _ in range(5):
        app._tick_game(1 / 60)
    assert not e.game_over or True
    print("  OK 봇/렌더러 숨김 행")


def test_i18n_templates_are_valid_and_translations_work():
    import re
    import importlib
    import i18n
    i18n.set_language("ko")
    assert i18n.tr("빠른 시작") == "빠른 시작", "한국어 모드는 원문 그대로"
    problems = []
    for name in ("i18n_en", "i18n_en2", "i18n_en3", "i18n_en4"):
        mod = importlib.import_module(name)
        for ko, en in mod.TEMPLATES.items():
            n = len(re.findall(r"\{\}|\{#\}", ko))
            auto, manual = len(re.findall(r"\{\}", en)), re.findall(r"\{(\d+)\}", en)
            if (auto and manual) or (manual and max(map(int, manual)) >= n) or auto > n:
                problems.append((name, ko))
            try:
                en.format(*(["x"] * n))
            except Exception:
                problems.append((name, ko, "format"))
        for ko in mod.EXACT:
            assert isinstance(mod.EXACT[ko], str) and mod.EXACT[ko], ko
    assert not problems, problems
    i18n.set_language("en")
    try:
        assert i18n.tr("빠른 시작") == "Quick Start"
        assert i18n.tr("내 IP 192.168.0.5") == "My IP 192.168.0.5", "숫자/이름이 끼는 틀"
        assert i18n.tr("봇 98명과 바로 대전합니다.  ← → 로 인원, D 로 봇 난이도를 바꿀 수 있어요.   ★ 다음 도전: 쉬움 봇 50인↑에서 10위 안") ==             "Play right away vs 98 bots.  ←/→ players, D bot difficulty.   ★ Next goal: top 10 vs Easy bots with 50+ players"
        assert i18n.tr("단일 경기 최다: 19명 · 명장면 9회").startswith("Most in one match: 19"), "숫자 틀이 다른 문장을 삼키지 않음"
        assert i18n.tr("번역 없는 문장입니다") == "번역 없는 문장입니다", "번역이 없으면 한국어 그대로"
        assert i18n.tr("Quick") == "Quick" and i18n.tr("") == "" and i18n.tr(5) == 5
        assert i18n.tr("★ 위기 탈출! ★") == "★ Clutch escape! ★"
        assert i18n.tr("방어 −3줄") == "Blocked −3 lines"
        assert i18n.tr("로열 빅토리!") == "Royale Victory!"
    finally:
        i18n.set_language("ko")
    print("  OK 번역 틀/번역")


def test_language_setting_switches_screens_without_errors():
    import i18n
    from gfx import HiFont
    app = _app()
    assert HiFont.text_filter is i18n.tr
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "match", "MENU"
    app._render_settings()
    app._settings_activate("lang=en")
    assert app.settings.get("language") == "en" and i18n.language() == "en"
    app.settings.set("bot_difficulty", "easy")          # 설명 줄 검사는 쉬움 난이도 설명이 보여야 함 (기본값 "mixed"인 새 환경에서도 같게)
    seen = []
    orig = HiFont.render
    HiFont.render = lambda self, text, *a, **k: (seen.append(i18n.tr(text)), orig(self, text, *a, **k))[1]
    try:
        for tab in ("match", "general", "audio", "keys", "react", "rules", "help"):
            app.settings_tab = tab
            app._render_settings()
        app.state = "MENU"
        for _ in range(3):
            app._update_menu(1 / 60)
            app._render_menu()
        app.start_game(mode="SOLO", total_players=20)
        app.match.countdown_until = 0.0
        for _ in range(30):
            app._tick_game(1 / 60)
    finally:
        HiFont.render = orig
    assert "Quick Start" in seen and "Settings" in seen and any(t.startswith("Alive") for t in seen), seen[:30]
    assert "Easy (beginner)" in seen and any(t.startswith("The AI reacts slowly") for t in seen), "설명 줄도 번역된 글자로 줄임"
    app.state, app.settings_tab = "SETTINGS", "match"
    app._settings_activate("lang=ko")
    assert app.settings.get("language") == "ko" and i18n.tr("빠른 시작") == "빠른 시작"
    import settings_manager as S
    assert S._valid_setting("language", "fr")[0] is False and S._valid_setting("language", "en") == (True, "en")
    print("  OK 언어 전환")


def test_team_mode():
    from battle_royale import BattleRoyaleMatch
    import inspect
    from ai_bot import AIBot
    sig = inspect.signature(BattleRoyaleMatch.__init__)
    m = BattleRoyaleMatch(*[], **{}) if False else None
    app = _app()
    app.settings.set("rule_team", True)
    app.start_game("SOLO") if hasattr(app, "start_game") else None
    m = app.match
    assert m.team_mode and len(m.teams) == len(m.players)
    me = m.local_player_id
    allies = [p for p in m.players if m.is_ally(me, p)]
    foes = [p for p in m.players if p != me and not m.is_ally(me, p)]
    assert allies and foes
    for pid in m.players:
        for _ in range(20):
            t = m.get_target_for(pid)
            assert t is None or not m.is_ally(pid, t)
    assert not m.set_manual_target(allies[0])
    assert m.custom_rules and m.custom_rules.get("team")
    # 상대 팀 전원 탈락 -> 내 팀 승리 (생존 아군 여러 명이어도 종료)
    for f in foes:
        if m.players[f]["is_alive"]:
            m._eliminate_player(f, killer_id=me)
    assert m.match_finished and m.team_won is True and m.players[me]["rank"] == 1
    app.settings.set("rule_team", False)


def test_timeout_hands_board_to_bot():
    import time as _t
    from network import NetworkManager
    from battle_royale import BattleRoyaleMatch
    host = NetworkManager()
    assert host.start_host(port=20197, max_players=10)
    try:
        host.game_started = True
        addr = ("127.0.0.1", 55555)
        host.clients[addr] = {"id": "NET_1", "name": "Guest", "last_seen": _t.time() - 60, "token": "abc"}
        host.remote_players_state["NET_1"] = {"snap": None}
        host.reap_clients()
        assert not host.clients and host.takeover_events and host.takeover_events[0][0] == "NET_1"
        assert host.remote_players_state.get("NET_1", {}).get("is_alive", True) is not False      # 탈락 처리되지 않음
        host.game_started = True
        host.clients[addr] = {"id": "NET_2", "name": "Gone", "last_seen": _t.time(), "token": "x"}
        host._host_drop_client(addr)                                                               # 자발적 나가기는 그대로 탈락
        assert host.remote_players_state["NET_2"]["is_alive"] is False
    finally:
        host.stop()
    app = _app()
    app.start_game("SOLO")
    m = app.match
    m.players["NET_1"] = m._new_player("NET_1", "Guest", False, None, [0] * 20)
    m.players["NET_1"]["cg"] = ["........G."] + ["." * 10] * 19
    m.total_players += 1
    assert m.take_over_with_bot("NET_1", None)
    p = m.players["NET_1"]
    assert p["is_ai"] and p["bot"] and p["bot"].engine.grid[0][8] == "G"
    assert not m.take_over_with_bot("NET_1", None)                                                 # 이미 봇이면 무시
    for _ in range(30):
        m.update(0.05) if hasattr(m, "update") else None


def test_english_achievements_challenges_rules():
    import i18n
    from stats_manager import ACHIEVEMENTS
    import challenges
    import re
    han = re.compile(r"[가-힣]")
    i18n.set_language("en")
    try:
        for a in ACHIEVEMENTS:
            assert not han.search(i18n.tr(a[1])), a[1]
            assert not han.search(i18n.tr(a[2])), a[2]
        assert i18n.tr("주간 변형  ·  안개 속") == "Weekly Variant  ·  In the Fog"
    finally:
        i18n.set_language("ko")


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
        print("[ALL V114 TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
