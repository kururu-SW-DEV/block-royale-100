"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트 - 저장 데이터: 전적 모드 분리/크기 구간/필터, 설정·전적 파일 손상 복구, 업적
(예전 test_review_fixes.py를 영역별로 나눈 파일. 실행: python test_review_data.py, SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
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


def test_stats_split_by_mode():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "stats.json")
        st = StatsManager(tp)
        st.record_match(1, 10, 3, 20, 4, 100)                       # 기본 = 배틀로얄
        st.record_match(5, 30, 0, 50, 6, 400, mode="survival")
        st.record_match(2, 30, 0, 10, 2, 60, mode="survival")
        b, sv = st.get_summary("battle"), st.get_summary("survival")
        assert (b["total_games"], b["victories"], b["total_kos"]) == (1, 1, 3)
        assert (sv["total_games"], sv["victories"], sv["best_rank_str"], sv["total_lines"]) == (2, 0, "#2위", 60)
        assert len(b["recent_matches"]) == 1 and len(sv["recent_matches"]) == 2
        st2 = StatsManager(tp)                                       # 재로드해도 분리 유지
        assert st2.get_summary("survival")["total_games"] == 2 and st2.get_summary()["total_games"] == 1
        # 예전 형식(survival 키 없음) 파일 호환 + 잘못된 survival 값 무시
        with open(tp, "w", encoding="utf-8") as f:
            json.dump({"total_games": 7, "survival": "oops"}, f)
        st3 = StatsManager(tp)
        assert st3.get_summary()["total_games"] == 7 and st3.get_summary("survival")["total_games"] == 0
        st3.reset_stats()
        assert st3.get_summary()["total_games"] == 0 and st3.get_summary("survival")["total_games"] == 0
    # 실제 게임 종료 시 모드별 집계
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    rec = []
    app.stats_mgr.record_match = lambda **kw: rec.append(kw["mode"])
    for atk, want in ((False, "survival"), (True, "battle")):
        app.settings.data["game_mode"] = "battle" if atk else "survival"
        app.start_game(mode="SOLO", total_players=4)
        app.match.local_is_alive = False
        app._tick_game(1 / 60)
        assert rec and rec[-1] == want, (atk, rec)
    print("  OK stats split by game mode")


def test_settings_and_stats_corruption():
    with tempfile.TemporaryDirectory() as d:
        sp = os.path.join(d, "settings.json")
        with open(sp, "w", encoding="utf-8") as f:
            json.dump({"bgm_volume": "60", "target_player_count": "many", "sfx_volume": 500, "custom_keys": {"hold": 5},
                       "bot_difficulty": "godlike", "fullscreen": "yes", "player_name": "Zed"}, f)
        s = SettingsManager(sp)
        assert s.get("bgm_volume") == 60 and s.get("target_player_count") == 100 and s.get("sfx_volume") == 100
        assert s.get("custom_keys") is None and s.get("bot_difficulty") == "mixed" and s.get("fullscreen") is False
        assert s.get("player_name") == "Zed"
        with open(sp, "w", encoding="utf-8") as f:
            f.write("{broken json")
        SettingsManager(sp)
        assert any(n.startswith("settings.json.corrupt-") for n in os.listdir(d)), "손상 파일 백업 없음"

        tp = os.path.join(d, "stats.json")
        with open(tp, "w", encoding="utf-8") as f:
            json.dump({"total_games": "x", "victories": 3, "recent_matches": "oops"}, f)
        st = StatsManager(tp)
        assert st.data["total_games"] == 0 and st.data["victories"] == 3 and st.data["recent_matches"] == []
        st.record_match(1, 10, True, 2, 30, 2, 55) if False else None
        with open(tp, "w", encoding="utf-8") as f:
            f.write("[1,2]")
        StatsManager(tp)
        assert any(n.startswith("stats.json.corrupt-") for n in os.listdir(d))
        # 기본값 리스트를 공유하지 않는지
        a, b = StatsManager(os.path.join(d, "a.json")), StatsManager(os.path.join(d, "b.json"))
        a.data["recent_matches"].append({"x": 1})
        assert b.data["recent_matches"] == []
    print("  OK settings/stats validation + backup")


