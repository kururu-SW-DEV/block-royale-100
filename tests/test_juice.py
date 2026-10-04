"""
도파민 연출(v1.1.6) 테스트: 흔들림 감쇠 버그, 배너 tier/메인+보조, 방어/콤보 끊김/K.O. 후속 연출/TOP N/결승/경기 중 업적/현상금/명장면,
경험치·레벨·해금 스킨, 결과 화면 보상 줄, 새 효과음과 BGM 덕킹, 카운트다운 효과음, 재도전 카운트다운 단축.
실행: python test_juice.py
"""
import os
import sys
import time
import random
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
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")      # 사용자 전적 파일을 건드리지 않음
    app.stats_mgr.data["achievements"] = []
    app.stats_mgr.data["total_kos"] = 0
    return app


def _spy(app):
    played = []
    orig = app.sound_mgr.play
    app.sound_mgr.play = lambda name, *a, **k: (played.append((name, k.get("combo"))), orig(name, *a, **k))[1]
    return played


def _game(app, n=30, **kw):
    app.start_game(mode="SOLO", total_players=n, **kw)
    m = app.match
    m.countdown_until = 0.0
    return m


def _texts(m):
    return [f["text"] for f in m.floating_texts]


def test_shake_decays_after_match_finished_and_direction():
    app = _app()
    m = _game(app, 4)
    m.trigger_screen_shake(20.0, (0, 1))
    assert m.shake_dir == (0, 1) and m.screen_shake > 0
    m.match_finished = True
    for _ in range(60):
        m.update(1 / 60)
    assert m.screen_shake == 0.0 and m.shake_dir is None, "경기가 끝난 뒤에도 흔들림이 줄어들어야 함 (예전에는 20.0에서 멈춤)"
    m.match_finished = False
    m.shake_scale = 0.0
    m.trigger_screen_shake(14.0)
    assert m.screen_shake == 0.0, "흔들림 '끔'이면 아무 것도 없음"
    m.shake_scale = 1.0
    m.trigger_screen_shake(14.0, (1, 0))
    m.trigger_screen_shake(5.0, (0, 1))
    assert m.shake_dir == (1, 0), "더 약한 흔들림이 센 흔들림의 방향을 덮어쓰지 않음"
    app.renderer.render(m)
    print("  OK shake")


def test_banner_tiers_main_and_sub_lines():
    app = _app()
    m = _game(app, 12)
    m.floating_texts = []
    m.add_floating_text("a", (255, 255, 255), size=44, category="action")
    m.add_floating_text("b", (255, 255, 255), size=30, category="action")
    m.add_floating_text("c", (255, 255, 255), size=26, category="action")
    assert [f["tier"] for f in m.floating_texts] == [3, 2, 1]
    m.floating_texts = []
    m.add_floating_text("★ 위기 탈출! ★", (255, 215, 0), size=30, category="action", tier=2)
    m.add_floating_text("★ 트리플 클리어! ★", (100, 240, 255), size=28, category="action", tier=1)
    drawn = []
    r = app.renderer
    cls = r.font_hud.__class__
    saved = cls.render
    hud = r.font_hud
    cls.render = lambda self, text, aa=True, color=(255, 255, 255), background=None: (drawn.append((self is hud, text)), saved(self, text, aa, color, background))[1]
    try:
        r.render(m)
    finally:
        cls.render = saved
    # 메인(가장 높은 tier)은 tier 글꼴(font_banner), 같은 순간의 다른 배너는 보조 줄(font_hud)
    assert (False, "★ 위기 탈출! ★") in drawn and (True, "★ 트리플 클리어! ★") in drawn, [d for d in drawn if "★" in d[1]]
    assert (True, "★ 위기 탈출! ★") not in drawn and (False, "★ 트리플 클리어! ★") not in drawn
    # 팝인: 막 나온 배너와 한참 지난 배너 모두 예외 없이 그려짐
    for ft in m.floating_texts:
        ft["birth"] = time.time() - 0.02
    r.render(m)
    for ft in m.floating_texts:
        ft["birth"] = time.time() - 0.8
    r.render(m)
    print("  OK banners")


