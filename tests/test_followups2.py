"""
v1.4.40 후속 점검 테스트: 일시정지 뒤 박자 시계, 글로우 스프라이트 LRU, 창 크기 변경 시 배경 장식 다시 미리 굽기와 성운 계산 상한,
전체 화면 장면 캐시 비우기, 테스트가 환경변수를 지우지 않음, 봇 B2B 연쇄 인식, 빛 연출 상태 안내, 진단 정보 복사,
설정 파일 형식 버전, 결과 화면 코드 분리.
실행: python tests/test_followups2.py
"""
import json
import os
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


def _game(app, n=20):
    app.start_game(mode="SOLO", total_players=n)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    return m


def test_beat_clock_stops_while_music_is_paused():
    app = _app()
    sm = app.sound_mgr
    sm._beat = (120.0, time.time() - 0.25)                 # 120BPM, 0.25초 지남 = 위상 0.5
    sm.is_bgm_playing, sm.bgm_enabled, sm._bgm_paused = True, True, False
    p0 = sm.beat_phase()[0]
    sm.pause_bgm()
    t_before = sm._beat[1]
    time.sleep(0.3)                                        # 일시정지 중 0.3초가 지나감
    sm.unpause_bgm()
    assert sm._beat[1] - t_before >= 0.29, "재개할 때 시작 시각을 멈춘 시간만큼 뒤로 미룸"
    p1 = sm.beat_phase()[0]
    assert abs(((p1 - p0 + 0.5) % 1.0) - 0.5) < 0.08, (p0, p1)      # 멈춘 자리에서 이어짐 (박자 어긋남 없음)
    sm.pause_bgm()
    sm.pause_bgm()                                         # 두 번 눌러도 멈춘 시각이 덮어써지지 않음
    sm.unpause_bgm()


def test_glow_sprite_cache_is_lru_and_keeps_big_ones_in_use():
    import ui_glow
    ui_glow._SPRITES.clear()
    big = ui_glow.glow_sprite("orb", 900, 300, (110, 90, 230), 2)          # 메인 화면 로고 후광처럼 큰 것
    for i in range(ui_glow._MAX_SPRITES + 60):
        ui_glow.glow_sprite("band", 20 + i % 7, 10 + i, (i % 255, 1, 2), 0)
        ui_glow.glow_sprite("orb", 900, 300, (110, 90, 230), 2)             # 계속 쓰이는 큰 스프라이트
    assert len(ui_glow._SPRITES) <= ui_glow._MAX_SPRITES
    assert ui_glow.glow_sprite("orb", 900, 300, (110, 90, 230), 2) is big, "계속 쓰는 큰 스프라이트는 캐시가 넘쳐도 다시 만들지 않음 (전에는 전부 비웠음)"


def test_trail_heights_are_bucketed_to_few_sprites():
    app = _app()
    m = _game(app)
    import ui_glow
    r = app.renderer
    m.visual_fx = "normal"
    ui_glow._SPRITES.clear()
    cs = r.cell_size
    for cells in range(1, 21):
        tr = {"x": 4, "y0": 0, "y1": cells, "t0": time.time(), "col": (255, 200, 80)}
        r._glow_trail(m, tr, 500, 130, cells * cs, 0.9, cs)
    cols = {k for k in ui_glow._SPRITES if k[0] == "column"}
    assert len(cols) <= 6, len(cols)                       # 높이 1~20칸이 만드는 기둥 스프라이트는 5종 안팎


def test_resize_rebakes_backdrops_gradually_and_nebula_has_a_cost_cap():
    app = _app()
    m = _game(app, 30)
    r = app.renderer
    m.visual_fx = "normal"
    for _ in range(4):
        r.render(m, app.sound_mgr)
    assert r._deco_prebaked == 3
    CANVAS.version += 1                                    # 창 크기/배율이 바뀜 (캐시 무효화)
    r.render(m, app.sound_mgr)
    assert r._deco_prebaked < 3, "배율이 바뀌면 미리 굽기를 처음부터 다시 (단계가 바뀌는 순간 한꺼번에 굽지 않게)"
    assert (2, "deco") not in r._bg_by_phase, "새 배율의 2단계 장식은 아직 안 구워짐 (프레임마다 하나씩)"
    for _ in range(4):
        r.render(m, app.sound_mgr)
    assert (2, "deco") in r._bg_by_phase and (3, "deco") in r._bg_by_phase
    import random
    t0 = time.time()
    neb = r._nebula_surface(3840, 2160, random.Random(1), 1000, 2800, 140.0)       # 4K: 계산 해상도에 상한이 있어 1366 기준과 비슷한 비용
    assert neb.get_size() == (3840, 2160) and time.time() - t0 < 5.0
    CANVAS.version += 0


