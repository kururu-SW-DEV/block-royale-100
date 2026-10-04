"""
2026-10-03 Opus 게임성·UI 검토 반영 회귀 테스트: 조준 칩 클릭/수동 해제, 일시정지 다시 시작, 결과 기본 포커스, 첫 경험 팁,
대기실 규칙 전파와 참가자 난이도 기록, 호스트 이탈 확인, 규칙 카드, 키 안내 바 옵션, 경고음 음량, 180도 회전, 관전 배속,
색약 HUD, 전광판 내 소식 우선.
실행: python test_opus_review3.py
"""
import os
import sys
import time
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
    return app


def _key(app, k, mod=0):
    app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))


def test_chip_click_and_manual_release():
    app = _app()
    app.start_game(mode="SOLO", total_players=12)
    app.match.countdown_until = 0.0
    for _ in range(5):
        app._tick_game(1 / 60)
    other = next(pid for pid in app.match.players if pid != app.match.local_player_id)
    assert app.match.set_manual_target(other)
    rect = app.renderer.target_chip_rects["BADGES"]
    app._handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(rect.centerx, rect.centery)))
    assert app.match.local_target_mode == "BADGES" and app.match.local_manual_target_id is None
    # 같은 카드를 다시 누르거나 우클릭하면 수동 해제(모드는 유지)
    app.match.set_manual_target(other)
    app._tick_game(1 / 60)
    r = app.renderer.mini_board_rects.get(other)
    if r is not None:
        app._handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(r.centerx, r.centery)))
        assert app.match.local_manual_target_id is None, "같은 카드를 다시 누르면 해제"
    app.match.set_manual_target(other)
    app._handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(5, 5)))
    assert app.match.local_manual_target_id is None and app.match.local_target_mode == "BADGES"
    print("  OK chips")


def test_pause_restart_and_result_focus():
    app = _app()
    app.start_game(mode="SOLO", total_players=6)
    app.match.countdown_until = 0.0
    app._tick_game(1 / 60)
    app.is_paused = True
    app.match.is_paused = True
    app._tick_game(1 / 60)
    assert app.renderer.pause_restart_btn is not None
    old = app.match
    _key(app, pygame.K_r)                                   # 일시정지 중 R: 확인 창
    assert app.modal is not None and any(b[0] == "restart_ok" for b in app.modal["buttons"])
    app._modal_choose("restart_ok")
    assert app.match is not old and not app.is_paused, "다시 시작하면 새 경기"
    assert app.renderer.result_focus_id == "restart", "결과 화면 기본 포커스는 재도전"
    # ↑↓가 4개 항목을 순환
    app.is_paused = True
    app.match.is_paused = True
    app.renderer.pause_focus = 0
    for _ in range(4):
        _key(app, pygame.K_DOWN)
    assert app.renderer.pause_focus == 0
    print("  OK pause restart")


def test_first_experience_tips():
    app = _app()
    app.settings.set("tips_seen", [], autosave=False)
    app.settings.set("tips_replay", False, autosave=False)
    app.stats_mgr.data["total_games"] = 0                   # 사용자의 실제 전적 파일과 무관하게 초보자 상태에서 시작
    app.start_game(mode="SOLO", total_players=12)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    m.get_attackers_count_for = lambda pid: 0                # 봇이 나를 노리는 우연을 배제
    m.local_ko_count = 1
    app._check_tips()
    tips = [f for f in m.floating_texts if f["category"] == "tip"]
    assert tips and "ko" in app.settings.get("tips_seen"), "첫 K.O. 팁"
    app._check_tips()
    assert len([f for f in m.floating_texts if f["category"] == "tip"]) == 1, "한 번에 하나, 같은 팁은 반복하지 않음"
    # 숙련자(10판 이상)에게는 보이지 않고, 다시 보기를 켜면 보임
    app.settings.set("tips_seen", [], autosave=False)
    m.floating_texts.clear()
    app.stats_mgr.data["total_games"] = 50
    app._check_tips()
    assert not [f for f in m.floating_texts if f["category"] == "tip"]
    app._settings_activate("tips_replay")
    assert app.settings.get("tips_replay") and app.settings.get("tips_seen") == []
    app._check_tips()
    assert [f for f in m.floating_texts if f["category"] == "tip"]
    app.renderer.render(m)                                   # 팁이 떠 있는 프레임도 예외 없이 그려짐
    print("  OK tips")