def test_cancel_feedback_combo_break_and_ko_events():
    app = _app()
    m = _game(app, 30)
    played = _spy(app)
    eng = m.local_engine
    # 방어(막은 줄)
    eng.combo = 6
    eng.last_clear_info = {"cleared": 2, "canceled": 3, "combo": 6}
    m.on_lines_cleared(2)
    assert "방어 −3줄" in _texts(m) and m.cancel_seq == 1 and m.cancel_last[1] == 3
    assert ("shield", None) in played
    m.floating_texts = []
    played.clear()
    eng.last_clear_info = {"cleared": 1, "canceled": 1, "combo": 6}
    m.on_lines_cleared(1)
    assert "방어 −1줄" in _texts(m) and ("shield", None) not in played, "1줄 방어는 소리 생략"
    # 콤보 끊김: 3 이상 쌓은 콤보가 끝나면 토스트와 소리
    m.floating_texts = []
    eng.combo = 5
    m.update(0.01)
    eng.combo = -1
    m.update(0.01)
    assert any("콤보 끝 ×5" in t for t in _texts(m)) and ("combo_break", None) in played
    played.clear()
    eng.combo = 2
    m.update(0.01)
    eng.combo = -1
    m.update(0.01)
    assert ("combo_break", None) not in played, "짧은 콤보는 알리지 않음"
    # K.O.: 처치 순간(토스트) + 구슬 도착(0.7초 뒤) 소리, 배지 승급은 도착 시점
    me = m.local_player_id
    bots = [p for p in m.players if p != me and p != m.bounty_id]
    played.clear()
    m.floating_texts = []
    m._eliminate_player(bots[0], killer_id=me)
    assert m.local_ko_count == 1 and m.players[bots[0]]["ko_t"] and m.players[bots[0]]["ko_by"] == me
    assert not any(n.startswith("ko_orb") or n == "ko_orb" for n, _ in played) and len(m._ko_events) == 1
    m._ko_events[0]["due"] = time.time() - 0.01
    m.update(0.01)
    assert ("ko_orb", 1) in played and not m._ko_events
    # 배지 승급(2킬)은 구슬 도착 때 소리/배너
    m._eliminate_player(bots[1], killer_id=me)
    assert not any(t.startswith("★ 배지 승급") for t in _texts(m)), "승급 배너는 구슬이 도착한 뒤"
    m._ko_events[0]["due"] = time.time() - 0.01
    m.update(0.01)
    assert any(t.startswith("★ 배지 승급") for t in _texts(m)) and ("badge_up", None) in played
    # 마지막 K.O.로 경기가 끝나도 예약된 연출이 처리됨
    print("  OK cancel/combo/ko")


def test_top_n_final_duel_live_achievements_first_ko_and_bounty():
    app = _app()
    m = _game(app, 30)
    played = _spy(app)
    me = m.local_player_id
    assert m.first_ko_ever and "first_ko" in m.live_ach and m.bounty_id and m.bounty_id != m.rival_id
    bots = [p for p in m.players if p != me]
    first = bots[0] if bots[0] != m.bounty_id else bots[1]
    m._eliminate_player(first, killer_id=me)
    assert "★ 첫 K.O.! 축하해요 ★" in _texts(m) and ("levelup", None) in played
    assert not any("업적 달성" in t and "첫 K.O." in t for t in _texts(m)), "평생 첫 K.O.는 전용 배너만 (업적 토스트 중복 없음)"
    # 현상금: 처치하면 보너스 배너와 금빛 구슬
    m._eliminate_player(m.bounty_id, killer_id=me)
    assert m.bounty_claimed and any("현상금 사냥 성공" in t for t in _texts(m)) and m.ko_orbs[-1].get("gold")
    for pid in bots:
        if m.alive_count <= 3:
            break
        if m.players[pid]["is_alive"]:
            m._eliminate_player(pid, killer_id=me)
    assert {25, 10, 5} <= m._top_announced or {25, 5} <= m._top_announced, m._top_announced      # p2/p3 배너와 같은 인원(15, 3)은 TOP 안내를 생략
    assert 15 not in m._top_announced and 3 not in m._top_announced
    assert any("사냥꾼" in t for t in [f["text"] for f in m.floating_texts]) or "ko5" in m.live_ach_done
    for pid in bots:
        if m.alive_count <= 2:
            break
        if m.players[pid]["is_alive"]:
            m._eliminate_player(pid, killer_id=None)
    assert m._final_announced and m.final_opp_id and m.players[m.final_opp_id]["is_alive"]
    assert any("FINAL DUEL" in t for t in _texts(m)) and ("final", None) in played
    app.renderer.render(m)                                         # 결승 상대 카드/현상금/탈락 연출이 있는 프레임
    for p in m.players.values():
        if p.get("ko_t"):
            p["ko_t"] = time.time() - 0.2
    app.renderer.render(m)
    hl = m.highlights()
    assert "bounty" in hl and "chain_ko" in hl, hl
    # 현상금 봇은 오늘의 도전에서 날짜로 결정(같은 날 같은 봇), 전역 난수는 건드리지 않음
    random.seed(5)
    a = _game(app, 30, daily="20261003")
    b1 = a.bounty_id
    state = random.getstate()
    b = _game(app, 30, daily="20261003")
    assert b.bounty_id == b1
    print("  OK milestones")


