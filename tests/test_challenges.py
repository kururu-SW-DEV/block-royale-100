"""
도전 과제 시스템 테스트: 과제 정의, 하루 목표 뽑기(결정론/전역 난수 보존), 추적기 판정, 엔진 상쇄량 지표, 저장/검증/스트릭,
연습 12과제와 타임어택, 오늘의 도전/주간 변형 연결, 브리핑 카드, 업적/스킨 해금, 주간 규칙 순환과 규칙 카드.
실행: python test_challenges.py
"""
import os
import sys
import json
import random
import tempfile
import datetime

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import challenges as CH
from gfx import CANVAS


def _app():
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    return app


def test_definitions_are_consistent():
    assert len(CH.PRACTICE_GOALS) == 12 and len(set(CH.PRACTICE_IDS)) == 12
    assert len({g["id"] for g in CH.ALL_GOALS.values()}) == len(CH.ALL_GOALS), "과제 id 중복 없음"
    for g in CH.ALL_GOALS.values():
        assert g["tier"] in (1, 2, 3) and g["op"] in (">=", "<=") and len(g["short"]) <= 8, g
        assert g["metric"] in ChallengeMetrics, g
    for tier in (1, 2, 3):
        assert any(g["tier"] == tier for g in CH.DAILY_POOL), tier
    for rule, goals in CH.WEEKLY_GOALS.items():
        assert [g["tier"] for g in goals] == [1, 2, 3], rule


ChallengeMetrics = set(CH.ChallengeTracker([]).m)


def test_pick_daily_deterministic_and_balanced():
    state = random.getstate()
    seen = set()
    d = datetime.date(2026, 1, 1)
    for i in range(400):
        key = (d + datetime.timedelta(days=i)).strftime("%Y%m%d")
        ids = CH.pick_daily(key)
        assert ids == CH.pick_daily(key), "같은 날은 같은 목표"
        goals = [CH.DAILY_BY_ID[x] for x in ids]
        assert [g["tier"] for g in goals] == [1, 2, 3]
        assert len({g["cat"] for g in goals}) == 3, (key, ids)
        assert sum(1 for g in goals if g["cat"] == "rank") <= 1
        seen.update(ids)
    assert len(seen) >= 12, "여러 날에 걸쳐 다양한 목표가 나옴"
    assert random.getstate() == state, "전역 난수(봇 구성)를 건드리지 않음"


def test_tracker_metrics_and_dedup():
    t = CH.ChallengeTracker(CH.PRACTICE_GOALS)
    t.on_clear({"cleared": 4, "is_b2b": True, "b2b_chain": 1, "combo": 0})
    assert {"p_quad", "p_b2bquad"} <= t.done and t.m["quads"] == 1 and t.m["b2b_quads"] == 1
    t.on_clear({"cleared": 2, "is_tspin": True, "is_mini": True, "combo": 1})
    assert "p_tspin" in t.done and "p_tsd" not in t.done, "미니 T-스핀은 더블 과제에 안 침"
    t.on_clear({"cleared": 2, "is_tspin": True, "is_mini": False, "combo": 2})
    assert "p_tsd" in t.done
    t.on_clear({"cleared": 1, "combo": 5, "canceled": 4, "is_pc": True, "b2b_chain": 3})
    assert {"p_combo5", "p_cancel_big", "p_pc", "p_b2b3", "p_cancel2", "p_combo3"} <= t.done
    new = t.pop_new()
    assert len(new) == len(set(new)) and t.pop_new() == [], "새로 달성한 것은 한 번만 꺼냄"
    t.on_clear({"cleared": 4})
    assert t.pop_new() == [], "이미 달성한 과제는 다시 나오지 않음"
    t.on_drill(61, 2)
    assert "p_drill60" in t.done and "p_drill_lv5" not in t.done
    t.on_drill(125, 5)
    assert "p_drill_lv5" in t.done
    # 이미 저장된 달성분을 넘겨 주면 처음부터 done에 있고 newly_done에는 안 나옴
    t2 = CH.ChallengeTracker(CH.PRACTICE_GOALS, done=["p_quad", "bogus"])
    assert t2.done == {"p_quad"}
    t2.on_clear({"cleared": 4})
    assert "p_quad" not in t2.pop_new()


