"""
LAN: 끊김/재바인딩/봇 대행/팀전/대기실
실행: python test_lan.py
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


def test_network_rebind_loss_and_reorder():
    """루프백에서 손실/순서 뒤바뀜/주소 변경을 직접 만들어 호스트 처리를 확인"""
    import json
    import socket
    import time as _t
    from network import NetworkManager, MsgType

    def state(score):
        return {"compact_grid": [0] * 20, "highest_y": 20, "score": score, "is_alive": True}

    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=20198, max_players=10)
    client.start_client("127.0.0.1", 20198, "Guest")
    t0 = _t.time()
    while not client.connected and _t.time() - t0 < 3:
        client.client_retry_join()
        _t.sleep(0.1)
    assert client.connected
    raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)           # 공유기 때문에 주소(포트)가 바뀐 같은 참가자를 흉내 냄
    try:
        host.game_started = True
        pid = client.my_player_id
        send = lambda sock, seq, score, tok: sock.sendto(json.dumps({"type": MsgType.CLIENT_STATE, "seq": seq, "state": state(score), "tok": tok}).encode(), ("127.0.0.1", 20198))
        # 순서 뒤바뀜: seq 5 다음에 seq 3이 늦게 도착 -> 무시
        client.state_seq = 4
        client.client_send_state(state(50))
        _t.sleep(0.2)
        assert host.remote_players_state[pid]["score"] == 50
        client.state_seq = 2
        client.client_send_state(state(30))
        _t.sleep(0.2)
        assert host.remote_players_state[pid]["score"] == 50, "오래된 패킷이 최신 상태를 덮어씀"
        # 손실: seq가 건너뛰어도(5 -> 9) 받아들임
        client.state_seq = 8
        client.client_send_state(state(90))
        _t.sleep(0.2)
        assert host.remote_players_state[pid]["score"] == 90
        # 주소 변경 + 틀린 토큰은 거절, 맞는 토큰은 이어 붙음
        send(raw, 100, 777, "wrongtoken")
        _t.sleep(0.2)
        assert len(host.clients) == 1 and host.remote_players_state[pid]["score"] == 90
        send(raw, 100, 777, client.session_token)
        _t.sleep(0.2)
        assert host.remote_players_state[pid]["score"] == 777
        assert raw.getsockname()[1] in {a[1] for a in host.clients}
        # 대기실(게임 시작 전)에서는 토큰으로 이어 붙이지 않음
        host.game_started = False
        raw2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send(raw2, 200, 5, client.session_token)
        _t.sleep(0.2)
        assert host.remote_players_state[pid]["score"] == 777
        raw2.close()
    finally:
        raw.close()
        host.stop()
        client.stop()


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


def test_bot_takeover_ignores_stale_remote_state():
    app = _app()
    app.start_game("SOLO", total_players=20)
    m = app.match
    m.players["NET_9"] = m._new_player("NET_9", "G", False, None, [0] * 20)
    m.total_players += 1
    assert m.take_over_with_bot("NET_9", None)
    class N:
        mode = "HOST"; running = True; incoming_attacks = []; chat_log = []; remote_details = {}
        remote_players_state = {"NET_9": {"compact_grid": [1] * 20, "highest_y": 0, "score": 999, "is_alive": False}}
    m.net_mgr = N()
    m.countdown_until = 0.0
    for _ in range(5):
        m.update(0.05)
    assert m.players["NET_9"]["is_alive"] and m.players["NET_9"]["score"] != 999


def test_bot_pool_detects_stalled_worker():
    import time as _t
    import bot_pool

    class _Proc:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            pass

    class _Q:
        def get_nowait(self):
            import queue
            raise queue.Empty

        def put_nowait(self, x):
            pass

    st = bot_pool._state
    saved = {k: (list(v) if isinstance(v, list) else (set(v) if isinstance(v, set) else (dict(v) if isinstance(v, dict) else v))) for k, v in st.items()}
    try:
        st.update(procs=[_Proc()], req=_Q(), res=_Q(), hello=1, broken=False, last_res=_t.time() - 60)
        st["pending"].clear()
        bot_pool.pump()
        assert not st["broken"], "요청이 없으면 멈춘 것이 아님"
        st["pending"].add(99)
        st["born"][99] = _t.time()
        bot_pool.pump()
        assert st["broken"], "응답 없는 작업자를 감지하지 못함"
    finally:
        st.clear()
        st.update(saved)


def test_lan_team_mode_is_identical_on_every_machine():
    import time as _t
    from network import NetworkManager, PROTOCOL_VERSION
    from battle_royale import BattleRoyaleMatch
    assert PROTOCOL_VERSION >= 3
    plist = [{"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": "NET_P1", "name": "G1", "is_ai": False}, {"id": "NET_P2", "name": "G2", "is_ai": False}] +             [{"id": f"BOT_{i:02d}", "name": f"b{i}", "is_ai": True} for i in range(1, 18)]

    class FakeNet:
        mode = "CLIENT"; running = True; incoming_attacks = []; chat_log = []; remote_details = {}; remote_players_state = {}; host_view_of_me = None

    ms = {}
    for me in ("HOST_P1", "NET_P1", "NET_P2"):
        fn = FakeNet()
        fn.mode = "HOST" if me == "HOST_P1" else "CLIENT"
        ms[me] = BattleRoyaleMatch(total_players=20, local_player_id=me, net_mgr=fn, initial_players=plist, team_mode=True)
    base = ms["HOST_P1"].teams
    assert base and all(m.teams == base for m in ms.values()), "컴퓨터마다 팀 배정이 다름"
    assert abs(sum(1 for t in base.values() if t == 0) - sum(1 for t in base.values() if t == 1)) <= 1
    assert base["HOST_P1"] != base["NET_P1"] and base["NET_P1"] != base["NET_P2"] or base["HOST_P1"] != base["NET_P2"]
    for me, m in ms.items():
        mine, foes = m.team_alive_counts()
        assert mine + foes == 20 and abs(mine - foes) <= 1
        allies = [p for p in m.players if m.is_ally(me, p)]
        assert allies and all(base[p] == base[me] for p in allies)
        for _ in range(10):
            t = m.get_target_for(me)
            assert t is None or not m.is_ally(me, t)
    # 호스트 -> 참가자: 팀전 여부가 시작/명단 메시지로 전달됨
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=20199, max_players=10)
    client.start_client("127.0.0.1", 20199, "Guest")
    t0 = _t.time()
    while not client.connected and _t.time() - t0 < 3:
        client.client_retry_join()
        _t.sleep(0.1)
    assert client.connected
    try:
        host.room_settings["team"] = True
        host.host_broadcast_roster()
        _t.sleep(0.3)
        assert client.room_rules.get("team") is True
        host.host_send_start_game(plist, attacks_enabled=True, team=True)
        _t.sleep(0.3)
        assert client.game_started and client.match_team is True
    finally:
        host.stop(); client.stop()
    # 생존(공격 없음)이면 팀전이 아님
    c2 = NetworkManager()
    c2.match_attacks = False
    assert c2.match_team is False


def test_lan_team_lobby_renders_and_toggles():
    app = _app()
    app.settings.set("rule_team", False)
    app.state = "HOST_LOBBY"
    assert app.net_mgr.start_host(port=20200, max_players=10) if hasattr(app.net_mgr, "start_host") else True
    try:
        app._render_host_lobby()
        assert "team_toggle" in app.lobby_buttons
        app._handle_host_lobby_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t, mod=0, unicode="t"))
        assert app.settings.get("rule_team") is True
        app._update_host_lobby(0.1)
        assert app.net_mgr.room_settings.get("team") is True
        app._render_host_lobby()
    finally:
        app.net_mgr.stop()
        app.settings.set("rule_team", False)


def test_v133_lobby_reap_rejoin_and_taken_over_notice():
    import json
    import socket
    import time as _t
    from network import NetworkManager, MsgType, PROTOCOL_VERSION
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=20201, max_players=10)
    client.start_client("127.0.0.1", 20201, "Guest")
    t0 = _t.time()
    while not client.connected and _t.time() - t0 < 3:
        client.client_retry_join()
        _t.sleep(0.1)
    assert client.connected
    raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    raw.settimeout(1.0)
    try:
        pid = client.my_player_id
        # 대기실: 같은 토큰으로 다른 주소에서 다시 JOIN하면 새 참가자가 아니라 기존 자리를 이어받음
        raw.sendto(json.dumps({"type": MsgType.JOIN_REQ, "proto": PROTOCOL_VERSION, "name": "Guest", "tok": client.session_token}).encode(), ("127.0.0.1", 20201))
        ack = json.loads(raw.recvfrom(65535)[0].decode())
        assert ack["type"] == MsgType.JOIN_ACK and ack["assigned_id"] == pid and len(host.clients) == 1
        # 대기실에서 신호가 끊긴 참가자는 명단에서 빠짐
        for info in host.clients.values():
            info["last_seen"] = _t.time() - 60
        host.reap_clients(lobby=True)
        assert not host.clients
        # 경기 중: 다시 접속해 같은 토큰으로 상태를 보내면 봇이 이어받았다는 통보를 받음
        host.game_started = True
        host.clients[("127.0.0.1", 59999)] = {"id": "NET_9", "name": "G9", "last_seen": _t.time() - 60, "token": client.session_token}
        host.reap_clients()
        assert host.takeover_events and client.session_token in host.taken_tokens
        client.taken_over = False
        _t.sleep(1.2)
        client.client_send_state({"compact_grid": [0] * 20, "highest_y": 20, "score": 1, "is_alive": True})
        _t.sleep(0.4)
        assert client.taken_over is True, "돌아온 참가자에게 통보되지 않음"
    finally:
        raw.close()
        host.stop(); client.stop()


def test_host_lobby_labels_fit_beside_their_controls():
    """대기실 경기 설정 카드: 왼쪽 라벨이 오른쪽 컨트롤(칩/증감 버튼)과 겹치지 않아야 함 (영어 "Team Battle (2 teams)"가 칩 밑으로 잘리던 문제)"""
    import i18n
    app = _app()
    try:
        for lang in ("ko", "en"):
            i18n.set_language(lang)
            app.state = "HOST_LOBBY"
            app._render_host_lobby()
            card_w = 170 - 18 - 10                                   # 라벨 시작(card.x+18)부터 컨트롤 시작(card.x+170)까지, 여유 10px
            for src in ("대전 인원", "봇 난이도", "게임 모드", "팀전 (2팀)"):
                w = app.font_mid.size(i18n.tr(src))[0]
                assert w <= card_w, f"{lang}: {src!r} 라벨 폭 {w} > {card_w}"
            # 방 제목 라벨과 방 이름 입력 글자 사이 간격은 코드가 라벨 폭에서 계산하므로 라벨이 상자 안에 들어가는지만 확인
            assert app.font_small.size(i18n.tr("방 제목"))[0] < 200
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
        print("[ALL LAN TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