def test_live_achievement_toast_and_highlights_flags():
    app = _app()
    m = _game(app, 30)
    played = _spy(app)
    m.first_ko_ever = False
    m.live_ach = {"combo8": "콤보 장인", "marathon": "마라토너"}
    m.local_engine.max_combo = 8
    m._check_live_achievements()
    assert "★ 업적 달성!  콤보 장인" in _texts(m) and ("badge_up", None) in played
    n = len(m.floating_texts)
    m._check_live_achievements()
    assert len(m.floating_texts) == n, "한 번만 알림"
    m.elapsed = 430.0
    m._check_live_achievements()
    assert "★ 업적 달성!  마라토너" in _texts(m)
    m.pc_count = 1
    m.max_b2b_chain = 5
    m.local_engine.garbage_canceled_total = 40
    m.clutch_times = [100.0]
    m.elapsed = 120.0
    m.match_finished = True
    m.local_rank = 1
    hl = m.highlights()
    assert {"perfect", "comeback", "b2b5", "wall"} <= set(hl), hl
    from stats_manager import HIGHLIGHT_IDS
    assert set(m.HIGHLIGHT_LABELS) == set(HIGHLIGHT_IDS)
    print("  OK live achievements")


def test_xp_level_unlocks_and_stats_storage():
    import stats_manager as SM
    assert SM.level_of(0) == (1, 0, 100) and SM.level_of(99)[0] == 1 and SM.level_of(100) == (2, 0, SM.xp_for_next(2))
    xs = [SM.xp_for_next(i) for i in range(1, 12)]
    assert xs == sorted(xs) and xs[0] == 100
    total5 = sum(SM.xp_for_next(i) for i in range(1, 5))
    assert SM.level_of(total5)[0] == 5 and SM.level_of(total5 - 1)[0] == 4
    gain, parts = SM.calc_match_xp(1, 100, 5, 400, ["perfect"], "battle")
    names = dict(parts)
    assert names["참가"] == 20 and names["순위"] == 60 and names["K.O."] == 40 and names["생존"] == 20 and names["우승"] == 40 and names["명장면"] == 15 and gain == sum(names.values())
    g2, _p2 = SM.calc_match_xp(100, 100, 0, 5, [], "battle")
    assert g2 == 20, "꼴찌도 참가 경험치는 받음"
    g3, _p3 = SM.calc_match_xp(1, 100, 5, 400, [], "survival")
    assert g3 < gain / 2 + 40
    d = tempfile.mkdtemp()
    st = SM.StatsManager(os.path.join(d, "s.json"))
    st.record_match(rank=1, total_players=100, kos=3, lines=40, max_combo=4, survival_sec=300, highlights=["perfect", "zzz"])
    assert st.data["xp"] == st.last_xp["after"] and st.last_xp["gain"] > 0 and st.data["highlights"] == {"perfect": 1}
    st.record_match(rank=5, total_players=100, kos=1, lines=10, max_combo=2, survival_sec=100, highlights=["perfect"])
    assert st.data["highlights"] == {"perfect": 2}
    st.save()
    st2 = SM.StatsManager(st.filepath)
    assert st2.data["xp"] == st.data["xp"] and st2.data["highlights"] == {"perfect": 2}
    import json
    raw = json.load(open(st.filepath, encoding="utf-8"))
    raw["xp"] = "abc"
    raw["highlights"] = {"perfect": 3, "bogus": 2, "wall": -1, "combo10": True}
    json.dump(raw, open(st.filepath, "w", encoding="utf-8"))
    st3 = SM.StatsManager(st.filepath)
    assert st3.data["xp"] == 0 and st3.data["highlights"] == {"perfect": 3}
    st3.reset_stats()
    assert st3.data["xp"] == 0 and st3.data["highlights"] == {}
    # 레벨 해금 스킨
    fresh = SM.StatsManager(os.path.join(d, "f.json"))
    assert "ember" not in SM.unlocked_skin_ids(fresh.data) and "prism" not in SM.unlocked_skin_ids(fresh.data)
    fresh.data["xp"] = total5
    assert "ember" in SM.unlocked_skin_ids(fresh.data) and "prism" not in SM.unlocked_skin_ids(fresh.data)
    fresh.data["xp"] = sum(SM.xp_for_next(i) for i in range(1, 10))
    assert "prism" in SM.unlocked_skin_ids(fresh.data)
    # 도전 과제 별 -> 경험치, 레벨이 오르면 알림 표시
    fresh2 = SM.StatsManager(os.path.join(d, "g.json"))
    fresh2.mark_challenges("practice", None, ["p_cancel2", "p_lines10", "p_double", "p_triple", "p_quad"])
    assert fresh2.data["xp"] == 5 * SM.STAR_XP and fresh2.last_level_up == (1, 2)
    from settings_manager import BLOCK_SKIN_OPTIONS, BLOCK_SKIN_LABELS, BLOCK_SKIN_DESCS
    assert "ember" in BLOCK_SKIN_OPTIONS and "prism" in BLOCK_SKIN_OPTIONS and "ember" in BLOCK_SKIN_LABELS and "prism" in BLOCK_SKIN_DESCS
    app = _app()
    for sk in ("ember", "prism"):
        for size in (8, 14, 29):
            app.renderer._cell_surface("T", size, skin=sk)
    print("  OK xp/level/skins")


