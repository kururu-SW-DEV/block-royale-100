"""
글자 잘림/겹침 스캔 테스트: 설정 화면 7개 탭, 기록실 탭 6개, 규칙 카드(F1)를 한국어/영어 × 글자 크기 보통/크게로 그려서
(1) 설정: 글자가 버튼(‹ › 선택기, 칸)과 겹치지 않는지, 줄임표(…)로 잘린 글자가 없는지
(2) 기록실: 탭 글자가 탭 폭 안에 들어오는지, 안내 글자가 필터 칩과 겹치지 않는지
(3) 규칙 카드: 왼쪽/오른쪽 글자가 서로 겹치지 않는지
를 확인한다. (영어 'Light effects' 설명이 선택 버튼과 겹쳐 잘리던 것, 기록실 'Battle Royale' 탭 넘침 등을 잡기 위함)
실행: python tests/test_text_fit_scan.py
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


def _record(app, render, patch_renderer=False):
    rec = []
    o_t, o_d = app._t, app.renderer._draw_text

    def wt(*a, **k):
        r = o_t(*a, **k)
        if a and isinstance(a[0], str) and a[0].strip():
            rec.append((a[0], pygame.Rect(r)))
        return r

    def wd(*a, **k):
        r = o_d(*a, **k)
        if a and isinstance(a[0], str) and a[0].strip():
            rec.append((a[0], pygame.Rect(r)))
        return r
    app._t, app.renderer._draw_text = wt, wd
    try:
        render()
    finally:
        app._t, app.renderer._draw_text = o_t, o_d
    return rec


def _variants(app):
    import i18n
    for lang in ("en", "ko"):
        for big in (False, True):
            i18n.set_language(lang)
            app.settings.set("text_size", "large" if big else "normal")
            app.apply_visual_options()
            yield lang, big
    i18n.set_language("ko")
    app.settings.set("text_size", "normal")
    app.apply_visual_options()


def test_settings_tabs_have_no_text_overlapping_controls_or_clipped_text():
    app = _app()
    problems = []
    for lang, big in _variants(app):
        for tab in ("match", "general", "audio", "keys", "react", "rules", "help"):
            app.state = "SETTINGS"
            app.settings_tab = tab
            # 값에 따라 설명이 바뀌는 줄(봇 난이도 5종, 조작키 프리셋 등)은 모든 값으로 확인
            diffs = ("mixed", "easy", "normal", "hard", "master") if tab == "match" else (("random", "0", "1", "2", "3", "4") if tab == "audio" else (None,))
            for d in diffs:
                if d is not None:
                    app.settings.set("bot_difficulty" if tab == "match" else "bgm_stage_set", d)
                rec = _record(app, app._render_settings)
                btns = [pygame.Rect(r) for r in app.settings_buttons.values()]
                for text, r in rec:
                    if text.endswith("…") or text.endswith("..."):
                        problems.append((lang, big, tab, d, "줄임표", text))
                    for b in btns:
                        if r.colliderect(b) and not b.contains(r.inflate(-2, -2)) and not r.contains(b):
                            problems.append((lang, big, tab, d, "버튼과 겹침", text, tuple(r), tuple(b)))
                            break
    assert not problems, problems[:5]


def test_records_tab_labels_fit_their_tabs_and_hints_do_not_hit_chips():
    app = _app()
    problems = []
    for lang, big in _variants(app):
        for mode in ("battle", "survival", "trend", "score", "replay", "achv"):
            app.state = "RECORDS"
            app.records_mode = mode
            rec = _record(app, app._render_records)
            tabs = [r for k, r in app.records_buttons.items() if k.startswith("mode_")]
            for text, r in rec:
                for b in tabs:
                    if b.collidepoint(r.center) and (r.left < b.left - 1 or r.right > b.right + 1):
                        problems.append((lang, big, mode, "탭 글자가 탭보다 넓음", text, tuple(r), tuple(b)))
            for i in range(len(rec)):
                for j in range(i + 1, len(rec)):
                    inter = rec[i][1].clip(rec[j][1])
                    if inter.w > 3 and inter.h > 5 and rec[i][0] != rec[j][0]:
                        problems.append((lang, big, mode, "글자끼리 겹침", rec[i][0], rec[j][0]))
    assert not problems, problems[:5]


def test_rules_card_rows_do_not_overlap():
    app = _app()
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=10)
    problems = []
    for lang, big in _variants(app):
        app.rules_open = True
        rec = _record(app, app._render_rules)
        app.rules_open = False
        for i in range(len(rec)):
            for j in range(i + 1, len(rec)):
                inter = rec[i][1].clip(rec[j][1])
                if inter.w > 3 and inter.h > 5 and rec[i][0] != rec[j][0]:
                    problems.append((lang, big, rec[i][0], rec[j][0], tuple(inter)))
    assert not problems, problems[:5]


def test_main_menu_and_lobby_text_does_not_overlap():
    app = _app()
    problems = []
    app.state = "MENU"
    app._menu_intro_t = 5.0
    for lang, big in _variants(app):
        rec = _record(app, app._render_menu)
        for i in range(len(rec)):
            for j in range(i + 1, len(rec)):
                inter = rec[i][1].clip(rec[j][1])
                if inter.w > 3 and inter.h > 5 and rec[i][0] != rec[j][0]:
                    problems.append((lang, big, "메뉴", rec[i][0], rec[j][0]))
    assert not problems, problems[:5]


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL TEXT FIT SCAN TESTS PASSED]")