def test_lobby_rules_propagate_and_client_difficulty():
    from network import NetworkManager
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=20271, max_players=10)
    try:
        client.start_client("127.0.0.1", 20271, "Guest")
        t0 = time.time()
        while not client.connected and time.time() - t0 < 3:
            client.client_retry_join()
            time.sleep(0.1)
        assert client.connected
        host.room_settings.update({"target": 7, "diff": "master", "mode": "survival"})
        host.host_broadcast_roster()
        t0 = time.time()
        while client.room_rules.get("diff") != "master" and time.time() - t0 < 3:
            time.sleep(0.05)
        assert client.room_rules == {"diff": "master", "mode": "survival"} and client.roster_target == 7, client.room_rules
        host.room_settings["diff"] = "bogus"
        host.host_broadcast_roster()
        time.sleep(0.3)
        assert "diff" not in client.room_rules, "알 수 없는 난이도는 무시"
        host.room_settings["diff"] = "hard"
        host.host_send_start_game([{"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": client.my_player_id, "name": "G", "is_ai": False}], attacks_enabled=False)
        t0 = time.time()
        while not client.game_started and time.time() - t0 < 3:
            time.sleep(0.05)
        assert client.match_difficulty == "hard" and client.match_attacks is False
    finally:
        client.stop()
        host.stop()
    # 참가자의 경기는 호스트가 정한 난이도로 기록됨 (자기 설정이 아니라)
    app = _app()
    app.bot_difficulty = "easy"
    app.net_mgr.mode = "CLIENT"
    app.net_mgr.match_difficulty = "master"
    app.net_mgr.my_player_id = "NET_P1"
    app.start_game(mode="CLIENT", total_players=4, initial_players=[
        {"id": "HOST_P1", "name": "H", "is_ai": False}, {"id": "NET_P1", "name": "G", "is_ai": False},
        {"id": "BOT_01", "name": "b1", "is_ai": True}, {"id": "BOT_02", "name": "b2", "is_ai": True}])
    assert app.match.bot_difficulty == "master"
    app.net_mgr.mode = "NONE"
    print("  OK lobby rules")


def test_host_leave_confirm_and_lobby_return_grace():
    app = _app()
    app.state = "HOST_LOBBY"
    app.net_mgr.mode = "HOST"
    app.net_mgr.clients[("127.0.0.1", 1)] = {"id": "NET_P1", "name": "x", "last_seen": time.time(), "color": 0}
    try:
        _key(app, pygame.K_ESCAPE)
        assert app.modal is not None and any(b[0] == "close_room" for b in app.modal["buttons"]) and app.state == "HOST_LOBBY"
        app.modal = None
        app.net_mgr.clients.clear()
        app.net_mgr.mode = "NONE"
    finally:
        app.net_mgr.clients.clear()
        app.net_mgr.mode = "NONE"
    # 경기가 끝난 뒤 방장이 대기실로 돌아가도 참가자는 10초 동안 순위표를 볼 수 있음
    from network import NetworkManager
    app.start_game(mode="SOLO", total_players=4)
    app.match.match_finished = True
    fake = NetworkManager()
    fake.mode = "CLIENT"
    fake.lobby_return = True
    real, app.net_mgr = app.net_mgr, fake
    try:
        app._tick_game(1 / 60)
        assert app.state == "GAME" and app.renderer.lobby_return_left > 5.0
        app.renderer.render(app.match)
    finally:
        app.net_mgr = real
    print("  OK host leave")


