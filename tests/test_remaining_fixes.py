"""
외부 분석(2026-10-08)의 나머지 항목을 코드로 확인해 고친 것의 회귀 테스트
- 호스트 이름 DNS 조회가 메인 스레드를 막지 않음 / 방 목록 키보드·패드 선택 / 영어 줄바꿈이 단어 중간에서 끊기지 않음
- 관전 대상 탈락 시 1.2초 뒤 처치한 상대로 전환 / alpha_rect 캐시 / 조작키 캐시 / 구버전 리플레이 재생 / 창 초점 상실
실행: python tests/test_remaining_fixes.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame


def _app():
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    return app


def _start(app, players=10):
    app.start_game(mode="SOLO", total_players=players)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    app.state = "GAME"
    return m


def test_hostname_lookup_does_not_block_the_ui_thread():
    import socket
    import network as N
    orig = socket.gethostbyname
    nm = N.NetworkManager()
    try:
        socket.gethostbyname = lambda h: (time.sleep(1.5), (_ for _ in ()).throw(OSError("no such host")))[1]
        t0 = time.perf_counter()
        assert nm.start_client("typo.invalid-host", 20955, "T") is True
        assert time.perf_counter() - t0 < 0.6, "DNS 조회를 기다리느라 메인 스레드가 멈춤"
        t0 = time.time()
        while nm.join_rejected is None and time.time() - t0 < 6:
            time.sleep(0.05)
        assert nm.join_rejected == "unresolved", nm.join_rejected
        nm.client_retry_join()                                   # 주소가 없는 동안 호출해도 오류 없음
    finally:
        socket.gethostbyname = orig
        nm.stop()
    nm2 = N.NetworkManager()
    try:
        assert not nm2._is_ip_literal("my-host") and nm2._is_ip_literal("192.168.0.7") and nm2._is_ip_literal("::1")
        assert nm2.start_client("   ", 20955, "T") is False
    finally:
        nm2.stop()


def test_join_menu_rooms_can_be_chosen_with_keys():
    app = _app()
    app.state = "JOIN_MENU"
    app.join_ip_input = ""
    rows = [{"host": "10.0.0.5", "port": app.host_port, "ok": True, "rect": None, "tag": "LAN", "name": "A", "players": 1, "max": 10},
            {"host": "10.0.0.6", "port": 25555, "ok": True, "rect": None, "tag": "LAN", "name": "B", "players": 1, "max": 10}]
    app.join_rows = rows
    joined = []
    app._join_by_input = lambda: joined.append(app.join_ip_input)
    key = lambda k: app._handle_join_menu_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))
    key(pygame.K_DOWN)
    assert app.join_sel == 0
    key(pygame.K_DOWN)
    key(pygame.K_DOWN)
    assert app.join_sel == 1, "목록 끝에서 넘어가지 않음"
    key(pygame.K_UP)
    assert app.join_sel == 0
    key(pygame.K_UP)
    assert app.join_sel is None, "첫 줄에서 위로 가면 선택 해제"
    key(pygame.K_DOWN)
    key(pygame.K_DOWN)
    key(pygame.K_RETURN)
    assert joined == ["10.0.0.6:25555"], joined
    app.join_sel = None
    app.join_ip_input = ""
    key(pygame.K_RETURN)                                         # 주소를 안 적고 Enter: 목록의 첫 방
    assert joined[-1] == "10.0.0.5", joined
    app.join_ip_input = "1.2.3.4"
    app.join_sel = 1
    app._handle_join_menu_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, mod=0, unicode="5"))
    assert app.join_sel is None, "글자를 입력하면 주소 입력 상태로 돌아감"


def test_english_wrap_never_splits_words_in_the_records_screen():
    import i18n
    app = _app()
    i18n.set_language("en")
    try:
        text = "Eliminate 10 opponents in a single match without dying"
        font = app.font_tiny
        lines = app._wrap_text(text, font, 130)
        assert len(lines) >= 2
        words = set(text.split())
        for ln in lines:
            for w in ln.split():
                assert w in words, f"단어 중간에서 끊김: {ln!r}"
        assert app._wrap_text(text, font, 130) == lines, "캐시된 결과가 다름"
        assert app._wrap_cache, "줄바꿈 결과를 캐시해야 함"
    finally:
        i18n.set_language("ko")


def test_spectate_switches_after_a_delay_and_prefers_the_killer():
    app = _app()
    m = _start(app, 12)
    me = m.local_player_id
    m._eliminate_player(me)
    m.is_spectating = True
    bots = [p for p in m.players if p != me and m.players[p]["is_alive"]]
    victim, killer, other = bots[0], bots[5], bots[1]
    m.spectate_target_id = victim
    m._eliminate_player(victim, killer)
    t0 = time.time()
    m._check_spectate_target(t0)
    assert m.spectate_target_id == victim, "탈락 장면을 보여 주지 않고 바로 넘어감"
    m._check_spectate_target(t0 + 0.5)
    assert m.spectate_target_id == victim
    m._check_spectate_target(t0 + 1.3)
    assert m.spectate_target_id == killer, "처치한 상대로 넘어가야 함"
    assert m.spectate_notice and "패배" in m.spectate_notice["text"]
    m.players[killer]["is_alive"] = False                         # 처치한 쪽도 죽었다면 순서상 다음 생존자
    m.alive_count -= 1
    t1 = time.time()
    m._check_spectate_target(t1)
    m._check_spectate_target(t1 + 1.3)
    assert m.players[m.spectate_target_id]["is_alive"]


def test_alpha_rect_cache_draws_identical_pixels():
    from gfx import CANVAS
    pygame.display.set_mode((400, 300))
    CANVAS.attach(pygame.display.get_surface())
    CANVAS.__dict__.pop("_alpha_rect_cache", None)
    snap = []
    for i in range(3):
        CANVAS.display.fill((20, 30, 50))
        CANVAS.alpha_rect((10, 10, 120, 60), (255, 40, 60, 110), radius=8)
        CANVAS.alpha_rect((150, 10, 80, 60), (90, 200, 255, 160), width=2, radius=6)
        snap.append(pygame.image.tobytes(CANVAS.display, "RGBA"))
        if i == 0:
            CANVAS.__dict__.pop("_alpha_rect_cache", None)         # 첫 그림은 캐시 없이 새로 만든 것
    assert snap[0] == snap[1] == snap[2], "캐시를 쓴 그림이 달라짐"
    assert len(CANVAS._alpha_rect_cache) == 2, "같은 모양은 한 장만 만들어야 함"


def test_bound_key_cache_follows_key_changes():
    from settings_manager import SettingsManager
    from app_common import ACTION_NAMES
    s = SettingsManager(filepath=os.path.join(tempfile.mkdtemp(), "set.json"))
    assert not s.is_bound_key(pygame.K_F9, ACTION_NAMES)
    assert s.is_bound_key(pygame.K_SPACE, ACTION_NAMES)
    s.set_action_key("hard_drop", pygame.K_F9)
    assert s.is_bound_key(pygame.K_F9, ACTION_NAMES), "키를 바꿨는데 캐시가 그대로"
    s.set_key_preset("arcade")
    assert not s.is_bound_key(pygame.K_F9, ACTION_NAMES), "프리셋으로 되돌렸는데 캐시가 그대로"
    s.set_key_preset("wasd")
    assert s.is_bound_key(pygame.K_w, ACTION_NAMES)


def test_old_format_replays_still_play():
    from replay import ReplayPlayer, _clean
    legacy = {"date": "10-01 12:00", "rank": 5, "total": 100, "kos": 1, "score": 900, "secs": 30,         # mode/custom 없음 (v1.2.0 이전)
              "events": [{"k": "L", "t": 1.0, "p": "O", "c": [[4, 19], [5, 19], [4, 18], [5, 18]], "r": [], "s": 10},
                         {"k": "L", "t": 2.0, "p": "I", "c": [[0, 19], [1, 19], [2, 19], [3, 19]], "r": [], "s": 20},   # cp/nx/hd/ig 없음
                         {"k": "G", "t": 3.0, "n": 2, "h": [3, 3]},
                         {"k": "L", "t": 4.0, "p": "T", "c": [[6, 17], [7, 17], [8, 17], [7, 16]], "r": [], "s": 30, "cp": "I", "nx": "OTL", "hd": "", "ig": 0}],
              "extra_future_field": {"x": 1}}
    clean = _clean(legacy)
    assert clean is not None and clean["mode"] == "battle" and clean["custom"] is False
    pl = ReplayPlayer(clean)
    for t in (0.5, 1.5, 3.5, 5.0, 0.2, 5.0):                      # 앞으로/되감기 모두
        pl.seek(t)
    assert pl.score == 30 and pl.next == "OTL"
    pl2 = ReplayPlayer({"events": [], "secs": 3})                  # 사건이 없는 판
    pl2.seek(2.0)
    assert _clean({"events": "not a list"}) is None and _clean(None) is None


def test_losing_window_focus_releases_keys_and_pauses_solo_only():
    app = _app()
    m = _start(app)
    app.key_left_down = app.key_down_down = True
    app.h_dir = -1
    app._handle_game_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    assert not app.key_left_down and not app.key_down_down and app.h_dir == 0, "창 초점을 잃었는데 키가 눌린 채 남음"
    assert app.is_paused and m.is_paused, "솔로 경기는 창 초점을 잃으면 자동 일시정지"
    app.is_paused = m.is_paused = False
    app.net_mgr.mode = "HOST"                                     # 네트워크 경기는 멈출 수 없으니 입력만 정리
    app.key_right_down = True
    app._handle_game_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    assert not app.key_right_down and not app.is_paused
    app.net_mgr.mode = "NONE"


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
        print("[ALL REMAINING FIX TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