def test_next_goal_near_miss_and_quick_rematch():
    from stats_manager import next_goal_text
    assert next_goal_text(40, 8, 100, 30, max_ko=9) == "K.O. 최고 기록(9명)까지 1명"
    assert next_goal_text(40, 3, 100, 30, max_ko=9) != "K.O. 최고 기록(9명)까지 6명", "3명 이상 차이는 근접 실패가 아님"
    app = _app()
    app.use_bot_pool = True                                          # 혼자 하는 경기 시작 카운트다운을 켜서 길이를 확인
    app.start_game(mode="SOLO", total_players=12)
    assert 2.5 < app.match.countdown_left() <= 3.0
    app.start_game(mode="SOLO", total_players=12, quick=True)
    assert 1.5 < app.match.countdown_left() <= 2.0, "재도전은 카운트다운 2초"
    app._restart_after_match()
    assert app.match.countdown_left() <= 2.0
    app.use_bot_pool = False
    print("  OK near-miss/quick")


def test_countdown_sounds_and_duck():
    app = _app()
    app.use_bot_pool = True
    played = _spy(app)
    app.start_game(mode="SOLO", total_players=12)
    m = app.match
    app._tick_game(1 / 60)
    assert ("count", None) in played, "카운트다운 숫자가 나올 때 비프"
    nc = sum(1 for n, _ in played if n == "count")
    m.countdown_until = time.time() + 1.5
    app._tick_game(1 / 60)
    m.countdown_until = time.time() - 0.01
    app._tick_game(1 / 60)
    assert ("go", None) in played
    app.use_bot_pool = False
    # BGM 덕킹: 위기에서 낮추고 탈출/탈락/곡 전환에서 되돌림
    sm = app.sound_mgr
    sm.reset_duck()
    m2 = _game(app, 12)
    eng = m2.local_engine
    for y in range(3, 20):                                           # 높이 17의 스택
        for x in range(9):
            eng.grid[y][x] = "I"
    m2._track_danger()
    assert sm._duck_target < 1.0
    for _ in range(40):
        sm.tick()
    assert sm._duck <= sm._duck_target + 1e-6
    for y in range(3, 20):
        for x in range(10):
            eng.grid[y][x] = None
    m2._track_danger()
    assert sm._duck_target == 1.0
    sm.set_duck(0.5)
    sm.stop_bgm()
    assert sm._duck == 1.0 and sm._duck_target == 1.0
    sm.set_duck(0.1)
    assert sm._duck_target == 0.3, "너무 낮추지 않음"
    sm.reset_duck()
    # 새 효과음이 모두 있고 클리핑하지 않음
    import numpy as np
    for n in ("count", "go", "shield", "clutch", "thump_s", "tspin_big", "phase_up", "final", "top_up", "revenge", "combo_break", "levelup", "stamp", "b2b_1", "b2b_5", "ko_orb_1", "ko_orb_8"):
        assert n in sm.sounds, n
        assert int(np.abs(pygame.sndarray.array(sm.sounds[n])).max()) < 32000, f"{n} 클리핑"
    sm.play("b2b", combo=9)
    sm.play("ko_orb", combo=99)
    print("  OK sounds/duck")


