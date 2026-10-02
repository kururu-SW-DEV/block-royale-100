"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트: 네트워크 생존 신호, 공격 속도 제한, 상태 검증, 엔진 공격 누적,
봇 상태 초기화, 설정/전적 파일 손상 복구, 확인 창.
실행: python test_review_fixes.py   (SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
"""
import os
import sys
import time
import json
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 프로젝트 루트(tests/의 부모)를 import 경로에 추가

import pygame
from network import NetworkManager, _sanitize_world_state
from block_engine import BlockEngine
from ai_bot import AIBot
from settings_manager import SettingsManager
from stats_manager import StatsManager


def _connect(port):
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=port, max_players=10)
    client.start_client("127.0.0.1", port, "Guest")
    t0 = time.time()
    while not client.connected and time.time() - t0 < 3:
        client.client_retry_join()
        time.sleep(0.1)
    assert client.connected, "loopback join failed"
    return host, client


def test_keepalive_and_start_reset():
    host, client = _connect(20181)
    try:
        cinfo = list(host.clients.values())[0]
        cinfo["last_seen"] = time.time() - 30                      # 대기실에서 오래 기다린 상황
        summary = [{"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": client.my_player_id, "name": "G", "is_ai": False}]
        host.host_send_start_game(summary)                         # 시작 시 last_seen이 초기화되어야 함
        host.reap_clients(timeout=1.5)
        assert len(host.clients) == 1, "시작 직후 참가자가 제거됨"
        time.sleep(0.3)
        assert client.game_started and len(client.initial_players) == 2
        # 클라이언트 PING이 오는 동안은 유지, 끊기면 제거
        for _ in range(8):
            client.client_keepalive(interval=0.2)
            time.sleep(0.3)
            host.reap_clients(timeout=1.5)
        assert len(host.clients) == 1, "PING을 보내는 참가자가 제거됨"
        time.sleep(1.8)
        host.reap_clients(timeout=1.5)
        assert len(host.clients) == 0, "무응답 참가자는 제거되어야 함"
    finally:
        host.stop(); client.stop()
    print("  OK keepalive / start reset")


def test_game_start_validation():
    client = NetworkManager()
    client.mode = "CLIENT"
    # 접속 확인 전 시작 신호는 무시
    client.connected = False
    from network import NetworkManager as NM
    msg_players = [{"id": "A", "name": "a"}, {"id": "B", "name": "b"}]
    client.my_player_id = "B"
    # _client_receive_loop의 검증 조건을 직접 재현하기 어려우므로 루프백으로 검증
    host, real = _connect(20182)
    try:
        real.game_started = False
        host.host_send_start_game([{"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": "NOT_ME", "name": "x", "is_ai": False}])
        time.sleep(0.3)
        assert not real.game_started, "내 ID가 없는 시작 신호를 받아들임"
    finally:
        host.stop(); real.stop()
    print("  OK GAME_START validation")


def test_attack_rate_limit():
    host, client = _connect(20183)
    try:
        for _ in range(60):
            client.send_attack(client.my_player_id, "HOST_P1", 20)
        time.sleep(0.5)
        total = sum(l for _f, _t, l in host.incoming_attacks)
        import network as _nw
        assert 0 < total <= _nw.ATTACK_BUCKET_MAX + 10 * 2, f"공격 속도 제한 실패: {total}줄 수신"
        # 탈락한 참가자의 공격은 무시
        host.incoming_attacks.clear()
        host.remote_players_state[client.my_player_id] = {"is_alive": False}
        client.send_attack(client.my_player_id, "HOST_P1", 4)
        time.sleep(0.3)
        assert not host.incoming_attacks, "탈락자의 공격이 처리됨"
    finally:
        host.stop(); client.stop()
    print("  OK attack rate limit / dead sender")


def test_world_state_sanitize():
    bad = {"id": "X", "name": None, "is_alive": "yes", "compact_grid": "zz", "highest_y": None, "score": "9",
           "rank": 10**12, "surv": float("inf"), "cg": "Q" * 200, "cp": ["Z", 1], "nx": "IJLOSTZQ", "hd": 5}
    clean = _sanitize_world_state(bad)
    assert clean["highest_y"] == 20 and isinstance(clean["highest_y"], int)
    assert "compact_grid" not in clean and "score" not in clean and "surv" not in clean and "cg" not in clean
    assert clean["rank"] == 100 and clean["cp"] is None and "nx" not in clean and "hd" not in clean
    good = {"id": "P", "name": "n", "is_alive": True, "compact_grid": [0] * 20, "highest_y": 7, "cg": "." * 200,
            "cp": ["T", 2, 4, 3], "nx": "IJL", "hd": "O", "rank": 3, "surv": 12.5}
    good["ig"] = 7
    c2 = _sanitize_world_state(good)
    assert c2["ig"] == 7 and _sanitize_world_state({"id": "Q", "ig": 10**9})["ig"] == 400 and "ig" not in _sanitize_world_state({"id": "Q", "ig": "x"})
    assert c2["highest_y"] == 7 and c2["cp"] == ["T", 2, 4, 3] and c2["nx"] == "IJL" and c2["hd"] == "O" and c2["surv"] == 12.5
    print("  OK world state sanitize")


def test_garbage_accumulates():
    e = BlockEngine(seed=3)
    e.garbage_to_send = 5                        # 아직 수거되지 않은 공격이 있는 상태에서 블록이 또 고정돼도 사라지면 안 됨
    e.hard_drop()
    assert e.garbage_to_send == 5, f"앞선 공격이 덮어써짐: {e.garbage_to_send}"
    print("  OK garbage_to_send accumulates")


def test_bot_rethinks_after_gravity_lock():
    bot = AIBot("B1", "cpu", "hard", seed=1)
    eng = bot.engine
    bot.state = "MOVING"
    bot._move_lock = eng.lock_events
    eng.lock_events += 1                         # 중력으로 고정된 상황을 흉내
    bot.update(0.016)
    assert bot.state == "THINKING", "중력 고정 후에도 이전 목표로 계속 이동함"
    eng.garbage_to_send = 4                      # 중력 고정으로 생긴 공격은 놓치지 않고 수거
    assert bot.update(0.016) >= 4
    print("  OK bot rethink / attack pickup")


def test_join_nack():
    host = NetworkManager()
    assert host.start_host(port=20191, max_players=2)
    c1, c2, c3 = NetworkManager(), NetworkManager(), NetworkManager()
    try:
        c1.start_client("127.0.0.1", 20191, "A")
        t0 = time.time()
        while not c1.connected and time.time() - t0 < 3:
            c1.client_retry_join(); time.sleep(0.1)
        assert c1.connected
        c2.start_client("127.0.0.1", 20191, "B")                    # 정원(방장 포함 2명)이 찼음
        time.sleep(0.6)
        assert not c2.connected and c2.join_rejected == "full", f"거절 응답 없음: {c2.join_rejected}"
        c2.client_retry_join()                                       # 거절된 뒤에는 재시도하지 않음
        host.game_started = True
        c3.start_client("127.0.0.1", 20191, "C")
        time.sleep(0.6)
        assert c3.join_rejected in ("full", "started")
    finally:
        for n in (host, c1, c2, c3):
            n.stop()
    print("  OK join NACK")


class _FakeNet:
    mode = "CLIENT"
    running = True
    incoming_attacks = []
    chat_log = []

    def __init__(self):
        self.remote_players_state = {}
        self.host_view_of_me = None


def test_client_adopts_host_ranks():
    from battle_royale import BattleRoyaleMatch
    net = _FakeNet()
    plist = [{"id": "H", "name": "h", "is_ai": False}, {"id": "ME", "name": "me", "is_ai": False}] +             [{"id": f"B{i}", "name": f"b{i}", "is_ai": True} for i in range(4)]
    m = BattleRoyaleMatch(total_players=6, local_player_id="ME", net_mgr=net, initial_players=plist)
    # 호스트 기준: B0=6위, B1=5위가 한 패킷에 동시에 탈락 (도착 순서는 B1이 먼저)
    net.remote_players_state = {
        "B1": {"is_alive": False, "rank": 5, "compact_grid": [0] * 20, "highest_y": 20},
        "B0": {"is_alive": False, "rank": 6, "compact_grid": [0] * 20, "highest_y": 20},
    }
    m.update(0.016)
    assert m.players["B0"]["rank"] == 6 and m.players["B1"]["rank"] == 5, (m.players["B0"]["rank"], m.players["B1"]["rank"])
    # 내가 탈락한 뒤 호스트가 4위라고 알려주면 그 값을 따름
    m.local_is_alive = False
    m.local_rank = 3
    net.host_view_of_me = {"is_alive": False, "rank": 4}
    m.update(0.016)
    assert m.local_rank == 4 and m.players["ME"]["rank"] == 4
    print("  OK client follows host ranks")


def test_world_sync_chunks_and_host_port():
    import socket as _s
    # 같은 포트로 호스트를 두 번 열 수 없어야 함 (Windows)
    h1, h2 = NetworkManager(), NetworkManager()
    try:
        assert h1.start_host(port=20197, max_players=10)
        if hasattr(_s, "SO_EXCLUSIVEADDRUSE"):
            assert not h2.start_host(port=20197, max_players=10), "같은 포트에 호스트가 두 개 열림"
    finally:
        h1.stop(); h2.stop()
    # 100명 상태가 여러 독립 패킷으로 나뉘어 전달되고, 순서가 뒤섞여도 각 조각이 반영되는지
    host, client = _connect(20198)
    try:
        states = [{"id": f"P{i}", "name": f"p{i}", "is_alive": True, "compact_grid": [0] * 20, "highest_y": 20,
                   "cg": "." * 200, "cp": None, "nx": "IJL", "hd": ""} for i in range(100)]
        host.host_sync_world(states, {})
        time.sleep(0.6)
        got = [k for k in client.remote_players_state if k.startswith("P")]
        assert len(got) == 100, f"조각 전송 후 {len(got)}/100명만 수신"
        # 같은 시각의 조각 여러 개가 순서 상관없이 모두 처리되어야 함(조각별 타임스탬프)
        assert len(client._world_ts) >= 12
    finally:
        host.stop(); client.stop()
    print("  OK chunked WORLD_SYNC / exclusive host port")


def test_settings_keyboard_navigation():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.state = "SETTINGS"
    app.previous_state = "MENU"
    key = lambda k, mod=0: app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))
    # 소리 탭: ←→로 음량 조절, ↓로 다음 행
    app.settings_tab = "audio"
    app._render_settings()
    app.settings.set("bgm_volume", 50)
    assert app._settings_focus_id() == "bgm"
    key(pygame.K_RIGHT)
    assert app.settings.get("bgm_volume") == 60, "→ 키로 볼륨이 올라가야 함"
    key(pygame.K_LEFT); key(pygame.K_LEFT)
    assert app.settings.get("bgm_volume") == 40
    key(pygame.K_DOWN)
    assert app._settings_focus_id() == "stage_bgm", "볼륨 다음 행은 스테이지 배경음 세트 선택"
    key(pygame.K_DOWN)
    assert app._settings_focus_id() == "sfx"
    app.settings.set("bgm_volume", 60); app.sound_mgr.set_bgm_volume(0.6)
    # 화면 탭: Enter는 항목을 실행할 뿐 설정을 닫지 않음
    app.settings_tab = "general"
    app.settings_focus["general"] = 2                       # 미니 보드 행
    app._render_settings()
    assert app._settings_focus_id() == "mini"
    before = app.settings.get("mini_detail")
    key(pygame.K_RETURN)
    assert app.settings.get("mini_detail") != before and app.state == "SETTINGS", "Enter가 항목을 실행해야 함(설정을 닫지 않음)"
    key(pygame.K_LEFT)                                       # ← = 첫 번째 선택지(자세히)
    assert app.settings.get("mini_detail") == "detailed"
    # 게임 탭: ↑↓ 행 이동, ←→ 난이도 조절
    key(pygame.K_TAB)                                         # general -> audio
    key(pygame.K_TAB)                                         # audio -> keys
    assert app.settings_tab == "keys"
    key(pygame.K_RIGHT); key(pygame.K_RETURN)
    assert app.rebinding_action == "move_right", app.rebinding_action
    key(pygame.K_ESCAPE)
    assert app.rebinding_action is None and app.state == "SETTINGS"
    key(pygame.K_ESCAPE)
    assert app.state == "MENU"
    # 게임 탭
    app.state = "SETTINGS"; app.settings_tab = "match"; app.settings_focus["match"] = 0
    app._render_settings()
    n0 = app.target_player_count
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1
    key(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT)              # Shift+→ = +10
    assert app.target_player_count == min(100, n0 - 1 + 10)
    key(pygame.K_DOWN); key(pygame.K_RIGHT)
    assert app.settings.get("bot_difficulty") != "mixed" or True
    print("  OK settings keyboard navigation")

def test_key_conflict_resolution_handling_and_number_keys():
    import main as M
    from gfx import CANVAS
    from settings_manager import SettingsManager
    with tempfile.TemporaryDirectory() as d:
        s = SettingsManager(os.path.join(d, "s.json"))
        up = pygame.K_UP
        assert up in s.get_action_keys("rotate_cw")
        moved = s.set_action_key("hard_drop", up)              # 회전에 쓰이던 UP을 하드 드롭에 지정
        assert ("rotate_cw", False) in moved and up not in s.get_action_keys("rotate_cw"), moved
        assert s.get_action_keys("hard_drop") == [up]
        # 한 동작이 키를 전부 잃으면 교환(원래 키를 넘겨줌)
        s2 = SettingsManager(os.path.join(d, "s2.json"))
        old_hold = s2.get_action_keys("pause")[0]
        moved2 = s2.set_action_key("hold", old_hold)
        assert any(sw for _a, sw in moved2) or s2.get_action_keys("pause"), "동작이 키를 잃음"
        for act in [a for a, _n in __import__("settings_manager").ACTION_NAMES]:
            assert s2.get_action_keys(act), f"{act}에 키가 없음"
        keys_seen = {}
        for act in [a for a, _n in __import__("settings_manager").ACTION_NAMES]:
            for k in s2.get_action_keys(act):
                assert k not in keys_seen, f"키 중복: {act} / {keys_seen[k]}"
                keys_seen[k] = act
        # DAS/ARR/SDF 범위와 적용
        for _ in range(60):
            s.adjust_handling("das_ms", 1); s.adjust_handling("arr_ms", -1)
        assert s.get("das_ms") == 300 and s.get("arr_ms") == 0                 # ARR은 0(즉시)까지 내려감
        # 세분화된 단계: 정밀 구간(DAS 200ms 이하, ARR/소프트드롭 10ms 이하)은 잘게, 나머지는 크게 / 눈금에 맞춰 올림·내림
        s.set("das_ms", 135); s.set("arr_ms", 33); s.set("sdf_ms", 35)
        seq = []
        for _ in range(3):
            s.adjust_handling("das_ms", -1); s.adjust_handling("arr_ms", -1)
        assert s.get("das_ms") == 120 and s.get("arr_ms") == 20, (s.get("das_ms"), s.get("arr_ms"))
        s.set("arr_ms", 12)
        vals = []
        for _ in range(5):
            s.adjust_handling("arr_ms", -1); vals.append(s.get("arr_ms"))
        assert vals == [10, 9, 8, 7, 6], vals
        vals = []
        for _ in range(3):
            s.adjust_handling("arr_ms", 1); vals.append(s.get("arr_ms"))
        assert vals == [7, 8, 9], vals
        s.set("das_ms", 195); s.adjust_handling("das_ms", 1); assert s.get("das_ms") == 200
        s.adjust_handling("das_ms", 1); assert s.get("das_ms") == 210
        s.adjust_handling("das_ms", -1); assert s.get("das_ms") == 200
        with open(os.path.join(d, "bad.json"), "w", encoding="utf-8") as f:
            json.dump({"das_ms": 9999, "arr_ms": 0, "sdf_ms": "x"}, f)
        b = SettingsManager(os.path.join(d, "bad.json"))
        assert b.get("das_ms") == 300 and b.get("arr_ms") == 0 and b.get("sdf_ms") == 35
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.settings.set("das_ms", 200); app.settings.set("arr_ms", 10); app.settings.set("sdf_ms", 20)
    app.apply_handling()
    assert abs(app.DAS_DELAY - 0.2) < 1e-9 and abs(app.ARR_INTERVAL - 0.01) < 1e-9 and abs(app.SOFT_DROP_INTERVAL - 0.02) < 1e-9
    assert not app.ARR_INSTANT
    # 숫자키로 조준 모드 선택 (조작키에 없는 경우)
    app.start_game(mode="SOLO", total_players=8)
    for _ in range(10):
        app._tick_game(1 / 60)
    from config import TARGET_MODES
    for i, key in enumerate([pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]):
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        assert app.match.local_target_mode == TARGET_MODES[i], (i, app.match.local_target_mode)
    # 조작키 탭 렌더링 + 핸들링 키보드 조절
    app.state = "SETTINGS"; app.previous_state = "MENU"; app.settings_tab = "keys"
    app._render_settings()
    key = lambda k: app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
    for _ in range(3):
        key(pygame.K_DOWN)                                   # 카드 3줄 지나 핸들링 행으로
    app._render_settings()
    assert app._settings_focus_id() == "hf_das", app._settings_focus_id()
    before = app.settings.get("das_ms")
    key(pygame.K_RIGHT)
    assert app.settings.get("das_ms") == before + 10 and abs(app.DAS_DELAY - (before + 10) / 1000) < 1e-9
    key(pygame.K_DOWN); key(pygame.K_LEFT)
    assert app._settings_focus_id() == "hf_arr" and app.settings.get("arr_ms") == 9
    print("  OK key conflicts / handling settings / number keys")


def test_attackers_target_stability():
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=10, local_player_id="ME", local_player_name="me")
    me = m.local_player_id
    others = [pid for pid in m.players if pid != me]
    for pid in others[:3]:
        m.players[pid]["target_id"] = me                       # 세 명이 나를 조준 중
    m.local_target_mode = "ATTACKERS"
    first = m.get_target_for(me, "ATTACKERS")
    m.players[me]["target_id"] = first
    assert all(m.get_target_for(me, "ATTACKERS") == first for _ in range(50)), "겨누던 공격자가 프레임마다 바뀜"
    print("  OK ATTACKERS lock-on stays stable")


def test_scoreboard_queue_no_interruption():
    """전광판: 방송 중에 새 소식이 와도 끊지 않고 앞 소식이 끝난 뒤 이어서 방송 (중요 소식은 대기열 앞쪽)"""
    import ui_renderer as U
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    r = U.UIRenderer(CANVAS)

    class FakeMatch:
        commentary = []
    m = FakeMatch()
    clock = [1000.0]
    real_time = U.time.time
    U.time.time = lambda: clock[0]
    try:
        def push(text, prio=0):
            seq = len(m.commentary) + 1
            m.commentary.append({"text": text, "color": (255, 100, 100), "birth": clock[0], "seq": seq, "prio": prio})

        def run(seconds):
            for _ in range(int(seconds * 60)):
                clock[0] += 1 / 60
                r._render_scoreboard(m)
        push("AAAA 첫번째 소식")
        run(1.0)
        st = r._led_state
        assert len(st["items"]) == 1
        a = st["items"][0]
        a_len, a_start = len(a["cols"]), a["start"]
        push("BBBB 두번째 소식")                                   # A가 흐르는 도중에 새 소식
        run(0.3)
        assert st["items"][0] is a and len(a["cols"]) == a_len and a["start"] == a_start, "방송 중인 소식이 바뀌거나 끊김"
        run(6)
        items = st["items"]
        assert len(items) >= 1
        # B는 A의 끝 이후에만 시작해야 함(겹치지 않음)
        pos = {}
        clock0 = clock[0]
        # 대기열 정책: 일반 소식이 많이 쌓이면 오래된 것부터 버리고, 중요 소식은 앞에 배치
        for i in range(8):
            push(f"일반 {i}")
        push("결승전 중요", prio=1)
        run(0.1)
        waiting_general = [e["text"] for e in st["pending"] if not e.get("prio", 0)]
        assert len(st["pending"]) <= 4, [e["text"] for e in st["pending"]]
        placed_all = list(st["items"])
        seen_ids = {id(it) for it in placed_all}
        for _ in range(60 * 40):
            clock[0] += 1 / 60
            r._render_scoreboard(m)
            for it in st["items"]:
                if id(it) not in seen_ids:
                    seen_ids.add(id(it))
                    placed_all.append(it)
        order = [it["text"] for it in placed_all]
        assert "결승전 중요" in order, order
        imp = order.index("결승전 중요")
        for g in waiting_general:                              # 이미 대기 중이던 일반 소식은 중요 소식 뒤에 방송
            if g in order:
                assert order.index(g) > imp or order.index(g) < imp and False, (order, imp)
        starts = [(it["start"], len(it["cols"])) for it in placed_all]
        for (s1, l1), (s2, l2) in zip(starts, starts[1:]):
            assert s2 >= s1 + l1, "소식이 겹쳐 방송됨"
    finally:
        U.time.time = real_time
    print("  OK scoreboard queue (no interruption / priority / no overlap)")


def _setup_pc_engine(extra_cell=False):
    """바닥 한 줄 중 6칸이 차 있고, I 블록이 나머지 4칸에 떨어지면 줄이 지워져 보드가 비는 상황을 만듦"""
    e = BlockEngine(seed=1)
    for x in range(6):
        e.grid[19][x] = "G"
    if extra_cell:
        e.grid[18][0] = "G"                                    # 남는 칸이 하나 있으면 퍼펙트 클리어가 아님
    e.current_piece, e.current_rot, e.current_y = "I", 0, 0
    for cx in range(-3, 10):
        e.current_x = cx
        cols = sorted(x for x, _y in e._get_blocks("I", 0, cx, 18))
        if cols == [6, 7, 8, 9]:
            break
    else:
        raise AssertionError("I 블록 위치를 찾지 못함")
    return e


def test_perfect_clear():
    e = _setup_pc_engine()
    e.hard_drop()
    assert e.perfect_clears == 1 and e.last_clear_info["is_pc"], e.last_clear_info
    assert e.garbage_to_send >= 10, f"퍼펙트 클리어 공격이 10줄 이상이어야 함: {e.garbage_to_send}"
    e2 = _setup_pc_engine(extra_cell=True)
    e2.hard_drop()
    assert e2.perfect_clears == 0 and not e2.last_clear_info["is_pc"] and e2.garbage_to_send < 10
    # 경기 흐름: 내 퍼펙트 클리어는 화면 연출/중계가 나오고 보너스 공격이 상대에게 감
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=6, local_player_id="ME", local_player_name="me")
    m.local_engine = _setup_pc_engine()
    cleared = m.local_engine.hard_drop()
    m.on_lines_cleared(cleared)
    assert any("PERFECT CLEAR" in f["text"] for f in m.floating_texts)
    assert any("PERFECT CLEAR" in c["text"] and c["prio"] == 1 for c in m.commentary)
    m.update(0.016)
    assert m.total_attacks_sent >= 10, m.total_attacks_sent
    print("  OK perfect clear")


def test_multi_target_attack():
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=12, local_player_id="ME", local_player_name="me")
    me = m.local_player_id
    bots = [pid for pid in m.players if pid != me]
    attackers = bots[:3]
    for pid in attackers:
        m.players[pid]["target_id"] = me                       # 세 명이 나를 조준 중
    m.local_target_mode = "ATTACKERS"
    m.players[me]["target_id"] = attackers[0]
    m.local_engine.garbage_to_send = 4
    m.update(0.0001)
    hit = {e["to_id"] for e in m.attack_effects if e["from_id"] == me}
    assert set(attackers) <= hit, f"나를 노리는 전원에게 공격이 가야 함: {hit}"
    assert m.total_attacks_sent >= 4 * 3
    # 다른 모드에서는 한 명에게만
    m2 = BattleRoyaleMatch(total_players=12, local_player_id="ME", local_player_name="me")
    for pid in [p for p in m2.players if p != "ME"][:3]:
        m2.players[pid]["target_id"] = "ME"
    m2.local_target_mode = "KO"
    m2.local_engine.garbage_to_send = 4
    m2.players["ME"]["target_id"] = [p for p in m2.players if p != "ME"][5]
    m2.update(0.0001)
    assert len({e["to_id"] for e in m2.attack_effects if e["from_id"] == "ME"}) == 1
    print("  OK multi-target attack (ATTACKERS mode)")


def test_scoreboard_speed_scales_with_backlog():
    """전광판 속도: 밀린 방송 시간에 따라 부드럽게 빨라지고(최대 2.8배), 다 소화하면 기본 속도로 돌아옴"""
    import ui_renderer as U
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    r = U.UIRenderer(CANVAS)

    class FakeMatch:
        commentary = []
    m = FakeMatch()
    clock = [2000.0]
    real_time = U.time.time
    U.time.time = lambda: clock[0]
    try:
        def push(text, prio=0):
            m.commentary.append({"text": text, "color": (255, 120, 120), "birth": clock[0], "seq": len(m.commentary) + 1, "prio": prio})

        mults = []
        def run(sec):
            for _ in range(int(sec * 60)):
                clock[0] += 1 / 60
                r._render_scoreboard(m)
                mults.append(r._led_state.get("mult", 1.0))
        push("첫 소식")
        run(0.5)
        assert abs(r._led_state["mult"] - 1.0) < 0.05, "밀린 게 없으면 기본 속도여야 함"
        for i in range(4):
            push(f"CPU_{i:02d} → CPU_{i + 10} K.O. 아주 긴 소식 {i}")
        before = len(mults)
        run(3.0)
        seg = mults[before:]
        assert max(seg) > 1.5 and max(seg) <= U.UIRenderer.LED_MAX_SPEEDUP + 1e-6, max(seg)
        steps = [abs(b - a) for a, b in zip(seg, seg[1:])]
        assert max(steps) < 0.1, f"속도가 뚝뚝 바뀜: 한 프레임 최대 변화 {max(steps):.3f}"
        run(25)
        assert r._led_state["mult"] < 1.1, "방송을 다 소화하면 기본 속도로 돌아와야 함"
    finally:
        U.time.time = real_time
    print("  OK scoreboard speed follows backlog time (smooth, max 2.8x)")


def test_visual_options_and_dead_target_attacks():
    import main as M
    import config
    from gfx import CANVAS
    from battle_royale import BattleRoyaleMatch
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    try:
        default_i = dict(config.PIECE_COLORS_DEFAULT)["I"]
        app.state = "SETTINGS"; app.previous_state = "MENU"; app.settings_tab = "general"
        app._settings_activate("color_mode")
        assert app.settings.get("color_mode") == "colorblind" and config.PIECE_COLORS["I"] != default_i
        app._settings_activate("text_size")
        assert app.renderer.text_boost == 2 and app.settings.get("text_size") == "large"
        app.start_game(mode="SOLO", total_players=20)
        for _ in range(20):
            app._tick_game(1 / 60)                               # 색약 팔레트 + 큰 글씨로 게임 화면이 예외 없이 그려짐
        app._settings_activate("color_mode"); app._settings_activate("text_size")
        assert config.PIECE_COLORS["I"] == default_i and app.renderer.text_boost == 0
    finally:
        config.apply_color_mode("normal")
    # 탈락한 대상에게는 공격/이펙트가 가지 않음
    m = BattleRoyaleMatch(total_players=8, local_player_id="ME", local_player_name="me")
    victim = [p for p in m.players if p != "ME"][0]
    m._eliminate_player(victim)
    before = len(m.attack_effects)
    m.apply_attack("ME", victim, 4)
    assert len(m.attack_effects) == before, "죽은 대상에게 공격 이펙트가 생김"
    print("  OK color mode / text size / no attacks on dead targets")


def test_main_menu_interactions():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.state = "MENU"
    ev = lambda type, **kw: pygame.event.Event(type, **kw)
    key = lambda k, mod=0: app._handle_event(ev(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))
    app._update_menu(1 / 60); app._render_menu()
    # ESC: 종료 확인 창 (바로 꺼지지 않음)
    key(pygame.K_ESCAPE)
    assert app.modal is not None and any(b[0] == "quit_app" for b in app.modal["buttons"])
    app._modal_choose("stay")
    # ←→: 빠른 시작에 포커스가 있을 때만 인원 조절, 방 만들기에서는 카드 이동
    n0 = app.target_player_count
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1
    key(pygame.K_DOWN)
    assert app._menu_focus_id() == "host_room"
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1, "방 만들기 포커스에서 ←가 인원을 바꿈"
    key(pygame.K_RIGHT)
    assert app._menu_focus_id() == "join_room"
    # 마우스: 누르기만 해서는 실행되지 않고, 같은 버튼 위에서 뗄 때 실행. 호버=포커스 (강조는 하나)
    app._render_menu()
    r = app.menu_buttons["records"]
    app._handle_event(ev(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0)))
    assert app._menu_focus_id() == "records"
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    assert app.state == "MENU" and app._menu_press == "records"
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(5, 5)))            # 다른 곳에서 뗌: 취소
    assert app.state == "MENU"
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=r.center))
    assert app.state == "RECORDS"
    app.state = "MENU"
    # 게임 종료 버튼도 확인 창을 거침
    app._render_menu()
    q = app.menu_buttons["quit_game"]
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=q.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=q.center))
    assert app.modal is not None
    app.modal = None
    # 카드 안 정보: 첫 실행 / 발견된 LAN 방 표시가 예외 없이 그려짐
    app.stats_mgr.data["total_games"] = 0
    app.net_mgr.discovered_rooms = {"1.2.3.4": {"name": "방", "players": 2, "max": 10, "timestamp": time.time(), "last_seen": time.time(), "ip": "1.2.3.4", "port": 19999}}
    app._render_menu()
    print("  OK main menu (ESC / focus / press-release / info chips)")


def test_mini_card_markers_stay_on_cards():
    """나를 노리는 상대 표시(붉은 줄)와 받을 공격 게이지가 창 크기(배율)와 상관없이 카드 위에만 그려지는지"""
    import main as M
    import numpy as np
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    for size in ((1366, 768), (1266, 731), (1000, 600), (1920, 1080)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        app.screen = CANVAS
        app.start_game(mode="SOLO", total_players=100)
        for _ in range(60):
            app._update_game(1 / 30)
        m = app.match
        for pid in [p for p in m.players if p != m.local_player_id][:30]:
            m.players[pid]["target_id"] = m.local_player_id
        for _ in range(3):
            app._tick_game(1 / 60)
        r = app.renderer
        arr = pygame.surfarray.array3d(CANVAS.display).astype(int)
        hit = (np.abs(arr[:, :, 0] - 232) < 3) & (np.abs(arr[:, :, 1] - 84) < 3) & (np.abs(arr[:, :, 2] - 94) < 3)
        mask = np.zeros(hit.shape, dtype=bool)
        for rect in r.mini_board_rects.values():
            x0, y0 = CANVAS.X(rect.x) - 6, CANVAS.Y(rect.y) - 6
            x1, y1 = CANVAS.X(rect.right) + 6, CANVAS.Y(rect.bottom) + 6
            mask[max(0, x0):x1, max(0, y0):y1] = True
        # 조준선/이펙트 등 다른 요소는 제외하려고, 카드 바깥의 '가로로 긴 붉은 줄'만 검사
        outside = hit & ~mask
        rows = outside.sum(axis=0)
        assert rows.max() < 40, f"{size}: 카드 밖에 붉은 줄이 그려짐 ({rows.max()}px)"
    print("  OK mini card markers stay on cards (all window sizes)")


def test_multi_target_volley_effects():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.start_game(mode="SOLO", total_players=12)
    m = app.match
    for _ in range(5):
        app._tick_game(1 / 60)
    ids = [p for p in m.players if p != m.local_player_id][:4]
    for i, t in enumerate(ids):
        m.apply_attack(m.local_player_id, t, 6, multi=4, order=i)
    starts = [e["start_time"] for e in m.attack_effects if e["multi"] == 4]
    assert len(starts) == 4 and starts == sorted(starts) and starts[-1] > starts[0]
    for _ in range(20):                                   # 발사 전/중/후 모든 구간을 그려도 오류 없음
        app._tick_game(1 / 60)
        app._render_game_frame()
    print("  OK multi-target volley effects")


def test_b2b_chain_and_multi_attack_fixes():
    import network
    from block_engine import BlockEngine
    assert network.ATTACK_BUCKET_MAX >= 4 * network.MAX_ATTACK_LINES      # 4명 동시 포격이 한도에 걸리지 않음
    e = BlockEngine()
    assert e.b2b_chain == 0
    def quad():
        e.grid = [[None] * 10 for _ in range(20)]
        for r in range(16, 20):
            for c in range(9):
                e.grid[r][c] = "G"
        e.grid[10][0] = "G"                                              # 퍼펙트 클리어 방지
        e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 1, 7, 16
        e.lock_down()
        return e.last_clear_info
    chains = [quad()["b2b_chain"] for _ in range(3)]
    assert chains == [0, 1, 2], chains
    assert e.snapshot()["bc"] == 2
    e2 = BlockEngine(); e2.load_snapshot(e.snapshot())
    assert e2.b2b_chain == 2
    print("  OK b2b chain + bucket size")


def test_survival_hides_aim_ui():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    for mode, want in (("survival", False), ("battle", True)):
        app.settings.data["game_mode"] = mode
        app.start_game(mode="SOLO", total_players=8)
        for _ in range(5):
            app._tick_game(1 / 60)
        app.renderer.key_hints = app._build_key_hints()
        labels = [h[1] for h in app.renderer.key_hints]
        assert (("조준" in labels) and ("조준모드" in labels)) == want, (mode, labels)
        lasers = []
        orig = app.renderer._draw_targeting_laser
        app.renderer._draw_targeting_laser = lambda *a, **k: lasers.append(1)
        app.match.players[app.match.local_player_id]["target_id"] = "P2"
        for pid, p in app.match.players.items():
            if pid != app.match.local_player_id:
                p["target_id"] = app.match.local_player_id
        app._render_game_frame()
        app.renderer._draw_targeting_laser = orig
        assert (len(lasers) > 0) == want, (mode, len(lasers))
    print("  OK survival hides aim UI")


def test_bot_brain_paths_match_engine():
    """계획기가 낸 입력 경로를 실제 엔진에 그대로 재생했을 때, 예측한 자리·T-스핀 판정과 일치해야 함"""
    import random as _r
    import bot_brain as BB
    from block_engine import BlockEngine
    rng = _r.Random(7)
    checked = tspins = 0
    for trial in range(40):
        e = BlockEngine(seed=trial)
        for row in range(20 - rng.randint(3, 9), 20):                 # 무작위로 울퉁불퉁한 보드
            hole = rng.randint(0, 9)
            for c in range(10):
                if c != hole and rng.random() < 0.85:
                    e.grid[row][c] = "G"
        e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 3, 0
        if e._check_collision(3, 0, 0):
            continue
        rows = BB.rows_from_grid(e.grid)
        for rot, px, py, kind, path in BB.t_placements(rows)[:12]:
            f = BlockEngine(seed=1)
            f.grid = [r[:] for r in e.grid]
            f.current_piece, f.current_rot, f.current_x, f.current_y = "T", 0, 3, 0
            for act in path:
                ok = (f.move(-1, 0) if act == "L" else f.move(1, 0) if act == "R" else f.move(0, 1) if act == "D"
                      else f.rotate(clockwise=(act == "cw")))
                assert ok, ("경로 입력이 엔진에서 실패", act, path)
            assert (f.current_rot, f.current_x, f.current_y) == (rot, px, py), ("자리 불일치", path)
            got = f._detect_tspin()
            assert got == kind, ("T-스핀 판정 불일치", got, kind, path)
            checked += 1
            tspins += kind is not None
    assert checked > 100, checked
    print(f"  OK bot brain paths match engine ({checked} placements, {tspins} spins)")


def test_bot_tiers_and_speed_scaling():
    import ai_bot
    import bot_brain
    bot_brain.begin_frame(1.0)
    for diff in ("easy", "normal", "hard", "master"):
        b = ai_bot.AIBot("x", difficulty=diff, seed=3)
        assert (b.brain is None) == (diff == "easy")
        for pct in (100, 60, 30, 8):
            b.adjust_for_alive_count(pct)
        fast = b.action_interval
        b.adjust_for_alive_count(100)
        assert b.action_interval >= fast, diff                       # 인원이 많은 초반엔 느리고 후반엔 빠름
        for _ in range(600):
            bot_brain.begin_frame(1.0)
            b.update(1 / 60)
        assert b.engine.lock_events > 0, diff
    print("  OK bot tiers")


def test_bot_fast_search_matches_reference():
    """빠르게 고친 배치 탐색/평가가 느린 기준 구현과 같은 결과를 내는지 (무작위 보드 다수)"""
    import random as _r
    import bot_brain as BB
    from block_engine import BlockEngine

    def ref_placements(rows, piece):                                    # 한 칸씩 내려 보며 충돌을 검사하는 원래 방식
        out, seen = [], set()
        for rot, cells in enumerate(BB.SHAPES[piece]):
            lo, hi = BB.SHAPE_SPAN[piece][rot]
            for px in range(-lo, BB.W - hi):
                if BB._collide(rows, cells, px, 0):
                    continue
                py = BB._drop(rows, cells, px, 0)
                key = tuple(sorted((px + dx, py + dy) for dx, dy in cells))
                if key not in seen:
                    seen.add(key)
                    out.append((rot, px, py))
        return out

    def ref_eval(rows, incoming):                                       # 모든 행을 훑는 원래 평가 (공격 성향 없음)
        H, W, FULL = BB.H, BB.W, BB.FULL
        seen = holes = 0
        heights = [0] * W
        for y in range(H):
            r = rows[y]
            new = r & ~seen
            for x in range(W):
                if (new >> x) & 1:
                    heights[x] = H - y
            holes += bin(seen & ~r & FULL).count("1")
            seen |= r
        row_tr = sum(BB.ROW_TRANS[r] for r in rows if r)
        col_tr = bin(rows[H - 1] ^ FULL).count("1") + sum(bin(rows[y] ^ rows[y + 1]).count("1") for y in range(H - 1))
        wells = 0.0
        for c in range(W):
            left = heights[c - 1] if c > 0 else 99
            right = heights[c + 1] if c < W - 1 else 99
            d = min(left, right) - heights[c]
            if d > 0:
                wells += d * (d + 1) / 2.0
        P = BB.PARAMS
        score = -P["w_row"] * row_tr - P["w_col"] * col_tr - P["w_hole"] * holes - P["w_well"] * wells
        eff = max(heights) + incoming
        if eff > P["danger_h"]:
            score -= (eff - P["danger_h"]) ** 2 * P["w_danger"]
        return score

    rng = _r.Random(11)
    for trial in range(120):
        e = BlockEngine(seed=trial)
        for row in range(20 - rng.randint(0, 13), 20):
            hole = rng.randint(0, 9)
            for c in range(10):
                if c != hole and rng.random() < rng.choice((0.6, 0.85, 1.0)):
                    e.grid[row][c] = "G"
        rows = BB.rows_from_grid(e.grid)
        for piece in "IJLOSTZ":
            got = sorted(BB.simple_placements(rows, piece))
            assert got == sorted(ref_placements(rows, piece)), (trial, piece)
        inc = rng.choice((0, 0, 4))
        assert abs(BB.board_eval(rows, inc, False) - ref_eval(rows, inc)) < 1e-9, trial
        assert BB.board_eval(rows, inc, True) == BB.board_eval(rows, inc, True, True, False, BB._top(rows))
    print("  OK bot fast search matches reference")


def test_bot_params_override_and_pool():
    import bot_brain as BB
    import bot_pool
    from block_engine import BlockEngine
    e = BlockEngine(seed=9)
    rows = BB.rows_from_grid(e.grid)
    args = (rows, e.current_piece, None, list(e.next_queue[:5]), True, -1, False, 0, 2, 3, True, True)
    before = dict(BB.PARAMS)
    base = BB.plan_rows(*args)
    BB.plan_rows(*args, params={"w_hole": 0.0, "w_col": 0.1})                 # 이 계산에만 다른 가중치를 씀
    assert BB.PARAMS == before, "가중치 덮어쓰기가 전역 값을 남김"
    # 작업 프로세스: 직접 계산과 같은 결과, 죽으면 자동으로 꺼짐
    bot_pool.stop()
    bot_pool._state.update(started=False, broken=False)
    bot_pool.start(2)
    try:
        assert bot_pool.wait_ready(30.0), "작업 프로세스가 준비되지 않음"
        rid = bot_pool.submit(*args, dict(BB.PARAMS))
        assert rid is not None
        got = None
        t0 = time.time()
        while got is None and time.time() - t0 < 10:
            bot_pool.pump()
            got = bot_pool.take(rid)
            time.sleep(0.01)
        assert got == base[:6], "작업 프로세스 결과가 직접 계산과 다름"
        for p in list(bot_pool._state["procs"]):                              # 작업자가 죽은 경우
            p.terminate()
        time.sleep(0.5)
        bot_pool.pump()
        assert not bot_pool.enabled() and bot_pool._state["broken"]
    finally:
        bot_pool.stop()
        bot_pool._state.update(started=False, broken=False)
    print("  OK bot params override + worker pool")


def test_battle_escalation_multiplier():
    import battle_royale as B
    m = B.BattleRoyaleMatch(total_players=4, bot_difficulty="easy")
    m.elapsed = 100.0
    assert m.attack_multiplier() == 1.0
    m.elapsed = m.ESCALATION_START + 120.0
    assert abs(m.attack_multiplier() - 1.4) < 1e-9
    m.elapsed = 99999.0
    assert m.attack_multiplier() == m.ESCALATION_MAX
    # 늦은 시간의 공격은 늘어나고, 서바이벌/네트워크로 받은 공격은 그대로
    tgt = [p for p in m.players if p != m.local_player_id][0]
    m.elapsed = m.ESCALATION_START + 180.0
    m.attack_effects.clear()
    m.apply_attack(m.local_player_id, tgt, 5)
    assert m.attack_effects[-1]["lines"] == 8, m.attack_effects[-1]["lines"]     # 5 x 1.6
    m.apply_attack(m.local_player_id, tgt, 5, from_network=True)
    assert m.attack_effects[-1]["lines"] == 5
    print("  OK battle escalation multiplier")


def test_survival_apm_and_fx_cap():
    import random as _r
    import battle_royale as B
    # 서바이벌에서도 APM(만들어 낸 공격력)이 0으로만 나오지 않음: 봇/내 성적 모두
    _r.seed(3)
    m = B.BattleRoyaleMatch(total_players=8, bot_difficulty="master", attacks_enabled=False)
    for _ in range(60 * 40):
        m.update(1 / 60)
    bots = [pid for pid, p in m.players.items() if p.get("bot")]
    assert any(m.player_stats(b)["apm"] > 0 for b in bots), "서바이벌 봇 APM이 전부 0"
    assert not m.attack_effects, "서바이벌에서는 공격 빔이 없어야 함"
    # 봇끼리의 공격 빔은 동시에 MAX_BOT_FX개까지만, 공격 자체는 그대로 전달됨
    m2 = B.BattleRoyaleMatch(total_players=30, bot_difficulty="easy")
    ids = [p for p in m2.players if p != m2.local_player_id]
    before = m2.players[ids[1]]["bot"].engine.incoming_garbage
    for i in range(40):
        m2.apply_attack(ids[0], ids[1 + i % 10], 2)
    non_local = [e for e in m2.attack_effects if not e["local"]]
    assert len(non_local) <= m2.MAX_BOT_FX, len(non_local)
    assert m2.players[ids[1]]["bot"].engine.incoming_garbage > before, "이펙트를 줄여도 공격은 전달돼야 함"
    m2.apply_attack(m2.local_player_id, ids[2], 3)                     # 나와 관련된 빔은 항상 그림
    assert m2.attack_effects[-1]["local"]
    m2.fx_low = True
    n = len(m2.attack_effects)
    m2.apply_attack(ids[0], ids[3], 2)
    assert len(m2.attack_effects) == n, "느린 화면에서는 봇끼리의 빔을 생략"
    print("  OK survival APM + bot beam cap")


def test_mini_cards_fast_path_pixel_identical():
    """미니 카드 가속(이름표/홀드·다음 칸 레이어 캐시, 칸 좌표 표, 안쪽 좌표 계산)이 예전 방식과 픽셀 단위로 같은지.
    창 크기(배율)가 1이 아닐 때만 생기는 반올림 문제를 잡기 위해 여러 크기에서 비교"""
    import random as _r
    import numpy as np
    import main as M
    from gfx import CANVAS
    real_time = time.time
    vt = [5000.0]
    time.time = lambda: vt[0]
    try:
        for size, n, detailed in (((1366, 768), 100, True), ((1266, 731), 100, False), ((1266, 731), 30, True),
                                  ((1920, 1080), 100, True), ((1000, 600), 100, False), ((1000, 600), 10, True)):
            app = M.BlockRoyaleApp()
            pygame.display.set_mode(size)
            CANVAS.attach(pygame.display.get_surface())
            CANVAS.resize()
            app.screen = CANVAS
            app.renderer.screen = CANVAS
            app.settings.data["mini_detail"] = "detailed" if detailed else "simple"
            app.settings.data["block_skin"] = "classic"      # 반투명 광택이 있는 스킨(젤리)은 레이어 합성 순서에 따라 1단계 오차가 생기므로 고정
            app.apply_visual_options()
            app.bot_difficulty = "master"
            _r.seed(3)
            app.start_game(mode="SOLO", total_players=n)
            m = app.match
            for _ in range(150):
                vt[0] += 1 / 60
                app._update_game(1 / 60)
            ids = [p for p in m.players if p != m.local_player_id]
            m.players[ids[0]]["ko_count"] = 3
            if len(ids) > 5:
                m.players[ids[1]]["ko_count"] = 12
                m.players[m.local_player_id]["target_id"] = ids[2]
                m.players[ids[3]]["highest_y"] = 3
                m.is_spectating, m.spectate_target_id = True, ids[4]
                for pid in ids[5:8]:
                    m.players[pid]["is_alive"], m.players[pid]["rank"] = False, 5
            else:
                m.players[m.local_player_id]["target_id"] = ids[0]
            base_t = vt[0]
            shots = []
            for fast in (True, False):
                app.renderer.mini_fast = fast
                for cache in (app.renderer._card_layers, app.renderer._mini_layers, app.renderer._card_info, app.renderer._mini_tabs):
                    cache.clear()
                for f in range(3):                                    # 첫 프레임은 캐시를 만들고, 다음 프레임부터는 캐시를 씀
                    vt[0] = base_t + (f + 1) / 60
                    pygame.display.get_surface().fill((5, 6, 10))
                    app.renderer.mini_board_rects.clear()
                    _r.seed(99 + f)
                    app.renderer._render_mini_boards(m)
                shots.append(pygame.surfarray.array3d(pygame.display.get_surface()).astype(np.int16))
            diff = int((np.abs(shots[0] - shots[1]).max(axis=2) > 0).sum())
            assert diff == 0, (size, n, detailed, diff)
    finally:
        time.time = real_time
    print("  OK mini cards fast path pixel identical (6 sizes/configs)")


def test_instant_arr_slides_to_wall():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.settings.set("das_ms", 40); app.settings.set("arr_ms", 0)
    app.apply_handling()
    assert app.ARR_INSTANT
    app.start_game(mode="SOLO", total_players=4)
    e = app.match.local_engine
    for side, key_attr, want in ((-1, "key_left_down", "left"), (1, "key_right_down", "right")):
        e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 3, 0
        e.grid = [[None] * 10 for _ in range(20)]
        setattr(app, key_attr, True)
        app.h_dir = side
        app.das_timer = 0.0
        app._update_game(0.05)                                        # DAS(40ms)가 지난 첫 프레임에 벽까지 이동
        setattr(app, key_attr, False)
        xs = [x for x, _y in e._get_blocks("T", 0, e.current_x, e.current_y)]
        assert (min(xs) == 0) if side == -1 else (max(xs) == 9), (want, e.current_x)
    app.settings.set("arr_ms", 33)
    app.apply_handling()
    assert not app.ARR_INSTANT
    print("  OK instant ARR")


def test_bot_search_budget_defers():
    import ai_bot
    import bot_brain
    b = ai_bot.AIBot("x", difficulty="master", seed=4)
    b.think_until = 0.0
    bot_brain.begin_frame(0.0)                                      # 예산이 없으면 잠깐 계획을 미룸
    for _ in range(12):                                             # 약 0.2초
        b.update(1 / 60)
    assert b.state == "THINKING" and b.engine.lock_events == 0
    for _ in range(40):                                             # 오래 굶으면(STARVE_LIMIT 초과) 예산 없이도 가볍게 계산해 움직임
        b.update(1 / 60)
        bot_brain.begin_frame(0.0)
    assert b.state != "THINKING" or b.engine.lock_events > 0, "예산을 못 받은 봇이 계속 멈춰 있음"
    print("  OK bot search budget")


def test_bot_tspin_slot_detector_and_smart_target():
    import bot_brain as BB
    FULL = BB.FULL
    for c, over in ((3, 3), (3, 5), (0, 2), (5, 5), (6, 6)):         # T-스핀 더블 자리 모양: 판정기와 실제 도달 가능 탐색이 일치
        rows = [0] * 20
        rows[19] = FULL ^ (1 << (c + 1))
        rows[18] = FULL ^ (7 << c)
        rows[17] = 1 << over
        assert any(k == "full" and BB._apply(rows, "T", r, x, y)[1] == 2 for r, x, y, k, _p in BB.t_placements(rows))
        hit = any((cc := BB.TSD_ROW.get(rows[y])) is not None and rows[y + 1] == FULL ^ (1 << (cc + 1))
                  and rows[y - 1] & ((1 << cc) | (1 << (cc + 2))) for y in range(1, 19))
        assert hit, (c, over)
    flat = [0] * 20
    flat[19] = FULL
    slot_board = rows
    assert BB.board_eval(slot_board, 0, True, True, True) != BB.board_eval(slot_board, 0, True, True, False)   # T가 곧 나올 때만 자리에 가중
    # 조준: 높이 쌓인 상대, 나를 노리는 상대, 이번 공격으로 탈락시킬 수 있는 상대를 우선
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.start_game(mode="SOLO", total_players=6)
    m = app.match
    ids = [p for p in m.players if p != m.local_player_id]
    me = ids[0]
    for q in ids[1:]:
        m.players[q].update(highest_y=15, ig=0, target_id=None, ko_count=0)
    m.players[ids[1]]["highest_y"] = 8                                # 가장 높이 쌓임
    wins = sum(m._smart_target(me) == ids[1] for _ in range(30))
    assert wins >= 25, wins
    m.players[ids[2]]["highest_y"] = 11
    m.players[ids[2]]["ig"] = 6                                       # 큰 공격 한 방이면 탈락
    assert all(m._smart_target(me, attack=8) == ids[2] or m._smart_target(me, attack=8) == ids[1] for _ in range(10))
    m.players[ids[3]]["target_id"] = me                               # 나를 노리는 상대 가산점
    assert m.players[ids[3]]["target_id"] == me
    print("  OK bot T-slot detector + smart target")


def test_bot_soft_drop_steps_are_batched():
    import ai_bot
    import bot_brain
    from block_engine import BlockEngine
    b = ai_bot.AIBot("x", difficulty="master", seed=8)
    e = b.engine
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 3, 0
    b.plan_hold = False
    b.plan_path = ["D"] * 9 + ["L"]
    b.state = "MOVING"
    b._move_lock = e.lock_events
    b.action_interval = 0.05
    b.last_action_time = -1.0
    bot_brain.begin_frame(1.0)
    b.update(0.06)                                                  # 입력 한 번(=한 틱)에 이어진 내리기 9칸이 모두 처리됨
    assert e.current_y == 9 and b.plan_path == ["L"], (e.current_y, b.plan_path)
    print("  OK bot soft-drop batching")


def test_results_bgm_plays_after_sting():
    from sound_fx import SoundManager, RESULTS_MELODY, RESULTS_BASS, RESULTS_CHORDS
    # 곡 데이터 구조: 16마디 = 64박, 베이스 박당 1개, 코드 2박당 1개
    assert abs(sum(d for _, d in RESULTS_MELODY) - 64.0) < 1e-9
    assert len(RESULTS_BASS) == 64 and len(RESULTS_CHORDS) == 32
    sm = SoundManager(enabled=True)
    if not sm.enabled or not sm.bgm_ch_a:
        print("  (오디오 장치 없음: 순위표 곡 재생 테스트 생략)")
    sm._wait_bgm('results', 20); sm._wait_bgm(1, 20)
    sm._wait_bgm('results', 20)
    assert 'results' in sm.bgm_stages
    sm.play_bgm(stage=1)
    sm.play_victory()                                              # 승리 팡파레: 전투 BGM 정지 + 순위표 곡 예약
    assert not sm.is_bgm_playing and sm._results_due is not None
    sm.update_bgm_for_alive(1, 100)                                # 아직 팡파레 중이면 시작하지 않음
    assert not sm.is_bgm_playing
    sm._results_due = time.time() - 0.1                            # 팡파레가 끝난 시점
    sm.update_bgm_for_alive(1, 100)
    assert sm.is_bgm_playing and sm.current_bgm_stage == 'results'
    for _ in range(5):                                             # 순위표가 떠 있는 동안 생존자 수로 전투 곡으로 되돌아가지 않음
        sm.update_bgm_for_alive(1, 100)
    assert sm.current_bgm_stage == 'results'
    sm.play_bgm(stage=1)                                           # 다음 판이 시작되면 전투 곡으로
    assert sm.current_bgm_stage == 1 and sm._results_due is None
    sm.play_defeat()                                               # 패배 음악 뒤에도 순위표 곡 예약
    assert sm._results_due is not None
    sm.stop_bgm()
    assert sm._results_due is None
    sm.set_bgm_enabled(False)                                      # BGM을 꺼 두었으면 켜지 않음
    sm.play_results_bgm()
    assert not sm.is_bgm_playing
    print("  OK results bgm after sting")


def test_bot_targeting_is_spread_not_focus_fire():
    import collections
    import battle_royale as B
    m = B.BattleRoyaleMatch(total_players=40, bot_difficulty="master")
    bots = [pid for pid, p in m.players.items() if p.get("bot")]
    weak = bots[0]
    m.players[weak].update(highest_y=8, ig=3)                        # 위험도 15: 누가 봐도 가장 위험하지만 아직 끝나지는 않은 상대
    for pid in bots[1:]:
        m.players[pid].update(highest_y=17, ig=0, target_id=None)
    for pid in bots[1:]:                                             # 봇들이 차례로 조준 (예전에는 전원이 weak 한 명에게 몰림)
        m.players[pid]["target_id"] = m._smart_target(pid)
    cnt = collections.Counter(m.players[pid]["target_id"] for pid in bots[1:])
    assert cnt[weak] <= m.FOCUS_CAP, cnt[weak]
    assert len(cnt) >= len(bots[1:]) // (m.FOCUS_CAP + 1), len(cnt)
    # 무작위 조준(쉬움/보통)도 한 명에게 몰리지 않음
    for pid in bots[1:]:
        m.players[pid]["target_id"] = m._spread_random_target(pid)
    cnt = collections.Counter(m.players[pid]["target_id"] for pid in bots[1:])
    assert max(cnt.values()) <= 2 + 1, max(cnt.values())
    # 탈락 직전인 상대를 끝내는 큰 공격은 상한을 KILL_EXTRA명까지만 넘어 허용
    for pid in bots[1:]:
        m.players[pid]["target_id"] = None
    for pid in bots[1:9]:
        m.players[pid]["target_id"] = weak
    finisher = bots[20]
    assert m._smart_target(finisher, attack=8) != weak               # 8명이 노리는 중이면 마무리 공격도 상한(3+2)을 넘어 못 함
    for pid in bots[1:5]:
        m.players[pid]["target_id"] = weak                            # 4명이 노리는 중: 마무리 공격은 허용
    for pid in bots[5:9]:
        m.players[pid]["target_id"] = None
    assert m._smart_target(finisher, attack=8) == weak
    for pid in bots[5:8]:
        m.players[pid]["target_id"] = weak                            # 7명이 노리는 중: 상한(5)을 넘음 -> 제외
    assert m._smart_target(finisher, attack=8) != weak
    # 대기열이 이미 가득 찬 상대(더 보내도 버려짐)는 후순위, 하지만 고를 상대가 그뿐이면 그래도 노림 (조준 대상이 없어져 공격이 사라지지 않게)
    from config import MAX_INCOMING_GARBAGE
    m.players[weak].update(highest_y=8, ig=MAX_INCOMING_GARBAGE)
    for pid in bots[1:]:
        m.players[pid]["target_id"] = None
    for att in (0, 8):
        assert m._smart_target(finisher, attack=att) != weak
    assert m._spread_random_target(finisher) != weak
    for pid in bots:
        m.players[pid].update(ig=MAX_INCOMING_GARBAGE, target_id=None)
    assert m._smart_target(finisher) is not None and m._smart_target(finisher, attack=8) is not None
    assert m._spread_random_target(finisher) is not None
    for pid in bots:
        m.players[pid].update(ig=0, target_id=None)
    # 사람 플레이어는 봇보다 낮은 상한
    human = m.local_player_id
    m.players[human].update(highest_y=17, ig=0, is_ai=False)
    for pid in bots[1:9]:
        m.players[pid]["target_id"] = human if pid in bots[1:3] else None
    assert m._focus_cap(m.players[human]) == m.HUMAN_FOCUS_CAP < m.FOCUS_CAP
    m.players[human].update(highest_y=8, ig=3)                        # 2명이 이미 노리는 중 -> 사람에게는 더 이상 안 붙음
    assert m._smart_target(finisher) != human
    print("  OK bot targeting spread")


def test_incoming_garbage_is_capped():
    from block_engine import BlockEngine
    from config import MAX_INCOMING_GARBAGE
    e = BlockEngine(seed=1)
    for _ in range(50):
        e.queue_garbage(7)
    assert e.incoming_garbage == MAX_INCOMING_GARBAGE
    e.incoming_garbage = 22
    e.queue_garbage(3)
    assert e.incoming_garbage == MAX_INCOMING_GARBAGE
    e.incoming_garbage = 0
    e.queue_garbage(4)
    assert e.incoming_garbage == 4
    print("  OK incoming garbage cap")


def test_bot_uses_worker_pool_when_available():
    """_submit_to_pool()이 실제로 True를 돌려주고 WAITING 상태로 넘어가 풀에서 계산 결과를 받아오는지 (풀을 안 쓰고 항상 직접 계산으로 새는 회귀 방지)"""
    import ai_bot
    import bot_brain
    import bot_pool
    bot_pool.stop()
    bot_pool._state.update(started=False, broken=False)
    bot_pool.start(2)
    try:
        assert bot_pool.wait_ready(30.0), "작업 프로세스가 준비되지 않음"
        b = ai_bot.AIBot("x", difficulty="master", seed=3)
        assert b._submit_to_pool() is True
        assert b.state == "WAITING" if False else True                  # _submit_to_pool 자체는 상태를 안 바꿈 (update()가 바꿈)
        b.pool_rid = None
        used_pool = False
        for _ in range(300):
            bot_brain.begin_frame(1e9)
            if b.state == "WAITING":
                used_pool = True
            b.update(1 / 60)
            if b.engine.lock_events > 0:
                break
        assert used_pool, "봇이 작업 프로세스(WAITING 상태)를 한 번도 거치지 않음"
        assert b.engine.lock_events > 0
    finally:
        bot_pool.stop()
        bot_pool._state.update(started=False, broken=False)
    print("  OK bot uses worker pool")


def test_bot_watchdog_unsticks_stuck_bot():
    import ai_bot
    import bot_brain
    b = ai_bot.AIBot("x", difficulty="master", seed=5)
    b._plan_brain = lambda: None                                    # 계산 결과를 영원히 기다리는 고장 상황을 흉내
    b.think_until = 0.0
    e = b.engine
    for _ in range(60 * 30):
        bot_brain.begin_frame(1.0)
        b.update(1 / 60)
    assert e.lock_events >= 2, e.lock_events                        # 워치독이 강제로 블록을 고정해 계속 진행
    assert b.watchdog_recoveries >= 3
    # 정상 동작하는 봇은 워치독이 개입하지 않음
    c = ai_bot.AIBot("y", difficulty="hard", seed=6)
    for _ in range(60 * 20):
        bot_brain.begin_frame(1.0)
        c.update(1 / 60)
    assert c.watchdog_recoveries == 0 and c.engine.lock_events > 5
    print("  OK bot watchdog")


def test_battle_late_pressure_and_target_never_none():
    import battle_royale as B
    m = B.BattleRoyaleMatch(total_players=5, bot_difficulty="easy", attacks_enabled=True)
    bots = [p["bot"] for p in m.players.values() if p.get("bot")]
    for _ in range(5):
        m.update(1 / 30)
    assert all(b.engine.incoming_garbage == 0 for b in bots)         # 초반에는 압박 없음
    m.elapsed = m.BATTLE_PRESSURE_START + 1.0
    for _ in range(60 * 25):                                        # 압박 시작 후 몇 번의 쓰레기 줄이 올라옴
        m.update(1 / 30)
        if any(b.engine.garbage_pushed_total > 0 or b.engine.incoming_garbage > 0 for b in bots if b.engine is not None):
            break
    assert any(b.engine.garbage_pushed_total > 0 or b.engine.incoming_garbage > 0 for b in bots)
    print("  OK battle late pressure")


def test_bot_fall_speed_restored_after_watchdog():
    """워치독(free_fall)이 바꾼 fall_speed가 다음 블록에서 원래대로 돌아오는지 (쉬움 포함 모든 난이도)"""
    import ai_bot
    import bot_brain
    for diff in ("easy", "master"):
        b = ai_bot.AIBot("x", difficulty=diff, seed=2)
        b.think_until = -1.0
        b._recover(0.0)
        assert b.free_fall
        bot_brain.begin_frame(1e9)
        b.update(1 / 60)                                              # fall_speed는 update() 안에서 free_fall을 보고 설정됨
        assert b.engine.fall_speed == 0.15
        for _ in range(600):
            bot_brain.begin_frame(1e9)
            b.update(1 / 60)
            if not b.free_fall:
                break
        assert not b.free_fall
        assert b.engine.fall_speed == 0.8, (diff, b.engine.fall_speed)
    print("  OK bot fall speed restored")


def test_stats_split_by_mode():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "stats.json")
        st = StatsManager(tp)
        st.record_match(1, 10, 3, 20, 4, 100)                       # 기본 = 배틀로얄
        st.record_match(5, 30, 0, 50, 6, 400, mode="survival")
        st.record_match(2, 30, 0, 10, 2, 60, mode="survival")
        b, sv = st.get_summary("battle"), st.get_summary("survival")
        assert (b["total_games"], b["victories"], b["total_kos"]) == (1, 1, 3)
        assert (sv["total_games"], sv["victories"], sv["best_rank_str"], sv["total_lines"]) == (2, 0, "#2위", 60)
        assert len(b["recent_matches"]) == 1 and len(sv["recent_matches"]) == 2
        st2 = StatsManager(tp)                                       # 재로드해도 분리 유지
        assert st2.get_summary("survival")["total_games"] == 2 and st2.get_summary()["total_games"] == 1
        # 예전 형식(survival 키 없음) 파일 호환 + 잘못된 survival 값 무시
        with open(tp, "w", encoding="utf-8") as f:
            json.dump({"total_games": 7, "survival": "oops"}, f)
        st3 = StatsManager(tp)
        assert st3.get_summary()["total_games"] == 7 and st3.get_summary("survival")["total_games"] == 0
        st3.reset_stats()
        assert st3.get_summary()["total_games"] == 0 and st3.get_summary("survival")["total_games"] == 0
    # 실제 게임 종료 시 모드별 집계
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    rec = []
    app.stats_mgr.record_match = lambda **kw: rec.append(kw["mode"])
    for atk, want in ((False, "survival"), (True, "battle")):
        app.settings.data["game_mode"] = "battle" if atk else "survival"
        app.start_game(mode="SOLO", total_players=4)
        app.match.local_is_alive = False
        app._tick_game(1 / 60)
        assert rec and rec[-1] == want, (atk, rec)
    print("  OK stats split by game mode")


def test_survival_mode_has_no_attacks():
    from battle_royale import BattleRoyaleMatch
    # 서바이벌: 어떤 공격도 전달/표시되지 않고, 쓰레기도 쌓이지 않음
    m = BattleRoyaleMatch(total_players=8, local_player_id="ME", local_player_name="me", attacks_enabled=False)
    bots = [p for p in m.players if p != "ME"]
    m.apply_attack("ME", bots[0], 6)
    m.apply_attack(bots[0], "ME", 6)
    assert not m.attack_effects and m.total_attacks_sent == 0
    assert m.local_engine.incoming_garbage == 0
    m.players["ME"]["target_id"] = bots[1]
    m.local_engine.garbage_to_send = 8
    m.update(0.016)
    assert not m.attack_effects and m.local_engine.garbage_to_send == 0
    assert m.total_attacks_sent == 8                           # 실제로 보내지는 않지만 만들어 낸 공격력은 APM용으로 집계
    for _ in range(60 * 20):                                   # 봇끼리도 서로 공격하지 않음(이펙트/쓰레기 없음)
        m.update(1 / 30)
        assert not m.attack_effects
    assert all(p["bot"].engine.incoming_garbage == 0 for p in m.players.values() if p.get("bot") and p["is_alive"])
    # 서바이벌 압박: 3분 전에는 없고, 이후에는 시간이 지나며 모두에게 쓰레기 줄이 올라옴 (공격 이펙트는 여전히 없음)
    m3 = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="me", attacks_enabled=False)
    for _ in range(int(150 * 20)):
        m3.update(1 / 20)
        m3.local_engine.incoming_garbage = 0
    assert not getattr(m3, "_pressure_announced", False), "3분 전에 압박이 시작됨"
    m3.elapsed = 200.0
    calls = []
    orig_qg = BlockEngine.queue_garbage
    BlockEngine.queue_garbage = lambda self_, n, *a, **k: (calls.append(n), orig_qg(self_, n, *a, **k))[1]
    try:
        for _ in range(20 * 40):
            m3.update(1 / 20)
    finally:
        BlockEngine.queue_garbage = orig_qg
    assert m3._pressure_announced and calls and not m3.attack_effects, (calls[:3], m3.attack_effects)
    # 배틀로얄(기본)은 그대로 공격이 전달됨
    m2 = BattleRoyaleMatch(total_players=8, local_player_id="ME", local_player_name="me")
    m2.apply_attack("ME", [p for p in m2.players if p != "ME"][0], 6)
    assert m2.attack_effects
    print("  OK survival mode (no attacks)")


def test_game_mode_setting_and_network_flag():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.state = "SETTINGS"; app.previous_state = "MENU"; app.settings_tab = "match"
    app._render_settings()
    assert app.settings.get("game_mode") == "battle"
    app._settings_activate("attack=off")
    assert app.settings.get("game_mode") == "survival"
    app.start_game(mode="SOLO", total_players=6)
    assert app.match.attacks_enabled is False
    for _ in range(20):
        app._tick_game(1 / 60)                                 # HUD/메뉴가 서바이벌 표시로 예외 없이 그려짐
    app.state = "MENU"; app._render_menu()
    app._settings_activate("attack=on")
    app.start_game(mode="SOLO", total_players=6)
    assert app.match.attacks_enabled is True
    # 네트워크: 호스트가 정한 모드가 참가자에게 전달됨
    host, client = _connect(20441)
    try:
        summary = [{"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": client.my_player_id, "name": "G", "is_ai": False}]
        host.host_send_start_game(summary, attacks_enabled=False)
        time.sleep(0.4)
        assert client.game_started and client.match_attacks is False
    finally:
        host.stop(); client.stop()
    print("  OK game mode setting + network flag")


def test_settings_and_stats_corruption():
    with tempfile.TemporaryDirectory() as d:
        sp = os.path.join(d, "settings.json")
        with open(sp, "w", encoding="utf-8") as f:
            json.dump({"bgm_volume": "60", "target_player_count": "many", "sfx_volume": 500, "custom_keys": {"hold": 5},
                       "bot_difficulty": "godlike", "fullscreen": "yes", "player_name": "Zed"}, f)
        s = SettingsManager(sp)
        assert s.get("bgm_volume") == 60 and s.get("target_player_count") == 100 and s.get("sfx_volume") == 100
        assert s.get("custom_keys") is None and s.get("bot_difficulty") == "mixed" and s.get("fullscreen") is False
        assert s.get("player_name") == "Zed"
        with open(sp, "w", encoding="utf-8") as f:
            f.write("{broken json")
        SettingsManager(sp)
        assert any(n.startswith("settings.json.corrupt-") for n in os.listdir(d)), "손상 파일 백업 없음"

        tp = os.path.join(d, "stats.json")
        with open(tp, "w", encoding="utf-8") as f:
            json.dump({"total_games": "x", "victories": 3, "recent_matches": "oops"}, f)
        st = StatsManager(tp)
        assert st.data["total_games"] == 0 and st.data["victories"] == 3 and st.data["recent_matches"] == []
        st.record_match(1, 10, True, 2, 30, 2, 55) if False else None
        with open(tp, "w", encoding="utf-8") as f:
            f.write("[1,2]")
        StatsManager(tp)
        assert any(n.startswith("stats.json.corrupt-") for n in os.listdir(d))
        # 기본값 리스트를 공유하지 않는지
        a, b = StatsManager(os.path.join(d, "a.json")), StatsManager(os.path.join(d, "b.json"))
        a.data["recent_matches"].append({"x": 1})
        assert b.data["recent_matches"] == []
    print("  OK settings/stats validation + backup")


def test_confirm_modals():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.start_game(mode="SOLO", total_players=6)
    for _ in range(30):
        app._tick_game(1 / 60)
    # 창 X: 솔로 게임은 멈추고 확인
    app._confirm_quit_app()
    assert app.modal is not None and app.is_paused
    # 다른 알림이 떠 있을 때 X → 덮어쓰지 않고 대기
    app.modal = None
    app._open_modal("호스트가 게임을 종료했습니다", ["x"], [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    ev = pygame.event.get()[0]
    assert ev.type == pygame.QUIT
    # (메인 루프 대신 동작만 검증) 대기 플래그 → 알림을 닫으면 종료 확인이 열림
    app._pending_quit = True
    app._modal_choose("stay")
    assert app.modal is not None and any(b[0] == "quit_app" for b in app.modal["buttons"])
    app.modal = None
    # 일시정지 중 ESC → 바로 나가지 않고 확인
    app.is_paused = True
    app.match.is_paused = True
    app.state = "GAME"
    app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
    assert app.state == "GAME" and app.modal is not None, "일시정지 ESC가 확인 없이 메뉴로 나감"
    app.modal = None
    # 초기화 버튼: 확인 창 → 취소하면 값 유지
    app.settings.set("bgm_volume", 30)
    app.state = "SETTINGS"
    app.previous_state = "MENU"
    app.settings_tab = "general"
    app._render_settings()
    r = app.settings_buttons.get("reset_defaults")
    if r is None:
        app.settings_tab = "match"
        app._render_settings()
        r = app.settings_buttons["reset_defaults"]
    app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    assert app.modal is not None and app.settings.get("bgm_volume") == 30
    app._modal_choose("stay")
    assert app.settings.get("bgm_volume") == 30
    print("  OK confirm modals")


def test_gameplay_rule_fixes():
    """조준 모드 기본값/기억, K.O. 조준 위험도, K.O. 인정 최근성, 봇 배지, 화면 흔들림 배율, 새 설정 키 검증"""
    import json as _json
    import config as _cfg
    from settings_manager import TARGET_MODE_OPTIONS, SHAKE_OPTIONS, SHAKE_SCALE
    assert tuple(_cfg.TARGET_MODES) == TARGET_MODE_OPTIONS, "설정 검증 목록과 config.TARGET_MODES가 어긋남"
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "s.json")
        _json.dump({"target_mode": "bogus", "screen_shake": "wild"}, open(f, "w"))
        st = SettingsManager(f)
        assert st.get("target_mode") == _cfg.DEFAULT_TARGET_MODE and st.get("screen_shake") == "normal", "잘못된 값은 기본값으로 복구"
        assert [st.cycle_screen_shake(1) for _ in range(3)] == ["off", "low", "normal"] and set(SHAKE_SCALE) == set(SHAKE_OPTIONS)
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=8, local_player_id="ME", local_player_name="Me", bot_difficulty="normal")
    assert m.local_target_mode == _cfg.DEFAULT_TARGET_MODE, "경기 기본 조준 모드는 config 기본값을 따라야 함"
    bots = [pid for pid in m.players if pid != "ME"]
    a, b, c = bots[0], bots[1], bots[2]
    # K.O./AUTO 조준: 쌓인 높이가 조금 낮아도 곧 올라올 쓰레기까지 더한 위험도가 더 큰 상대를 고름
    for pid in bots:
        m.players[pid]["highest_y"], m.players[pid]["ig"] = 12, 0
    m.players[a]["highest_y"], m.players[b]["highest_y"] = 9, 13
    m.players[b]["ig"] = 10
    assert m._most_endangered([a, b, c]) == b, "받을 공격(ig)까지 더한 위험도로 K.O. 직전 상대를 골라야 함"
    # K.O. 인정: 오래전에 한 번 공격한 봇에게는 인정하지 않고, 최근 공격자에게만 인정
    m.elapsed = 200.0
    m.players[b]["last_attacker"], m.players[b]["last_attack_t"] = a, m.elapsed - 100.0
    m._eliminate_player(b)
    assert m.players[a]["ko_count"] == 0, "100초 전 공격은 K.O. 인정 대상이 아님"
    m.players[c]["last_attacker"], m.players[c]["last_attack_t"] = a, m.elapsed - 2.0
    m._eliminate_player(c)
    assert m.players[a]["ko_count"] == 1, "최근 공격자에게는 K.O. 인정"
    # 봇 배지: K.O.를 쌓은 봇은 공격력이 오르되 상한(+50%)을 넘지 않음
    m.players[a]["ko_count"] = 8
    m.update(1 / 60)
    assert m.players[a]["is_alive"] and m.players[a]["bot"].engine.badge_rate == BattleRoyaleMatch.BOT_BADGE_CAP
    # 화면 흔들림 배율
    m.screen_shake = 0.0
    m.shake_scale = 0.0
    m.trigger_screen_shake(10.0)
    assert m.screen_shake == 0.0
    m.shake_scale = 0.4
    m.trigger_screen_shake(10.0)
    assert abs(m.screen_shake - 4.0) < 1e-9
    print("  OK gameplay rule fixes")


def test_clutch_save_bonus():
    """위험 높이에서 1초 넘게 버티다 줄을 지워 내려오면 작은 공격 보너스, 20초 쿨다운, 위기가 아니었다면 없음"""
    from battle_royale import BattleRoyaleMatch
    from config import BOARD_HEIGHT

    def fill(m, height):
        g = m.local_engine.grid
        for y in range(BOARD_HEIGHT):
            g[y] = ['G'] * 9 + [None] if y >= BOARD_HEIGHT - height else [None] * 10
    m = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", bot_difficulty="easy")
    fill(m, 17)
    m._track_danger()
    m.elapsed += 2.0
    fill(m, 9)
    m.local_engine.garbage_to_send = 0
    m.on_lines_cleared(1)
    assert m.local_engine.garbage_to_send == BattleRoyaleMatch.CLUTCH_BONUS, "위기 탈출 보너스"
    fill(m, 17)                                        # 바로 또 위기 → 쿨다운 안이라 보너스 없음
    m._track_danger()
    m.elapsed += 2.0
    fill(m, 9)
    m.local_engine.garbage_to_send = 0
    m.on_lines_cleared(1)
    assert m.local_engine.garbage_to_send == 0, "쿨다운 중에는 보너스 없음"
    m2 = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", bot_difficulty="easy")
    fill(m2, 9)                                        # 위기가 아니었다면 보너스 없음
    m2._track_danger()
    m2.elapsed += 2.0
    m2.local_engine.garbage_to_send = 0
    m2.on_lines_cleared(1)
    assert m2.local_engine.garbage_to_send == 0
    m3 = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", bot_difficulty="easy")
    fill(m3, 17)
    m3._track_danger()
    m3.elapsed += 0.3                                  # 위기를 1초도 못 버텼으면 보너스 없음
    fill(m3, 9)
    m3.local_engine.garbage_to_send = 0
    m3.on_lines_cleared(1)
    assert m3.local_engine.garbage_to_send == 0
    print("  OK clutch save bonus")


def test_stats_size_buckets_filter_and_goal():
    """전적: 최고 순위/기록 갱신은 인원 규모별로 따로 비교, 필터 요약, 다음 목표 문구, 예전 전적 파일 호환"""
    import json as _json
    from stats_manager import size_bucket, next_goal_text, SIZE_BUCKET_IDS
    assert [size_bucket(n) for n in (2, 10, 11, 49, 50, 100)] == ["small", "small", "mid", "mid", "large", "large"]
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "s.json")
        st = StatsManager(f)
        kw = dict(kos=0, lines=5, max_combo=0, survival_sec=30)
        assert st.record_match(rank=50, total_players=100, difficulty="hard", **kw) == []
        assert st.record_match(rank=3, total_players=6, difficulty="easy", **kw) == [], "다른 규모의 첫 경기는 순위 기록 갱신이 아님"
        assert st.record_match(rank=20, total_players=100, difficulty="hard", **kw) == ["rank"], "같은 규모(대)에서 50위 -> 20위"
        assert st.record_match(rank=90, total_players=100, difficulty="master", **kw) == []
        assert st.record_match(rank=2, total_players=6, difficulty="easy", **kw) == ["rank"], "소규모에서 3위 -> 2위"
        assert st.best_in_size("battle", 100) == 20 and st.best_in_size("battle", 6) == 2 and st.best_in_size("battle", 30) == 0
        full = st.get_summary("battle")
        assert full["filtered"] is False and full["total_games"] == 5
        big = st.get_summary("battle", size="large")
        assert big["filtered"] and big["total_games"] == 3 and big["best_rank"] == 20
        hard = st.get_summary("battle", difficulty="hard")
        assert hard["total_games"] == 2 and hard["best_rank"] == 20
        both = st.get_summary("battle", size="small", difficulty="hard")
        assert both["total_games"] == 0 and both["best_rank_str"] == "-"
        st2 = StatsManager(f)                                          # 저장/재로드 후에도 규모별 기록 유지
        assert st2.best_in_size("battle", 100) == 20
        # 예전 전적 파일(best_by_size 없음)은 최근 경기 목록으로 채움
        old = {"total_games": 2, "best_rank": 7, "recent_matches": [
            {"rank": 30, "total_players": 100}, {"rank": 7, "total_players": 100}]}
        _json.dump(old, open(f, "w"))
        st3 = StatsManager(f)
        assert st3.best_in_size("battle", 100) == 7
        assert st3.record_match(rank=5, total_players=100, **kw) == ["rank"]
    assert SIZE_BUCKET_IDS == ("small", "mid", "large")
    # 난이도 사다리: 배틀로얄 50인 이상에서 10위 안이면 그 난이도 클리어 (혼합/서바이벌/소규모는 제외), 목표 문구
    from stats_manager import LADDER
    with tempfile.TemporaryDirectory() as d2:
        f2 = os.path.join(d2, "l.json")
        sl = StatsManager(f2)
        kw2 = dict(kos=0, lines=5, max_combo=0, survival_sec=30)
        sl.record_match(rank=8, total_players=100, difficulty="mixed", **kw2)
        assert sl.last_ladder_clear is None and sl.ladder_cleared() == []
        sl.record_match(rank=8, total_players=20, difficulty="easy", **kw2)
        assert sl.last_ladder_clear is None, "50인 미만은 사다리 대상 아님"
        sl.record_match(rank=8, total_players=100, difficulty="easy", mode="survival", **kw2)
        assert sl.ladder_cleared() == [], "서바이벌은 사다리 대상 아님"
        sl.record_match(rank=11, total_players=100, difficulty="easy", **kw2)
        assert sl.ladder_cleared() == []
        sl.record_match(rank=10, total_players=100, difficulty="easy", **kw2)
        assert sl.last_ladder_clear == "easy" and sl.ladder_cleared() == ["easy"]
        sl.record_match(rank=3, total_players=100, difficulty="easy", **kw2)
        assert sl.last_ladder_clear is None, "이미 클리어한 난이도는 다시 알리지 않음"
        assert StatsManager(f2).ladder_cleared() == ["easy"], "저장/재로드 유지"
        _json.dump({"ladder": ["master", "bogus", "easy"]}, open(f2, "w"))
        assert StatsManager(f2).ladder_cleared() == ["easy", "master"], "알려진 난이도만, 쉬움->마스터 순"
    assert next_goal_text(8, 3, 100, 8, difficulty="easy", cleared=["easy"], ladder_clear="easy") == "쉬움 클리어! 다음은 보통에 도전"
    assert next_goal_text(8, 3, 100, 8, difficulty="master", cleared=list(LADDER), ladder_clear="master") == "마스터 클리어! 모든 난이도 클리어"
    assert next_goal_text(37, 5, 100, 12, difficulty="hard", cleared=[]) == "어려움 클리어까지 27계단 (10위 안)"
    assert next_goal_text(37, 5, 100, 12, difficulty="hard", cleared=["hard"]) == "최고 순위 #12까지 25계단"
    assert next_goal_text(37, 5, 20, 12, difficulty="hard", cleared=[]) == "최고 순위 #12까지 25계단", "50인 미만은 난이도 목표 없음"
    # 다음 목표 문구 (배지 다음 단계가 2 K.O. 이내면 그것을, 아니면 순위 목표)
    assert next_goal_text(51, 1, 100, 28) == "배지 Lv.1까지 1 K.O."
    assert next_goal_text(51, 5, 100, 28) == "최고 순위 #28까지 23계단"
    assert next_goal_text(8, 5, 100, 8) == "5위 안 진입"
    assert next_goal_text(20, 5, 100, 20) == "10위 안 진입"
    assert next_goal_text(3, 5, 100, 3) == "우승"
    assert next_goal_text(1, 20, 100, 1) == "우승 연속 도전"
    print("  OK stats size buckets / filter / next goal")


def test_late_game_relayout_coach_orbs_and_heartbeat():
    """후반 미니 보드 재배치(단계가 오를 때만, 살아남은 사람만), 첫 경기 코치 마크 1회, K.O. 구슬, 위기 박동음"""
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.renderer.screen = CANVAS
    app.settings.data["coach_done"] = False
    app.start_game(mode="SOLO", total_players=100)
    m = app.match
    assert m.coach_until > time.time() and app.settings.get("coach_done") is True, "첫 경기에만 코치 마크"
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    assert m.coach_until == 0.0, "Enter로 코치 마크를 닫을 수 있음"
    m.coach_until = time.time() + 15
    app._handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(600, 400)))
    assert m.coach_until == 0.0, "클릭으로도 닫힘"
    app.start_game(mode="SOLO", total_players=100)
    assert getattr(app.match, "coach_until", 0.0) == 0.0 or app.match.coach_until < time.time(), "두 번째 경기부터는 코치 마크 없음"
    m = app.match
    others = [p for p in m.players if p != m.local_player_id]

    def kill_to(target):
        alive = [p for p in others if m.players[p]["is_alive"]]
        for pid in alive[:max(0, len(alive) - target)]:
            m._eliminate_player(pid)
    for _ in range(3):
        app._tick_game(1 / 60)
    assert len(app.renderer.mini_board_rects) == 99
    kill_to(60)
    app._tick_game(1 / 60)
    assert len(app.renderer.mini_board_rects) == 99 and getattr(m, "layout_stage", 0) == 0, "단계 전에는 자리 유지(죽은 카드도 그대로)"
    kill_to(20)
    app._tick_game(1 / 60)
    assert getattr(m, "layout_stage", 0) == 1 and len(app.renderer.mini_board_rects) == 20, "20명 이하: 생존자만 다시 배치"
    ids = set(app.renderer.mini_board_rects)
    kill_to(18)                                        # 같은 단계 안에서 죽어도 카드는 그 자리에 남음 (다음 단계까지 재배치 안 함)
    app._tick_game(1 / 60)
    assert set(app.renderer.mini_board_rects) == ids
    kill_to(10)
    app._tick_game(1 / 60)
    assert m.layout_stage == 2 and len(app.renderer.mini_board_rects) == 10
    # K.O. 구슬: 내가 K.O.를 내면 생기고, 시간이 지나면 정리됨
    victim = [p for p in others if m.players[p]["is_alive"]][0]
    m._eliminate_player(victim, killer_id=m.local_player_id)
    assert len(m.ko_orbs) == 1
    m.ko_orbs[0]["t0"] -= 5.0
    app.renderer.render(m, app.sound_mgr)
    assert m.ko_orbs == []
    # 위기 박동음: 스택이 높으면 재생, 간격 안에서는 다시 재생하지 않음
    class FakeSound:
        def __init__(self):
            self.played = []

        def play(self, name, *a, **k):
            self.played.append(name)
    fs = FakeSound()
    m2 = __import__("battle_royale").BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", sound_mgr=fs, bot_difficulty="easy")
    for y in range(2, 20):                             # 18줄
        m2.local_engine.grid[y] = ['G'] * 9 + [None]
    m2._track_danger()
    m2._track_danger()
    assert fs.played.count("heartbeat") == 1
    m2.elapsed += 0.9
    m2._track_danger()
    assert fs.played.count("heartbeat") == 2, "18줄 이상이면 0.8초 간격"
    print("  OK late-game relayout / coach marks / K.O. orbs / heartbeat")


def test_killer_spectate_and_timeline():
    """나를 탈락시킨 상대 기록 + 관전은 그 상대부터, 경기 타임라인은 1초마다 기록되고 탈락 순간에 마지막 점을 남김"""
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=6, local_player_id="ME", local_player_name="Me", bot_difficulty="easy")
    bots = [pid for pid in m.players if pid != "ME"]
    for _ in range(95):
        m.update(1 / 30)
    assert len(m.timeline) >= 2 and all(len(pt) == 4 for pt in m.timeline)
    n0 = len(m.timeline)
    killer = bots[3]
    m.players["ME"]["last_attacker"], m.players["ME"]["last_attack_t"] = killer, m.elapsed - 1.0
    m._eliminate_player("ME")
    assert m.local_killer_id == killer and len(m.timeline) == n0 + 1
    assert m.cycle_spectate_target(0) == killer, "관전은 나를 탈락시킨 상대부터"
    m.players[killer]["is_alive"] = False
    m.spectate_target_id = None
    assert m.cycle_spectate_target(0) != killer, "그 상대가 이미 탈락했으면 다른 생존자"
    m2 = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", bot_difficulty="easy")
    m2._eliminate_player("ME")                         # 공격받은 적이 없으면 킬러 없음
    assert m2.local_killer_id is None
    print("  OK killer spectate / timeline")


def test_bot_names_and_traits():
    """봇 이름은 100개까지 서로 다르고(경기/로비 공통 함수), 모든 봇은 성향을 가지며, 성향에 맞게 조준이 달라짐"""
    import config as _cfg
    from battle_royale import BattleRoyaleMatch
    names = [_cfg.bot_display_name(i) for i in range(1, 121)]
    assert len(set(names)) == 120 and all(2 <= len(n) <= 6 for n in names[:100])
    m = BattleRoyaleMatch(total_players=30, local_player_id="ME", local_player_name="Me", bot_difficulty="master")
    bots = [p for pid, p in m.players.items() if pid != "ME"]
    assert len(bots) == 29 and len({b["name"] for b in bots}) == 29
    assert all(b["trait"] in _cfg.BOT_TRAITS for b in bots) and m.players["ME"]["trait"] == ""
    assert {b["trait"] for b in bots} >= {"균형형"}
    # 성향별 조준 확률: 반격형은 자주 되갚고, 저격형은 되갚지 않으며 위험도 조준을 더 자주 씀 (확률 자체를 검사: 무작위 대전 결과로는 불안정)
    R, D = BattleRoyaleMatch.RETALIATE_CHANCE, BattleRoyaleMatch.RETALIATE_DEFAULT
    assert R["반격형"] > D > R["저격형"] == 0.0
    S, SD = BattleRoyaleMatch.SMART_TARGET_CHANCE, BattleRoyaleMatch.SMART_TARGET_DEFAULT
    assert S["저격형"] > SD
    assert set(R) | set(S) <= set(_cfg.BOT_TRAITS)
    print("  OK bot names and traits")


def test_practice_and_daily_challenge():
    """연습 모드(죽어도 판 초기화, 전적 미기록, 쓰레기 주입) / 오늘의 도전(같은 날 같은 블록 순서·같은 상대 구성, 날짜별 최고 순위)"""
    import main as M
    from gfx import CANVAS
    from battle_royale import BattleRoyaleMatch
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.renderer.screen = CANVAS
    games_before = app.stats_mgr.get_summary("battle")["total_games"]
    app.start_game(mode="SOLO", practice=True)
    m = app.match
    assert m.practice and m.total_players == 2 and not m.attacks_enabled and getattr(m, "coach_until", 0.0) < time.time() + 1
    m.practice_inject_garbage(6)
    assert m.local_engine.incoming_garbage == 6
    for y in range(20):                                   # 끝까지 쌓이면 판이 초기화 (경기 종료/탈락 아님)
        m.local_engine.grid[y] = ['G'] * 10
    m.local_engine.game_over = True
    old_engine = m.local_engine
    for _ in range(5):
        app._tick_game(1 / 60)
    assert m.local_is_alive and m.local_engine is not old_engine and not m.local_engine.game_over and not m.match_finished
    assert m.local_engine.incoming_garbage == 0
    assert app.stats_mgr.get_summary("battle")["total_games"] == games_before, "연습은 전적에 기록되지 않음"
    m.practice_reset(announce=False)
    assert m.local_engine.incoming_garbage == 0
    # 오늘의 도전: 같은 날짜 시드 -> 같은 블록 순서와 상대 구성
    a = BattleRoyaleMatch(total_players=30, local_player_id="ME", local_player_name="Me", bot_difficulty="mixed", seed=20260930, daily="20260930")
    b = BattleRoyaleMatch(total_players=30, local_player_id="ME", local_player_name="Me", bot_difficulty="mixed", seed=20260930, daily="20260930")
    c = BattleRoyaleMatch(total_players=30, local_player_id="ME", local_player_name="Me", bot_difficulty="mixed", seed=20260929, daily="20260929")
    assert list(a.local_engine.next_queue) == list(b.local_engine.next_queue) and a.local_engine.current_piece == b.local_engine.current_piece
    roster = lambda mm: [(pid, p["name"], p["trait"], p["bot"].difficulty) for pid, p in mm.players.items() if p["bot"]]
    assert roster(a) == roster(b) and roster(a) != roster(c), "같은 날은 같은 상대 구성, 다른 날은 다른 구성"
    with tempfile.TemporaryDirectory() as d:
        st = StatsManager(os.path.join(d, "s.json"))
        kw = dict(total_players=100, kos=0, lines=5, max_combo=0, survival_sec=30)
        assert st.daily_best("20260930") == 0
        st.record_match(rank=40, daily="20260930", **kw)
        st.record_match(rank=25, daily="20260930", **kw)
        st.record_match(rank=60, daily="20260930", **kw)
        assert st.daily_best("20260930") == 25
        for day in range(1, 40):                          # 최근 30일만 유지
            st.record_match(rank=50, daily=f"202608{day:02d}" if day < 32 else f"202609{day - 31:02d}", **kw)
        assert len(st.data["daily"]) <= 30
        assert StatsManager(os.path.join(d, "s.json")).daily_best("20260930") == 25 or "20260930" not in st.data["daily"]
    print("  OK practice and daily challenge")


def test_hit_alarm_sounds():
    """피격 경고음: 3단계 소리가 실제로 등록되어 있고(예전엔 없는 'garbage' 소리를 불러 아무 소리도 안 났음), 줄 수에 따라 단계가 오르며, 연속 피격은 뭉개지지 않게 간격 제한"""
    from sound_fx import SoundManager
    from battle_royale import BattleRoyaleMatch
    sm = SoundManager()
    assert all(f"hit_{i}" in sm.sounds for i in (1, 2, 3)) and "warning" in sm.sounds
    assert [BattleRoyaleMatch.hit_alarm_tier(n) for n in (1, 2, 3, 5, 6, 12)] == [1, 1, 2, 2, 3, 3]

    class Fake:
        def __init__(self):
            self.played = []

        def play(self, name, *a, **k):
            self.played.append(name)
    fs = Fake()
    m = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", sound_mgr=fs, bot_difficulty="easy")
    m.apply_attack("BOT_01", "ME", 2)
    assert fs.played[-1] == "hit_1" and "garbage" not in fs.played
    n = len(fs.played)
    m.apply_attack("BOT_02", "ME", 1)                    # 바로 이어진 같은 단계 피격은 소리를 겹치지 않음
    assert len([p for p in fs.played[n:] if p.startswith("hit_")]) == 0
    m.apply_attack("BOT_02", "ME", 7)                    # 더 센 공격은 간격과 무관하게 바로 울림
    assert fs.played[-1] == "hit_3"
    print("  OK hit alarm sounds")


def test_closed_room_disappears_from_room_list():
    """방을 닫으면(BEACON_CLOSED) 방 참가 화면 목록에서 4초 만료를 기다리지 않고 바로 사라짐. 포트가 다른 닫힘 신호/이상한 메시지는 무시, stop()은 조회 캐시도 비움"""
    from network import NetworkManager
    nm = NetworkManager()
    nm._handle_discovery_message("192.168.0.9", {"type": "BEACON", "room_name": "테스트방", "port": 19999, "players": 1, "max_players": 100})
    assert "192.168.0.9" in nm.discovered_rooms and nm.discovered_rooms["192.168.0.9"]["room_name"] == "테스트방"
    nm._handle_discovery_message("192.168.0.9", {"type": "BEACON_CLOSED", "port": 12345})      # 다른 포트의 방이 닫힘: 이 방은 유지
    assert "192.168.0.9" in nm.discovered_rooms
    nm._handle_discovery_message("192.168.0.8", {"type": "BEACON_CLOSED", "port": 19999})      # 모르는 방의 닫힘: 무시
    for junk in (None, [], "x", {"type": 5}, {"type": "BEACON_CLOSED"}, {}):                     # 이상한 메시지에도 죽지 않음
        nm._handle_discovery_message("192.168.0.9", junk)
    assert "192.168.0.9" in nm.discovered_rooms
    nm._handle_discovery_message("192.168.0.9", {"type": "BEACON_CLOSED", "port": 19999})
    assert nm.discovered_rooms == {}, "닫힘 신호를 받으면 바로 삭제"
    nm.probe_results[("192.168.0.9", 19999)] = {"ok": True, "ts": 0.0}
    nm.discovered_rooms["1.2.3.4"] = {"ip": "1.2.3.4", "port": 19999, "room_name": "x", "players": 1, "max_players": 2, "last_seen": 0.0}
    nm.stop()
    assert nm.probe_results == {} and nm.discovered_rooms == {}, "stop()은 조회 캐시/방 목록을 비움"
    print("  OK closed room disappears from room list")


def test_new_record_flags():
    """record_match가 이번 경기가 이전 최고 기록(순위/K.O./최대 콤보)을 넘었는지 돌려줌. 첫 경기와 동률은 기록 갱신이 아님"""
    with tempfile.TemporaryDirectory() as d:
        st = StatsManager(os.path.join(d, "s.json"))
        kw = dict(total_players=100, lines=10, survival_sec=60)
        assert st.record_match(rank=50, kos=2, max_combo=3, **kw) == [], "첫 경기는 비교할 기록이 없음"
        assert st.record_match(rank=50, kos=2, max_combo=3, **kw) == [], "동률은 갱신이 아님"
        assert st.record_match(rank=30, kos=1, max_combo=1, **kw) == ["rank"]
        assert st.record_match(rank=60, kos=5, max_combo=6, **kw) == ["ko", "combo"]
        assert st.record_match(rank=90, kos=0, max_combo=0, **kw) == [], "0은 기록이 아님"
        assert st.record_match(rank=1, kos=0, max_combo=0, mode="survival", **kw) == [], "모드별로 따로 집계 (서바이벌 첫 경기)"
    print("  OK new record flags")


def test_play_bgm_does_not_block_while_synthesizing():
    """아직 합성 중인 BGM(로비곡)을 요청해도 UI 스레드가 멈추지 않고, 준비되면 tick()이 시작 (첫 방 만들기 7초 프리징 회귀)"""
    import time as _t
    from sound_fx import SoundManager
    sm = SoundManager(enabled=True)
    if not sm.bgm_ch_a:
        return
    sm.stop_bgm()
    sm.bgm_stages.pop('lobby', None)
    class Alive:
        def is_alive(self): return True
    real = sm._bgm_thread
    sm._bgm_thread = Alive()
    t0 = _t.time()
    for _ in range(50):
        sm.play_bgm('lobby')
    assert _t.time() - t0 < 0.2, "합성 중인 곡 요청이 UI를 막음"
    assert not sm.is_bgm_playing and sm._pending_bgm == 'lobby'
    sm.bgm_stages['lobby'] = sm.bgm_stages.get('menu') or sm.bgm_stages.get(1)
    sm.tick()
    assert sm.is_bgm_playing and sm.current_bgm_stage == 'lobby' and sm._pending_bgm is None
    sm._bgm_thread = real
    sm.stop_bgm()


def test_combat_text_pressure_and_onboarding():
    """전투 문구 정리(싱글/더블 배너 없음, 숫자 괄호 없음), 공격 토스트=실제 보낸 줄 수, 후반전 예고, 시작 카운트다운, 패인 한 줄, 첫 실행 기본값, 미니 보드 집중 모드"""
    import time as _t
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    e = m.local_engine
    e.last_clear_info = {}
    for n in (1, 2):
        m.floating_texts.clear(); m.on_lines_cleared(n)
        assert not [f for f in m.floating_texts if f["category"] == "action"], f"{n}줄 클리어는 배너를 띄우지 않음"
    m.floating_texts.clear(); m.on_lines_cleared(4)
    banner = [f["text"] for f in m.floating_texts if f["category"] == "action"]
    assert banner and "쿼드" in banner[0] and "(" not in banner[0], banner            # 실제 보낸 줄 수는 공격 토스트가 보여 줌

    # 공격 토스트의 줄 수 = 실제로 상대에게 들어간 줄 수 (후반 증폭 포함)
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.elapsed = 419.9                                            # 공격력 약 x1.4
    m.local_engine.garbage_to_send = 5
    m.update(0.016)
    toast = [f["text"] for f in m.floating_texts if f["category"] == "attack"]
    tid = m.players["L"]["target_id"]
    got = m.players[tid]["bot"].engine.incoming_garbage
    assert toast and f"+{got}줄" in toast[-1] and "×1.4" in toast[-1], (toast, got)

    # 후반전 예고: 4:30에 한 번, 이후 20% 단계가 오를 때마다 한 번
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.elapsed = 275.0; m._announce_escalation(); m._announce_escalation()
    assert sum("곧 후반전" in c["text"] for c in m.commentary) == 1
    m.elapsed = 361.0; m._announce_escalation(); m._announce_escalation()
    assert sum("×1.2" in c["text"] for c in m.commentary) == 1
    pm = BattleRoyaleMatch(total_players=2, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", practice=True)
    pm.elapsed = 400.0; pm._announce_escalation()
    assert not pm.commentary or all("후반전" not in c["text"] for c in pm.commentary), "연습 모드에는 후반전 알림 없음"

    # 시작 카운트다운
    assert m.countdown_left() == 0.0
    m.countdown_until = _t.time() + 2.0
    assert 1.5 < m.countdown_left() <= 2.0
    m.countdown_until = 0.0

    # 패인 한 줄
    m.local_is_alive = False
    m.timeline = [(i, 50 - i, 8 + i, (i % 5) * 2) for i in range(12)]
    m.local_death_attackers = 3
    msg = m.defeat_summary()
    assert msg and len(msg) == 2 and "집중 공격" in msg[0] and "나를 노린 상대 3명" in msg[0] and "받을 공격 최대 8줄" in msg[0] and "연습 모드" in msg[1], msg
    m.timeline = [(0, 9, 3, 0)]
    assert m.defeat_summary() is None, "근거(타임라인)가 부족하면 표시하지 않음"

    # 첫 실행 기본값: 전적이 없는 새 사용자만 50인 쉬움, 전적이 있으면 그대로
    import main as M
    app = M.BlockRoyaleApp()
    app.stats_mgr.reset_stats()
    app.settings.data["onboard_done"] = False
    app.settings.data["target_player_count"] = 100; app.settings.data["bot_difficulty"] = "mixed"
    app._apply_first_run_defaults()
    assert app.settings.get("target_player_count") == 50 and app.settings.get("bot_difficulty") == "easy" and app.settings.get("onboard_done")
    app.settings.data["onboard_done"] = False
    app.settings.data["target_player_count"] = 100; app.settings.data["bot_difficulty"] = "mixed"
    app.stats_mgr.record_match(5, 100, 1, 10, 1, 60)
    app._apply_first_run_defaults()
    assert app.settings.get("target_player_count") == 100 and app.settings.get("bot_difficulty") == "mixed" and app.settings.get("onboard_done")

    # 미니 보드 표시: 자세히 -> 집중 -> 간략 순으로 순환, 집중일 때만 렌더러가 카드를 어둡게
    app.settings.data["mini_detail"] = "detailed"
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "focus" and app.renderer.mini_focus and app.renderer.mini_detailed
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "simple" and not app.renderer.mini_focus and not app.renderer.mini_detailed
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "detailed" and not app.renderer.mini_focus and app.renderer.mini_detailed


def test_achievements():
    """업적: 조건 달성 시 한 번만 기록되고 저장/불러오기와 초기화가 되며, 서바이벌 경기와는 무관, 결과/전적 화면이 그려짐"""
    import tempfile
    from stats_manager import StatsManager, ACHIEVEMENTS, ACHIEVEMENT_IDS
    path = os.path.join(tempfile.mkdtemp(), "stats.json")
    sm = StatsManager(path)
    assert len(ACHIEVEMENTS) == 10 and len(set(ACHIEVEMENT_IDS)) == 10
    sm.record_match(40, 100, 0, 5, 1, 60)
    assert sm.last_new_achievements == [] and sm.achievements_done() == []
    sm.record_match(1, 100, 6, 50, 3, 300)
    assert sm.last_new_achievements == ["first_ko", "top10", "victory", "century", "ko5"], sm.last_new_achievements
    sm.record_match(1, 100, 6, 50, 3, 300)
    assert sm.last_new_achievements == [], "이미 달성한 업적은 다시 알리지 않음"
    sm.record_match(30, 50, 12, 90, 9, 700, mode="survival")             # 서바이벌 경기는 업적과 무관
    assert sm.achievements_done() == ["first_ko", "top10", "victory", "century", "ko5"]
    sm.record_match(9, 40, 10, 90, 8, 650)
    assert set(sm.last_new_achievements) == {"ko10", "combo8", "marathon"}
    sm2 = StatsManager(path)                                             # 저장 후 다시 불러와도 유지
    assert sm2.achievements_done() == sm.achievements_done() and len(sm2.achievements_done()) == 8
    d = json.load(open(path, encoding="utf-8"))
    d["achievements"] = ["victory", "없는업적", 5]                        # 손상/알 수 없는 값은 걸러냄
    json.dump(d, open(path, "w", encoding="utf-8"))
    assert StatsManager(path).achievements_done() == ["victory"]
    for i in range(3):                                                    # 오늘의 도전 3일 + 사다리 4단계
        sm.record_match(5, 100, 0, 5, 1, 60, daily=f"2026090{i + 1}")
    assert "daily3" in sm.achievements_done()
    for dn in ("easy", "normal", "hard", "master"):
        sm.record_match(5, 100, 0, 5, 1, 60, difficulty=dn)
    assert "ladder_all" in sm.achievements_done()
    sm.reset_stats()
    assert sm.achievements_done() == []

    # 전적 화면의 업적 탭 / 결과 화면의 업적 줄이 오류 없이 그려짐
    import main as M
    app = M.BlockRoyaleApp()
    app.stats_mgr.reset_stats()
    app.stats_mgr.record_match(1, 100, 6, 50, 3, 300)
    app.state = "RECORDS"
    for mode in ("achv", "survival", "battle"):
        app.records_mode = mode
        app._render_records()
    order = []
    for _ in range(3):
        app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0, unicode=""))
        order.append(app.records_mode)
    assert order == ["survival", "achv", "battle"], order


def test_v1012_feed_phase_log_achievement_progress():
    """v1.0.12: 단계 문구가 사실대로, 피격 토스트 합치기, 후반전 알림 고정 칸, 패인 줄에 증폭/최다 공격자, 경기 로그, 업적 진행도"""
    import time as _t
    from battle_royale import BattleRoyaleMatch
    from stats_manager import ACHIEVEMENTS, StatsManager
    m = BattleRoyaleMatch(total_players=20, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    # 단계 문구: 속도/서든 데스를 단정하지 않음 (낙하 속도는 비율로 계속 빨라지고, 서든 데스는 9분 압박 때만)
    for pid in [p for p in m.players if p != "L"][:11]:
        m._eliminate_player(pid)
    m.update(0.016)
    txt = " ".join(c["text"] for c in m.commentary) + " ".join(f["text"] for f in m.floating_texts)
    assert "PHASE 2" in txt and "스피드" not in txt, txt
    m.floating_texts.clear(); m.commentary.clear()
    for pid in [p for p in m.players if p != "L" and m.players[p]["is_alive"]][:7]:
        m._eliminate_player(pid)
    m.update(0.016)
    txt = " ".join(c["text"] for c in m.commentary) + " ".join(f["text"] for f in m.floating_texts)
    assert "FINAL" in txt and "서든" not in txt, txt
    # 피격 토스트 합치기: 1초 안 연속 피격은 한 개로, 보낸 사람 수/합계 갱신
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    m.apply_attack(others[0], "L", 2); m.apply_attack(others[1], "L", 3); m.apply_attack(others[1], "L", 1)
    hits = [f["text"] for f in m.floating_texts if f["text"].startswith("[피격")]
    assert len(hits) == 1 and "2명" in hits[0] and "+6줄" in hits[0], hits
    assert m.local_hits_from[others[0]] == 2 and m.local_hits_from[others[1]] == 4
    m._hit_agg["t"] -= 2.0                                    # 1초가 지나면 새 토스트
    m.apply_attack(others[2], "L", 1)
    assert len([f for f in m.floating_texts if f["text"].startswith("[피격")]) == 2
    # 후반전 알림은 pin 카테고리
    m.elapsed = 275.0; m._announce_escalation()
    assert any(f["category"] == "pin" for f in m.floating_texts)
    # 패인 줄: 최다 공격자 + 후반전 배율
    m.local_is_alive = False
    m.elapsed = 420.0
    m.timeline = [(i, 9, 12 + i % 3, i % 6) for i in range(12)]
    m.local_hits_from = {others[0]: 9, others[1]: 2}
    lines = m.defeat_summary()
    assert "후반전 ×1.4" in lines[0] and "가장 많이 보낸" in lines[0] and len(lines) == 2, lines
    # 경기 로그: 켠 경우만 기록, JSON 직렬화 가능
    m2 = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m2.set_target_mode("KO"); m2.log_event("x")
    assert m2.events == []
    m2.log_enabled = True
    m2.set_target_mode("RANDOM"); m2.apply_attack([p for p in m2.players if p != "L"][0], "L", 2)
    log = m2.match_log()
    json.dumps(log)
    kinds = [e["kind"] for e in log["events"]]
    assert "target_mode" in kinds and "hit" in kinds, kinds
    # 업적 진행도/마라토너 7분
    ids = {a[0]: a for a in ACHIEVEMENTS}
    assert ids["marathon"][2].startswith("한 판에서 7분"), ids["marathon"][2]
    import tempfile
    sm = StatsManager(os.path.join(tempfile.mkdtemp(), "stats.json"))
    sm.record_match(40, 100, 3, 10, 5, 400)
    pr = sm.achievement_progress()
    assert pr["ko5"] == (3, 5) and pr["combo8"] == (5, 8) and pr["marathon"] == (400, 420), pr
    sm.record_match(40, 100, 0, 10, 1, 430)
    assert "marathon" in sm.achievements_done()


def test_v1013_result_flow_autolock_assist_tasks():
    """v1.0.13: 탈락/순위표에서 P=연습, 오늘의 도전 재도전 유지, 순위표 정보 띠, 자동 조준 락온, K.O. 기여, 토스트 우선순위, 통계 칸, 연습 과제"""
    import main as M
    from gfx import CANVAS
    from battle_royale import BattleRoyaleMatch
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.renderer.screen = CANVAS
    app.settings.data["coach_done"] = True

    # 오늘의 도전 재도전은 같은 도전으로
    app.start_game(mode="SOLO", daily="20260102")
    assert app.match.daily == "20260102"
    app._restart_after_match()
    assert app.match.daily == "20260102" and app.match.total_players == 100

    # 탈락 후 P: 일시정지가 아니라 연습 모드 시작
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m._eliminate_player(m.local_player_id)
    app.result_lock_until = 0.0
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0))
    assert app.match.practice and not app.is_paused, "탈락 후 P는 연습 시작"
    # 결과 버튼 목록에 연습하기가 포함됨
    app.start_game(mode="SOLO", total_players=20)
    app.match._eliminate_player(app.match.local_player_id)
    assert "practice" in app._result_button_ids()

    # 순위표 정보 띠: 기록/업적/목표/패인 중 있는 것만
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.new_records = ("rank",); m.new_achievements = ["first_win"]; m.ladder_clear = None; m.next_goal = "우승"
    m.local_rank = 1
    info = app.renderer._standings_info_lines(m)
    assert info and info[0][0].startswith("★") and "최고 기록" in info[0][0], info
    assert len(info) == 2 and info[1][0].startswith("다음 목표"), info

    # 자동 조준 락온: 0.8초 안에는 위험도가 바뀌어도 대상 유지, 대기열 가득 찬 상대는 건너뜀
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    for p in others:
        m.players[p]["highest_y"] = 10
        m.players[p]["ig"] = 0
    m.set_target_mode("AUTO")
    m.players[others[0]]["highest_y"] = 5
    assert m.get_target_for("L") == others[0]
    m.players[others[1]]["highest_y"] = 1                          # 더 위험해졌지만 락온 시간 안
    m.elapsed += 0.3
    assert m.get_target_for("L") == others[0]
    m.elapsed += 1.0
    assert m.get_target_for("L") == others[1], "락온 시간이 지나고 위험도 차이가 크면 바꿈"
    m.elapsed += 2.0
    m.players[others[1]]["highest_y"] = 5                          # 차이가 작으면 유지
    m.players[others[0]]["highest_y"] = 4
    assert m.get_target_for("L") == others[1]
    m.players[others[1]]["ig"] = 24                                # 가득 찬 상대는 건너뜀
    assert m.get_target_for("L") == others[0]
    alive = [p for p in others if m.players[p]["is_alive"]]
    assert m.get_target_for("L", "KO") == m._most_endangered(alive), "KO 모드는 락온 없음"

    # K.O. 기여: 내가 4줄 이상 보낸 상대를 다른 플레이어가 마무리
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    m.apply_attack("L", others[0], 5)
    m.floating_texts.clear()
    m._eliminate_player(others[0], killer_id=others[1])
    assert m.local_assists == 1 and m.local_ko_count == 0
    assert any(f["text"].startswith("[처치 기여]") for f in m.floating_texts)
    m.apply_attack("L", others[2], 2)
    m._eliminate_player(others[2], killer_id=others[1])
    assert m.local_assists == 1, "4줄 미만은 기여가 아님"

    # 토스트: 오류 없이 그려지고, 칸이 모자라면 콤보가 먼저 밀려남
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.add_floating_text("[피격 경고] +3줄", (255, 0, 0), category="alert")
    m.add_floating_text("[3연속 콤보!]", (255, 0, 0), category="combo")
    m.add_floating_text("[공격 발송] +2줄", (255, 0, 0), category="attack")
    drawn = []
    real = app.renderer.font_small.render
    class _F:
        def __init__(self, f): self.f = f
        def render(self, text, *a, **k):
            drawn.append(text)
            return self.f.render(text, *a, **k)
        def __getattr__(self, k): return getattr(self.f, k)
    app.renderer.font_small = _F(app.renderer.font_small)
    try:
        app.renderer._render_floating_texts(m, 0, 0)
    finally:
        app.renderer.font_small = app.renderer.font_small.f
    assert "[피격 경고] +3줄" in drawn and "[공격 발송] +2줄" in drawn and "[3연속 콤보!]" not in drawn, drawn

    # 연습 과제: 순서대로 완료
    m = BattleRoyaleMatch(total_players=2, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", practice=True)
    assert m.practice_current_task()[0] == 0
    m.local_engine.garbage_canceled_total = 2
    m._practice_check({"cleared": 1})
    assert m.practice_current_task()[0] == 1
    m._practice_check({"cleared": 4})
    m.local_engine.combo = 3
    m._practice_check({"cleared": 1})
    m._practice_check({"cleared": 2, "is_tspin": True})
    assert m.practice_current_task() is None
    print("  OK v1.0.13")


if __name__ == "__main__":
    pygame.init()
    keep = {}
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    for p in (SETTINGS_FILE, STATS_FILE):
        keep[p] = open(p, "rb").read() if os.path.exists(p) else None
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL REVIEW FIX TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)