def test_tracker_rank_survival_and_combat():
    goals = [CH.DAILY_BY_ID[x] for x in ("d_top20", "d_life90", "d_ko4", "d_sent30", "d_clutch1")]
    t = CH.ChallengeTracker(goals)
    for alive_count, el in ((100, 10.0), (40, 60.0), (21, 80.0)):
        t.tick(el, True, alive_count)
    assert "d_top20" not in t.done and t.m["top"] == 21
    t.tick(95.0, True, 20)
    assert {"d_top20", "d_life90"} <= t.done, "TOP N은 살아 있는 채로 생존자가 N명이 되는 순간 확정"
    t3 = CH.ChallengeTracker(goals)
    t3.tick(50.0, False, 1)                                    # 이미 탈락한 뒤에는 순위/생존이 갱신되지 않음
    assert t3.m["survive"] == 0.0 and t3.m["top"] == CH.TOP_INIT
    for _ in range(4):
        t.on_ko()
    t.on_attack(10, 2)
    t.on_attack(10, 1)
    assert "d_ko4" in t.done and t.m["sent_total"] == 30 and t.m["multi"] == 1 and t.m["sent_max"] == 10 and "d_sent30" in t.done
    t.on_clutch()
    assert "d_clutch1" in t.done
    # 증폭 상태 생존 시간(후반 가속)
    t4 = CH.ChallengeTracker(CH.WEEKLY_GOALS["rush"])
    for i in range(1, 80):
        t4.tick(100.0 + i, True, 50, multiplier=1.3 if i > 10 else 1.0)
    assert 60 <= t4.m["esc_survive"] <= 70 and "w_rs_1" in t4.done


def test_engine_reports_canceled_lines():
    from block_engine import BlockEngine
    e = BlockEngine(seed=1)
    e.grid = [[None] * 10 for _ in range(20)]
    for y in range(16, 20):                       # 맨 아래 4줄을 한 칸(x=0)만 비우고 채움
        for x in range(1, 10):
            e.grid[y][x] = "G"
    e.incoming_garbage = 3
    e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 1, -2, 16     # 세로 I를 x=0 칸에 떨어뜨림
    e.lock_down()
    info = e.last_clear_info
    assert info["cleared"] == 4 and info["canceled"] >= 1 and e.garbage_canceled_total == info["canceled"], info
    e2 = BlockEngine(seed=1)
    e2.current_piece, e2.current_rot, e2.current_x, e2.current_y = "O", 0, 3, 18
    e2.lock_down()
    assert e2.last_clear_info["canceled"] == 0


