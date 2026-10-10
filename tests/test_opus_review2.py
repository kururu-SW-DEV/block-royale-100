"""
2026-10-02 Opus 검토 반영 회귀 테스트: UDP 수신 스레드 CONNRESET, 프로토콜 버전 확인, 좌표 변환 왕복(여러 해상도/종횡비),
Canvas 헬퍼, 프레임 시간 상한, 오버레이 클릭 관통, 리바인딩 예약 키, 카운트다운 중 키 입력, 흔들림 양자화.
실행: python test_opus_review2.py
"""
import os
import sys
import time
import json
import socket

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from network import NetworkManager, PROTOCOL_VERSION
from gfx import CANVAS, BASE_W, BASE_H, HiSurf

SIZES = [(1366, 768), (1920, 1080), (1920, 1200), (2560, 1080), (1024, 768), (3840, 2160), (640, 360)]


def _free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_receive_thread_survives_closed_port():
    port = 20261
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=port, max_players=10)
    try:
        dead = _free_udp_port()
        for _ in range(5):                                   # 닫힌 포트로 보내면 Windows는 다음 recvfrom에서 CONNRESET을 냄
            host.sock.sendto(b"x", ("127.0.0.1", dead))
            time.sleep(0.05)
        assert host.listen_thread.is_alive(), "호스트 수신 스레드가 죽음"
        client.start_client("127.0.0.1", port, "Guest")
        t0 = time.time()
        while not client.connected and time.time() - t0 < 3:
            client.client_retry_join()
            time.sleep(0.1)
        assert client.connected and host.listen_thread.is_alive()
    finally:
        client.stop()
        host.stop()
    # 클라이언트: 아직 열리지 않은 방에 접속 시도 -> 수신 스레드 유지
    c2 = NetworkManager()
    c2.start_client("127.0.0.1", _free_udp_port(), "G2")
    try:
        for _ in range(5):
            c2.client_retry_join()
            time.sleep(0.05)
        assert c2.listen_thread.is_alive(), "클라이언트 수신 스레드가 죽음"
    finally:
        c2.stop()
    print("  OK connreset")


def test_protocol_version_rejected():
    port = 20262
    host = NetworkManager()
    assert host.start_host(port=port, max_players=10)
    try:
        for extra in ({"proto": PROTOCOL_VERSION + 99}, {}):         # 다른 버전 / 버전 정보 없는 옛 클라이언트
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            s.sendto(json.dumps({"type": "JOIN_REQ", "name": "Old", "color": 0, **extra}).encode(), ("127.0.0.1", port))
            msg = json.loads(s.recvfrom(4096)[0].decode())
            s.close()
            assert msg["type"] == "JOIN_NACK" and msg["reason"] == "version", msg
        assert not host.clients
    finally:
        host.stop()
    print("  OK version")


def test_message_types_are_constants():
    """network.py가 보내거나 받는 모든 메시지 타입은 MsgType에 정의되어 있고, 문자열 리터럴로 직접 비교하지 않음"""
    import re
    from network import MsgType
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "network.py"), encoding="utf-8").read()
    used = set(re.findall(r"MsgType\.([A-Z_]+)", src))
    assert used and used <= MsgType.ALL, used - MsgType.ALL
    assert not re.findall(r"(?:mtype|kind) (?:==|!=) \"", src), "타입 비교에 문자열 리터럴이 남아 있음"
    assert not re.findall(r"\"type\": \"[A-Z_]+\"", src), "송신 메시지에 문자열 리터럴이 남아 있음"
    assert not re.findall(r"""b['"][^'"
]*MsgType""", src), "바이트 문자열 안에 MsgType 이름이 그대로 들어감"
    print("  OK msgtype")


def test_bot_pool_params_and_stale_cleanup():
    import tempfile
    _saved_dir = os.environ.get("BR_DATA_DIR")
    os.environ["BR_DATA_DIR"] = tempfile.mkdtemp()               # 일부러 작업자를 비정상으로 만드는 검사라 'bot_pool disabled' 기록이 진짜 error.log에 남지 않게
    try:
        _body_botpool()
    finally:
        if _saved_dir is None:
            os.environ.pop("BR_DATA_DIR", None)
        else:
            os.environ["BR_DATA_DIR"] = _saved_dir


