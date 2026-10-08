"""
시각 개선(스카이라인 윤곽선/굳은 블록 명도/쓰레기 해칭, 미니 보드 실루엣, 조준선 곡선, 콤보 오라, 3단계 비네트)의 동작 확인.
눈으로 보는 것은 캡처로 따로 확인했고, 여기서는 '언제 그리고 언제 안 그리는가'와 캐시/오류만 검사함
실행: python tests/test_board_visuals.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from config import BOARD_HEIGHT, BOARD_WIDTH


def _app(players=30):
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    app.start_game(mode="SOLO", total_players=players)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    app.state = "GAME"
    for _ in range(60):
        app._tick_game(1 / 60)
    return app, m


def test_skyline_is_cached_and_follows_the_stack():
    app, m = _app()
    r = app.renderer
    e = m.local_engine
    grid = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    for x in range(10):
        grid[19][x] = "I"
    s1 = r._skyline_surface(grid, 360, 720, 36)
    assert r._skyline_surface(grid, 360, 720, 36) is s1, "보드가 그대로인데 윤곽선 서피스를 다시 만듦"
    grid[18][4] = "T"
    s2 = r._skyline_surface(grid, 360, 720, 36)
    assert s2 is not s1, "보드가 바뀌었는데 윤곽선이 그대로"
    # 지붕 아래 갇힌 빈칸(구멍)은 윤곽선에 포함되지 않음: 갇힌 칸 주변에 선이 생기지 않아야 함
    grid2 = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    for x in range(10):
        grid2[17][x] = "O"                                       # 완전히 닫힌 지붕
        grid2[19][x] = "O"
    s3 = r._skyline_surface(grid2, 360, 720, 36)
    w, h = s3.get_size()
    sc = w / 360.0
    inner = s3.subsurface(pygame.Rect(int(40 * sc), int(18 * 36 * sc + 6 * sc), int(280 * sc), int(24 * sc)))      # 18행 안쪽 (갇힘)
    assert pygame.mask.from_surface(inner, 10).count() == 0, "갇힌 빈칸 주변에 윤곽선이 그려짐"
    r._skyline_surface([[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)], 360, 720, 36)     # 빈 보드도 오류 없이


def test_settled_cells_are_dimmer_than_active_cells():
    app, m = _app()
    r = app.renderer
    act = r._cell_surface("T", 36)
    dim = r._settled_surface("T", 36)
    ca = pygame.transform.average_color(act)
    cd = pygame.transform.average_color(dim)
    assert sum(cd[:3]) < sum(ca[:3]), (ca, cd)
    assert r._settled_surface("T", 36) is dim                     # 캐시


def test_garbage_cell_has_hatching():
    app, m = _app()
    g = app.renderer._cell_surface("G", 36)
    n = pygame.Surface.get_width(g)                              # 화면 배율에 따라 실제 크기가 다름 (러너의 작은 가상 화면에서는 36px보다 작음)
    lo, hi = max(1, n // 18), n - max(1, n // 18)
    pix = {tuple(g.get_at((x, y)))[:3] for x in range(lo, hi) for y in range(lo, hi)}
    assert len(pix) >= 3, "쓰레기 칸에 해칭 무늬(여러 밝기)가 없음"


def test_quiet_background_cards_are_silhouettes_in_focus_mode():
    app, m = _app(30)
    r = app.renderer
    r.mini_focus = True
    bots = [pid for pid, p in m.players.items() if pid != m.local_player_id and p["is_alive"]]
    target, attacker, leader = bots[1], bots[2], bots[3]
    m.players[m.local_player_id]["target_id"] = target
    m.players[attacker]["target_id"] = m.local_player_id
    m.players[leader]["ko_count"] = 4

    def calm(pid):                                               # 봇은 무작위라, 현상금/라이벌/결승 상대/위기/나를 노리는 봇이 아닌 '조용한' 봇을 골라야 함
        p = m.players[pid]
        special = (target, attacker, leader, getattr(m, "bounty_id", None), getattr(m, "rival_id", None), getattr(m, "final_opp_id", None))
        return pid not in special and p.get("is_ai", True) and p.get("highest_y", 20) > 5 and p.get("target_id") != m.local_player_id and p.get("ko_count", 0) < 2
    plain = next(pid for pid in bots if calm(pid))
    drawn = set()
    orig = r._blit_card_layer
    r._blit_card_layer = lambda key, *a, **k: (drawn.add(key[0]) if key[1] == "tag" else None, orig(key, *a, **k))[1]
    r.render(m, app.sound_mgr)
    assert target in drawn and leader in drawn, "조준 대상/킬 리더의 이름표가 그려져야 함"
    assert plain not in drawn, "교전과 무관한 봇에 이름표가 그려짐 (실루엣이어야 함)"
    r.mini_focus = False
    drawn.clear()
    r.render(m, app.sound_mgr)
    assert plain in drawn, "집중 모드가 꺼져 있으면 모든 카드에 이름표"
    r.mini_focus = True


def test_aura_levels_and_vignette_conditions():
    app, m = _app(30)
    r = app.renderer
    keys = []
    orig = r._blit_overlay
    r._blit_overlay = lambda key, *a, **k: (keys.append(key[0] if isinstance(key, tuple) else key) if isinstance(key, tuple) else None, orig(key, *a, **k))[1]
    e = m.local_engine
    e.combo, e.b2b, e.b2b_chain = -1, False, 0
    r.render(m, app.sound_mgr)
    assert "aura" not in keys, "콤보/B2B가 없는데 오라가 그려짐"
    levels = []
    r._blit_overlay = lambda key, *a, **k: (levels.append(key[1]) if isinstance(key, tuple) and key[0] == "aura" else None, orig(key, *a, **k))[1]
    for combo, b2b, chain, want in ((3, False, 0, 1), (5, True, 1, 2), (8, True, 4, 3)):
        e.combo, e.b2b, e.b2b_chain = combo, b2b, chain
        levels.clear()
        r.render(m, app.sound_mgr)
        assert levels and levels[0] == want, (combo, b2b, chain, levels)
    seen = []
    r._blit_overlay = lambda key, *a, **k: (seen.append(key[0]) if isinstance(key, tuple) else None, orig(key, *a, **k))[1]
    m.phase = 2
    r.render(m, app.sound_mgr)
    assert "vignette3" not in seen, "2단계에 3단계 비네트가 그려짐"
    m.phase = 3
    r._theme_to, r._theme_t0 = 3, -10.0
    r.render(m, app.sound_mgr)
    assert "vignette3" in seen, "3단계인데 비네트가 없음"
    seen.clear()
    m.shake_scale = 0                                             # 진동 효과 끔: 맥박 없이 고정이지만 그려는 짐
    r.render(m, app.sound_mgr)
    assert "vignette3" in seen
    assert abs(r._heartbeat(m) - 0.4) < 1e-9


def test_curved_tether_draws_dashes_along_the_curve():
    app, m = _app()
    r = app.renderer
    segs = []
    orig = pygame.draw.line
    import gfx
    r.screen = type("S", (), {})()                               # 그리기 호출만 가로채는 가짜 화면
    saved = pygame.draw.line
    pygame.draw.line = lambda surf, color, a, b, w=1: segs.append((a, b))
    try:
        r._draw_targeting_laser((100, 100), (700, 500), (255, 80, 90), 30.0)
    finally:
        pygame.draw.line = saved
        r.screen = gfx.CANVAS
    assert len(segs) >= 8, len(segs)
    # 직선(두 점을 잇는 선)에서 벗어나 휘어 있어야 함
    import math
    dx, dy = 600.0, 400.0
    dev = max(abs((px - 100) * dy - (py - 100) * dx) / math.hypot(dx, dy) for (px, py), _ in segs)
    assert dev > 10, f"곡선이 아니라 직선: 최대 이탈 {dev:.1f}px"


def test_skyline_is_off_by_default_and_toggles_from_settings():
    app, m = _app()
    r = app.renderer
    assert app.settings.get("board_skyline") is False and r.skyline is False, "지형 윤곽선 기본값은 꺼짐"
    calls = []
    orig = r._skyline_surface
    r._skyline_surface = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
    m.local_engine.grid[19][0] = "I"
    r.render(m, app.sound_mgr)
    assert not calls, "꺼져 있는데 윤곽선을 그림"
    rim = []
    orig_rim = r._draw_active_rim
    r._draw_active_rim = lambda *a, **k: (rim.append(1), orig_rim(*a, **k))[1]
    r.render(m, app.sound_mgr)
    assert not rim, "꺼져 있는데 조작 블록 테두리를 그림"
    app.state, app.previous_state, app.settings_tab = "SETTINGS", "MENU", "help"
    app._settings_activate("skyline=on")
    assert app.settings.get("board_skyline") is True and r.skyline is True
    r.render(m, app.sound_mgr)
    assert calls, "켰는데 윤곽선을 그리지 않음"
    assert rim, "켰는데 조작 블록 테두리를 그리지 않음"
    calls.clear()
    app._settings_activate("skyline_toggle")                         # 토글 버튼은 반대로
    assert app.settings.get("board_skyline") is False and r.skyline is False
    r.render(m, app.sound_mgr)
    assert not calls
    app.settings.set("board_skyline", True)
    app.settings_tab = "help"
    app._reset_current_tab()                                         # 이 탭 기본값으로 -> 다시 꺼짐
    assert app.settings.get("board_skyline") is False


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
        print("[ALL BOARD VISUAL TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