def test_rules_card_uses_config_values():
    import config
    from screens.rules import rules_card_data, rules_card_notes
    data = dict(rules_card_data())
    attacks = dict(data["공격 줄 수"])
    assert attacks["쿼드(4줄)"] == f"{config.GARBAGE_ATTACK_TABLE[4]}줄"
    assert attacks["퍼펙트 클리어"] == f"+{config.PERFECT_CLEAR_ATTACK}줄"
    badges = dict(data["K.O. 배지 (공격력 증폭)"])
    assert badges["K.O. 16개"] == "공격력 +100%"
    assert any("차징" in n for n in rules_card_notes())
    app = _app()
    app.state = "MENU"
    _key(app, pygame.K_F1)
    assert app.rules_open
    app._render_rules()
    app._handle_rules_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a"))
    assert not app.rules_open
    # 솔로 경기 중 F1은 경기를 멈춤
    app.start_game(mode="SOLO", total_players=6)
    app.match.countdown_until = 0.0
    _key(app, pygame.K_F1)
    assert app.rules_open and app.is_paused
    app.rules_open = False
    print("  OK rules card")


def test_key_hint_option_warn_volume_and_defaults():
    app = _app()
    app.settings.set("key_hints", "always", autosave=False)
    assert app._build_key_hints()
    app.settings.set("key_hints", "off", autosave=False)
    assert app._build_key_hints() == []
    app.settings.set("key_hints", "novice", autosave=False)
    app.stats_mgr.data["total_games"] = 3
    assert app._build_key_hints()
    app.stats_mgr.data["total_games"] = 30
    assert app._build_key_hints() == []
    assert app.settings.get("key_hints") == "novice"
    ok, _ = __import__("settings_manager")._valid_setting("key_hints", "bogus")
    assert not ok
    # 경고음 음량: 0이면 경고음만 안 남, 효과음은 그대로
    sm = app.sound_mgr
    played = []

    class FakeSnd:
        def __init__(self, n): self.n = n
        def set_volume(self, v): played.append((self.n, round(v, 2)))
        def play(self): pass
    sm.sounds["hit_2"] = FakeSnd("hit_2")
    sm.sounds["rotate"] = FakeSnd("rotate")
    sm.enabled = sm.sfx_enabled = True
    sm.set_sfx_volume(0.8)
    sm.set_warn_scale(0.5)
    sm.play("hit_2"); sm.play("rotate")
    assert ("hit_2", 0.4) in played and ("rotate", 0.8) in played, played
    sm.set_warn_scale(0.0)
    played.clear()
    sm.play("hit_2"); sm.play("rotate")
    assert played == [("rotate", 0.8)], played
    sm.set_warn_scale(1.0)
    # 첫 실행 기본 창 크기는 자동
    from settings_manager import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["resolution"] == "auto"
    print("  OK hints/warn")


def test_rotate_180_and_key_card():
    from block_engine import BlockEngine
    e = BlockEngine(seed=3)
    for piece in "IJLSTZ":
        e.current_piece, e.current_rot, e.current_x, e.current_y = piece, 0, 3, 5
        assert e.rotate180() and e.current_rot == 2, piece
        assert e.rotate180() and e.current_rot == 0
    e.current_piece = "O"
    assert not e.rotate180()
    # 벽에 붙은 I도 킥으로 돌아감 / 막히면 False
    e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 1, -1, 5
    r = e.rotate180()
    assert r and not e._check_collision(e.current_x, e.current_y, e.current_rot)
    app = _app()
    assert app.settings.get_action_keys("rotate_180") == [], "기본은 비어 있음"
    app.start_game(mode="SOLO", total_players=4)
    app.match.countdown_until = 0.0
    before = app.match.local_engine.current_rot
    _key(app, pygame.K_e)
    assert app.match.local_engine.current_rot == before, "키를 지정하기 전에는 아무 일도 없음"
    app.settings.set_action_key("rotate_180", pygame.K_e)
    app.match.local_engine.current_piece = "T"
    app.match.local_engine.current_rot = 0
    _key(app, pygame.K_e)
    assert app.match.local_engine.current_rot == 2
    assert any(h[1] == "180°" for h in app._build_key_hints())
    print("  OK rotate180")