def _body_botpool():
    import pickle
    import bot_pool
    st = bot_pool._state
    bot_pool.stop()
    st["started"] = False
    # 워커 없이 큐만 흉내: submit이 params를 바뀔 때만 다시 묶는지, 오래된 요청이 정리되는지 확인
    class Q:
        def __init__(self): self.items = []
        def put(self, x): self.items.append(x)
        def put_nowait(self, x): self.items.append(x)
    st["req"] = Q(); st["hello"] = 1; st["broken"] = False
    args = ([0] * 20, "T", None, ["I"], True, -1, False, 0, 2, 3, True, True)
    r1 = bot_pool.submit(*args, {"a": 1})
    blob1 = st["req"].items[-1][-1]
    r2 = bot_pool.submit(*args, {"a": 1})
    blob2 = st["req"].items[-1][-1]
    assert blob1 == blob2 and blob1[1] is blob2[1], "같은 params는 다시 pickle하지 않아야 함"
    bot_pool.submit(*args, {"a": 2})
    assert st["req"].items[-1][-1][0] != blob1[0] and pickle.loads(st["req"].items[-1][-1][1]) == {"a": 2}
    # 탈락한 봇이 남긴 결과: 일정 시간 뒤 pump가 정리
    st["ready"][r1] = []
    st["born"][r1] = time.time() - bot_pool.STALE_AFTER - 1
    st["procs"] = [type("P", (), {"is_alive": lambda self: True})()]
    st["res"] = type("R", (), {"get_nowait": lambda self: (_ for _ in ()).throw(__import__("queue").Empty())})()
    bot_pool.pump()
    assert r1 not in st["ready"] and r1 not in st["pending"] and r2 in st["pending"]
    st["procs"] = []
    bot_pool.stop()
    print("  OK botpool")


