"""
영어 UI: 번역표/화면 전환/업적/충돌 검사, 순위표 줄바꿈
실행: python test_i18n.py
"""
import os
import sys
import time
import json
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
    return app


def test_i18n_templates_are_valid_and_translations_work():
    import re
    import importlib
    import i18n
    i18n.set_language("ko")
    assert i18n.tr("빠른 시작") == "빠른 시작", "한국어 모드는 원문 그대로"
    problems = []
    for name in ("i18n_en", "i18n_en2", "i18n_en3", "i18n_en4"):
        mod = importlib.import_module(name)
        for ko, en in mod.TEMPLATES.items():
            n = len(re.findall(r"\{\}|\{#\}", ko))
            auto, manual = len(re.findall(r"\{\}", en)), re.findall(r"\{(\d+)\}", en)
            if (auto and manual) or (manual and max(map(int, manual)) >= n) or auto > n:
                problems.append((name, ko))
            try:
                en.format(*(["x"] * n))
            except Exception:
                problems.append((name, ko, "format"))
        for ko in mod.EXACT:
            assert isinstance(mod.EXACT[ko], str) and mod.EXACT[ko], ko
    assert not problems, problems
    i18n.set_language("en")
    try:
        assert i18n.tr("빠른 시작") == "Quick Start"
        assert i18n.tr("내 IP 192.168.0.5") == "My IP 192.168.0.5", "숫자/이름이 끼는 틀"
        assert i18n.tr("봇 98명과 바로 대전합니다.  ← → 로 인원, D 로 봇 난이도를 바꿀 수 있어요.   ★ 다음 도전: 쉬움 봇 50인↑에서 10위 안") ==             "Play right away vs 98 bots.  ←/→ players, D bot difficulty.   ★ Next goal: top 10 vs Easy bots with 50+ players"
        assert i18n.tr("단일 경기 최다: 19명 · 명장면 9회").startswith("Most in one match: 19"), "숫자 틀이 다른 문장을 삼키지 않음"
        assert i18n.tr("번역 없는 문장입니다") == "번역 없는 문장입니다", "번역이 없으면 한국어 그대로"
        assert i18n.tr("Quick") == "Quick" and i18n.tr("") == "" and i18n.tr(5) == 5
        assert i18n.tr("★ 위기 탈출! ★") == "★ Clutch escape! ★"
        assert i18n.tr("방어 −3줄") == "Blocked −3 lines"
        assert i18n.tr("로열 빅토리!") == "Royale Victory!"
    finally:
        i18n.set_language("ko")
    print("  OK 번역 틀/번역")


def test_language_setting_switches_screens_without_errors():
    import i18n
    from gfx import HiFont
    app = _app()
    assert HiFont.text_filter is i18n.tr
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "match", "MENU"
    app._render_settings()
    app._settings_activate("lang=en")
    assert app.settings.get("language") == "en" and i18n.language() == "en"
    app.settings.set("bot_difficulty", "easy")          # 설명 줄 검사는 쉬움 난이도 설명이 보여야 함 (기본값 "mixed"인 새 환경에서도 같게)
    seen = []
    orig = HiFont.render
    HiFont.render = lambda self, text, *a, **k: (seen.append(i18n.tr(text)), orig(self, text, *a, **k))[1]
    try:
        for tab in ("match", "general", "audio", "keys", "react", "rules", "help"):
            app.settings_tab = tab
            app._render_settings()
        app.state = "MENU"
        for _ in range(3):
            app._update_menu(1 / 60)
            app._render_menu()
        app.start_game(mode="SOLO", total_players=20)
        app.match.countdown_until = 0.0
        for _ in range(30):
            app._tick_game(1 / 60)
    finally:
        HiFont.render = orig
    assert "Quick Start" in seen and "Settings" in seen and any(t.startswith("Alive") for t in seen), seen[:30]
    assert "Easy (beginner)" in seen and any(t.startswith("The AI reacts slowly") for t in seen), "설명 줄도 번역된 글자로 줄임"
    app.state, app.settings_tab = "SETTINGS", "match"
    app._settings_activate("lang=ko")
    assert app.settings.get("language") == "ko" and i18n.tr("빠른 시작") == "빠른 시작"
    import settings_manager as S
    assert S._valid_setting("language", "fr")[0] is False and S._valid_setting("language", "en") == (True, "en")
    print("  OK 언어 전환")