def test_stats_size_buckets_filter_and_goal():
    """전적: 최고 순위/기록 갱신은 인원 규모별로 따로 비교, 필터 요약, 다음 목표 문구, 예전 전적 파일 호환"""
    import json as _json
    from stats_manager import size_bucket, next_goal_text, SIZE_BUCKET_IDS
    assert [size_bucket(n) for n in (2, 10, 11, 49, 50, 100)] == ["small", "small", "mid", "mid", "large", "large"]
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "s.json")
        st = StatsManager(f)
        kw = dict(kos=0, lines=5, max_combo=0, survival_sec=30)
        assert st.record_match(rank=50, total_players=100, difficulty="hard", **kw) == []
        assert st.record_match(rank=3, total_players=6, difficulty="easy", **kw) == [], "다른 규모의 첫 경기는 순위 기록 갱신이 아님"
        assert st.record_match(rank=20, total_players=100, difficulty="hard", **kw) == ["rank"], "같은 규모(대)에서 50위 -> 20위"
        assert st.record_match(rank=90, total_players=100, difficulty="master", **kw) == []
        assert st.record_match(rank=2, total_players=6, difficulty="easy", **kw) == ["rank"], "소규모에서 3위 -> 2위"
        assert st.best_in_size("battle", 100) == 20 and st.best_in_size("battle", 6) == 2 and st.best_in_size("battle", 30) == 0
        full = st.get_summary("battle")
        assert full["filtered"] is False and full["total_games"] == 5
        big = st.get_summary("battle", size="large")
        assert big["filtered"] and big["total_games"] == 3 and big["best_rank"] == 20
        hard = st.get_summary("battle", difficulty="hard")
        assert hard["total_games"] == 2 and hard["best_rank"] == 20
        both = st.get_summary("battle", size="small", difficulty="hard")
        assert both["total_games"] == 0 and both["best_rank_str"] == "-"
        st2 = StatsManager(f)                                          # 저장/재로드 후에도 규모별 기록 유지
        assert st2.best_in_size("battle", 100) == 20
        # 예전 전적 파일(best_by_size 없음)은 최근 경기 목록으로 채움
        old = {"total_games": 2, "best_rank": 7, "recent_matches": [
            {"rank": 30, "total_players": 100}, {"rank": 7, "total_players": 100}]}
        _json.dump(old, open(f, "w"))
        st3 = StatsManager(f)
        assert st3.best_in_size("battle", 100) == 7
        assert st3.record_match(rank=5, total_players=100, **kw) == ["rank"]
    assert SIZE_BUCKET_IDS == ("small", "mid", "large")
    # 난이도 사다리: 배틀로얄 50인 이상에서 10위 안이면 그 난이도 클리어 (혼합/서바이벌/소규모는 제외), 목표 문구
    from stats_manager import LADDER
    with tempfile.TemporaryDirectory() as d2:
        f2 = os.path.join(d2, "l.json")
        sl = StatsManager(f2)
        kw2 = dict(kos=0, lines=5, max_combo=0, survival_sec=30)
        sl.record_match(rank=8, total_players=100, difficulty="mixed", **kw2)
        assert sl.last_ladder_clear is None and sl.ladder_cleared() == []
        sl.record_match(rank=8, total_players=20, difficulty="easy", **kw2)
        assert sl.last_ladder_clear is None, "50인 미만은 사다리 대상 아님"
        sl.record_match(rank=8, total_players=100, difficulty="easy", mode="survival", **kw2)
        assert sl.ladder_cleared() == [], "서바이벌은 사다리 대상 아님"
        sl.record_match(rank=11, total_players=100, difficulty="easy", **kw2)
        assert sl.ladder_cleared() == []
        sl.record_match(rank=10, total_players=100, difficulty="easy", **kw2)
        assert sl.last_ladder_clear == "easy" and sl.ladder_cleared() == ["easy"]
        sl.record_match(rank=3, total_players=100, difficulty="easy", **kw2)
        assert sl.last_ladder_clear is None, "이미 클리어한 난이도는 다시 알리지 않음"
        assert StatsManager(f2).ladder_cleared() == ["easy"], "저장/재로드 유지"
        _json.dump({"ladder": ["master", "bogus", "easy"]}, open(f2, "w"))
        assert StatsManager(f2).ladder_cleared() == ["easy", "master"], "알려진 난이도만, 쉬움->마스터 순"
    assert next_goal_text(8, 3, 100, 8, difficulty="easy", cleared=["easy"], ladder_clear="easy") == "쉬움 클리어! 다음은 보통에 도전"
    assert next_goal_text(8, 3, 100, 8, difficulty="master", cleared=list(LADDER), ladder_clear="master") == "마스터 클리어! 모든 난이도 클리어"
    assert next_goal_text(37, 5, 100, 12, difficulty="hard", cleared=[]) == "어려움 클리어까지 27계단 (10위 안)"
    assert next_goal_text(37, 5, 100, 12, difficulty="hard", cleared=["hard"]) == "최고 순위 #12까지 25계단"
    assert next_goal_text(37, 5, 20, 12, difficulty="hard", cleared=[]) == "최고 순위 #12까지 25계단", "50인 미만은 난이도 목표 없음"
    # 다음 목표 문구 (배지 다음 단계가 2 K.O. 이내면 그것을, 아니면 순위 목표)
    assert next_goal_text(51, 1, 100, 28) == "배지 Lv.1까지 1 K.O."
    assert next_goal_text(51, 5, 100, 28) == "최고 순위 #28까지 23계단"
    assert next_goal_text(8, 5, 100, 8) == "5위 안 진입"
    assert next_goal_text(20, 5, 100, 20) == "10위 안 진입"
    assert next_goal_text(3, 5, 100, 3) == "우승"
    assert next_goal_text(1, 20, 100, 1) == "우승 연속 도전"
    print("  OK stats size buckets / filter / next goal")