def test_scene_caches_are_released_after_the_match():
    app = _app()
    m = _game(app, 10)
    r = app.renderer
    r._ray_cache = {"_stamp": 1, (False, 2): object()}
    r._bg_beat_cache = {"_stamp": 1, 1: object()}
    app.state = "MENU"
    app._update_menu(0.016)
    assert not r._ray_cache and not r._bg_beat_cache, "메뉴로 돌아오면 전체 화면 장면 캐시를 비움"
    r._ray_cache = {"_stamp": 1, (True, 1): object()}
    app.start_game(mode="SOLO", total_players=6)           # 새 경기도 이전 결과 장면의 캐시를 비움
    assert not r._ray_cache


def test_steamos_tests_do_not_leak_environment_or_touch_the_real_error_log():
    import test_steamos as ts
    before = os.environ.get("BR_DATA_DIR")
    real_log = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "error.log")
    size_before = os.path.getsize(real_log) if os.path.exists(real_log) else 0
    for name in ("test_unfinished_launch_is_reported_next_time", "test_trace_is_noop_before_begin_and_never_raises", "test_set_mode_retries_then_falls_back"):
        getattr(ts, name)()
        assert os.environ.get("BR_DATA_DIR") == before, (name, os.environ.get("BR_DATA_DIR"), before)
    size_after = os.path.getsize(real_log) if os.path.exists(real_log) else 0
    if before is None:
        assert size_after == size_before, "가짜 오류가 프로젝트의 진짜 error.log에 쌓이지 않음"


def test_bot_understands_b2b_chain_tiers_when_enabled():
    import bot_brain
    from block_engine import GARBAGE_ATTACK_TABLE
    base = GARBAGE_ATTACK_TABLE.get(4, 0)
    # 끄면 예전과 같음: True = 1 -> +1
    a_old, diff = bot_brain._attack(4, None, 1, True, False)
    assert diff and a_old == base + 1 + bot_brain.COMBO_BONUS[1]
    # 연쇄 단계 보너스: 엔진과 같음 (4~7 = +2, 8 이상 = +3)
    for v, bonus in ((1, 1), (3, 1), (4, 2), (7, 2), (8, 3), (12, 3)):
        a, _ = bot_brain._attack(4, None, 1, v, False)
        assert a == base + bonus + bot_brain.COMBO_BONUS[1], (v, a)
    old = dict(bot_brain.PARAMS)
    try:
        bot_brain.PARAMS["b2b_chain"] = 1
        r1, c1, nb = bot_brain._step_reward(0, 0, 4, None, 0, 2, 0, False, 8, True)
        assert nb == 3, "어려운 클리어는 연쇄를 +1"
        r2, c2, nb2 = bot_brain._step_reward(0, 0, 1, None, 0, 5, 0, False, 8, True)
        r3, c3, nb3 = bot_brain._step_reward(0, 0, 1, None, 0, 1, 0, False, 8, True)
        assert nb2 == 0 and nb3 == 0, "일반 클리어는 연쇄를 끊음"
        assert r3 - r2 >= 3.0, "연쇄가 길수록 끊을 때 감점이 큼"
        _, _, first = bot_brain._step_reward(0, 0, 4, None, 0, 0, 0, False, 8, True)
        assert first == 1
        bot_brain.PARAMS["b2b_chain"] = 0
        _, _, nb_off = bot_brain._step_reward(0, 0, 4, None, 0, 2, 0, False, 8, True)
        assert nb_off is True, "꺼져 있으면 예전처럼 참/거짓"
    finally:
        bot_brain.PARAMS.clear()
        bot_brain.PARAMS.update(old)
    import ai_bot
    bot = ai_bot.AIBot("T", difficulty="master", seed=5)
    bot.engine.b2b, bot.engine.b2b_chain = True, 3
    bot.params = dict(bot_brain.PARAMS, b2b_chain=1)
    assert bot._b2b_state() == 4
    bot.params = dict(bot_brain.PARAMS, b2b_chain=0)
    assert bot._b2b_state() is True
    bot.engine.b2b = False
    bot.params = dict(bot_brain.PARAMS, b2b_chain=1)
    assert not bot._b2b_state()
    assert bot_brain.PARAMS.get("b2b_chain") == 0, "기본값은 꺼짐 (측정: 승률 중립, 분당 공격 +7%, 연쇄 길이는 거의 같음)"