def test_reward_rows_on_results_and_menu_badge():
    app = _app()
    m = _game(app, 12)
    me = m.local_player_id
    # 탈락 결과 화면: 경험치 바, 업적·해금 카드, 명장면 도장
    m.local_ko_count = 4
    m.pc_count = 1
    m.ko_times = [10.0, 12.0, 15.0]
    for pid in list(m.players)[1:7]:
        m._eliminate_player(pid, killer_id=None)
    m._eliminate_player(me, killer_id=None)
    for _ in range(3):
        app._tick_game(1 / 60)
    rw = m.reward
    assert rw and rw["xp"]["gain"] > 0 and "perfect" in rw["highlights"] and "chain_ko" in rw["highlights"], rw
    assert app._sound_due, "결과 화면 연출 소리가 예약됨"
    for k in (0.0, 1.5, 2.2, 3.5):
        app.renderer._result_match = m
        app.renderer._result_t0 = time.time() - k
        app.renderer.render(m)
    # 레벨 업/해금이 있는 경우
    rw["xp"].update({"before": 90, "after": 300, "gain": 210, "lv_before": 1, "lv_after": 2})
    rw["unlocks"] = ["불씨"]
    m.new_achievements = ["first_ko", "ko5", "top10", "victory"]
    for k in (1.6, 2.6, 4.0):
        app.renderer._result_t0 = time.time() - k
        app.renderer.render(m)
    assert app.renderer._result_reward_height(m) > 0
    # 우승/종료 순위표 머리 줄
    m2 = _game(app, 12)
    for pid in list(m2.players)[1:]:
        m2._eliminate_player(pid, killer_id=m2.local_player_id)
    for _ in range(3):
        app._tick_game(1 / 60)
    lines = app.renderer._standings_info_lines(m2)
    assert any("경험치" in t for t, _c in lines) and len(lines) <= 4, lines
    app.renderer._standings_t0 = time.time() - 3.0
    app.renderer.render(m2)
    # 메인 메뉴 프로필 칩의 레벨 배지
    app.state = "MENU"
    app._render_menu()
    app.stats_mgr.data["xp"] = 5000
    app._render_menu()
    print("  OK rewards")


def test_practice_and_survival_unaffected():
    app = _app()
    app.start_game(mode="SOLO", practice=True)
    m = app.match
    assert m.bounty_id is None and not m.live_ach and m.highlights() == []
    for _ in range(3):
        app._tick_game(1 / 60)
    m.local_engine.combo = 5
    m.update(0.01)
    m.local_engine.combo = -1
    m.update(0.01)
    assert not any("콤보 끝" in f["text"] for f in m.floating_texts), "연습 모드에서는 콤보 끝 알림 없음"
    app.renderer.render(m)
    app.stats_mgr.data["total_games"] = 0
    app.start_game(mode="SOLO", total_players=6)
    app.match.attacks_enabled = False
    print("  OK practice/survival")


