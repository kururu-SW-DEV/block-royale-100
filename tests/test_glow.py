"""
화려한 빛 연출(v1.4.37) 테스트: 가산 글로우 스프라이트/캐시, 설정 단계(최소/보통/화려하게)·fx_low·번쩍임·흔들림 연결, 비트 맞춤 배경,
단계별 배경 장식, 줄 삭제 띠가 블록 칸에 정확히 맞는지, 우승 광선, 순위표 빛줄기, 미니 카드 강화, 메뉴 배경, 이펙트 테마, 설정 행.
실행: python tests/test_glow.py
"""
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


class _CountBlits:
    """CANVAS.display.blit 중 가산(BLEND_RGB_ADD) 호출 수를 셈"""
    def __enter__(self):
        self.n = 0
        self.disp = CANVAS.display
        self.orig = self.disp.blit
        outer = self

        class Proxy:
            def __getattr__(self, name):
                return getattr(outer.disp, name)

            def blit(self, src, dest, area=None, special_flags=0):
                if special_flags == pygame.BLEND_RGB_ADD:
                    outer.n += 1
                return outer.orig(src, dest, area, special_flags)
        self.proxy = Proxy()
        return self

    def __exit__(self, *a):
        pass


def test_glow_sprites_are_cached_black_background_additive_gradients():
    import ui_glow
    a = ui_glow.glow_sprite("band", 120, 40, (255, 200, 80), 4)
    b = ui_glow.glow_sprite("band", 120, 40, (255, 200, 80), 4)
    assert a is b, "같은 종류/크기/색/단계는 한 번만 만듦"
    assert ui_glow.glow_sprite("band", 120, 40, (255, 200, 80), 1) is not a
    assert a.get_at((60, 20))[:3] != (0, 0, 0) and a.get_at((0, 0))[:3] == (0, 0, 0), "가운데가 밝고 모서리는 검정(가산하면 변화 없음)"
    col = ui_glow.glow_sprite("column", 30, 100, (255, 255, 255), 4)
    assert sum(col.get_at((15, 95))[:3]) > sum(col.get_at((15, 5))[:3]), "기둥은 아래가 더 밝고 위로 옅어짐"
    orb = ui_glow.glow_sprite("orb", 80, 40, (255, 255, 255), 4)
    assert orb.get_at((40, 20))[0] > 200 and orb.get_at((0, 0))[0] == 0, "타원 구슬 (가로세로가 달라도 가운데 밝음)"
    assert ui_glow.glow_sprite("band", 50, 20, (1, 2, 3), 0).get_size() == (50, 20)


def test_fx_mode_levels_and_gates():
    app = _app()
    m = _game(app)
    r = app.renderer
    from ui_glow import FX_MIN, FX_NORMAL, FX_FANCY
    m.visual_fx = "normal"
    assert r._fx_mode(m) == FX_NORMAL
    m.visual_fx = "fancy"
    assert r._fx_mode(m) == FX_FANCY
    m.visual_fx = "min"
    assert r._fx_mode(m) == FX_MIN
    m.visual_fx = "fancy"
    m.fx_low = True
    assert r._fx_mode(m) == FX_MIN, "화면이 느리면 자동으로 최소"
    m.fx_low = False
    m.flash_enabled = False
    assert r._fx_level(m, 1.0, cap=4) <= 1, "번쩍임이 꺼지면 밝기 상한"
    m.flash_enabled = True
    assert r._fx_level(m, 1.0, cap=4) == 4 and r._fx_level(m, 0.0) == 0
    m.shake_scale = 0.0
    assert r._fx_motion(m) is False
    assert r._particle_glow_budget(m) == 80
    m.visual_fx = "min"
    assert r._particle_glow_budget(m) == 0