def test_stats_challenge_storage_and_streak():
    import stats_manager as SM
    d = tempfile.mkdtemp()
    st = SM.StatsManager(os.path.join(d, "s.json"))
    ids = st.daily_goal_ids("20261003")
    assert ids == CH.pick_daily("20261003") and st.daily_goal_ids("20261003") == ids, "한 번 정해지면 저장되어 유지"
    assert st.mark_challenges("daily", "20261003", [ids[0], ids[0], "bogus"]) == [ids[0]]
    assert st.daily_stars_today("20261003") == 1 and st.ch()["stars"]["daily"] == 1
    assert st.mark_challenges("daily", "20261003", [ids[0]]) == [], "중복 저장 없음"
    st.mark_challenges("daily", "20261004", [CH.pick_daily("20261004")[0]])
    st.mark_challenges("daily", "20261005", [CH.pick_daily("20261005")[0]])
    sc = st.ch()["daily_streak"]
    assert sc["cur"] == 3 and sc["best"] == 3 and sc["last"] == "20261005"
    st.mark_challenges("daily", "20261008", [CH.pick_daily("20261008")[0]])         # 이틀 건너뜀 -> 1로
    assert st.ch()["daily_streak"]["cur"] == 1 and st.ch()["daily_streak"]["best"] == 3
    st.mark_challenges("daily", "20261008", [CH.pick_daily("20261008")[1]])         # 같은 날 두 번째 별은 출석 중복 없음
    assert st.ch()["daily_streak"]["cur"] == 1
    # 연습/주간
    assert st.mark_challenges("practice", None, ["p_quad", "p_pc", "nope"]) == ["p_quad", "p_pc"]
    assert st.challenge_done("practice") == {"p_quad", "p_pc"}
    st.mark_challenges("weekly", "2026W40", ["w_fg_1"])
    st.mark_challenges("weekly", "2026W41", ["w_rs_1"])
    assert st.ch()["weekly_rules"] == ["fog", "rush"]
    c0 = st.ch()["stars"]
    assert c0 == {"daily": 5, "weekly": 2, "practice": 2} and st.stars_total() == 9, c0     # 일일 5(첫날 2+3일 하루 1씩) / 주간 2 / 연습 2
    # 저장/불러오기, 깨진 값 거르기
    st.save()
    st2 = SM.StatsManager(st.filepath)
    assert st2.challenge_done("practice") == {"p_quad", "p_pc"} and st2.ch()["daily"]["20261003"]["done"] == [ids[0]]
    raw = json.load(open(st.filepath, encoding="utf-8"))
    raw["challenges"] = {"practice": {"done": ["p_quad", "zzz", 5], "ta_best": -3}, "daily": {"x": {}, "20261010": {"ids": ["d_ko1", "q"], "done": ["d_ko1", "p_quad"], "tries": "a"}},
                         "weekly": {"2026W45": {"rule": "bad", "done": ["w_el_1", "d_ko1"]}}, "daily_streak": {"cur": "x", "best": 2, "last": "zz"},
                         "stars": {"daily": -1, "weekly": 2.9}, "weekly_rules": ["elite", "hax"]}
    json.dump(raw, open(st.filepath, "w", encoding="utf-8"))
    st3 = SM.StatsManager(st.filepath)
    c = st3.ch()
    assert c["practice"] == {"done": ["p_quad"], "ta_best": 0}
    assert c["daily"] == {"20261010": {"ids": ["d_ko1"], "done": ["d_ko1"], "tries": 0}}
    assert c["weekly"] == {"2026W45": {"rule": "", "done": ["w_el_1"]}}
    assert c["daily_streak"] == {"cur": 0, "best": 2, "last": ""} and c["stars"]["daily"] == 0 and c["stars"]["weekly"] == 2 and c["weekly_rules"] == ["elite"]
    # 키가 없는 예전 파일 / 전적 초기화
    del raw["challenges"]
    json.dump(raw, open(st.filepath, "w", encoding="utf-8"))
    assert SM.StatsManager(st.filepath).ch()["practice"]["done"] == []
    st3.reset_stats()
    assert st3.ch()["stars"] == {"daily": 0, "weekly": 0, "practice": 0}
    # 30일/20주 정리
    st4 = SM.StatsManager(os.path.join(d, "t.json"))
    for i in range(35):
        st4.daily_goal_ids((datetime.date(2026, 1, 1) + datetime.timedelta(days=i)).strftime("%Y%m%d"))
    assert len(st4.ch()["daily"]) == 30
    print("  OK storage")