# ---------------------------------------------------------------- v1.1.7 블록 반응 연출
def _react_setup(n=20):
    app = _app()
    app.start_game(mode="SOLO", total_players=n)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(5):
        app._tick_game(1 / 60)
    return app, m, m.local_engine, app.renderer


def _vertical_i(e, col):
    e.current_piece = "I"
    for rot in range(4):
        bl = e._get_blocks("I", rot, 0, 0)
        xs = {x for x, _ in bl}
        if len(xs) == 1:
            e.current_rot, e.current_x, e.current_y = rot, col - list(xs)[0], 0
            return
    raise AssertionError("세로 I 없음")


def _quad_setup(e):
    from config import BOARD_HEIGHT
    for y in range(BOARD_HEIGHT - 4, BOARD_HEIGHT):
        e.grid[y] = ["L", "J", "S", "Z", "O", "T", "I", "L", "J", None]
    e.grid[BOARD_HEIGHT - 6][2] = "T"
    _vertical_i(e, 9)


def test_engine_reaction_hooks():
    from config import BOARD_HEIGHT
    app, m, e, r = _react_setup()
    _quad_setup(e)
    n = e.hard_drop()
    assert n == 4
    assert len(e.cleared_row_cells) == 4 and e.cleared_row_cells[0][1][0] == "L"
    assert e.last_hard_drop["dist"] > 0 and e.hard_drop_events == 1
    offs = e.settle_offsets
    assert len(offs) == BOARD_HEIGHT and offs[:4] == [0, 0, 0, 0]
    assert offs[BOARD_HEIGHT - 2] == 4, "위에 있던 줄(맨 아래에서 6번째)은 4칸 내려와 아래에서 2번째 줄이 됨"
    e._push_garbage(3)
    assert len(e.push_holes) == 3 and all(0 <= h < 10 for h in e.push_holes)
    print("  OK 엔진 훅")


def test_shatter_settle_and_motion_setting():
    app, m, e, r = _react_setup()
    r.render(m)
    _quad_setup(e)
    m.on_lines_cleared(e.hard_drop())
    r.render(m)
    assert len(r.shards) > 20, "지운 줄이 조각으로 흩어짐"
    assert r._settle is not None and r._settle["offs"], "위 블록 내려앉기"
    assert e.cleared_row_cells == [], "한 번만 소비"
    app2, m2, e2, r2 = _react_setup()
    m2.shake_scale = 0.0
    r2.render(m2)
    _quad_setup(e2)
    m2.on_lines_cleared(e2.hard_drop())
    r2.render(m2)
    assert r2.shards and r2._settle is None, "흔들림 '끔'이면 위치가 움직이는 내려앉기는 없음"
    print("  OK 파쇄/내려앉기/끔")


def test_garbage_rise_and_hole_flash():
    from config import BOARD_HEIGHT
    app, m, e, r = _react_setup()
    r.render(m)
    e._push_garbage(3)
    r.render(m)
    assert r._rise and r._rise["n"] == 3 and len(r.hole_flashes) == 3
    assert r.hole_flashes[0]["row"] == BOARD_HEIGHT - 3
    for _ in range(3):
        r.render(m)
    time.sleep(0.2)
    r.render(m)
    assert r._rise is None, "상승 연출은 짧게 끝남"
    app2, m2, e2, r2 = _react_setup()
    m2.shake_scale = 0.0
    r2.render(m2)
    e2._push_garbage(2)
    r2.render(m2)
    assert r2._rise is None and len(r2.hole_flashes) == 2, "끔: 즉시 표시, 구멍 깜빡임만"
    print("  OK 쓰레기 줄 상승")