def test_achievements():
    """업적: 조건 달성 시 한 번만 기록되고 저장/불러오기와 초기화가 되며, 서바이벌 경기와는 무관, 결과/전적 화면이 그려짐"""
    import tempfile
    from stats_manager import StatsManager, ACHIEVEMENTS, ACHIEVEMENT_IDS
    path = os.path.join(tempfile.mkdtemp(), "stats.json")
    sm = StatsManager(path)
    assert len(ACHIEVEMENTS) == 14 and len(set(ACHIEVEMENT_IDS)) == 14      # 11번째 복수의 화신, 12~14번째 도전 과제 업적(별 수집가/변형 정복자/수련 완료)
    sm.record_match(40, 100, 0, 5, 1, 60)
    assert sm.last_new_achievements == [] and sm.achievements_done() == []
    sm.record_match(1, 100, 6, 50, 3, 300)
    assert sm.last_new_achievements == ["first_ko", "top10", "victory", "century", "ko5"], sm.last_new_achievements
    sm.record_match(1, 100, 6, 50, 3, 300)
    assert sm.last_new_achievements == [], "이미 달성한 업적은 다시 알리지 않음"
    sm.record_match(30, 50, 12, 90, 9, 700, mode="survival")             # 서바이벌 경기는 업적과 무관
    assert sm.achievements_done() == ["first_ko", "top10", "victory", "century", "ko5"]
    sm.record_match(9, 40, 10, 90, 8, 650)
    assert set(sm.last_new_achievements) == {"ko10", "combo8", "marathon"}
    sm2 = StatsManager(path)                                             # 저장 후 다시 불러와도 유지
    assert sm2.achievements_done() == sm.achievements_done() and len(sm2.achievements_done()) == 8
    d = json.load(open(path, encoding="utf-8"))
    d["achievements"] = ["victory", "없는업적", 5]                        # 손상/알 수 없는 값은 걸러냄
    json.dump(d, open(path, "w", encoding="utf-8"))
    assert StatsManager(path).achievements_done() == ["victory"]
    for i in range(3):                                                    # 오늘의 도전 3일 + 사다리 4단계
        sm.record_match(5, 100, 0, 5, 1, 60, daily=f"2026090{i + 1}")
    assert "daily3" in sm.achievements_done()
    for dn in ("easy", "normal", "hard", "master"):
        sm.record_match(5, 100, 0, 5, 1, 60, difficulty=dn)
    assert "ladder_all" in sm.achievements_done()
    sm.reset_stats()
    assert sm.achievements_done() == []

    # 전적 화면의 업적 탭 / 결과 화면의 업적 줄이 오류 없이 그려짐
    import main as M
    app = M.BlockRoyaleApp()
    app.stats_mgr.reset_stats()
    app.stats_mgr.record_match(1, 100, 6, 50, 3, 300)
    app.state = "RECORDS"
    for mode in ("achv", "trend", "survival", "battle"):
        app.records_mode = mode
        app._render_records()
    order = []
    for _ in range(4):
        app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0, unicode=""))
        order.append(app.records_mode)
    assert order == ["survival", "trend", "achv", "battle"], order


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
        print("[ALL REVIEW DATA TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)