def test_english_achievements_challenges_rules():
    import i18n
    from stats_manager import ACHIEVEMENTS
    import challenges
    import re
    han = re.compile(r"[가-힣]")
    i18n.set_language("en")
    try:
        for a in ACHIEVEMENTS:
            assert not han.search(i18n.tr(a[1])), a[1]
            assert not han.search(i18n.tr(a[2])), a[2]
        assert i18n.tr("주간 변형  ·  안개 속") == "Weekly Variant  ·  In the Fog"
    finally:
        i18n.set_language("ko")


def test_i18n_files_do_not_conflict():
    """번역 파일 여러 개를 이어 읽으므로, 같은 한국어 문구가 파일마다 다른 영어로 있으면 어느 것이 이길지 읽는 순서에 달려 있음 -> 값이 다른 중복은 금지"""
    import importlib
    for kind in ("EXACT", "TEMPLATES"):
        seen = {}
        for m in ("i18n_en", "i18n_en2", "i18n_en3", "i18n_en4", "i18n_en5"):
            for k, v in getattr(importlib.import_module(m), kind, {}).items():
                assert k not in seen or seen[k][1] == v, f"{kind} 충돌: {k!r}: {seen[k][0]}={seen[k][1]!r} / {m}={v!r}"
                seen.setdefault(k, (m, v))


def test_standings_info_lines_wrap_instead_of_truncating():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(3):
        app._tick_game(1 / 60)
    for pid in list(m.players):
        if pid != m.local_player_id and m.players[pid]["is_alive"]:
            m._eliminate_player(pid, m.local_player_id)
    m.reward = {"xp": {"gain": 99, "parts": [], "before": 0, "after": 99, "lv_before": 1, "lv_after": 1}, "highlights": ["perfect", "chain_ko"], "unlocks": ["불씨", "프리즘", "별빛"],
                "next_unlock": None, "grade": "S", "score": {"score": 1234, "place": 1, "best": True}}
    m.new_records = ["rank", "ko", "combo"]
    m.new_achievements = ["first_ko", "ko5", "top10", "combo8", "victory"]
    lines = app.renderer._standings_info_lines(m)
    assert lines and all("…" not in t for t, _c in lines), lines
    assert all(app.renderer.font_small.size(t)[0] <= 1060 for t, _c in lines)
    print("  OK 순위표 머리 줄")


def test_translation_tables_are_imported_statically():
    """번역표 묶음(i18n_en*.py)은 정적 import로 읽어야 PyInstaller가 exe에 넣음. importlib로 이름을 만들어 읽으면 exe에서 영어가 통째로 빠짐 (v1.2.0~v1.4.3 버그)"""
    import ast
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tree = ast.parse(open(os.path.join(root, "i18n.py"), encoding="utf-8").read())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    files = {f[:-3] for f in os.listdir(root) if f.startswith("i18n_en") and f.endswith(".py")}
    assert files and files <= imported, f"정적 import 안 된 번역표: {sorted(files - imported)}"
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "import_module" for n in ast.walk(tree)), "importlib.import_module은 exe 빌드에서 모듈이 빠질 수 있음"


def test_no_glyphs_missing_from_the_game_font():
    """맑은 고딕에는 체크/가위표 기호(✓ ✔ ✗ ✘ ✕)가 없어 네모(두부 글자)로 깨져 보임 -> 화면에 그리는 글에 쓰지 않음 (●○■□ 같은 있는 기호를 쓸 것)"""
    bad = "✓✔✗✘✕"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hits = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("tests", "backups", "tools", "build_tmp", "release", "docs", ".git", "__pycache__")]
        for f in files:
            if f.endswith(".py"):
                text = open(os.path.join(base, f), encoding="utf-8").read()
                for i, line in enumerate(text.splitlines(), 1):
                    if any(c in line for c in bad) and not line.lstrip().startswith("#"):
                        hits.append(f"{f}:{i}")
    assert not hits, f"글꼴에 없는 기호 사용: {hits}"


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
        print("[ALL I18N TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