def test_challenge_achievements_and_skin_unlock():
    import stats_manager as SM
    d = tempfile.mkdtemp()
    st = SM.StatsManager(os.path.join(d, "s.json"))
    assert len(SM.ACHIEVEMENTS) == 14
    st.mark_challenges("practice", None, CH.PRACTICE_IDS)
    assert "practice_all" in st.data["achievements"], "연습 12개 완료 -> 수련 완료 (경기 기록 없이도 판정)"
    for i, rule in enumerate(CH.WEEKLY_GOALS):
        st.mark_challenges("weekly", f"2026W{10 + i}", [CH.WEEKLY_GOALS[rule][0]["id"]])
    assert "variant_master" in st.data["achievements"]
    st.ch()["stars"]["daily"] = 29
    st.mark_challenges("daily", "20261003", [st.daily_goal_ids("20261003")[0]])
    assert "star_collector" in st.data["achievements"]
    assert "starlight" not in SM.unlocked_skin_ids(st.data)
    st.ch()["stars"]["weekly"] = 60
    assert SM.unlocked_skin_ids(st.data).count("starlight") == 1
    from settings_manager import BLOCK_SKIN_OPTIONS
    assert "starlight" in BLOCK_SKIN_OPTIONS
    app = _app()
    app.renderer._cell_surface("T", 20, skin="starlight")     # 새 스킨도 예외 없이 그려짐
    print("  OK rewards")


def test_practice_flow_ta_and_save():
    app = _app()
    app.stats_mgr.data.pop("challenges", None)
    app.start_game(mode="SOLO", practice=True)
    m = app.match
    m.countdown_until = 0.0
    assert m.challenge is not None and m.challenge_kind == "practice" and m.practice_current_task()[0] == 0
    # N 키: 다음 과제로 넘김 (조작키로 쓰지 않는 키일 때)
    app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=0, unicode="n", scancode=0))
    assert m.practice_current_task()[0] == 1
    app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=pygame.KMOD_SHIFT, unicode="N", scancode=0))
    assert m.practice_current_task()[0] == 0
    m.on_lines_cleared  # (엔진 없이 직접 이벤트를 넣어 판정)
    m._practice_check({"cleared": 4, "combo": 0})
    app._tick_game(1 / 60)
    assert "p_quad" in app.stats_mgr.challenge_done("practice"), "달성한 과제는 저장됨"
    assert any("과제 완료" in f["text"] for f in m.floating_texts)
    # 보드를 리셋해도 진행도 유지
    m.practice_reset()
    assert "p_quad" in m.challenge.done
    # 새 연습 판에서도 저장된 달성분이 이어짐
    app.start_game(mode="SOLO", practice=True)
    assert "p_quad" in app.match.challenge.done
    # 모두 깨면 타임어택
    m = app.match
    m.challenge.done = set(m.challenge.order)
    m._practice_check({"cleared": 1})
    assert m.ta_t0 is not None
    for _ in range(CH.TA_QUADS):
        m.elapsed += 5.0
        m._practice_check({"cleared": 4})
    assert m.ta_last and m.ta_best == m.ta_last
    app._tick_game(1 / 60)
    assert app.stats_mgr.ch()["practice"]["ta_best"] == m.ta_best
    app.renderer.render(m)
    print("  OK practice")