def test_spectate_speed_and_colorblind_and_ticker():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    m.local_is_alive = False
    m.local_engine.game_over = True
    _key(app, pygame.K_f)
    assert m.spectate_speed == 2
    _key(app, pygame.K_f); _key(app, pygame.K_f)
    assert m.spectate_speed == 1
    _key(app, pygame.K_f)
    t0 = m.elapsed
    app._tick_game(0.05)
    assert m.elapsed - t0 >= 0.09, "×2 배속이면 같은 프레임에 두 번 진행"
    # 색약 모드: 받을 공격 게이지 색이 파랑->주황 계열 (초록/빨강 아님)
    import ui_renderer as U
    import config
    config.apply_color_mode("colorblind")
    try:
        lo, hi = U.UIRenderer._garbage_level_color(0), U.UIRenderer._garbage_level_color(7)
        assert lo[2] > lo[1] > 0 and hi[0] > 200 and hi[2] < 100, (lo, hi)
        app.renderer.render(m)
    finally:
        config.apply_color_mode("normal")
    # 전광판: 대기열이 밀려도 내 소식(mine)은 남의 일반 소식보다 나중에 버려짐
    m2 = app.match
    m2.commentary.clear()
    m2.add_commentary("A 일반", mine=False)
    m2.add_commentary("나의 쿼드", mine=True)
    for i in range(6):
        m2.add_commentary(f"남의 소식 {i}")
    app.renderer.render(m2)
    pend = app.renderer._led_state["pending"]
    assert any(e.get("mine") for e in pend) or any("나의 쿼드" in str(e["text"]) for e in app.renderer._led_state.get("items", []))
    print("  OK spectate/colorblind/ticker")


def test_weekly_mutator_rules():
    import config
    import datetime
    key = config.week_key()
    assert len(key) == 7 and key[4] == "W"
    seen = {config.weekly_mutator(datetime.date(2026, 1, 1) + datetime.timedelta(weeks=i))["id"] for i in range(8)}
    assert seen == {m["id"] for m in config.WEEKLY_MUTATORS}, "주마다 돌아가며 네 규칙이 모두 나옴"
    assert config.weekly_seed("2026W40") == 202640
    app = _app()
    app.start_game(mode="SOLO", weekly=("2026W40", "elite"))
    m = app.match
    assert m.weekly == "2026W40" and m.total_players == 30 and m.bot_difficulty == "hard" and m.mutator["id"] == "elite"
    app.start_game(mode="SOLO", weekly=("2026W41", "perfect"))
    assert app.match.local_engine.perfect_clear_attack == 20
    app.start_game(mode="SOLO", weekly=("2026W42", "rush"))
    assert app.match.ESCALATION_START == 120.0 and type(app.match).ESCALATION_START == 300.0, "클래스 값은 그대로, 인스턴스만 바뀜"
    app.start_game(mode="SOLO", weekly=("2026W43", "fog"))
    app.renderer.render(app.match)
    assert app.renderer.next_visible == 1
    app.start_game(mode="SOLO", total_players=6)
    app.renderer.render(app.match)
    assert app.renderer.next_visible == 5, "변형 규칙이 다음 일반 경기에 남지 않음"
    app.start_game(mode="SOLO", weekly=("2026W43", "fog"))
    q1 = list(app.match.local_engine.next_queue)
    app.start_game(mode="SOLO", weekly=("2026W43", "fog"))
    assert list(app.match.local_engine.next_queue) == q1, "같은 주는 같은 블록 순서"
    app._restart_after_match()                              # 재도전도 같은 규칙
    assert app.match.mutator["id"] == "fog"
    app.state = "MENU"
    _key(app, pygame.K_w)
    assert app.state == "GAME" and app.match.weekly
    print("  OK weekly")


