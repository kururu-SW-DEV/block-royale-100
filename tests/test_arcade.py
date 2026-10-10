"""
아케이드 연출/메타 테스트 (v1.1.11): 랭크 글자, 점수표/이니셜/오늘 첫 판/연승/골든 타깃 경험치, 점수 팝업과 굴러가는 점수, 콤보 게이지,
줌 펀치/집중선, 결과 화면(랭크 도장/점수 줄/XP 칩), 점수표 탭, 어트랙트 화면, 골든 타깃 교체, 기록 근접/돌파 알림,
콤보 음악 층, 아나운서 설정과 쿨다운.
실행: python test_arcade.py
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
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    from stats_manager import DEFAULT_STATS
    import copy
    app.stats_mgr.data = copy.deepcopy(DEFAULT_STATS)
    app.stats_mgr.data["survival"] = copy.deepcopy(DEFAULT_STATS)
    return app


def _game(app, n=20):
    app.start_game(mode="SOLO", total_players=n)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(5):
        app._tick_game(1 / 60)
    return m, m.local_engine, app.renderer


def _quad(e):
    from config import BOARD_HEIGHT
    for y in range(BOARD_HEIGHT - 4, BOARD_HEIGHT):
        e.grid[y] = ["L", "J", "S", "Z", "O", "T", "I", "L", "J", None]
    e.current_piece = "I"
    for rot in range(4):
        bl = e._get_blocks("I", rot, 0, 0)
        xs = {x for x, _ in bl}
        if len(xs) == 1:
            e.current_rot, e.current_x, e.current_y = rot, 9 - list(xs)[0], 0
            return


def test_grade_letters():
    from stats_manager import calc_grade
    assert calc_grade(1, 100, kos=8, sent=50, defended=20, highlights=2) == "S+"
    assert calc_grade(1, 100) == "S"
    assert calc_grade(4, 100) == "S"                       # 상위 5%
    assert calc_grade(12, 100) == "A"
    assert calc_grade(35, 100) == "B"
    assert calc_grade(60, 100) == "C"
    assert calc_grade(95, 100) == "D"
    assert calc_grade(95, 100, kos=6, sent=40, defended=20) == "C", "공격/K.O./방어가 좋으면 한 단계 위"
    print("  OK 랭크 글자")


def test_record_match_score_table_bonuses_and_validation():
    from stats_manager import StatsManager, insert_hiscore
    sm = StatsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    sm.record_match(rank=5, total_players=100, kos=3, lines=40, max_combo=4, survival_sec=200, score=12000, initials="kur", sent=20, defended=5, bounties=2)
    parts = dict(sm.last_xp["parts"])
    assert "오늘 첫 판" in parts and parts["골든 타깃"] == 60, parts
    assert sm.last_grade in ("S", "A")
    assert sm.last_score["place"] == 1 and not sm.last_score["best"], "첫 판은 '개인 최고 갱신' 표시를 하지 않음"
    sm.record_match(rank=3, total_players=100, kos=5, lines=60, max_combo=6, survival_sec=300, score=30000, initials="kur")
    assert "오늘 첫 판" not in dict(sm.last_xp["parts"]), "같은 날 두 번째 판"
    assert sm.last_score["best"] and sm.last_score["place"] == 1
    assert "TOP 10 2연속" in dict(sm.last_xp["parts"]), dict(sm.last_xp["parts"])
    sm.record_match(rank=60, total_players=100, kos=0, lines=5, max_combo=1, survival_sec=30, score=500)
    assert sm.data["top10_streak"] == 0
    table = sm.data["hiscores"]["large"]
    assert [e["score"] for e in table] == [30000, 12000, 500] and table[0]["ini"] == "KUR"
    t = []
    for i in range(12):
        insert_hiscore(t, {"score": i * 10})
    assert len(t) == 10 and t[0]["score"] == 110
    sm.save()
    sm2 = StatsManager(sm.filepath)
    assert sm2.data["hiscores"]["large"][0]["score"] == 30000 and sm2.data["best_score"] == 30000
    sm2.data["hiscores"] = {"large": [{"score": "x"}, {"score": 5, "rank": 1, "total": 2, "kos": 0, "ini": "ABCDE", "date": "d"}], "bogus": []}
    sm2.save()
    sm3 = StatsManager(sm.filepath)
    assert sm3.data["hiscores"] == {"large": [{"score": 5, "rank": 1, "total": 2, "kos": 0, "ini": "ABC", "date": "d"}]}, sm3.data["hiscores"]
    print("  OK 점수표/보너스/검증")


def test_score_popups_rolling_score_gauge_and_big_move_fx():
    app = _app()
    m, e, r = _game(app)
    r.render(m)
    _quad(e)
    m.on_lines_cleared(e.hard_drop())
    r.render(m)
    assert r.score_pops and r.score_pops[-1]["n"] >= 100 and r._score_disp < e.score, "점수는 굴러 올라감"
    for _ in range(300):
        time.sleep(0.005)
        r.render(m)
        if abs(r._score_disp - e.score) < 5:
            break
    assert abs(r._score_disp - e.score) < 5, (r._score_disp, e.score)
    assert r.zoom_t0 > 0 and time.time() - r.speed_lines_t0 < 5, "쿼드: 줌 펀치와 집중선"
    r._render_speed_lines(0, 0)
    r._apply_zoom_punch(0, 0)
    e.combo = 9
    r.render(m)                                            # 콤보 게이지(RUSH)
    m.shake_scale = 0.0
    zt = r.zoom_t0
    r.zoom_t0 = -9.0
    _quad(e)
    m.on_lines_cleared(e.hard_drop())
    r.render(m)
    assert r.zoom_t0 == -9.0, "흔들림 '끔'이면 줌/집중선 없음"
    print("  OK 점수 팝업/게이지/줌 펀치")


def test_result_screens_show_grade_score_and_xp_chips():
    app = _app()
    m, e, r = _game(app)
    ids = [pid for pid in m.players if pid != m.local_player_id]
    m._eliminate_player(m.local_player_id, ids[0])
    m.reward = {"xp": {"gain": 120, "parts": [("참가", 20), ("순위", 40), ("오늘 첫 판", 60)], "before": 0, "after": 120, "lv_before": 1, "lv_after": 2},
                "highlights": [], "unlocks": [], "next_unlock": None, "grade": "A", "score": {"score": 12345, "place": 2, "best": False}}
    r.render(m)
    seen = []
    orig, orig_fade = r._draw_text, r._fade_text
    r._draw_text = lambda text, *a, **k: (seen.append(text), orig(text, *a, **k))[1]
    r._fade_text = lambda text, *a, **k: (seen.append(text), orig_fade(text, *a, **k))[1]
    r._res_t0 -= 5
    r._result_t0 = time.time() - 6
    r.render(m)
    assert any(str(t).startswith("SCORE") for t in seen) and "RANK" in seen, seen[:40]
    assert not any("…" in str(t) for t in seen), "결과 창은 글을 '…'로 자르지 않음"
    r._draw_text, r._fade_text = orig, orig_fade
    lines = r._standings_info_lines(m)
    assert any("랭크 A" in t and "12,345" in t and "점수표 #2" in t for t, _c in lines), lines
    print("  OK 결과 화면")


def test_score_tab_and_attract_screen():
    app = _app()
    app.stats_mgr.data["hiscores"] = {"large": [{"score": 9000 - i, "rank": 3, "total": 100, "kos": 2, "ini": "KUR", "date": "10-04 12:00"} for i in range(5)]}
    app.stats_mgr.data["best_score"] = 9000
    app.state, app.records_mode = "RECORDS", "score"
    app._render_records()
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3, mod=0, unicode="3"))
    app._render_records()
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0, unicode=""))
    assert app.records_mode == "replay"
    app._handle_records_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0, unicode=""))
    assert app.records_mode == "achv"
    app.state = "MENU"
    app._idle_t = time.time()
    assert not app._attract_on()
    app._idle_t = time.time() - 60
    assert app._attract_on()
    for _ in range(5):
        app._update_menu(1 / 60)
        app._render_menu()
        app._render_attract(1 / 60)
    assert app._attract is not None and len(app._attract["bots"]) == 2
    app._attract_reset()
    assert not app._attract_on()
    app.modal = {"buttons": []}
    app._idle_t = time.time() - 60
    assert not app._attract_on(), "알림 창이 떠 있으면 어트랙트는 켜지지 않음"
    app.modal = None
    print("  OK 점수표 탭/어트랙트")


def test_golden_target_and_record_toasts():
    app = _app()
    m, e, r = _game(app, 30)
    first = m.bounty_id
    assert first is not None
    m.bounty_claimed = True
    m._new_golden_target()
    assert m.bounty_id != first and not m.bounty_claimed and m.players[m.bounty_id]["is_alive"]
    texts = lambda: [f["text"] for f in m.floating_texts]
    assert any("골든 타깃" in t for t in texts())
    m.bests = {"max_ko": 4, "best_rank": 6, "best_score": 100}
    m.local_ko_count = 3
    m._check_kill_records()
    assert any("1명" in t for t in texts())
    m.local_ko_count = 5
    m._check_kill_records()
    assert any("돌파" in t for t in texts())
    m._check_rank_records(6)
    assert any("타이" in t for t in texts())
    m._check_rank_records(5)
    assert any("최고 순위 갱신" in t for t in texts())
    n = len(m.floating_texts)
    m._check_rank_records(5)
    assert len(m.floating_texts) == n, "같은 알림은 한 번만"
    e.score = 500
    m._check_score_record()
    assert any("최고 점수" in t for t in texts())
    print("  OK 골든 타깃/기록 알림")


def test_combo_layer_and_announcer_settings():
    app = _app()
    m, e, r = _game(app)
    calls = []
    m.sound_mgr.set_combo_layer = lambda lvl: calls.append(lvl)
    m._layer_seen = -1
    e.combo = 9
    m.update(0.01)
    e.combo = -1
    m.update(0.01)
    assert calls[:2] == [2, 0], calls
    del m.sound_mgr.set_combo_layer                         # 진짜 메서드로 되돌림
    sm = app.sound_mgr
    sm.bgm_enabled = True
    if not sm.enabled:
        print("  (오디오 없음: 아나운서 검사 생략)")
        return
    sm.sfx_enabled, sm.sfx_volume = True, 0.7
    sm.set_announcer(False)
    sm._vo_last = 0.0
    sm.play("vo_quad")
    assert sm._vo_last == 0.0, "설정이 꺼져 있으면 재생하지 않음"
    sm.set_announcer(True)
    sm.play("vo_quad")
    t1 = sm._vo_last
    assert t1 > 0
    sm.play("vo_combo")
    assert sm._vo_last == t1, "0.8초 쿨다운"
    assert all(k in sm.sounds for k in ("vo_quad", "vo_tspin", "vo_combo", "vo_perfect", "vo_bounty", "vo_final", "vo_top10", "vo_golden", "combo_layer"))
    sm.set_combo_layer(2)
    for _ in range(40):
        sm.tick()
    assert sm._layer_vol > 0.05
    sm.set_combo_layer(0)
    for _ in range(40):
        sm.tick()
    assert sm._layer_vol == 0.0
    # 설정 화면 토글
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "audio", "MENU"
    app._render_settings()
    before = app.settings.get("announcer", False)
    app._settings_activate("announcer_toggle")
    assert app.settings.get("announcer") != before and sm.announcer == (not before)
    app._settings_activate("announcer_toggle")
    print("  OK 콤보 층/아나운서")


def test_result_window_layout_has_no_overlap_and_fits():
    app = _app()
    m, e, r = _game(app, 99)
    ids = [pid for pid in m.players if pid != m.local_player_id]
    m.timeline = [(i, 99 - i // 4, 3 + (i * 0.3) % 12, (i // 7) % 4) for i in range(80)]
    m._eliminate_player(m.local_player_id, ids[0])
    parts = [("참가", 20), ("순위", 49), ("K.O.", 16), ("생존", 16), ("오늘 첫 판", 101), ("TOP 10 3연속", 30), ("골든 타깃", 30)]
    m.reward = {"xp": {"gain": 262, "parts": parts, "before": 120, "after": 382, "lv_before": 4, "lv_after": 5},
                "highlights": ["perfect", "chain_ko", "combo10", "bounty"], "unlocks": ["불씨", "프리즘"], "next_unlock": None,
                "grade": "A", "score": {"score": 48210, "place": 1, "best": True}}
    m.new_achievements = ["first_ko", "ko5", "top10", "combo8"]
    m.new_records = ["rank", "ko", "combo"]
    m.next_goal = "열기 Lv.2까지 2 K.O."
    for boost in (0, 2):
        r.set_text_boost(boost)
        L = r._result_layout(m, 760)
        assert L["card_y"] + 76 < L["sum_y"] < L["sum_y"] + L["sum_h"] < L["adv_y"] < L["adv_y"] + L["adv_h"] < L["btn_y"] < L["foot_y"] < L["box_h"], L
        assert L["box_h"] <= r.height - 24, (boost, L["box_h"])
        assert len(L["chip_lines"]) <= 3
        for kind, lines, _c in L["adv"]:
            assert all("…" not in ln for ln in lines)
            if kind != "lead":
                assert all(r.font_small.size(ln)[0] <= L["cont"] - 40 for ln in lines), "줄바꿈으로 폭 안에 들어감"
        r._res_t0 = time.time() - 6
        r._result_t0 = time.time() - 6
        r.render(m)
    r.set_text_boost(0)
    # 랭크 도장(72x72, 왼쪽)과 그래프(208x72, 오른쪽), 제목 가운데 영역이 서로 겹치지 않는 고정 배치
    stamp, graph = pygame.Rect(24, 20, 72, 72), pygame.Rect(760 - 24 - 208, 20, 208, 72)
    title = pygame.Rect(0, 24, r.font_title.size("K.O.  경기 탈락")[0], r.font_title.get_height())
    title.centerx = 380
    assert not stamp.colliderect(graph) and not stamp.colliderect(title) and not graph.colliderect(title)
    print("  OK 결과 창 배치")


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
        print("[ALL ARCADE TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
