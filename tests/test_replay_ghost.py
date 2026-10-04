"""
리플레이 기록/재생/연습 시작, 고스트 레이스
실행: python test_replay_ghost.py
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
    assert checks > 15, checks                                   # 봇 탐색이 완전히 결정적이지 않아 판마다 고정 횟수가 조금 다름
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
    assert loaded[-1]["rank"] == 12 and [r["rank"] for r in loaded[-R.MAX_REPLAYS:]] == list(range(3, 13)), "최근 10판 보관"
    assert len(loaded) == R.MAX_REPLAYS + 1 and loaded[0]["rank"] == 1, "모드별 최고 점수 판은 10판 순환 밖에 고정 보관"
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


def test_replay_keeps_hold_next_and_practice_from_here():
    import replay
    from block_engine import BlockEngine
    e = BlockEngine(seed=3)
    rec = replay.ReplayRecorder()
    rec.update(e, 0.0)
    e.hold()
    e.hard_drop()
    rec.update(e, 2.0)
    ev = rec.events[-1]
    assert ev["k"] == "L" and len(ev["nx"]) == 3 and ev["hd"] and ev["cp"] == e.current_piece
    data = rec.finish(5, 20, 1, 100, 30)
    clean = replay._clean(data)
    assert clean is not None and clean["events"][-1]["nx"] == ev["nx"]
    pl = replay.ReplayPlayer(clean)
    pl.seek(5.0)
    assert pl.next == ev["nx"] and pl.hold == ev["hd"] and pl.cur == ev["cp"]
    app = _app()
    app.records_mode = "replay"
    app.replay_view = pl
    app.state = "RECORDS"
    app._render_records()
    app._handle_replay_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="p"))
    m = app.match
    assert m is not None and m.practice
    eng = m.local_engine
    assert eng.hold_piece == (pl.hold or None) and eng.current_piece == pl.cur
    assert sum(1 for row in eng.grid for c in row if c) == sum(1 for row in pl.grid for c in row if c)


def test_ghost_race_follows_match_time():
    import replay
    from block_engine import BlockEngine
    from ai_bot import AIBot
    # 가짜 '최고 판' 두 개: 점수가 높은 쪽이 고스트
    e = BlockEngine(seed=11)
    rec = replay.ReplayRecorder()
    rec.update(e, 0.0)
    for i in range(6):
        e.hard_drop()
        rec.update(e, 1.0 + i)
    hi = rec.finish(3, 20, 2, 5000, 30)
    lo = dict(hi, score=100, secs=10)
    assert replay.best_replay([lo, hi])["score"] == 5000 and replay.best_replay([]) is None
    saved = replay.load_replays()
    tmp_path = os.path.join(tempfile.mkdtemp(), "replays.json")
    replay.save_replay(lo, tmp_path)
    replay.save_replay(hi, tmp_path)
    old_path = replay.replay_path
    replay.replay_path = lambda: tmp_path
    app = _app()
    try:
        app.settings.set("ghost_race", True)
        app.start_game("SOLO", total_players=20)
        m = app.match
        assert m.race_ghost is not None and m.race_ghost.data["score"] == 5000
        m.countdown_until = 0.0
        for _ in range(60):
            app._tick_game(1 / 30)
        assert m.race_ghost.t == min(m.race_ghost.duration, m.elapsed) or abs(m.race_ghost.t - m.elapsed) < 0.2
        app.renderer.render(m, app.sound_mgr)
        app.start_game("SOLO", total_players=20, practice=True)
        app.settings.set("ghost_race", False)
        app.start_game("SOLO", total_players=20)
        assert app.match.race_ghost is None
    finally:
        replay.replay_path = old_path
        app.settings.set("ghost_race", False)


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
        print("[ALL REPLAY_GHOST TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