def test_light_effects_row_explains_why_motion_or_brightness_is_reduced():
    import i18n
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "general"
    texts = []
    orig = app._t
    app._t = lambda *a, **k: (texts.append(a[0]) if a and isinstance(a[0], str) else None, orig(*a, **k))[1]
    try:
        app.settings.set("screen_shake", "off")
        app._render_settings()
        assert any("움직임 멈춤" in t for t in texts), texts[:20]
        texts.clear()
        app.settings.set("screen_shake", "normal")
        app.settings.set("screen_flash", False)
        app._render_settings()
        assert any("밝기 낮춤" in t for t in texts)
    finally:
        app._t = orig
    i18n.set_language("en")
    try:
        assert i18n.tr("움직임 멈춤: 화면 흔들림이 꺼져 있음").startswith("Motion paused")
        assert not any("가" <= ch <= "힣" for ch in i18n.tr("밝기 낮춤: 화면 번쩍임이 꺼져 있음"))
    finally:
        i18n.set_language("ko")


def test_diagnostics_text_and_copy_button():
    import crash_log
    app = _app()
    os.environ.setdefault("BR_DATA_DIR", tempfile.mkdtemp())
    crash_log.write_error("테스트 오류", "Traceback...\nValueError: x")
    txt = crash_log.diagnostics_text({"visual_fx": "fancy"})
    assert "BLOCK ROYALE 100 v" in txt and "visual_fx: fancy" in txt and "error.log" in txt and "ValueError: x" in txt
    app.state = "SETTINGS"
    app.settings_tab = "help"
    app.settings.set("player_name", "비밀이름")
    app._render_settings()
    assert "copy_diag" in app.settings_buttons and "open_errlog" in app.settings_buttons
    app._settings_activate("copy_diag")
    assert "BLOCK ROYALE 100" in app._diag_text and "visual_fx" in app._diag_text
    assert "비밀이름" not in app._diag_text, "이름 같은 개인 설정은 진단 정보에 넣지 않음"


def test_settings_file_has_schema_and_keeps_unknown_keys():
    import settings_manager as sm
    path = os.path.join(tempfile.mkdtemp(), "set.json")
    json.dump({"visual_fx": "fancy", "future_option": {"a": 1}, "screen_shake": "low"}, open(path, "w", encoding="utf-8"))
    s = sm.SettingsManager(path)
    assert s.get("visual_fx") == "fancy" and s.get("screen_shake") == "low"
    s.set("pad_rumble", "low")
    saved = json.load(open(path, encoding="utf-8"))
    assert saved["schema"] == sm.SettingsManager.SCHEMA == 1
    assert saved["future_option"] == {"a": 1}, "이 버전이 모르는 키(더 새 버전의 설정)는 저장할 때 그대로 돌려 씀"
    assert saved["pad_rumble"] == "low" and saved["visual_fx"] == "fancy"
    s2 = sm.SettingsManager(path)
    assert s2.get("pad_rumble") == "low" and "schema" not in s2.data
    json.dump(["not a dict"], open(path, "w", encoding="utf-8"))                 # 깨진 파일은 기존대로 기본값
    s3 = sm.SettingsManager(path)
    assert s3.get("visual_fx") == "normal"


def test_results_screen_code_lives_in_ui_results():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import ui_renderer
    import ui_results
    names = ("_render_standings_overlay", "_render_result_overlay", "_draw_result_summary", "_result_layout", "_draw_killcam", "_standings_info_lines", "_draw_timeline_graph")
    for n in names:
        assert n in ui_results.ResultsMixin.__dict__ and n not in ui_renderer.UIRenderer.__dict__, n
        assert callable(getattr(ui_renderer.UIRenderer, n))
    assert len(open(os.path.join(root, "ui_renderer.py"), encoding="utf-8").read().split("\n")) < 3800
    app = _app()
    m = _game(app, 12)
    m.match_finished = True
    m.local_rank = 3
    app.renderer._standings_t0 = time.time() - 5.0
    app.renderer.render(m, app.sound_mgr)                  # 결과 화면이 옮긴 코드로 그려짐


if __name__ == "__main__":
    pygame.init()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL FOLLOWUP2 TESTS PASSED]")
