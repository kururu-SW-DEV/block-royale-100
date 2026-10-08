"""
Block Royale 100 - 규칙 요약 카드 (F1)
게임 안(일시정지 포함)과 메뉴 어디서든 F1로 열어 공격표 / 배지 / 역습 보너스 / 조준 모드 / 경기 흐름을 한 화면에서 확인.
표의 숫자는 config 상수에서 직접 읽어 와서 규칙을 바꿔도 이 화면이 어긋나지 않는다.
BlockRoyaleApp(main.py)이 상속하는 믹스인.
"""

from app_common import C_ACCENT, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, SCREEN_HEIGHT, SCREEN_WIDTH, pygame
import config
from battle_royale import BattleRoyaleMatch


def rules_card_data(match=None):
    """(제목, [(왼쪽, 오른쪽)...]) 목록 3칸. 렌더링과 테스트가 같은 데이터를 쓴다. match가 있으면 그 경기의 주간 변형 값을 반영"""
    mut = (getattr(match, "mutator", None) or {}) if match is not None else {}
    pc = int(mut.get("perfect_attack", config.PERFECT_CLEAR_ATTACK))
    ga, ts, tm = config.GARBAGE_ATTACK_TABLE, config.TSPIN_ATTACK_TABLE, config.TSPIN_MINI_ATTACK_TABLE
    attacks = [("싱글(1줄)", f"{ga.get(1, 0)}줄"), ("더블(2줄)", f"{ga.get(2, 0)}줄"),
               ("트리플(3줄)", f"{ga.get(3, 0)}줄"), ("쿼드(4줄)", f"{ga.get(4, 0)}줄"),
               ("T-스핀 싱글/더블/트리플", f"{ts.get(1, 0)} / {ts.get(2, 0)} / {ts.get(3, 0)}줄"),
               ("T-스핀 미니 싱글/더블", f"{tm.get(1, 0)} / {tm.get(2, 0)}줄"),
               ("퍼펙트 클리어" + (" (이번 주 변형)" if pc != config.PERFECT_CLEAR_ATTACK else ""), f"+{pc}줄"),
               ("연속 콤보", f"+{config.COMBO_BONUS[2]}~{config.COMBO_BONUS[-1]}줄")]
    badges = [(f"K.O. {need}개", f"공격력 +{int(pct * 100)}%") for need, pct in config.BADGE_TIERS if need > 0]
    bonus = [(f"{n}명이 나를 노림", f"+{config.ATTACKER_BONUS[n]}줄") for n in (2, 3, 4, 5)]
    bonus.append(("6명 이상", f"+{config.ATTACKER_BONUS[6]}줄"))
    return [("공격 줄 수", attacks), ("K.O. 배지 (공격력 증폭)", badges), ("역습 보너스", bonus)]


def rules_card_notes(match=None):
    esc = BattleRoyaleMatch
    start = float(getattr(match, "ESCALATION_START", esc.ESCALATION_START) or esc.ESCALATION_START) if match is not None else esc.ESCALATION_START
    return [
        f"받은 공격은 {config.GARBAGE_CHARGE_DELAY}초 차징 뒤에 올라옵니다. 그 사이에 줄을 지우면 먼저 깎입니다. (한 번에 최대 {config.MAX_GARBAGE_PER_LOCK}줄)",
        f"경기 시작 {start / 60:.0f}분부터 매분 공격력 +{int(esc.ESCALATION_PER_MIN * 100)}% (최대 ×{esc.ESCALATION_MAX:.1f}). 생존자가 절반이 되면 PHASE 2, 더 줄면 FINAL.",
    ]


