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


def rules_card_data():
    """(제목, [(왼쪽, 오른쪽)...]) 목록 3칸. 렌더링과 테스트가 같은 데이터를 쓴다."""
    ga, ts, tm = config.GARBAGE_ATTACK_TABLE, config.TSPIN_ATTACK_TABLE, config.TSPIN_MINI_ATTACK_TABLE
    attacks = [("싱글(1줄)", f"{ga.get(1, 0)}줄"), ("더블(2줄)", f"{ga.get(2, 0)}줄"),
               ("트리플(3줄)", f"{ga.get(3, 0)}줄"), ("쿼드(4줄)", f"{ga.get(4, 0)}줄"),
               ("T-스핀 싱글/더블/트리플", f"{ts.get(1, 0)} / {ts.get(2, 0)} / {ts.get(3, 0)}줄"),
               ("T-스핀 미니 싱글/더블", f"{tm.get(1, 0)} / {tm.get(2, 0)}줄"),
               ("퍼펙트 클리어", f"+{config.PERFECT_CLEAR_ATTACK}줄"),
               ("연속 콤보", f"+{config.COMBO_BONUS[2]}~{config.COMBO_BONUS[-1]}줄")]
    badges = [(f"K.O. {need}개", f"공격력 +{int(pct * 100)}%") for need, pct in config.BADGE_TIERS if need > 0]
    bonus = [(f"{n}명이 나를 노림", f"+{config.ATTACKER_BONUS[n]}줄") for n in (2, 3, 4, 5)]
    bonus.append(("6명 이상", f"+{config.ATTACKER_BONUS[6]}줄"))
    return [("공격 줄 수", attacks), ("K.O. 배지 (공격력 증폭)", badges), ("역습 보너스", bonus)]


def rules_card_notes():
    esc = BattleRoyaleMatch
    return [
        f"받은 공격은 {config.GARBAGE_CHARGE_DELAY}초 차징 뒤에 올라옵니다. 그 사이에 줄을 지우면 먼저 깎입니다. (한 번에 최대 {config.MAX_GARBAGE_PER_LOCK}줄)",
        f"경기 시작 {int(esc.ESCALATION_START // 60)}분부터 매분 공격력 +{int(esc.ESCALATION_PER_MIN * 100)}% (최대 ×{esc.ESCALATION_MAX:.1f}). 생존자가 절반이 되면 PHASE 2, 더 줄면 FINAL.",
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
        cols = rules_card_data()
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
        for j, note in enumerate(rules_card_notes()):
            r._draw_text("• " + note, r.font_small, C_ORANGE if j else C_GREEN, x + 28, ny + j * 24)
