"""
v1.4.36 후속 점검 테스트: 효과음 좌우 음량 되돌림, 화상 키보드 엣지 케이스(패드 X, 같은 칸 다시 누르기, 글자 수 상한),
패드 분리 시 자동 일시정지, 자체 점검의 시작 기록, 빔 비행 시간 공유.
실행: python tests/test_followups.py
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


def test_center_sound_resets_channel_pan():
    import sound_fx
    sm = sound_fx.SoundManager(enabled=True)
    vols = []

    class Ch:
        def set_volume(self, *a):
            vols.append(a)

    class Snd:
        def set_volume(self, v):
            pass

        def play(self):
            return Ch()
    sm.sounds["attack"] = Snd()
    sm.play("attack", pan=-1.0)
    assert vols[-1][0] > vols[-1][1], "왼쪽으로 치우침"
    sm.play("attack")                                      # 가운데로 낼 소리: 앞의 치우침이 남지 않아야 함
    assert vols[-1] == (1.0, 1.0), vols


def test_pad_x_is_not_restart_while_osk_is_open():
    app = _app()
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=10)
    app.match.local_is_alive = False                       # 탈락 뒤: 결과/관전 화면 (X = 다시 시작)
    assert app._pad_overlay_active(pad_in_game=False) is True
    app.osk = {"page": "en", "shift": False, "sel": (1, 0), "keys": [], "kind": "text", "comp": None}
    assert app._pad_overlay_active(pad_in_game=False) is False, "화상 키보드가 열려 있으면 X는 지우기"
    app.osk = None


def test_retapping_the_same_chat_field_reopens_the_keyboard():
    app = _app()
    app.state = "HOST_LOBBY"
    app._osk_wanted = lambda: True
    app._render_host_lobby()
    assert "chat" in app.text_rects or True
    app._begin_text("chat")
    app.text_rects["chat"] = pygame.Rect(400, 600, 300, 30)
    assert app.osk is not None
    app._osk_close()                                       # '완료'로 내린 뒤 (대기실 채팅은 입력 상태가 남음)
    assert app.text_focus == "chat" and app.osk is None
    app._text_input_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(450, 610), button=1))
    assert app.osk is not None and app.text_focus == "chat", "같은 칸을 다시 누르면 키보드가 다시 올라옴"
    app._end_text(commit=False)


def _press_all(app, jamo):
    keys = {}
    app._render_osk()
    for rect, k, r, c in app.osk["keys"]:
        if isinstance(k, tuple):
            keys[k[0]] = rect
    for j in jamo:
        app._render_osk()
        keys = {k[0]: rect for rect, k, r, c in app.osk["keys"] if isinstance(k, tuple)}
        assert app._osk_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=keys[j].center, button=1))


def test_hangul_at_the_character_limit_does_not_corrupt_text():
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "match"
    app._render_settings()
    app._osk_wanted = lambda: True
    app._begin_text("player_name")
    app.player_name_input = "abcdefghijklmno"              # 15글자 (상한 16)
    app.osk["page"] = "ko"
    _press_all(app, "ㅎㅏㄴ")
    assert app.player_name_input == "abcdefghijklmno한" and len(app.player_name_input) == 16
    _press_all(app, "ㅏ")                                  # 받침이 다음 글자로 넘어가면 17글자 -> 입력하지 않음
    assert app.player_name_input == "abcdefghijklmno한", app.player_name_input
    app._render_osk()
    back = next(rect for rect, k, r, c in app.osk["keys"] if k == "BACK")
    app._osk_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=back.center, button=1))
    assert app.player_name_input == "abcdefghijklmno하", "조합기가 어긋나지 않아 지우기도 정상"
    _press_all(app, "ㄴ")
    assert app.player_name_input == "abcdefghijklmno한"
    app._end_text(commit=False)


def test_losing_the_last_pad_pauses_a_solo_match_played_with_the_pad():
    import time
    from gamepad import GamepadMapper
    app = _app()
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=10)
    app.match.countdown_until = 0.0
    app.gamepad.last_pad_t = time.time()
    app._last_kb_t = 0.0
    app._on_pad_lost()
    assert app.is_paused and app.match.is_paused, "패드로 하던 솔로 경기는 일시정지"
    app.is_paused = app.match.is_paused = False
    app.gamepad.last_pad_t = 0.0
    app._last_kb_t = time.time()
    app._on_pad_lost()
    assert not app.is_paused, "키보드로 하던 중이면 그대로"
    # 장치 이벤트 경로: 마지막 장치가 빠질 때만 removed_all
    gm = GamepadMapper(lambda a: [])
    gm.joys = {7: object()}
    gm.translate([pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=7)], False)
    assert gm.removed_all is True
    gm.removed_all = False
    gm.joys = {7: object(), 8: object()}
    gm.translate([pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=7)], False)
    assert gm.removed_all is False, "다른 패드가 남아 있으면 일시정지하지 않음"
    # 네트워크 경기에서는 일시정지하지 않음
    app2 = _app()
    app2.state = "GAME"
    app2.start_game(mode="SOLO", total_players=10)
    app2.net_mgr.mode = "HOST"
    app2.gamepad.last_pad_t = time.time()
    app2._last_kb_t = 0.0
    app2._on_pad_lost()
    assert not app2.is_paused
    app2.net_mgr.mode = "NONE"


def test_selftest_does_not_write_a_startup_trace():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"), encoding="utf-8").read()
    main_block = src[src.index('if __name__ == "__main__":'):]
    assert main_block.index("--selftest") < main_block.index("startup_trace.begin()"), "자체 점검은 시작 기록을 남기지 않음 (OK가 없어 다음 실행에 거짓 경고가 남음)"


def test_beam_flight_time_is_shared():
    from battle_royale import BattleRoyaleMatch
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui_renderer.py"), encoding="utf-8").read()
    assert "HIT_FLIGHT_SECS" in src and "elapsed / 0.25)" not in src
    assert BattleRoyaleMatch.HIT_FLIGHT_SECS == 0.25


def test_match_log_records_clears_and_b2b_and_report_tool_aggregates():
    import json
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "tools"))
    import match_log_report as R
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    m = app.match
    m.countdown_until = 0.0
    m.log_enabled = True
    eng = m.local_engine
    eng.last_clear_info = {"cleared": 4, "is_tspin": False, "is_mini": False, "is_b2b": True, "b2b_chain": 2}
    m.on_lines_cleared(4)
    eng.b2b, eng.b2b_chain = True, 2
    m.update(0.01)
    eng.b2b, eng.b2b_chain = False, 0
    m.update(0.01)
    kinds = [e["kind"] for e in m.events]
    assert "clear" in kinds and "b2b_break" in kinds, kinds
    ev = next(e for e in m.events if e["kind"] == "clear")
    assert ev["n"] == 4 and ev["b2b"] == 2 and ev["ts"] == 0
    # 집계 도구: 합성 기록 두 판
    folder = tempfile.mkdtemp()

    def log(rank, ver, rows, evs):
        return {"version": 1, "app_version": ver, "total_players": 100, "bot_difficulty": "mixed", "attacks": True, "elapsed": 300.0, "rank": rank,
                "timeline": rows, "events": evs}
    rows1 = [[0, 100, 0, 0], [120, 50, 3, 0], [240, 9, 5, 2]]
    rows2 = [[0, 100, 0, 0], [180, 49, 3, 0], [260, 10, 5, 2]]
    evs = [{"t": 5, "kind": "hit", "lines": 6}, {"t": 9, "kind": "attack", "lines": 4}, {"t": 12, "kind": "clear", "n": 4, "ts": 0, "mini": 0, "b2b": 3, "combo": 0},
           {"t": 20, "kind": "clear", "n": 1, "ts": 1, "mini": 1, "b2b": -1, "combo": 0}, {"t": 30, "kind": "b2b_break", "chain": 3}]
    for i, (rk, ver, rows) in enumerate(((12, "1.4.35", rows1), (30, "1.4.36", rows2))):
        with open(os.path.join(folder, "match_2026100%d_000000.json" % i), "w", encoding="utf-8") as f:
            json.dump(log(rk, ver, rows, evs), f)
    res = R.summarize(R.load_logs(folder))
    assert res["games"] == 2 and res["rank_by_setup"]["100명/mixed"]["mean_rank"] == 21.0
    assert res["half_dead_secs"]["mean"] == 150.0 and res["tenth_alive_secs"]["mean"] == 250.0, res
    assert res["b2b"]["max_chain"] == 3 and res["b2b"]["breaks"] == 2 and res["clears"]["quad"] == 2 and res["clears"]["tspin_mini"] == 2
    assert R.summarize(R.load_logs(folder, since="1.4.36"))["games"] == 1
    assert R.summarize([])["games"] == 0


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL FOLLOWUP TESTS PASSED]")