def test_stats_ghost_rival_weekly_unlocks():
    import json
    import stats_manager as SM
    d = tempfile.mkdtemp()
    st = SM.StatsManager(os.path.join(d, "s.json"))
    st.record_match(20, 100, 1, 10, 2, 100, daily="20261003")
    st.record_match(8, 100, 2, 10, 2, 150, daily="20261003")
    st.record_match(30, 100, 0, 10, 2, 300, daily="20261003")
    g = st.daily_ghost("20261003")
    assert g == {"rank": 8, "secs": 150, "tries": 3}, g
    assert st.daily_ghost("20250101") is None
    st.record_match(12, 30, 1, 5, 1, 90, weekly="2026W40")
    st.record_match(9, 30, 1, 5, 1, 90, weekly="2026W40")
    assert st.weekly_best("2026W40") == 9
    # 라이벌: 같은 봇에게 2번 탈락해야 라이벌, 복수하면 초기화 + 업적
    st.record_match(10, 100, 0, 5, 1, 90, killer="BOT_07")
    assert st.rival_id() is None
    st.record_match(10, 100, 0, 5, 1, 90, killer="BOT_07")
    assert st.rival_id() == "BOT_07"
    st.record_match(10, 100, 0, 5, 1, 90, killer="someone")      # 봇이 아니면 무시
    assert st.rival_id() == "BOT_07"
    st.record_match(3, 100, 1, 5, 1, 90, revenge=True)
    assert st.rival_id() is None and st.data["rivals"]["revenges"] == 1 and "revenge" in st.data["achievements"]
    st.save()
    st2 = SM.StatsManager(st.filepath)
    assert st2.daily_ghost("20261003") == g and st2.weekly_best("2026W40") == 9 and st2.data["rivals"]["revenges"] == 1
    raw = json.load(open(st.filepath, encoding="utf-8"))
    raw["daily_meta"] = {"bad": 1, "20261004": {"rank": "x", "secs": 1, "tries": 1}, "20261005": {"rank": 3, "secs": 10, "tries": 1}}
    raw["weekly"] = {"x": 1, "2026W41": -5, "2026W42": 4}
    raw["rivals"] = {"losses": {"BOT_01": 3, "cheat": 9, "BOT_02": -1}, "revenges": "many"}
    json.dump(raw, open(st.filepath, "w", encoding="utf-8"))
    st3 = SM.StatsManager(st.filepath)
    assert list(st3.data["daily_meta"]) == ["20261005"] and st3.data["weekly"] == {"2026W42": 4}
    assert st3.data["rivals"] == {"losses": {"BOT_01": 3}, "revenges": 0}, st3.data["rivals"]
    # 해금 스킨
    fresh = SM.StatsManager(os.path.join(d, "f.json"))
    assert SM.unlocked_skin_ids(fresh.data) == ["classic", "neon", "flat", "jelly"]
    assert {s for s, _ in SM.locked_skin_hints(fresh.data)} == {"pixel", "glass", "starlight", "ember", "prism"}
    fresh.record_match(1, 100, 1, 5, 1, 90)                      # 우승 -> glass
    assert "glass" in SM.unlocked_skin_ids(fresh.data)
    from settings_manager import SettingsManager
    sm = SettingsManager(os.path.join(d, "set.json"))
    sm.set("block_skin", "jelly")
    assert "pixel" in SM.unlocked_skin_ids(fresh.data), "우승 한 판으로 업적 3개(첫 K.O./로열 빅토리/백인의 왕)가 열려 pixel도 해금"
    assert sm.cycle_block_skin(1, available=["classic", "jelly", "glass"]) == "glass", "잠긴 스킨은 건너뜀"
    print("  OK stats ghost/rival/unlock")