def test_daily_and_weekly_hookup_hud_result_and_restart():
    app = _app()
    app.stats_mgr.data.pop("challenges", None)
    app.start_game(mode="SOLO", daily="20261003")
    m = app.match
    m.countdown_until = 0.0
    assert m.challenge_kind == "daily" and m.challenge.order == CH.pick_daily("20261003") and not m.brief_open, "헤드리스에서는 브리핑 생략"
    random_state = random.getstate()
    app.start_game(mode="SOLO", daily="20261003")
    q1 = list(app.match.local_engine.next_queue)
    app.start_game(mode="SOLO", daily="20261003")
    assert list(app.match.local_engine.next_queue) == q1, "같은 날 같은 블록 순서"
    m = app.match
    m.countdown_until = 0.0
    # 목표 하나 달성 -> 저장/알림, HUD/결과 요약
    gid = m.challenge.order[0]
    g = m.challenge.by_id[gid]
    m.challenge.m[g["metric"]] = g["goal"] if g["op"] == ">=" else g["goal"]
    m.challenge._check()
    m._challenge_events()
    app._tick_game(1 / 60)
    assert gid in app.stats_mgr.challenge_done("daily", "20261003") and app.stats_mgr.daily_stars_today("20261003") == 1
    app.renderer.render(m)
    s_long, s_short = m.challenge_summary()
    assert "오늘의 도전 ★" in s_long and s_short.endswith("1/3"), (s_long, s_short)
    m.local_is_alive = False
    m.local_rank = 40
    m.match_finished = True
    app.renderer.render(m)                                     # 결과 오버레이/순위표(요약 줄 포함)도 예외 없이
    # 재도전은 브리핑 없이 같은 도전, 달성한 별은 유지
    app.match.match_finished = True
    app._restart_after_match()
    assert app.match.challenge_kind == "daily" and gid in app.match.challenge.done and not app.match.brief_open
    # 주간
    import config
    app.start_game(mode="SOLO", weekly=(config.week_key(), "fog"))
    w = app.match
    assert w.challenge_kind == "weekly" and w.challenge.order == [g["id"] for g in CH.WEEKLY_GOALS["fog"]]
    w.countdown_until = 0.0
    w.challenge.on_clear({"cleared": 4})
    w.challenge.m["lines"] = 30
    w.challenge._check()
    w._challenge_events()
    app._tick_game(1 / 60)
    assert "w_fg_1" in app.stats_mgr.challenge_done("weekly", config.week_key())
    app.renderer.render(w)
    print("  OK daily/weekly")


def test_brief_card_flow():
    app = _app()
    app.start_game(mode="SOLO", daily="20261003")
    m = app.match
    m.brief_open = True                                        # 실제 실행에서는 start_game이 켜 줌 (헤드리스는 생략)
    t0 = m.elapsed
    for _ in range(5):
        app._tick_game(1 / 60)
    assert m.elapsed == t0, "브리핑이 열려 있는 동안 경기는 진행되지 않음"
    app._render_brief()
    app._handle_brief_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" "))
    assert not m.brief_open and m.countdown_left() > 2.0, "아무 키나 누르면 카운트다운 시작"
    import config
    app.start_game(mode="SOLO", weekly=(config.week_key(), "rush"))
    app.match.brief_open = True
    app._render_brief()
    app._handle_brief_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
    assert app.state == "MENU", "ESC는 시작하지 않고 메뉴로"
    print("  OK brief")


def test_weekly_rotation_and_rules_card_follow_mutator():
    import config
    from screens.rules import rules_card_data, rules_card_notes
    mondays = [datetime.date(2026, 12, 21) + datetime.timedelta(weeks=i) for i in range(8)]       # 연말(2026W52~2027W06) 포함
    ids = [config.weekly_mutator(d)["id"] for d in mondays]
    assert all(a != b for a, b in zip(ids, ids[1:])), ids
    assert config.weekly_mutator(datetime.date(2026, 12, 28))["id"] != config.weekly_mutator(datetime.date(2027, 1, 4))["id"], "2026W53과 2027W01이 같은 규칙이면 안 됨"
    app = _app()
    app.start_game(mode="SOLO", weekly=("2026W40", "perfect"))
    row = dict(dict(rules_card_data(app.match))["공격 줄 수"])
    assert any(k.startswith("퍼펙트 클리어") and v == "+20줄" for k, v in row.items()), row
    app.start_game(mode="SOLO", weekly=("2026W40", "rush"))
    assert "2분부터" in " ".join(rules_card_notes(app.match))
    app.start_game(mode="SOLO", total_players=4)
    assert "5분부터" in " ".join(rules_card_notes(app.match))
    # 후반 가속 예고 문구도 실제 시작 시각을 씀
    app.start_game(mode="SOLO", weekly=("2026W40", "rush"))
    m = app.match
    m.elapsed = 100.0
    m._announce_escalation()
    assert any("2분부터" in c["text"] for c in m.commentary), [c["text"] for c in m.commentary]
    print("  OK rotation/rules")


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
        print("[ALL CHALLENGE TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