class RulesMixin:
    def _open_rules(self):
        if self.rules_open:
            return
        self.rules_open = True
        self._clear_input_state()
        if self._auto_pause_solo():                      # 혼자 하는 경기는 규칙을 읽는 동안 멈춤
            self._paused_by_rules = True                 # 규칙 카드가 멈춘 것: 닫으면 다시 이어서 진행
        self.sound_mgr.play('move')

    def _close_rules(self):
        self.rules_open = False
        if getattr(self, "_paused_by_rules", False):     # 규칙 카드를 열려고 자동으로 멈춘 경기는 닫을 때 일시정지 창에 갇히지 않고 바로 재개
            self._paused_by_rules = False
            if self.is_paused and self.match is not None and self.state == "GAME":
                self.is_paused = False
                self.match.is_paused = False
                self.sound_mgr.unpause_bgm()
        self.sound_mgr.play('move')

    def _handle_rules_event(self, event):
        """규칙 카드가 열려 있는 동안의 입력: 아무 키나 클릭으로 닫음"""
        if (event.type == pygame.KEYDOWN and event.key not in self._MODIFIER_KEYS) or (event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3)):
            self._close_rules()

    # 조준 모드 한 줄 요약 (긴 설명은 게임 중 조준 칸 툴팁에 있음)
    TARGET_SHORT = {"AUTO": ("자동", "사람 우선, 없으면 탈락 직전인 상대"), "KO": ("K.O.", "쌓인 블록 + 받을 공격이 가장 큰 상대"),
                    "ATTACKERS": ("반격", "나를 노리는 상대에게 (여럿이면 동시에)"), "BADGES": ("배지", "K.O.를 가장 많이 쌓은 상대"),
                    "RANDOM": ("랜덤", "무작위 1명을 노리고 계속 유지")}

    def _rules_card(self, rect, title, accent):
        """규칙 카드 안의 구역 하나: 연한 면 + 제목 앞 색 막대"""
        r = self.renderer
        r._panel(rect, border=(46, 58, 92), bg=(21, 27, 46), radius=12, alpha=235)
        pygame.draw.rect(self.screen, accent, (rect.x + 16, rect.y + 17, 4, 20), border_radius=2)
        r._draw_text(title, r.font_mid, C_TEXT, rect.x + 28, rect.y + 14)

    def _render_rules(self):
        """규칙 요약 (F1): 위쪽에 숫자 표 3개(공격 줄 수 / K.O. 배지 / 역습 보너스), 아래쪽에 조준 모드와 경기 흐름. 구역마다 카드로 나누고 색은 제목 막대에만 씀"""
        from gfx import CANVAS
        r = self.renderer
        self.screen = CANVAS
        CANVAS.overlay((4, 6, 12, 215))
        w, h = 1120, 620
        x, y = (SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2
        r._panel((x, y, w, h), border=(64, 78, 118), bg=(14, 18, 32), radius=18, alpha=250, border_w=1)
        r._draw_text("규칙 요약", r.font_large, C_TEXT, x + 28, y + 16)
        r._draw_text("아무 키나 클릭으로 닫기  ·  F1", r.font_tiny, C_DIM, x + w - 28, y + 28, "topright")
        game_match = self.match if (self.state == "GAME" and self.match is not None) else None
        cols = rules_card_data(game_match)
        gap, pad = 14, 24
        col_w = (w - 2 * pad - 2 * gap) // 3
        top, card_h = y + 68, 284
        accents = (C_ACCENT, C_GOLD, C_ORANGE)
        for ci, (title, rows) in enumerate(cols):
            rect = pygame.Rect(x + pad + ci * (col_w + gap), top, col_w, card_h)
            self._rules_card(rect, title, accents[ci])
            row_h = 27
            for i, (a, b) in enumerate(rows):
                ry = rect.y + 54 + i * row_h
                r._draw_text(a, r.font_small, (205, 214, 232), rect.x + 20, ry)
                r._draw_text(b, r.font_small, C_GOLD, rect.right - 20, ry, "topright")
                if i < len(rows) - 1:
                    pygame.draw.line(self.screen, (36, 46, 74), (rect.x + 18, ry + row_h - 4), (rect.right - 18, ry + row_h - 4), 1)
            if ci == 2:
                r._draw_text("여럿이 나를 노릴 때 내 공격에 더해집니다", r.font_tiny, C_DIM, rect.x + 20, rect.bottom - 30)
        # 아래 줄: 조준 모드 (왼쪽, 넓게) + 경기 흐름 (오른쪽)
        by = top + card_h + gap
        bh = y + h - pad - by
        left_w = col_w * 2 + gap
        aim = pygame.Rect(x + pad, by, left_w, bh)
        self._rules_card(aim, "조준 모드", C_GREEN)
        r._draw_text("TAB 순환  ·  1~5 선택  ·  상단 칩 클릭", r.font_tiny, C_DIM, aim.right - 20, aim.y + 20, "topright")
        for i, mode in enumerate(config.TARGET_MODES):
            name, desc = self.TARGET_SHORT.get(mode, (mode, ""))
            ry = aim.y + 54 + i * 28
            r._draw_text(f"{i + 1}", r.font_tiny, C_DIM, aim.x + 22, ry + 3)
            r._draw_text(name, r.font_small, C_TEXT, aim.x + 44, ry)
            r._draw_text(desc, r.font_small, (150, 162, 192), aim.x + 130, ry)
        flow = pygame.Rect(aim.right + gap, by, col_w, bh)
        self._rules_card(flow, "경기 흐름", (255, 120, 120))
        fy = flow.y + 52
        for note in rules_card_notes(game_match):
            lines = r._wrap_words(note, r.font_small, flow.w - 44)
            r._draw_text("•", r.font_small, C_GOLD, flow.x + 20, fy)
            for ln in lines[:4]:
                r._draw_text(ln, r.font_small, (205, 214, 232), flow.x + 36, fy)
                fy += 22
            fy += 8


class BriefMixin:
    """오늘의 도전 / 주간 변형 시작 전 브리핑 카드: 규칙·목표·기록을 크게 보여 주고, 아무 키나 누르면 3-2-1 카운트다운을 시작"""

    def _close_brief(self):
        import time as _t
        m = self.match
        m.brief_open = False
        now = _t.time()
        m.countdown_until = now + m.COUNTDOWN_SECS
        if getattr(m, "coach_pending", False):
            m.coach_until = max(getattr(m, "coach_until", 0.0), now + m.COUNTDOWN_SECS + 12.0)     # 첫 판 코치는 카드를 닫은 뒤부터 보이게
        self.sound_mgr.play('move')

    # 단독으로 눌러도 창을 닫거나 경기를 시작하면 안 되는 수식키
    _MODIFIER_KEYS = frozenset(getattr(pygame, n) for n in ("K_LSHIFT", "K_RSHIFT", "K_LCTRL", "K_RCTRL", "K_LALT", "K_RALT", "K_LMETA", "K_RMETA",
                                                          "K_CAPSLOCK", "K_NUMLOCK", "K_SCROLLOCK", "K_MODE") if hasattr(pygame, n))

    def _handle_brief_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in self._MODIFIER_KEYS:
                return
            if event.key == pygame.K_ESCAPE:
                self.return_to_menu()                                # ESC: 시작하지 않고 메뉴로
            else:
                self._close_brief()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            menu_btn = getattr(self, "brief_menu_btn", None)
            if event.button == 1 and menu_btn is not None and menu_btn.collidepoint(event.pos):
                self.sound_mgr.play('move')
                self.return_to_menu()                                # 메인 메뉴 버튼: 시작하지 않고 메뉴로 (마우스로도 나갈 수 있게)
            else:
                self._close_brief()                                  # 그 밖의 클릭은 지금처럼 시작

    def _render_brief(self):
        import time as _t
        from gfx import CANVAS
        m, ch, r = self.match, self.match.challenge, self.renderer
        if ch is None:
            return
        CANVAS.overlay((4, 6, 12, 222))
        w, h = 940, 560
        x, y = (SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2
        weekly = m.challenge_kind == "weekly"
        accent = C_ORANGE if weekly else C_GREEN
        r._panel((x, y, w, h), border=accent, bg=(16, 20, 36), radius=18, alpha=250, border_w=2)
        if weekly:
            mut = m.mutator or {}
            r._draw_text(f"주간 변형  ·  {mut.get('name', '')}", r.font_title, accent, x + w // 2, y + 22, "midtop", shadow=True)
            r._draw_text(f"{m.weekly}  ·  이번 주만의 규칙", r.font_tiny, C_DIM, x + w // 2, y + 74, "midtop")
            box = pygame.Rect(x + 40, y + 100, w - 80, 56)
            r._panel(box, border=accent, bg=(34, 26, 14), radius=12)
            r._draw_text("바뀐 규칙:  " + str(mut.get("desc", "")), r.font_large, C_GOLD, box.centerx, box.centery, "center")
        else:
            import datetime as _dt
            d = _dt.datetime.strptime(m.daily, "%Y%m%d")
            r._draw_text("오늘의 도전", r.font_title, accent, x + w // 2, y + 22, "midtop", shadow=True)
            r._draw_text(f"{d.month}월 {d.day}일  ·  100인 혼합 난이도  ·  모두에게 같은 블록 순서", r.font_tiny, C_DIM, x + w // 2, y + 74, "midtop")
            box = pygame.Rect(x + 40, y + 100, w - 80, 56)
            r._panel(box, border=accent, bg=(14, 32, 26), radius=12)
            r._draw_text("목표 3개를 달성해 별(★)을 모으세요. 여러 번 도전해도 달성한 별은 유지됩니다", r.font_mid, C_TEXT, box.centerx, box.centery, "center")
        r._draw_text("오늘의 목표" if not weekly else "이번 주 목표", r.font_mid, C_ACCENT, x + 44, y + 176)
        for i, gid in enumerate(ch.order):
            g = ch.by_id[gid]
            row = pygame.Rect(x + 40, y + 208 + i * 62, w - 80, 54)
            got = gid in ch.done
            r._panel(row, border=C_GREEN if got else (60, 74, 110), bg=(18, 36, 30) if got else (20, 26, 46), radius=10)
            r._draw_text("★" * int(g["tier"]) + "☆" * (3 - int(g["tier"])), r.font_mid, C_GOLD, row.x + 18, row.centery, "midleft")
            r._draw_text(g["text"], r.font_large, C_TEXT, row.x + 120, row.centery, "midleft")
            r._draw_text("● 달성함" if got else "도전!", r.font_mid, C_GREEN if got else C_DIM, row.right - 20, row.centery, "midright")
        fy = y + 208 + 3 * 62 + 8
        lines = []
        if weekly:
            best = self.stats_mgr.weekly_best(m.weekly)
            lines.append(f"이번 주 최고 순위: {'#' + str(best) + '위' if best else '아직 기록 없음'}   ·   별 {len(ch.done)}/3")
        else:
            g = m.ghost
            if g:
                gs = int(g["secs"])
                lines.append(f"지난 최고: {g['rank']}위 · {gs // 60}:{gs % 60:02d} 생존   ·   {g['tries'] + 1}번째 도전")
            else:
                lines.append("오늘 첫 도전입니다 — 기록이 남아 다음 도전에서 비교됩니다")
            cur, best_s = self.stats_mgr.streak()
            lines.append(f"연속 출석 {cur}일 (최고 {best_s}일)   ·   별 하나만 따도 출석으로 인정")
        for i, ln in enumerate(lines):
            r._draw_text(ln, r.font_small, C_GOLD if i == 0 else C_DIM, x + w // 2, fy + i * 24, "midtop")
        blink = int(_t.time() * 2) % 2 == 0
        mx, my = pygame.mouse.get_pos()
        start_btn = pygame.Rect(x + w // 2 - 250, y + h - 96, 240, 42)           # 마우스로 시작 / 메인 메뉴로 나가는 버튼 (키보드는 아무 키 / ESC)
        self.brief_menu_btn = pygame.Rect(x + w // 2 + 10, y + h - 96, 240, 42)
        r._button(start_btn, "도전 시작", "green", start_btn.collidepoint(mx, my), "ENTER")
        r._button(self.brief_menu_btn, "메인 메뉴로", "blue", self.brief_menu_btn.collidepoint(mx, my), "ESC")
        r._draw_text("아무 키나 눌러 시작   ·   ESC: 메뉴로", r.font_small, accent if blink else C_DIM, x + w // 2, y + h - 36, "midtop")