def test_no_additive_blits_in_min_mode_for_wipe_lock_and_trail():
    app = _app()
    m = _game(app)
    r = app.renderer
    eng = m.local_engine
    fl = {"row": 18, "birth": time.time(), "duration": 0.4, "kind": "quad", "combo": 0}
    lf = {"cells": [(3, 18), (4, 18), (5, 18), (4, 17)], "birth": time.time(), "col": (255, 200, 80)}
    tr = {"x": 4, "y0": 3, "y1": 17, "t0": time.time(), "col": (255, 200, 80)}
    for mode, expect in (("min", False), ("normal", True)):
        m.visual_fx = mode
        calls = []
        import ui_glow
        orig = ui_glow.add_glow
        ui_glow.add_glow = lambda *a, **k: calls.append(a[0])
        try:
            r._glow_wipe(m, fl, 400, 100, 300, 30, 0.1, "quad")
            r._glow_lock(m, lf, 400, 100, 30, 0.02)
            r._glow_trail(m, tr, 500, 130, 300, 0.9, 30)
        finally:
            ui_glow.add_glow = orig
        assert bool(calls) == expect, (mode, calls)
    m.visual_fx = "normal"
    m.fx_low = True
    calls = []
    import ui_glow
    orig = ui_glow.add_glow
    ui_glow.add_glow = lambda *a, **k: calls.append(a[0])
    try:
        r._glow_wipe(m, fl, 400, 100, 300, 30, 0.1, "quad")
    finally:
        ui_glow.add_glow = orig
    assert not calls, "fx_low에서는 빛 번짐 생략"