def test_click_roundtrip_all_aspect_ratios():
    rects = [pygame.Rect(0, 0, 60, 30), pygame.Rect(10, 10, 200, 44), pygame.Rect(683, 384, 120, 30),
             pygame.Rect(BASE_W - 60, BASE_H - 40, 60, 40), pygame.Rect(1300, 0, 66, 20)]
    for (w, h) in SIZES:
        pygame.display.set_mode((w, h))
        CANVAS.attach(pygame.display.get_surface())
        for r in rects:
            if r.w < 5 or r.h < 5:
                continue
            # 버튼 안쪽(가장자리에서 2px 안)의 점은 어떤 배율/종횡비에서도 물리 픽셀 -> 논리 변환 후 같은 버튼 안이어야 함
            inner = r.inflate(-4, -4)
            pts = [(inner.x, inner.y), (inner.right - 1, inner.bottom - 1), (inner.centerx, inner.centery),
                   (inner.x, inner.bottom - 1), (inner.right - 1, inner.y)]
            for lx, ly in pts:
                px = (CANVAS.X(lx) + CANVAS.X(lx + 1)) // 2
                py = (CANVAS.Y(ly) + CANVAS.Y(ly + 1)) // 2
                back = CANVAS.to_logical((px, py))
                assert r.collidepoint(back), f"{w}x{h}: {(lx, ly)} -> {back} not in {r}"
        # 레터박스(검은 여백) 클릭은 논리 영역 밖이어야 함
        if CANVAS.ox > 2:
            lx, _ = CANVAS.to_logical((int(CANVAS.ox) - 2, h // 2))
            assert lx < 0, f"{w}x{h}: 왼쪽 여백이 안쪽으로 인정됨 ({lx})"
        if CANVAS.oy > 2:
            _, ly = CANVAS.to_logical((w // 2, int(CANVAS.oy) - 2))
            assert ly < 0, f"{w}x{h}: 위쪽 여백이 안쪽으로 인정됨 ({ly})"
    print("  OK roundtrip")


def test_canvas_helpers():
    pygame.display.set_mode((3840, 2160))
    CANVAS.attach(pygame.display.get_surface())
    r_float = CANVAS.rect((10.6, 20.4, 30.5, 8.7))
    r_int = CANVAS.rect(pygame.Rect(10, 20, 30, 8))
    assert r_float.x != r_int.x or r_float.w != r_int.w, "실수 좌표가 잘렸음"
    try:
        CANVAS.blit(pygame.Surface((4, 4)), (0, 0), area=pygame.Rect(0, 0, 2, 2))
        assert False, "area는 조용히 무시되면 안 됨"
    except NotImplementedError:
        pass
    stale = HiSurf((40, 40), pygame.SRCALPHA, 1.0)            # 배율이 다를 때 만든 서피스도 오류 없이 현재 배율로 그려짐
    CANVAS.blit(stale, (5, 5))
    # redirect 중에도 마우스 좌표 변환은 실제 창 기준
    p0 = CANVAS.to_logical((500, 400))
    with CANVAS.redirect(pygame.Surface((100, 100)), 123, 77):
        assert CANVAS.to_logical((500, 400)) == p0
    print("  OK canvas")


def _app():
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    return app


def test_long_frame_and_overlay_click():
    app = _app()
    app.start_game(mode="SOLO", total_players=9)
    for _ in range(30):
        app._tick_game(1 / 60)
    assert app.MAX_FRAME_DT <= 0.25
    app.key_left_down = True
    app._long_frame_grace_until = 0.0                         # 시작 직후 유예(느린 첫 장면 준비용)가 지난 뒤
    app._on_long_frame(2.0)                                   # 창 드래그로 멈췄다 돌아옴
    assert app.is_paused and not app.key_left_down
    # 일시정지 중에는 미니 보드 클릭이 조준을 바꾸지 않음
    app._tick_game(1 / 60)
    other = next(pid for pid in app.match.players if pid != app.match.local_player_id)
    rect = app.renderer.mini_board_rects.get(other)
    before = app.match.local_manual_target_id
    if rect is not None:
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(rect.centerx, rect.centery))
        app._handle_game_event(ev)
        assert app.match.local_manual_target_id == before, "일시정지 중 클릭이 오버레이를 뚫음"
    assert app.match.set_manual_target(other) is True and app.match.set_manual_target("nobody") is False
    print("  OK long-frame/overlay")


def test_reserved_keys_not_rebindable():
    app = _app()
    app.state = "SETTINGS"
    app.previous_state = "MENU"
    before = list(app.settings.get_action_keys("hold"))
    for key in (pygame.K_m, pygame.K_F11):
        app.rebinding_action = "hold"
        app._handle_settings_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
        assert app.rebinding_action is None
        assert key not in app.settings.get_action_keys("hold")
    assert before == list(app.settings.get_action_keys("hold"))
    print("  OK reserved keys")


def test_countdown_records_held_keys():
    app = _app()
    app.start_game(mode="SOLO", total_players=9)
    app._tick_game(1 / 60)
    app.match.countdown_until = time.time() + 3.0              # 카운트다운 중인 상황을 만듦
    app.key_left_down = False
    key = app.settings.get_action_keys("move_left")[0]
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
    assert app.key_left_down and app.h_dir == -1
    px = app.match.local_engine.current_piece_x if hasattr(app.match.local_engine, "current_piece_x") else None
    if px is not None:
        assert app.match.local_engine.current_piece_x == px
    print("  OK countdown keys")


def test_shake_draws_cards_without_layer_rebuild():
    app = _app()
    app.start_game(mode="SOLO", total_players=40)
    for size in ((1920, 1080), (1366, 768)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        app.match.screen_shake = 6.0
        app.renderer.render(app.match)
        assert app.renderer._shaking
        ids = {k: id(v[2]) for k, v in app.renderer._card_layers.items()}
        for _ in range(8):
            app.renderer.render(app.match)               # 흔들림 중에는 레이어를 새로 만들지 않고 직접 그림
        assert {k: id(v[2]) for k, v in app.renderer._card_layers.items()} == ids, f"{size}: 흔들림 중 카드 레이어가 다시 만들어짐"
        app.match.screen_shake = 0.0
        app.renderer.render(app.match)
        assert not app.renderer._shaking
    print("  OK shake")


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
        print("[ALL OPUS REVIEW 2 TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
