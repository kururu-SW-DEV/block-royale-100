"""
칸별 너비 검사: 영어 UI에서 글자가 자기 칸(상자) 밖으로 삐져나오는지 확인.
방법: 같은 화면 묶음을 한국어/영어로 한 번씩 그리면서 (1) 그려진 상자(채워진/테두리 사각형, 40x18 이상)와 (2) 글자 위치를 논리 좌표로 기록하고,
글자의 가운데가 들어 있는 가장 작은 상자 밖으로 글자 끝이 나가면 '넘침'으로 본다. 한국어에서도 같은 자리에서 넘치는 것(의도된 디자인)은 제외하고,
영어에서만 새로 생긴 넘침이 있으면 실패. (\"1 lines incoming soon\"이 받을 공격 칸을 넘던 문제 같은 것을 미리 잡기 위함)
실행: python test_ui_fit.py
"""
import datetime
import os
import random
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from gfx import CANVAS, HiFont, HiSurf
import i18n
from config import week_key

MIN_BOX_W, MIN_BOX_H = 40, 18          # 이보다 작은 사각형(줄, 막대, 점)은 '칸'으로 보지 않음
SLACK = 2                              # 반올림 오차 허용 (px)


class Recorder:
    """한 화면(프레임) 단위로 상자와 글자를 모음"""

    def __init__(self):
        self.boxes, self.texts = [], []
        self.seq = 0
        self.over = {}                                  # 시그니처 -> (글자, 상자) 넘침 목록

    def reset_frame(self):
        self.boxes, self.texts = [], []

    def check(self):
        for t, txt, tseq in self.texts:
            cx, cy = t.center
            cands = [(sq, b) for sq, b in self.boxes if sq < tseq and b.collidepoint(cx, cy) and b.w >= MIN_BOX_W and b.h >= MIN_BOX_H]
            if not cands:
                continue
            b = max(cands, key=lambda c: c[0])[1]               # 글자 아래에 가장 마지막으로 그려진 상자 (뒤에 깔린 다른 화면의 상자는 무시)
            if t.w <= 2:
                continue
            if t.left < b.left - SLACK or t.right > b.right + SLACK or t.top < b.top - 8 or t.bottom > b.bottom + 8:
                sig = (tuple(b), t.y // 6)
                self.over.setdefault(sig, (txt, tuple(b), tuple(t)))


def _install(rec):
    """pygame.draw.rect / Canvas.blit 을 감싸 기록 (원래 동작은 그대로)"""
    from ui_renderer import UIRenderer
    orig_rect, orig_blit, orig_render = pygame.draw.rect, CANVAS.blit, HiFont.render
    orig_panel, orig_alpha = UIRenderer._panel, CANVAS.alpha_rect

    def panel(self, r, *a, **k):
        rr = pygame.Rect(r)
        rec.seq += 1
        rec.boxes.append((rec.seq, rr))                  # 반투명 판(_panel)도 칸으로 기록
        return orig_panel(self, r, *a, **k)

    def alpha_rect(r, color, width=0, radius=0):
        if width == 0:
            rr = pygame.Rect(r)
            rec.seq += 1
            rec.boxes.append((rec.seq, rr))
        return orig_alpha(r, color, width, radius)

    def rect(surface, color, r, width=0, border_radius=0):
        if surface is CANVAS:
            rr = pygame.Rect(r)
            if width <= 3:
                rec.seq += 1
                rec.boxes.append((rec.seq, rr))
        return orig_rect(surface, color, r, width, border_radius=border_radius)

    def blit(src, dest=(0, 0), area=None):
        txt = getattr(src, "_txt", None)
        if txt is not None and isinstance(src, HiSurf):
            dx, dy = (dest.topleft if hasattr(dest, "topleft") else (dest[0], dest[1]))
            w, h = src.get_size()
            br = src.get_bounding_rect()
            rec.seq += 1
            rec.texts.append((pygame.Rect(dx + br.x, dy + br.y, br.w, br.h), txt, rec.seq))
        return orig_blit(src, dest, area)

    def render(self, text, *a, **k):
        surf = orig_render(self, text, *a, **k)
        try:
            surf._txt = text if isinstance(text, str) else ""
        except Exception:
            pass
        return surf

    pygame.draw.rect, CANVAS.blit, HiFont.render = rect, blit, render
    UIRenderer._panel, CANVAS.alpha_rect = panel, alpha_rect
    return orig_rect, orig_blit, orig_render, orig_panel, orig_alpha


def _uninstall(origs):
    from ui_renderer import UIRenderer
    pygame.draw.rect, CANVAS.blit, HiFont.render, UIRenderer._panel, CANVAS.alpha_rect = origs


def scenes(app, snap):
    """검사할 화면들을 차례로 그림. snap(label)을 화면마다 호출 (프레임 단위로 검사)"""
    frames = lambda n, dt=1 / 60: [app._tick_game(dt) for _ in range(n)]
    app.state = "MENU"
    for _ in range(40):
        app._update_menu(1 / 60)
    app._render_menu()
    snap("menu")
    for tab in ("match", "general", "audio", "keys", "react", "rules", "help"):
        app.state, app.previous_state, app.settings_tab = "SETTINGS", "MENU", tab
        for f in range(6):
            app.settings_focus[tab] = f
            app._kb_nav = True
            app._render_settings()
            snap(f"settings-{tab}-{f}")
    app.state = "RECORDS"
    for mode in ("battle", "survival", "trend", "score", "replay"):
        app.records_mode = mode
        app._render_records()
        snap(f"records-{mode}")
    app.records_mode = "achv"
    for pg in range(6):
        app.records_ach_page = pg
        app._render_records()
        snap(f"achv-{pg}")
    app.state = "MENU"
    app._open_rules()
    app._render_rules()
    snap("rules")
    app._close_rules()
    for st, fn in (("HOST_LOBBY", "_render_host_lobby"), ("JOIN_MENU", "_render_join_menu"), ("CLIENT_LOBBY", "_render_client_lobby")):
        app.state = st
        getattr(app, fn)()
        snap(st)
    for kw in (dict(daily=datetime.date.today().strftime("%Y%m%d")), dict(weekly=week_key())):
        app.start_game(mode="SOLO", total_players=40, **kw)
        frames(20)
        app._render_brief()
        snap("brief-" + ("daily" if "daily" in kw else "weekly"))
    # 경기 화면: 받을 공격 1줄 / 12줄 / 큰 콤보, 연습 패널
    app.start_game(mode="SOLO", total_players=40)
    m = app.match
    m.countdown_until = 0.0
    frames(60)
    for n in (1, 12, 30):
        m.local_engine.incoming_garbage = 0
        m.local_engine.queue_garbage(n, source="X", instant=True)
        frames(30)
        app.renderer.render(m, app.sound_mgr)
        snap(f"game-incoming-{n}")
    m.local_engine.combo = 14
    m.local_engine.b2b = True
    frames(5)
    app.renderer.render(m, app.sound_mgr)
    snap("game-combo")
    app.start_game(mode="SOLO", total_players=20, practice=True)
    frames(30)
    app.renderer.render(app.match, app.sound_mgr)
    snap("practice")
    app.settings.set("rule_team", True)
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    frames(90)
    app.renderer.render(m, app.sound_mgr)
    snap("team-game")
    app.is_paused = m.is_paused = True                  # 일시정지 창은 결과 창과 겹쳐 그리지 않도록 따로
    frames(3)
    app.renderer.render(m, app.sound_mgr)
    snap("pause")
    app.is_paused = m.is_paused = False
    foes = [p for p in m.players if p != m.local_player_id and not m.is_ally(m.local_player_id, p)]
    m._eliminate_player(m.local_player_id, foes[0])
    frames(10)
    app.renderer._res_t0 -= 6
    app.renderer._result_t0 -= 6
    frames(10)
    app.renderer.render(m, app.sound_mgr)
    snap("result")
    app.settings.set("rule_team", False)


def collect(lang):
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    i18n.set_language(lang)
    rec = Recorder()
    origs = _install(rec)
    random.seed(11)
    app.renderer.render_frame_hook = None

    def snap(label):
        rec.check()
        rec.reset_frame()

    # 화면 함수는 호출 때마다 상자/글자를 기록하므로, 화면 하나를 그리기 직전에 기록을 비우도록 렌더 함수들을 감쌈
    for name in ("_render_menu", "_render_settings", "_render_records", "_render_rules", "_render_host_lobby", "_render_join_menu",
                 "_render_client_lobby", "_render_brief"):
        fn = getattr(app, name)

        def wrap(fn=fn):
            rec.reset_frame()
            return fn()
        setattr(app, name, wrap)
    rr = app.renderer.render

    def render(match, sound=None):
        rec.reset_frame()
        return rr(match, sound)
    app.renderer.render = render
    try:
        scenes(app, snap)
    finally:
        _uninstall(origs)
        i18n.set_language("ko")
    return rec.over


def main():
    if not pygame.font.match_font("malgungothic"):
        # 글자 폭은 글꼴에 따라 달라지므로, 실제 게임이 쓰는 맑은 고딕이 없는 PC(예: GitHub Actions 러너)에서는 비교가 의미 없어 건너뜀
        print("[SKIP] 맑은 고딕이 없어 칸별 너비 검사를 건너뜁니다")
        print("[ALL UI FIT TESTS PASSED] (skipped)")
        return
    ko = collect("ko")
    en = collect("en")
    new = {sig: v for sig, v in en.items() if sig not in ko}
    if new:
        for sig, (txt, box, t) in list(new.items())[:25]:
            print(f"넘침: {txt!r}  글자 {t}  칸 {box}")
        ex = "; ".join(f"{v[0]!r} 글자{v[2]} 칸{v[1]}" for v in list(new.values())[:4])
        raise AssertionError(f"영어에서만 칸 밖으로 넘치는 글자 {len(new)}곳 ({ex})")
    print(f"[ALL UI FIT TESTS PASSED] (한국어에서도 같은 자리에서 넘치는 {len(ko)}곳은 의도된 디자인으로 제외)")


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
