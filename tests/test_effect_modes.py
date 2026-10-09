"""
경기 방식별 효과 시나리오 테스트: 솔로 / 서바이벌(공격 없음) / 팀전 / 연습 / 오늘의 도전 / 방장(HOST) / 참가자(CLIENT) 경기에서
받는 공격(날아오는 중 -> 도착), 내가 보내는 공격 누적, B2B 끊김, 줄 삭제 와이프, 탈락 뒤 관전까지 수백 프레임 돌려
예외가 없고 효과 상태가 서로 어긋나지 않는지(날아오는 줄 수, 대기 중 피격, 누적 카운터 등) 확인한다.
(v1.4.33의 효과들은 update/render 함수 안에 덧붙여져 있어, 방식마다 따로 확인하지 않으면 한 방식에서만 깨질 수 있음)
실행: python tests/test_effect_modes.py
"""
import os
import random
import sys
import tempfile
import time

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


def _start(app, kind):
    """kind별로 경기를 시작하고 (match, 로컬 id) 반환"""
    app.settings.set("rule_team", False)
    if kind == "survival":
        app.settings.set("game_mode", "survival")
        app.start_game(mode="SOLO", total_players=12)
    elif kind == "team":
        app.settings.set("rule_team", True)
        app.start_game(mode="SOLO", total_players=12)
    elif kind == "practice":
        app.start_game(mode="SOLO", practice=True)
    elif kind == "daily":
        app.start_game(mode="SOLO", daily="20261003")
    elif kind == "host":
        plist = [{"id": "HOST_P1", "name": "방장", "is_ai": False}, {"id": "NET_X", "name": "친구", "is_ai": False}] \
            + [{"id": f"BOT_{i:02d}", "name": f"봇{i}", "is_ai": True} for i in range(1, 11)]
        app.start_game(mode="HOST", total_players=12, initial_players=plist)
    elif kind == "client":
        app.net_mgr.my_player_id = "NET_P"
        plist = [{"id": "HOST_P1", "name": "방장", "is_ai": False}, {"id": "NET_P", "name": "나", "is_ai": False}] \
            + [{"id": f"BOT_{i:02d}", "name": f"봇{i}", "is_ai": True} for i in range(1, 11)]
        app.start_game(mode="CLIENT", total_players=12, initial_players=plist)
    else:
        app.start_game(mode="SOLO", total_players=12)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    return m


def _run(kind, frames=700):
    app = _app()
    m = _start(app, kind)
    eng = m.local_engine
    rnd = random.Random(11)
    played = []
    orig_play = app.sound_mgr.play
    app.sound_mgr.play = lambda name, *a, **k: (played.append(name), orig_play(name, *a, **k))[1]
    died_at = None
    seen = {"flight": 0, "agg": 0, "wipe": 0, "b2b_break": 0, "hit": 0}
    for f in range(frames):
        if f % 40 == 0 and m.local_is_alive and not eng.game_over:
            eng.hard_drop()
        if f % 70 == 0 and m.local_is_alive:
            ids = [k for k, p in m.players.items() if k != m.local_player_id and p["is_alive"] and not m.is_ally(k, m.local_player_id)]
            if ids:
                m.apply_attack(rnd.choice(ids), m.local_player_id, rnd.randint(1, 5), from_network=(kind == "client"))      # 참가자는 다른 플레이어의 공격을 네트워크로 받음
        if f % 90 == 0 and m.local_is_alive:
            eng.b2b, eng.b2b_chain = bool(rnd.getrandbits(1)), rnd.randint(1, 3)
        if f % 150 == 149 and m.local_is_alive:
            eng.last_clear_info = {"cleared": rnd.choice([1, 2, 4]), "is_tspin": rnd.random() < 0.3, "is_mini": rnd.random() < 0.5,
                                   "is_b2b": False, "b2b_chain": 0}
            m.on_lines_cleared(eng.last_clear_info["cleared"])
            if m.attacks_enabled and not m.practice:
                m._add_send_agg(rnd.randint(2, 12))
            eng.cleared_row_indices = [18, 19]
            eng.lines_cleared_total += 1
        if f % 100 == 99 and m.local_is_alive:
            for y in range(len(eng.grid)):
                eng.grid[y] = [None] * 10
        if f == frames // 2 and m.local_is_alive and kind not in ("practice",):
            m._eliminate_player(m.local_player_id)                 # 탈락 -> 관전
            died_at = f
        m.update(1 / 60)
        app._play_lock_feedback(1 / 60)
        app.renderer.render(m)
        # 불변식
        assert m.flight_lines() >= 0
        if not m.local_is_alive:
            assert m.flight_lines() == 0 or all(h[0] > time.time() - 5 for h in m._pending_hits)
        seen["flight"] = max(seen["flight"], m.flight_lines())
        seen["agg"] = max(seen["agg"], m.send_agg["lines"])
        seen["wipe"] = max(seen["wipe"], len(app.renderer.line_clear_flashes))
        seen["b2b_break"] = max(seen["b2b_break"], m.b2b_break_seq)
    # 마지막에 남은 대기 피격이 전부 도착 처리됨 (시간이 지나면 비워짐)
    time.sleep(0.4)
    m.update(1 / 60)
    assert m.flight_lines() == 0, (kind, m._pending_hits)
    return app, m, played, seen, died_at


def test_effects_run_in_every_match_kind():
    for kind in ("solo", "survival", "team", "practice", "daily", "host", "client"):
        app, m, played, seen, died_at = _run(kind)
        if kind == "survival":
            assert seen["flight"] == 0, "서바이벌(공격 없음)에는 날아오는 공격이 없음"
        elif kind not in ("practice",):
            assert seen["flight"] > 0 and any(p.startswith("hit_") for p in played), (kind, seen)
        assert seen["wipe"] >= 0
        print("  OK", kind, seen)


def test_incoming_hit_alarm_only_when_beam_lands_in_each_kind():
    for kind in ("solo", "team", "host", "client"):
        app = _app()
        m = _start(app, kind)
        played = []
        m.sound_mgr.play = lambda name, *a, **k: played.append(name)
        ids = [k for k, p in m.players.items() if k != m.local_player_id and p["is_alive"] and not m.is_ally(k, m.local_player_id)]
        assert ids, kind
        m.apply_attack(ids[0], m.local_player_id, 4, from_network=(kind == "client"))
        assert not any(p.startswith("hit_") for p in played), (kind, "날아오는 동안에는 조용")
        assert m.flight_lines() == 4
        time.sleep(m.HIT_FLIGHT_SECS + 0.05)
        m.update(1 / 60)
        assert any(p.startswith("hit_") for p in played) and m.flight_lines() == 0, (kind, played)


def test_dead_local_player_gets_no_late_hit_effects():
    app = _app()
    m = _start(app, "solo")
    ids = [k for k, p in m.players.items() if p.get("bot") and p["is_alive"]]
    played = []
    m.sound_mgr.play = lambda name, *a, **k: played.append(name)
    m.apply_attack(ids[0], m.local_player_id, 6)
    m._eliminate_player(m.local_player_id)
    m.screen_shake = 0.0
    time.sleep(m.HIT_FLIGHT_SECS + 0.05)
    m.update(1 / 60)
    assert m.screen_shake == 0.0 and not any(p.startswith("hit_") for p in played), "탈락한 뒤에는 늦게 도착한 피격 연출/경고음이 없음"
    assert m.flight_lines() == 0


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL EFFECT MODE TESTS PASSED]")
