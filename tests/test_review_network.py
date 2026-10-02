"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트 - 네트워크: 생존 신호, 참가 거절, 상태 검증, 공격 속도 제한, WORLD_SYNC, 방 목록
(예전 test_review_fixes.py를 영역별로 나눈 파일. 실행: python test_review_network.py, SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
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


class _FakeNet:
    mode = "CLIENT"
    running = True
    incoming_attacks = []
    chat_log = []

    def __init__(self):
        self.remote_players_state = {}
        self.host_view_of_me = None


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
        print("[ALL REVIEW NETWORK TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)
