"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트 - 게임 규칙: 쓰레기 누적/캡, 퍼펙트 클리어, 다중 공격, B2B, 후반 증폭, 서바이벌, 연속 이동 ARR, 구출 보너스, 연습
(예전 test_review_fixes.py를 영역별로 나눈 파일. 실행: python test_review_rules.py, SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
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


def test_garbage_accumulates():
    e = BlockEngine(seed=3)
    e.garbage_to_send = 5                        # 아직 수거되지 않은 공격이 있는 상태에서 블록이 또 고정돼도 사라지면 안 됨
    e.hard_drop()
    assert e.garbage_to_send == 5, f"앞선 공격이 덮어써짐: {e.garbage_to_send}"
    print("  OK garbage_to_send accumulates")


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
        print("[ALL REVIEW RULES TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)
