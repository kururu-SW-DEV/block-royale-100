"""
영어 UI 번역 누락 점검: 영어로 바꾼 뒤 주요 화면(메뉴/설정/기록실/경기/결과/일시정지/규칙 카드/오늘의 도전/주간 변형/연습/팀전)을
렌더하면서 글꼴이 그리는 모든 문자열을 모아, 한글이 남은 것이 있으면 실패. (새 문구를 추가하고 번역을 빠뜨리는 회귀를 잡음)
실행: python test_i18n_audit.py
"""
import datetime
import os
import random
import re
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from gfx import CANVAS, HiFont
import main as M
import i18n
from config import week_key

HAN = re.compile(r"[가-힣]")
ALLOWED = {"한국어", "Language / 언어"}          # 언어 선택 줄은 일부러 원래 언어로 표시


def main():
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    i18n.set_language("en")
    missing = {}
    orig = HiFont.render

    def render(self, text, *a, **k):
        out = HiFont.text_filter(text) if HiFont.text_filter else text
        if isinstance(out, str) and HAN.search(out) and out not in ALLOWED:
            missing[out] = missing.get(out, 0) + 1
        return orig(self, text, *a, **k)

    HiFont.render = render
    random.seed(5)
    try:
        frames = lambda n, dt=1 / 60: [app._tick_game(dt) for _ in range(n)]
        app.state = "MENU"
        for _ in range(20):
            app._update_menu(1 / 60)
            app._render_menu()
        for tab in ("match", "general", "audio", "keys", "react", "rules", "help"):
            app.state, app.previous_state, app.settings_tab = "SETTINGS", "MENU", tab
            for f in range(8):
                app.settings_focus[tab] = f
                app._kb_nav = True
                app._render_settings()
        app.state = "RECORDS"
        for mode in ("battle", "survival", "trend", "score", "replay"):
            app.records_mode = mode
            app._render_records()
        app.records_mode = "achv"
        for pg in range(6):
            app.records_ach_page = pg
            app._render_records()
        app.state = "MENU"
        app._open_rules()
        app._render_rules()
        app._close_rules()
        for st, fn in (("HOST_LOBBY", "_render_host_lobby"), ("JOIN_MENU", "_render_join_menu"), ("CLIENT_LOBBY", "_render_client_lobby")):
            app.state = st
            getattr(app, fn)()
        # 오늘의 도전 / 주간 변형 / 연습 / 팀전 경기
        for kw in (dict(daily=datetime.date.today().strftime("%Y%m%d")), dict(weekly=week_key()), dict(practice=True)):
            app.start_game(mode="SOLO", total_players=40, **kw)
            frames(30)
            if app.match.daily or app.match.weekly:
                app._render_brief()
            frames(20)
        app.settings.set("rule_team", True)
        app.start_game(mode="SOLO", total_players=20)
        m = app.match
        m.countdown_until = 0.0
        frames(120)
        m.phase = 2
        frames(30)
        foes = [p for p in m.players if p != m.local_player_id and not m.is_ally(m.local_player_id, p)]
        m._eliminate_player(m.local_player_id, foes[0])
        frames(10)
        app.renderer._res_t0 -= 6
        app.renderer._result_t0 -= 6
        frames(10)
        app.is_paused = m.is_paused = True
        frames(3)
        app.settings.set("rule_team", False)
    finally:
        HiFont.render = orig
        i18n.set_language("ko")
    if missing:
        for k, v in sorted(missing.items(), key=lambda kv: -kv[1])[:40]:
            print(v, repr(k))
        raise AssertionError(f"영어 UI에 번역되지 않은 한글 {len(missing)}종")
    print("[ALL I18N AUDIT TESTS PASSED]")


if __name__ == "__main__":
    pygame.init()
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    keep = {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in (SETTINGS_FILE, STATS_FILE)}
    try:
        main()
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