def test_rival_marker_defeat_and_ghost_title():
    app = _app()
    app.stats_mgr.data["rivals"] = {"losses": {"BOT_03": 4}, "revenges": 0}
    app.start_game(mode="SOLO", total_players=12)
    m = app.match
    assert m.rival_id == "BOT_03" and "BOT_03" in m.players
    m.countdown_until = 0.0
    for _ in range(3):
        app._tick_game(1 / 60)
    app.renderer.render(m)                                    # 라이벌 표식이 있는 프레임도 예외 없이
    m._eliminate_player("BOT_03", killer_id=m.local_player_id)
    assert m.rival_defeated and any("복수" in f["text"] for f in m.floating_texts)
    # 오늘의 도전 고스트: 생존자 칸 제목에 기록과 비교
    app.stats_mgr.data.setdefault("daily_meta", {})["20261003"] = {"rank": 5, "secs": 200, "tries": 2}
    app.start_game(mode="SOLO", daily="20261003")
    m = app.match
    assert m.ghost["rank"] == 5 and "기록까지" in app.renderer._survivor_title(m)
    m.elapsed = 250.0
    assert "경신" in app.renderer._survivor_title(m)
    app.start_game(mode="SOLO", daily="20991231")
    assert app.match.ghost is None and "첫 시도" in app.renderer._survivor_title(app.match)
    print("  OK rival/ghost")


def test_practice_drill():
    app = _app()
    app.settings.set("drill_best", 0, autosave=False)
    app.start_game(mode="SOLO", practice=True)
    m = app.match
    m.countdown_until = 0.0
    assert not m.drill_on
    _key(app, pygame.K_v)
    assert m.drill_on
    m.elapsed = m.drill_t0 + 9.0
    m._drill_tick()
    assert m.local_engine.incoming_garbage == 2, m.local_engine.incoming_garbage       # 1단계: 2줄
    m.elapsed = m.drill_t0 + 70.0
    assert m.drill_level() == 2 and m.DRILL_LINES[2] == 4 and m.drill_interval() == 7.0
    m.drill_next = 0.0
    m.local_engine.incoming_garbage = 0
    m._drill_tick()
    assert m.local_engine.incoming_garbage == 4
    # 죽으면 버틴 시간 기록 후 새 판으로 이어서 계속
    m.drill_t0 = m.elapsed - 40.0
    m.local_engine.game_over = True
    m.update(0.0)
    assert m.drill_best >= 40 and m.drill_on and not m.local_engine.game_over
    app._tick_game(1 / 60)
    assert app.settings.get("drill_best") >= 40, "최고 기록이 설정에 반영됨"
    app.renderer.render(m)
    _key(app, pygame.K_v)
    assert not m.drill_on
    print("  OK drill")


def test_trend_points_and_screen():
    from screens.records import RecordsMixin
    recent = [{"rank": 1, "total_players": 100, "won": True}, {"rank": 100, "total_players": 100}, {"rank": 5, "total_players": 10}]
    pts = RecordsMixin.trend_points(recent)
    assert pts[0][0] == 1.0 and pts[1][0] == 0.0 and abs(pts[2][0] - (1 - 4 / 9)) < 1e-9 and pts[0][1] is True
    last, prev = RecordsMixin.trend_summary(pts)
    assert prev is None and abs(last - sum(p[0] for p in pts) / 3) < 1e-9
    assert RecordsMixin.trend_summary([]) == (None, None)
    many = RecordsMixin.trend_points([{"rank": 50, "total_players": 100}] * 10 + [{"rank": 1, "total_players": 100}] * 10)
    last, prev = RecordsMixin.trend_summary(many)
    assert last == 1.0 and prev < 0.6
    app = _app()
    app.state = "RECORDS"
    app.records_mode = "trend"
    app._render_records()                                      # 경기가 적어도(안내 화면) 예외 없이
    for i in range(6):
        app.stats_mgr.record_match(10 + i, 50, 1, 5, 1, 60)
    app._render_records()
    _key(app, pygame.K_RIGHT)
    assert app.records_mode == "score", "추이 다음은 점수표 탭"
    _key(app, pygame.K_RIGHT)
    assert app.records_mode == "achv"
    print("  OK trend")


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
        print("[ALL OPUS REVIEW 3 TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
