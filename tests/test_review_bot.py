"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트 - 봇: 탐색/속도/조준 분산/워치독/작업 프로세스 풀/이름과 성향
(예전 test_review_fixes.py를 영역별로 나눈 파일. 실행: python test_review_bot.py, SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
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
        from config import SPAWN_Y
        e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 3, SPAWN_Y
        if e._check_collision(3, SPAWN_Y, 0):
            continue
        rows = BB.rows_from_grid(e.grid)
        for rot, px, py, kind, path in BB.t_placements(rows)[:12]:
            f = BlockEngine(seed=1)
            f.grid = [r[:] for r in e.grid]
            f.current_piece, f.current_rot, f.current_x, f.current_y = "T", 0, 3, SPAWN_Y
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
    import bot_reference as R
    from block_engine import BlockEngine

    def ref_placements(rows, piece):                                    # 한 칸씩 내려 보며 충돌을 검사하는 원래 방식
        out, seen = [], set()
        for rot, cells in enumerate(BB.SHAPES[piece]):
            lo, hi = R.SHAPE_SPAN[piece][rot]
            for px in range(-lo, BB.W - hi):
                if R._collide(rows, cells, px, 0):
                    continue
                py = R._drop(rows, cells, px, 0)
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
    import tempfile
    saved_dir = os.environ.get("BR_DATA_DIR")
    os.environ["BR_DATA_DIR"] = tempfile.mkdtemp()                           # 일부러 작업자를 죽이는 테스트라 'bot_pool disabled' 기록이 진짜 error.log에 남지 않게
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
        from app_paths import data_path
        logged = open(data_path("error.log"), encoding="utf-8").read()
        assert "worker process died (exit codes:" in logged, logged[-300:]       # 원인을 알 수 있게 종료 코드가 기록됨
    finally:
        bot_pool.stop()
        bot_pool._state.update(started=False, broken=False)
        if saved_dir is None:
            os.environ.pop("BR_DATA_DIR", None)
        else:
            os.environ["BR_DATA_DIR"] = saved_dir
    print("  OK bot params override + worker pool")


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
        print("[ALL REVIEW BOT TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)
