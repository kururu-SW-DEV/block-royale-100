"""
Block Royale 100 - 규칙 요약 카드 (F1)
게임 안(일시정지 포함)과 메뉴 어디서든 F1로 열어 공격표 / 배지 / 역습 보너스 / 조준 모드 / 경기 흐름을 한 화면에서 확인.
표의 숫자는 config 상수에서 직접 읽어 와서 규칙을 바꿔도 이 화면이 어긋나지 않는다.
BlockRoyaleApp(main.py)이 상속하는 믹스인.
"""

from app_common import C_ACCENT, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, SCREEN_HEIGHT, SCREEN_WIDTH, pygame
import config
from battle_royale import BattleRoyaleMatch
from ui_renderer import TARGET_MODE_HELP


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
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0
        # 혼자 하는 경기는 규칙을 읽는 동안 멈춤
        if (self.state == "GAME" and self.match is not None and self.net_mgr.mode == "NONE" and not self.is_paused
                and not self.match.match_finished and self.match.local_is_alive):
            self.is_paused = True
            self.match.is_paused = True
            self.renderer.pause_focus = 0
            self.sound_mgr.pause_bgm()
        self.sound_mgr.play('move')

    def _close_rules(self):
        self.rules_open = False
        self.sound_mgr.play('move')

    def _handle_rules_event(self, event):
        """규칙 카드가 열려 있는 동안의 입력: 아무 키나 클릭으로 닫음"""
        if event.type == pygame.KEYDOWN or (event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3)):
            self._close_rules()

    def _render_rules(self):
        from gfx import CANVAS
        r = self.renderer
        CANVAS.overlay((4, 6, 12, 215))
        w, h = 1120, 600
        x, y = (SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2
        r._panel((x, y, w, h), border=C_GOLD, bg=(16, 20, 36), radius=18, alpha=248, border_w=2)
        r._draw_text("규칙 요약", r.font_large, C_GOLD, x + w // 2, y + 18, "midtop")
        r._draw_text("아무 키나 클릭으로 닫기  ·  F1", r.font_tiny, C_DIM, x + w - 24, y + 28, "topright")
        game_match = self.match if (self.state == "GAME" and self.match is not None) else None
        cols = rules_card_data(game_match)
        col_w = (w - 72) // 3
        for ci, (title, rows) in enumerate(cols):
            cx = x + 24 + ci * (col_w + 12)
            r._draw_text(title if len(title) < 22 else title[:22] + "…", r.font_mid, C_ACCENT, cx, y + 76)
            for i, (a, b) in enumerate(rows):
                ry = y + 112 + i * 27
                r._draw_text(a, r.font_small, C_TEXT, cx + 4, ry)
                r._draw_text(b, r.font_small, C_GOLD, cx + col_w - 8, ry, "topright")
        r._draw_text("여럿이 나를 노릴 때 내 공격에 더해집니다", r.font_tiny, C_DIM, x + 24 + 2 * (col_w + 12) + 4, y + 112 + 6 * 27)
        # 조준 모드 5종
        my = y + 340
        r._draw_text("조준 모드  (TAB 순환 · 1~5 선택 · 상단 칩 클릭)", r.font_mid, C_ACCENT, x + 28, my)
        for i, mode in enumerate(config.TARGET_MODES):
            line = TARGET_MODE_HELP.get(mode, "")
            r._draw_text(line if len(line) < 80 else line[:78] + "…", r.font_small, C_TEXT, x + 32, my + 34 + i * 24)
        ny = my + 34 + 5 * 24 + 14
        for j, note in enumerate(rules_card_notes(game_match)):
            r._draw_text("• " + note, r.font_small, C_ORANGE if j else C_GREEN, x + 28, ny + j * 24)


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

    def _handle_brief_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.return_to_menu()                                # ESC: 시작하지 않고 메뉴로
            else:
                self._close_brief()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            self._close_brief()

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
            r._draw_text("달성함 ✓" if got else "도전!", r.font_mid, C_GREEN if got else C_DIM, row.right - 20, row.centery, "midright")
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
        r._draw_text("아무 키나 눌러 시작   ·   ESC: 메뉴로", r.font_mid, accent if blink else C_DIM, x + w // 2, y + h - 40, "midtop")
