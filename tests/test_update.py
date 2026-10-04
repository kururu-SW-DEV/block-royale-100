"""
업데이트 확인(옵트인), 요약/건너뛰기/LAN 경고
실행: python test_update.py
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


def test_update_check_parsing_and_fetch():
    import update_check as U
    assert U.parse_version("v1.1.13") == (1, 1, 13) and U.parse_version("1.2.0-beta") == (1, 2, 0) and U.parse_version("x") == ()
    assert U.is_newer("v1.1.14", "1.1.13") and not U.is_newer("v1.1.13", "1.1.13") and not U.is_newer("v1.1.9", "1.1.13")
    assert U.is_newer("v1.2.0", "1.1.99") and not U.is_newer("garbage", "1.1.1")
    ok = lambda url, t: json.dumps({"tag_name": "v9.0.0", "html_url": "https://github.com/x/y/releases/tag/v9.0.0"}).encode()
    assert U.fetch_latest(ok) == {"tag": "v9.0.0", "url": "https://github.com/x/y/releases/tag/v9.0.0", "summary": []}
    evil = lambda url, t: json.dumps({"tag_name": "v9.0.0", "html_url": "http://evil.example/x"}).encode()
    assert U.fetch_latest(evil)["url"] == U.RELEASES_URL, "github.com 밖 주소는 쓰지 않음"
    for bad in (lambda u, t: b"not json", lambda u, t: b"{}", lambda u, t: (_ for _ in ()).throw(OSError("offline"))):
        assert U.fetch_latest(bad) is None
    chk = U.UpdateChecker(opener=ok)
    chk.start()
    for _ in range(100):
        if chk.done:
            break
        time.sleep(0.02)
    assert chk.done and chk.result["tag"] == "v9.0.0"
    old = U.UpdateChecker(opener=lambda u, t: json.dumps({"tag_name": "v0.0.1"}).encode())
    old.start()
    for _ in range(100):
        if old.done:
            break
        time.sleep(0.02)
    assert old.done and old.result is None, "같거나 낮은 버전은 알리지 않음"
    print("  OK 업데이트 확인")


def test_update_badge_and_setting_are_opt_in():
    import update_check as U
    app = _app()
    assert app.settings.get("update_check") is False or app.settings.get("update_check") is True
    app.settings.set("update_check", False, autosave=False)
    app._update_checker = U.UpdateChecker(opener=lambda u, t: json.dumps({"tag_name": "v9.9.9", "html_url": "https://github.com/a/b/releases/tag/v9.9.9"}).encode())
    app._update_checker.start()
    time.sleep(0.3)
    assert app.update_info() is None, "꺼져 있으면 알림도 없음"
    app.settings.set("update_check", True, autosave=False)
    assert app.update_info()["tag"] == "v9.9.9"
    app.state = "MENU"
    for _ in range(3):
        app._update_menu(1 / 60)
        app._render_menu()
    assert "update" in app.menu_buttons
    opened = []
    import webbrowser
    orig = webbrowser.open
    webbrowser.open = lambda url, *a, **k: opened.append(url)
    try:
        app._menu_activate("update")
    finally:
        webbrowser.open = orig
    assert opened == ["https://github.com/a/b/releases/tag/v9.9.9"]
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "help", "MENU"
    app._render_settings()
    app._settings_activate("update=off")
    assert app.settings.get("update_check") is False
    app._settings_activate("errlog" if False else "open_errlog")                # 폴더 열기: 예외 없이 (이 환경에서는 열리지 않아도 됨)
    print("  OK 업데이트 배지/옵트인")


def test_v133_update_summary_skip_and_lan_warning():
    import json
    import update_check as U
    body = "## v1.3.3\n\n**요약**\n- **LAN 팀전** 추가: `T` 키\n- 두 번째 변경\n- 세 번째 변경\n\n### 실행 방법\n- 무시될 항목"
    data = json.dumps({"tag_name": "v1.4.0", "html_url": "https://github.com/x/y/releases/tag/v1.4.0", "body": body})
    info = U.fetch_latest(opener=lambda url, timeout: data.encode())
    assert info["summary"] == ["LAN 팀전 추가: T 키", "두 번째 변경"], info
    assert U.breaks_lan("v1.4.0", "1.3.2") and not U.breaks_lan("v1.3.3", "1.3.2") and U.breaks_lan("v2.0.0", "1.9.9")
    assert U.fetch_latest(opener=lambda url, timeout: json.dumps({"tag_name": "v1.3.3"}).encode())["summary"] == []
    app = _app()
    app.settings.set("update_check", True)
    chk = U.UpdateChecker(opener=lambda url, timeout: data.encode())
    chk.result, chk.done = info, True
    app._update_checker = chk
    app.state = "MENU"
    app._render_menu()
    assert app.update_info() and "update_skip" in app.menu_buttons
    app._menu_activate("update_skip")
    assert app.update_info() is None, "건너뛴 버전이 계속 알려짐"
    chk.result = dict(info, tag="v1.4.1")
    assert app.update_info() is not None, "더 새 버전은 다시 알려야 함"
    app.settings.set("update_check", False)
    app.settings.set("update_skip", "")


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
        print("[ALL UPDATE TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