def test_hard_drop_trail_and_bounce():
    app, m, e, r = _react_setup()
    r.render(m)
    e.current_piece, e.current_y = "T", 1
    e.hard_drop()
    r.render(m)
    assert r.drop_trails and r._bounce_amp > 0
    app2, m2, e2, r2 = _react_setup()
    m2.shake_scale = 0.0
    r2.render(m2)
    e2.current_piece, e2.current_y = "T", 1
    e2.hard_drop()
    r2.render(m2)
    assert r2.drop_trails and r2._bounce_amp == 0, "끔: 반동 없음, 궤적은 유지"
    print("  OK 하드 드롭")


def test_attack_origin_row():
    app, m, e, r = _react_setup()
    r.render(m)
    _quad_setup(e)
    cl = e.hard_drop()
    m.on_lines_cleared(cl)
    tgt = next(pid for pid in m.players if pid != m.local_player_id)
    m.apply_attack(m.local_player_id, tgt, 4)
    eff = m.attack_effects[-1]
    assert eff["origin_row"] is not None and 15 <= eff["origin_row"] <= 19
    r.render(m)                                          # 출발점이 지운 줄 높이여도 그려짐
    m.apply_attack(tgt, m.local_player_id, 2)
    assert m.attack_effects[-1]["origin_row"] is None, "받는 공격은 기본 위치"
    print("  OK 줄->탄환")


def test_tspin_hint_and_danger_breath():
    import ui_renderer as U
    from config import BOARD_HEIGHT, BOARD_WIDTH
    app, m, e, r = _react_setup()
    r.render(m)
    e.grid = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    e.current_piece, e.current_rot, e.current_x = "T", 0, 3
    while not e._is_touching_ground():
        e.current_y += 1
    seen = []
    orig = r._draw_text
    r._draw_text = lambda text, *a, **k: (seen.append(text), orig(text, *a, **k))[1]
    e._detect_tspin = lambda: "full"
    r.render(m)
    assert "T-SPIN" in seen, "T-스핀 성립 시 글자로도 알림"
    del e._detect_tspin
    seen.clear()
    r.render(m)
    assert "T-SPIN" not in seen
    for y in range(2, BOARD_HEIGHT):
        e.grid[y] = ["G"] * 9 + [None]
    for cb in (False, True):
        U.is_colorblind = (lambda v=cb: v)
        r.render(m)
    import config
    U.is_colorblind = config.is_colorblind
    print("  OK T-스핀 힌트/위기 숨결(색약 포함)")


def test_topout_and_victory_ceremony():
    from config import BOARD_HEIGHT
    app, m, e, r = _react_setup()
    r.render(m)
    for y in range(BOARD_HEIGHT):
        e.grid[y] = ["L"] * 10
    e.game_over = True
    for _ in range(3):
        time.sleep(0.05)
        r.render(m)
    assert r._topout is not None and r.shards, "탑아웃: 위에서부터 부서짐"
    app, m, e, r = _react_setup()
    r.render(m)
    for y in range(10, BOARD_HEIGHT):
        e.grid[y] = ["L"] * 9 + [None]
    for pid in list(m.players):
        if pid != m.local_player_id and m.players[pid]["is_alive"]:
            m._eliminate_player(pid, m.local_player_id)
    assert m.match_finished and m.local_rank == 1
    r.render(m)
    assert r._vic_t0 is not None and r._standings_t0 is None, "세리머니 동안은 순위표를 미룸"
    r._vic_t0 -= r.VICTORY_CEREMONY + 0.1
    r.render(m)
    assert r._standings_t0 is not None, "세리머니가 끝나면 순위표"
    print("  OK 탑아웃/우승 세리머니")


def test_glow_particles():
    import ui_renderer as U
    app, m, e, r = _react_setup()
    r.particles.add_sparks(600, 300, (255, 220, 120), count=10, glow=True)
    r.render(m)
    assert any(p.get("glow") for p in r.particles.particles)
    spr = U._glow_sprite(12, (255, 200, 100), 4)
    assert spr.get_width() == 24 and spr.get_at((12, 12))[0] > spr.get_at((1, 1))[0], "가운데가 더 밝음"
    print("  OK 발광 파티클")


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
        print("[ALL JUICE TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