def test_wipe_core_matches_cleared_row_cells_exactly():
    """줄 삭제 흰/금색 띠는 가로로 보드 폭, 세로로 칸 높이에 정확히 맞고, 옅은 번짐만 위아래로 나감 (전에는 좌우 8px, 위아래 1px 넘쳤음)"""
    app = _app()
    m = _game(app)
    r = app.renderer
    eng = m.local_engine
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui_renderer.py"), encoding="utf-8").read()
    assert "ww, hh = bw, cs + pad * 2" in src and "(0, pad, ww, cs)" in src and "bw + 16" not in src.split("3-2. 라인 클리어 와이프")[1][:3000]
    # 실제로 그려서 보드 폭 밖(왼쪽 바깥 2px)은 흰색이 아님
    for y in range(16, 20):
        for x in range(10):
            eng.grid[y][x] = "I"
    eng.last_clear_info = {"cleared": 4}
    eng.cleared_row_indices = [16, 17, 18, 19]
    eng.lines_cleared_total += 1
    m.visual_fx = "min"                                    # 빛 번짐 없이 띠만 확인
    r.render(m)
    time.sleep(0.03)
    r.render(m)
    surf = pygame.display.get_surface()
    bx, by, cs = r.main_board_x, r.main_board_y, r.cell_size
    S = CANVAS.S
    y_mid = int((by + 17 * cs + cs // 2) * S)
    outside = surf.get_at((int((bx - 4) * S), y_mid))[:3]
    inside = surf.get_at((int((bx + 40) * S), y_mid))[:3]
    assert min(outside) < 200 or sum(outside) < sum(inside), (outside, inside)
    r.line_clear_flashes.clear()


def test_beat_phase_and_bg_variants():
    app = _app()
    sm = app.sound_mgr
    sm._beat = (120.0, time.time() - 0.25)                # 120BPM: 0.5초마다 박자 -> 0.25초 지난 시점은 위상 0.5
    sm.is_bgm_playing, sm.bgm_enabled, sm._bgm_paused = True, True, False
    ph = sm.beat_phase()
    assert ph is not None and abs(ph[0] - 0.5) < 0.1, ph
    sm._bgm_paused = True
    assert sm.beat_phase() is None, "일시정지 중에는 박자 없음"
    sm._bgm_paused = False
    sm.is_bgm_playing = False
    assert sm.beat_phase() is None
    import sound_fx
    assert sound_fx.STAGE_BPM[0] == (128, 142, 156) and sound_fx.SPECIAL_BPM["menu"] == 114
    m = _game(app)
    r = app.renderer
    m.visual_fx = "normal"
    r._beat_info = (0.0, 3)
    assert r._beat_k(m) == 0, "보통에서는 음악에 맞춰 배경이 번쩍이지 않음"
    m.visual_fx = "min"
    assert r._beat_k(m) == 0
    m.visual_fx = "fancy"
    r._beat_info = (0.0, 3)                                # 박자 직후: 가장 밝음
    assert r._beat_k(m) == 3
    r._beat_info = (0.9, 3)
    assert r._beat_k(m) == 0
    r._beat_info = (0.0, 3)
    r._danger_now = True
    assert r._beat_k(m) == 0, "위기 중에는 맥동 정지"
    r._danger_now = False
    m.shake_scale = 0.0
    assert r._beat_k(m) == 0, "흔들림이 꺼지면 맥동 없음"
    m.shake_scale = 1.0
    m.flash_enabled = False
    assert r._beat_k(m) <= 1
    m.flash_enabled = True
    base = r._bg(1, True)
    v1, v3 = r._bg_beat(1, True, 1), r._bg_beat(1, True, 3)
    assert r._bg_beat(1, True, 0) is base and r._bg_beat(1, True, 1) is v1, "변형은 캐시"
    assert pygame.Surface.get_at(v3, (5, 5))[:3] != pygame.Surface.get_at(base, (5, 5))[:3], "밝기 변형"
    r._bg_beat(2, True, 1)
    assert 1 in r._bg_beat_cache and r._bg_beat_cache["_stamp"][0] == 2, "단계가 바뀌면 이전 단계 변형은 버림"
    r.render(m, sm)                                        # 박자 정보가 있는 채 한 프레임


def test_stage_deco_is_baked_once_and_keeps_board_area_clear():
    app = _app()
    m = _game(app)
    r = app.renderer
    from config import SCREEN_WIDTH
    S = CANVAS.S
    for ph in (1, 2, 3):
        plain, deco = r._bg(ph, False), r._bg(ph, True)
        assert r._bg(ph, True) is deco and plain is not deco
        bx = int((r.main_board_x + r.main_board_w // 2) * S)
        for y in (60, 380, 700):
            assert pygame.Surface.get_at(plain, (bx, int(y * S)))[:3] == pygame.Surface.get_at(deco, (bx, int(y * S)))[:3], (ph, y, "보드 둘레는 장식이 없음")
        diff = sum(1 for x in range(0, int(400 * S), 2) for y in range(0, int(768 * S), 2)
                   if pygame.Surface.get_at(plain, (x, y))[:3] != pygame.Surface.get_at(deco, (x, y))[:3])
        assert diff > 20, (ph, diff, "가장자리에는 단계별 장식이 있음")
    # 경기 시작 직후 세 프레임에 미리 구워짐
    r._theme_match_id = None
    m.visual_fx = "normal"
    for _ in range(4):
        r.render(m, app.sound_mgr)
    assert r._deco_prebaked == 3 and (2, "deco") in r._bg_by_phase and (3, "deco") in r._bg_by_phase


def test_embers_only_in_fancy_phase3_with_motion():
    app = _app()
    m = _game(app)
    r = app.renderer
    m.phase = 3
    m.visual_fx = "min"
    r._render_embers(m)
    assert not getattr(r, "_embers", []), "최소에서는 불씨 없음"
    m.visual_fx = "normal"
    r._render_embers(m)
    assert len(r._embers) == 18, "보통에서도 불씨가 있음 (18개)"
    m.visual_fx = "fancy"
    r._render_embers(m)
    assert len(r._embers) == 26
    zx0, zx1 = r.main_board_x - 170, r.main_board_x + r.main_board_w + 170
    assert all(not (zx0 < e["x"] < zx1) for e in r._embers), "보드 둘레에는 불씨가 없음"
    m.shake_scale = 0.0
    before = [e["y"] for e in r._embers]
    time.sleep(0.02)
    r._render_embers(m)
    assert [e["y"] for e in r._embers] == before, "흔들림이 꺼지면 정지"


def test_min_mode_keeps_backdrops_but_nothing_moves_or_flashes_to_the_music():
    """'최소': 단계별 배경 장식(정지된 그림)은 적용되지만 박자 맞춤 번쩍임/불씨/빛 번짐은 없음. 설정값을 렌더러가 직접 읽음"""
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "general"
    app._render_settings()
    while app.settings.get("visual_fx") != "min":
        app._settings_activate("fx_next")
    m = _game(app, 30)
    r = app.renderer
    m.visual_fx = "fancy"                                  # 경기 객체의 값이 어긋나 있어도 설정(최소)이 우선
    app.state = "GAME"
    sm = app.sound_mgr
    sm._beat = (120.0, time.time() - 0.01)
    sm.is_bgm_playing, sm.bgm_enabled, sm._bgm_paused = True, True, False
    frames = []
    for ph in (1, 2, 3):
        m.phase = ph
        r._theme_match_id = None
        for _ in range(5):
            r.fx_setting = app.settings.get("visual_fx")
            r.render(m, sm)
        assert (ph, "deco") in r._bg_by_phase, "배경 장식은 최소에서도 적용"
        assert not getattr(r, "_embers", []), "불씨 없음"
        assert r._beat_k(m) == 0, "박자에 맞춘 번쩍임 없음"
        assert not getattr(r, "_bg_beat_cache", {}).get(1), "밝기 변형 배경을 쓰지 않음"
        frames.append(pygame.surfarray.array3d(pygame.display.get_surface()).sum())
    # 박자 위상이 달라져도 배경 픽셀이 변하지 않음 (번쩍임 없음)
    m.phase = 1
    r._theme_match_id = None
    sums = []
    for off in (0.01, 0.2, 0.4):
        sm._beat = (120.0, time.time() - off)
        r.fx_setting = "min"
        r.render(m, sm)
        disp = pygame.display.get_surface()
        sums.append(pygame.Surface.get_at(disp, (min(40, disp.get_width() - 1), disp.get_height() - 30))[:3])        # 창 크기에 맞춰 (CI는 모니터가 작아 창이 더 작음)
    assert sums[0] == sums[1] == sums[2], sums
    r.fx_setting = None


def test_nebula_is_smooth_not_blocky_or_banded():
    app = _app()
    r = app.renderer
    import random
    w, h = CANVAS.length(r.width), CANVAS.length(r.height)
    neb = r._nebula_surface(w, h, random.Random(1), 0, 0, 100.0)
    assert neb.get_size() == (w, h)
    # 이웃 픽셀 차이가 아주 작음 (계단/블록 없음) + 값이 여러 단계로 퍼짐 (색 띠 없음, 디더링)
    big_jumps = 0
    levels = set()
    for y in range(h // 3, h // 3 + 60):
        prev = neb.get_at((w // 8, y))[:3]
        for x in range(w // 8 + 1, w // 8 + 120):
            c = neb.get_at((x, y))[:3]
            levels.add(c[0])
            if max(abs(c[i] - prev[i]) for i in range(3)) > 4:
                big_jumps += 1
            prev = c
    assert big_jumps == 0, big_jumps
    assert len(levels) >= 6, levels
    # 비움 구간(보드 둘레) 가장자리는 서서히: 구간 안은 0, 바깥으로 갈수록 증가
    neb2 = r._nebula_surface(w, h, random.Random(1), int(w * 0.3), int(w * 0.7), 120.0)
    inside = sum(neb2.get_at((int(w * 0.5), y))[0] for y in range(0, h, 30))
    assert inside == 0, inside


def test_victory_rays_fountain_ring_and_standings_shine():
    app = _app()
    m = _game(app, 8)
    r = app.renderer
    m.visual_fx = "normal"
    r._vic_t0 = time.time() - 3.0
    m.match_finished = True
    r._render_victory_backdrop(m)                          # 예외 없이 (캐시 생성): 카드를 가리는 막 + 광선
    assert any(k != "_stamp" for k in r._ray_cache)
    n = len(r._ray_cache)
    r._render_victory_rays(m)
    assert len(r._ray_cache) == n, "광선 판은 밝기 단계별로 한 번만"
    m.visual_fx = "fancy"
    before = len(r.particles.particles)
    r._vic_t0 = time.time() - 1.5
    r._victory_fountain(m, time.time())
    assert len(r.particles.particles) > before
    ups = [p for p in r.particles.particles[before:] if p["vy"] < 0]
    assert ups, "분수 불티는 위로 솟음"
    r.particles.rings.clear()
    r._victory_ring(m, time.time(), 600, 300)
    assert len(r.particles.rings) == 2
    r._victory_ring(m, time.time(), 600, 300)
    assert len(r.particles.rings) == 2, "왕관 충격 링은 한 번만"
    m.visual_fx = "min"
    r._render_victory_rays(m)
    r._standings_shine(m, pygame.Rect(200, 300, 900, 30), time.time())
    m.visual_fx = "normal"
    r._standings_shine(m, pygame.Rect(200, 300, 900, 30), time.time())
    m.shake_scale = 0.0
    r._standings_shine(m, pygame.Rect(200, 300, 900, 30), time.time())
    # 우승 순위표 화면 전체 그리기
    m.local_rank = 1
    r._standings_t0 = time.time() - 4.0
    r.render(m, app.sound_mgr)


def test_mini_card_extras():
    app = _app()
    m = _game(app, 40)
    r = app.renderer
    m.visual_fx = "normal"
    ids = [k for k, p in m.players.items() if p.get("bot") and p["is_alive"]]
    m.apply_attack(ids[0], m.local_player_id, 3)
    assert abs(m.players[ids[0]]["shot_t"] - time.time()) < 1.0, "나를 쏜 상대의 발사 시각 기록"
    r.render(m, app.sound_mgr)
    r._phase_fx = {"t0": time.time() - 0.3, "phase": 2}
    rect = pygame.Rect(600, 100, 60, 90)
    assert r._card_wave_alpha(m, rect, time.time()) >= 0
    m.flash_enabled = False
    assert r._card_wave_alpha(m, rect, time.time()) == 0, "번쩍임이 꺼지면 빛 물결 없음"
    m.flash_enabled = True
    m.visual_fx = "min"
    assert r._card_wave_alpha(m, rect, time.time()) == 0
    m.visual_fx = "normal"
    m.alive_count = 3                                      # 최후의 10%: 금빛 테두리 (예외 없이 그려짐)
    r._card_extras(m, ids[1], m.players[ids[1]], rect, time.time(), True)
    r.render(m, app.sound_mgr)


def test_menu_background_fx_only_on_main_menu_and_respects_settings():
    app = _app()
    app.state = "MENU"
    app.settings.set("visual_fx", "fancy")
    app.sound_mgr._beat = (114.0, time.time())
    app.sound_mgr.is_bgm_playing, app.sound_mgr.bgm_enabled, app.sound_mgr._bgm_paused = True, True, False
    app._render_menu()
    mb = app.menu_bg
    assert mb.fx_mode == 2 and mb.motion and mb.beat is not None
    for _ in range(30):
        mb._clock += 1.0
        mb.update(0.1)
    assert mb._streak is not None or mb._next_streak > mb._clock, "가끔 빛 띠가 지나감"
    app._render_menu()
    app.settings.set("visual_fx", "min")
    app._render_menu()
    assert mb.fx_mode == 0 and mb._streak is not None or mb.fx_mode == 0
    app.settings.set("visual_fx", "normal")                # 보통: 빛 띠는 지나가지만 음악에 맞춘 밝기 변화는 없음
    mb._streak = None
    mb._clock = mb._next_streak + 1.0
    app._render_menu()
    mb.update(0.1)
    assert mb._streak is not None and mb.fx_mode == 1, "보통에서도 가끔 빛 띠가 지나감"
    assert mb.beat is not None
    mb._streak = None
    app.settings.set("screen_shake", "off")
    app._render_menu()
    assert mb.motion is False and mb.mouse is None, "흔들림이 꺼지면 시차 없음"
    # 다른 화면은 예전과 같음
    app.state = "RECORDS"
    app._render_records()
    assert mb.fx_mode == 0
    app.state = "SETTINGS"
    app.settings_tab = "general"
    app._render_settings()
    assert mb.fx_mode == 0


def test_fx_themes_follow_block_skin_and_colorblind_uses_default():
    import ui_glow
    app = _app()
    r = app.renderer
    r.block_skin = "classic"
    assert r._fx_theme() is ui_glow.FX_THEMES["default"]
    for skin, theme in ui_glow.SKIN_THEME.items():
        r.block_skin = skin
        assert r._fx_theme() is ui_glow.FX_THEMES[theme]
        assert set(r._fx_theme()["wipe"]) == {"clear", "quad", "tspin"} and set(r._fx_theme()["aura"]) == {1, 2, 3}
    import config
    r.block_skin = "ember"
    orig = config.is_colorblind
    import ui_glow as ug
    config.is_colorblind = lambda: True
    try:
        assert r._fx_theme() is ug.FX_THEMES["default"], "색약 모드는 기본 테마"
    finally:
        config.is_colorblind = orig
    assert len({tuple(t["wipe"].values()) for t in ug.FX_THEMES.values()}) == len(ug.FX_THEMES), "테마마다 색이 다름"
    for skin in ("classic", "neon", "ember", "starlight", "prism", "glass"):
        r.block_skin = skin
        m = _game(app)
        m.local_engine.combo = 6
        m.local_engine.b2b, m.local_engine.b2b_chain = True, 4
        r.render(m, app.sound_mgr)
    r.block_skin = "classic"


def test_visual_fx_setting_row_cycles_and_is_translated():
    app = _app()
    assert app.settings.get("visual_fx") == "normal"
    seen = [app.settings.cycle_visual_fx(1) for _ in range(3)]
    assert seen == ["fancy", "min", "normal"]
    app.state = "SETTINGS"
    app.settings_tab = "general"
    app._render_settings()
    assert "visual_fx" in app._row_rects
    app._settings_activate("fx_next")
    assert app.settings.get("visual_fx") == "fancy"
    m = _game(app)
    app.apply_gameplay_options()
    assert m.visual_fx == "fancy"
    from screens.settings import TAB_NAV, TAB_DEFAULT_KEYS
    assert any(r[0] == "visual_fx" for r in TAB_NAV["general"]) and "visual_fx" in TAB_DEFAULT_KEYS["general"]
    import i18n
    i18n.set_language("en")
    try:
        for ko in ("빛 연출", "최소", "화려하게"):
            assert not any("가" <= ch <= "힣" for ch in i18n.tr(ko)), ko
    finally:
        i18n.set_language("ko")
    # 행이 설정 화면 안에 들어감 (마지막 행이 아래 설명 줄을 넘지 않음)
    last = max(rect.bottom for rect in app._row_rects.values())
    assert last <= 760, last


def test_light_effects_row_text_fits_next_to_the_cycler_in_both_languages():
    """'빛 연출' 행의 설명이 오른쪽 선택 버튼(‹ ›)과 겹치지 않음 (영어에서 길어서 잘리던 문제)"""
    import i18n
    from screens import settings as S
    app = _app()
    app.state = "SETTINGS"
    app.settings_tab = "general"
    for lang in ("ko", "en"):
        i18n.set_language(lang)
        try:
            app._render_settings()
            row = app._row_rects["visual_fx"]
            left_btn = app.settings_buttons["fx_prev"] if hasattr(app, "settings_buttons") and "fx_prev" in app.settings_buttons else None
            sub = i18n.tr("빛 번짐·불씨·우승 연출 (화려하게: 음악 맥동)")
            width = app.font_help.size(sub)[0]
            limit = (left_btn.left if left_btn is not None else row.right - 340) - (row.x + 22) - 12
            assert width <= limit, (lang, width, limit, sub)
        finally:
            i18n.set_language("ko")


def test_full_frame_in_every_fx_mode_and_phase_without_errors():
    app = _app()
    for mode in ("min", "normal", "fancy"):
        m = _game(app, 30)
        m.visual_fx = mode
        eng = m.local_engine
        for ph in (1, 2, 3):
            m.phase = ph
            for i in range(25):
                if i % 8 == 0:
                    eng.combo = 5
                    eng.last_clear_info = {"cleared": 4 if i % 16 == 0 else 1, "is_tspin": i % 3 == 0}
                    eng.cleared_row_indices = [18, 19]
                    eng.lines_cleared_total += 1
                    eng.hard_drop()
                m.update(1 / 60)
                app.renderer.render(m, app.sound_mgr)


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL GLOW TESTS PASSED]")
