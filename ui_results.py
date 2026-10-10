"""
Block Royale 100 - 경기 결과 화면: 순위표 오버레이, 결과 요약, 패인 조언, 타임라인 그래프, 마지막 8초 되감기 패널
UIRenderer가 상속하는 믹스인 (ui_renderer.py에서 코드 변경 없이 옮겨 온 것: 파일 크기를 줄이고 결과 화면 코드를 한곳에 모으기 위함)
"""

import math
import time

import pygame

from config import BOARD_HEIGHT
from gfx import CANVAS, mix_color as _mix
from i18n import tr as _tr
from stats_manager import ACHIEVEMENTS, LADDER_NAMES, level_of, perks_unlocked_between
from ui_palette import C_ACCENT, C_DANGER, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, ease_out as _ease_out


class ResultsMixin:
    def _render_standings_overlay(self, match):
        """경기 종료: 전체 플레이어 성적 리스트. 행이 아래에서부터 차례로 미끄러져 들어오고, 숫자가 올라가며 우승자는 빛남."""
        now = time.time()
        if self._standings_t0 is None:
            self._standings_t0 = now
            self.scroll_standings(-99999)
        t = now - self._standings_t0
        CANVAS.overlay((4, 6, 12, int(210 * self._ease_out(t / 0.5))))

        rows = match.standings()
        n = len(rows)
        info = self._standings_info_lines(match)               # 기록·업적·다음 목표·패인: 우승/상위권 때도 순위표에서 바로 보이게
        nl = len(info)
        box_w, box_h = 1100, 640 + 24 * nl
        bx, by = (self.width - box_w) // 2, max(8, min(60 - 6 * nl, self.height - box_h - 12))
        pop = self._ease_out(t / 0.45)
        by_off = int((1 - pop) * 40)
        won = match.local_rank == 1
        accent = C_GOLD if won else C_ACCENT
        self._panel((bx, by + by_off, box_w, box_h), border=accent, bg=(15, 19, 34), radius=18, alpha=int(248 * pop), border_w=2)
        if pop < 0.6:
            return
        a_head = 255 * self._ease_out((t - 0.3) / 0.4)

        winner = next((r for r in rows if r["rank"] == 1), rows[0] if rows else None)
        me = next((r for r in rows if r["is_local"]), None)
        title = "로열 빅토리!" if won else "경기 종료"
        self._fade_text(title, self.font_title, C_GOLD if won else C_TEXT, bx + box_w // 2, by + 20, a_head, "midtop")
        self._draw_grade_stamp(match, bx + 80, by + 74, t - 0.8)
        if winner:
            sub = f"우승  {winner['name']}" + ("  (나)" if won else "")
            self._fade_text(sub, self.font_hud, C_GOLD, bx + box_w // 2, by + 66, a_head, "midtop")
        if me and not won:
            self._fade_text(f"내 순위  {me['rank']}위 / {n}명", self.font_mid, C_DIM, bx + box_w // 2, by + 92, a_head, "midtop")

        for li, (txt, col) in enumerate(info):
            self._fade_text(txt, self.font_small, col, bx + box_w // 2, by + (92 if won else 118) + 24 * li, a_head, "midtop")

        # 열 머리글
        head_y = by + 124 + 24 * nl
        cols = [("순위", 46, "center"), ("이름", 96, "topleft"), ("K.O.", 520, "topright"), ("라인", 610, "topright"),
                ("APM", 706, "topright"), ("LPM", 800, "topright"), ("점수", 920, "topright"), ("시간", 1030, "topright")]
        for label, cx_, anc in cols:
            self._fade_text(label, self.font_tiny, C_DIM, bx + cx_, head_y, a_head, anc)
        pygame.draw.line(self.screen, (52, 64, 98), (bx + 24, head_y + 22), (bx + box_w - 24, head_y + 22), 1)

        # 행 (스크롤)
        row_h, top = 34, head_y + 30
        visible = 10
        max_scroll = max(0, n - visible)
        self.standings_scroll = min(self.standings_scroll, max_scroll)
        start = self.standings_scroll
        shown = rows[start:start + visible]
        top_score = max((r["score"] for r in rows), default=1) or 1
        count = self._ease_out((t - 0.5) / 1.1)                    # 숫자 올라가는 진행률
        intro_done = t > 0.4 + 0.06 * visible + 0.5
        for vi, r in enumerate(shown):
            # 아래쪽 행부터 차례로 등장 (1위가 마지막으로 나타나 강조됨)
            delay = 0.35 + (len(shown) - 1 - vi) * 0.06
            k = 1.0 if intro_done else self._ease_out((t - delay) / 0.4)
            if k <= 0:
                continue
            y = top + vi * row_h
            xo = int((1 - k) * 120)
            a = 255 * k
            rr = pygame.Rect(bx + 20 + xo, y, box_w - 40, row_h - 4)
            is_win = r["rank"] == 1
            is_me = r["is_local"]
            if is_win:
                glow = 0.5 + 0.5 * math.sin(now * 4.0)
                CANVAS.alpha_rect(rr.inflate(8, 6), (255, 210, 90, int((40 + 50 * glow) * k)), radius=12)
                CANVAS.alpha_rect(rr, (60, 48, 18, int(235 * k)), radius=9)
                CANVAS.alpha_rect(rr, (255, 210, 90, int(230 * k)), width=2, radius=9)
                if k >= 1.0:
                    self._standings_shine(match, rr, now)                  # 1위 행을 지나가는 빛줄기
            elif is_me:
                CANVAS.alpha_rect(rr, (22, 50, 66, int(235 * k)), radius=9)
                CANVAS.alpha_rect(rr, (100, 220, 255, int(220 * k)), width=1, radius=9)
            else:
                CANVAS.alpha_rect(rr, ((26, 32, 54, int(220 * k)) if (start + vi) % 2 == 0 else (20, 25, 44, int(220 * k))), radius=9)
            # 점수 비율 막대
            frac = (r["score"] / top_score) * count
            if frac > 0:
                CANVAS.alpha_rect((rr.x + 10, rr.bottom - 5, int((rr.w - 20) * frac * 0.999) + 1, 3), (*(C_GOLD if is_win else C_ACCENT), int(150 * k)), radius=2)
            col = C_GOLD if is_win else (C_ACCENT if is_me else C_TEXT)
            rank_txt = f"{r['rank']}" if r["rank"] > 0 else "-"
            self._fade_text(rank_txt, self.font_hud, C_GOLD if is_win else col, bx + 46 + xo, rr.centery, a, "center")
            nm = (r["name"][:16] + "  (나)") if is_me else r["name"][:22]
            self._fade_text(nm, self.font_mid, col, bx + 96 + xo, rr.centery, a, "midleft")
            self._fade_text(str(int(r["ko"] * count)), self.font_mid, col, bx + 520 + xo, rr.centery, a, "midright")
            self._fade_text(str(int(r["lines"] * count)), self.font_mid, col, bx + 610 + xo, rr.centery, a, "midright")
            self._fade_text(f"{r['apm'] * count:.1f}", self.font_mid, C_GOLD if not is_win else col, bx + 706 + xo, rr.centery, a, "midright")
            self._fade_text(f"{r['lpm'] * count:.1f}", self.font_mid, C_GREEN if not is_win else col, bx + 800 + xo, rr.centery, a, "midright")
            self._fade_text(f"{int(r['score'] * count):,}", self.font_mid, col, bx + 920 + xo, rr.centery, a, "midright")
            sec = int(r["time"])
            self._fade_text(f"{sec // 60}:{sec % 60:02d}", self.font_mid, C_DIM if not is_win else col, bx + 1030 + xo, rr.centery, a, "midright")
        self._standings_last_start = start

        # 스크롤 막대 + 내 행이 화면 밖이면 아래에 고정 표시
        if n > visible:
            track = pygame.Rect(bx + box_w - 16, top, 5, visible * row_h - 4)
            pygame.draw.rect(self.screen, (28, 34, 56), track, border_radius=3)
            th = max(24, int(track.h * visible / n))
            ty = track.y + int((track.h - th) * (start / max_scroll if max_scroll else 0))
            pygame.draw.rect(self.screen, accent, (track.x, ty, track.w, th), border_radius=3)
        if me and me not in shown and intro_done:
            y = top + visible * row_h + 2
            rr = pygame.Rect(bx + 20, y, box_w - 40, row_h - 4)
            CANVAS.alpha_rect(rr, (22, 50, 66, 240), radius=9)
            CANVAS.alpha_rect(rr, (100, 220, 255, 220), width=1, radius=9)
            self._draw_text(f"{me['rank']}", self.font_hud, C_ACCENT, bx + 46, rr.centery, "center")
            self._draw_text(f"{me['name'][:16]}  (나)", self.font_mid, C_ACCENT, bx + 96, rr.centery, "midleft")
            for val, cx_ in ((str(me["ko"]), 520), (str(me["lines"]), 610), (f"{me['apm']:.1f}", 706), (f"{me['lpm']:.1f}", 800),
                             (f"{me['score']:,}", 920), (f"{int(me['time']) // 60}:{int(me['time']) % 60:02d}", 1030)):
                self._draw_text(val, self.font_mid, C_ACCENT, bx + cx_, rr.centery, "midright")

        # 버튼
        mx, my = pygame.mouse.get_pos()
        btn_y = by + box_h - 64
        self.result_spectate_btn = None
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        self.result_practice_btn = None
        self.result_next_btn = None
        if net_on:
            self.result_restart_btn = pygame.Rect(bx + box_w // 2 - 260, btn_y, 250, 46)
            self.result_return_btn = pygame.Rect(bx + box_w // 2 + 10, btn_y, 250, 46)
        else:
            nxt_diff = getattr(match, "next_ladder", None)
            if nxt_diff:                                     # 난이도 클리어 직후: '다음 난이도 도전' 버튼을 맨 앞에 추가
                w4, g4 = 196, 12
                x4 = bx + (box_w - (w4 * 4 + g4 * 3)) // 2
                self.result_next_btn = pygame.Rect(x4, btn_y, w4, 46)
                self.result_restart_btn = pygame.Rect(x4 + (w4 + g4), btn_y, w4, 46)
                self.result_practice_btn = pygame.Rect(x4 + (w4 + g4) * 2, btn_y, w4, 46)
                self.result_return_btn = pygame.Rect(x4 + (w4 + g4) * 3, btn_y, w4, 46)
            else:
                self.result_restart_btn = pygame.Rect(bx + box_w // 2 - 318, btn_y, 200, 46)
                self.result_practice_btn = pygame.Rect(bx + box_w // 2 - 100, btn_y, 200, 46)
                self.result_return_btn = pygame.Rect(bx + box_w // 2 + 118, btn_y, 200, 46)
        ids = ["restart", "return"] if net_on else ["restart", "practice", "return"]
        if self.result_next_btn:
            ids = ["next"] + ids
        if self.result_focus_id not in ids:
            self.result_focus_id = ids[0]
        st_moved = (mx, my) != getattr(self, "_standings_last_mouse", None)       # 마우스가 실제로 움직였을 때만 포커스가 따라감
        self._standings_last_mouse = (mx, my)
        if st_moved:
            for bid, rect in (("next", self.result_next_btn), ("restart", self.result_restart_btn), ("practice", self.result_practice_btn), ("return", self.result_return_btn)):
                if rect and bid in ids and rect.collidepoint(mx, my):
                    self.result_focus_id = bid
        if self.result_next_btn:
            self._button(self.result_next_btn, "다음 난이도 도전", "gold", self.result_focus_id == "next", "N")
        self._button(self.result_restart_btn, "대기실로 돌아가기" if net_on else "재도전", "green",
                     self.result_focus_id == "restart", "R")
        if self.result_practice_btn:
            self._button(self.result_practice_btn, "연습하기", "blue", self.result_focus_id == "practice", "P")
        self._button(self.result_return_btn, "메인 메뉴", "blue", self.result_focus_id == "return", "ESC")
        if n > visible:
            self._draw_text("마우스 휠 / ↑ ↓ / PageUp·PageDown 으로 스크롤", self.font_tiny, C_DIM, bx + box_w // 2, by + box_h - 96, "midtop")

    @staticmethod
    def _reward_of(match):
        """결과 화면에 보여 줄 정산 {"xp": {...}, "highlights": [...], "unlocks": [...]} (없으면 None)"""
        r = getattr(match, "reward", None)
        return r if isinstance(r, dict) else None

    GRADE_COLORS = {"S+": (255, 225, 110), "S": (255, 205, 90), "A": (120, 235, 170), "B": (110, 190, 255), "C": (190, 200, 225), "D": (150, 150, 170)}

    def _draw_grade_stamp(self, match, cx, cy, age, size=1.0):
        """경기 랭크 글자(D~S+)가 쾅 찍히며 퍼지는 빛. 72x72 상자 안에 RANK 글자와 등급 글자를 함께 넣어 다른 요소와 겹치지 않음 (글자로 등급을 읽을 수 있어 색에 의존하지 않음)"""
        rw = self._reward_of(match)
        grade = rw.get("grade") if rw else None
        if not grade or age < 0:
            return
        k = _ease_out(age / 0.22)
        col = self.GRADE_COLORS.get(grade, C_TEXT)
        r = pygame.Rect(0, 0, int(72 * size), int(72 * size))
        r.center = (int(cx), int(cy))
        CANVAS.alpha_rect(r, (14, 18, 32, int(220 * k)), radius=14)
        CANVAS.alpha_rect(r, (*col, int(255 * k)), width=3, radius=14)
        surf = self.font_banner[3].render(grade, True, col)
        surf = self._scaled_hi(surf, (1.0 + 0.25 * (1.0 - k)) * size * 1.1)
        surf.set_alpha(int(255 * min(1.0, k * 1.4)))
        self.screen.blit(surf, surf.get_rect(center=(r.centerx, r.centery + int(8 * size))))
        self._fade_text("RANK", self.font_tiny, C_DIM, r.centerx, r.top + int(7 * size), 255 * k, "midtop")
        if age < 0.5:
            from ui_renderer import draw_glow                               # 지연 import: ui_renderer가 이 모듈을 먼저 불러오므로 (순환 방지)
            draw_glow(self.screen, cx, cy, int(40 * size), col, 1.0 - age / 0.5)

    def _result_reward_height(self, match):
        """결과 창(탈락 화면)에 보상 줄(경험치 바 / 업적·해금 카드 / 명장면 도장)이 차지하는 높이 (없으면 0)"""
        rw = self._reward_of(match)
        if not rw:
            return 0
        h = 0
        if rw.get("score"):
            h += 26
        if rw["xp"].get("gain", 0) > 0:
            h += 26 + (24 if rw["xp"].get("parts") else 0)
        if getattr(match, "new_achievements", None) or rw["unlocks"]:
            h += 34
        if rw["highlights"]:
            h += 30
        return h + (6 if h else 0)

    def _wrap_words(self, text, font, max_w):
        """공백 단위로 줄바꿈 (… 로 자르지 않음). 한 단어가 폭보다 길면 글자 단위로 나눔 (번역한 뒤에 나눔)"""
        text = _tr(text)
        lines, cur = [], ""
        for word in text.split(" "):
            trial = (cur + " " + word) if cur else word
            if font.size(trial)[0] <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            while font.size(word)[0] > max_w and len(word) > 1:
                k = len(word)
                while k > 1 and font.size(word[:k])[0] > max_w:
                    k -= 1
                lines.append(word[:k])
                word = word[k:]
            cur = word
        if cur:
            lines.append(cur)
        return lines or [""]

    def _result_summary_items(self, match):
        """탈락 결과 창의 요약 영역 재료: 점수 / 열기 / 경험치 / 내역 / 칩(기록·도전·업적·해금·명장면). 높이는 이 내용만으로 정해짐 (시간과 무관)"""
        rw = self._reward_of(match) or {}
        titles = {a[0]: a[1] for a in ACHIEVEMENTS}
        chips = []
        records = tuple(getattr(match, "new_records", ()) or ())
        names = {"rank": "순위", "ko": "K.O.", "combo": "최대 콤보"}
        for k in records:
            if k in names:
                chips.append((f"★ {names[k]} 기록 갱신", C_GOLD))
        lc = getattr(match, "ladder_clear", None)
        if lc:
            chips.append((f"난이도 클리어 {LADDER_NAMES.get(lc, lc)}", C_GOLD))
        for ob in (getattr(match, "onboarding_done", None) or []):
            chips.append((f"★ 입문 미션 완료 · {ob}", (255, 225, 110)))
        vu = getattr(match, "vs_usual", None)
        if vu:
            chips.append((vu, C_GREEN if "▲" in vu else C_DIM))              # 기록을 못 깨도 '오늘은 평소보다 잘했다/못했다'를 알려 줌
        csum = match.challenge_summary() if hasattr(match, "challenge_summary") else None
        if csum:
            chips.append((csum[1] if len(csum[0]) > 28 else csum[0], C_GREEN))
        for a in (getattr(match, "new_achievements", None) or []):
            chips.append(("★ 업적 " + titles.get(a, a), C_GOLD))
        for u in rw.get("unlocks", []):
            chips.append((f"◆ 새 스킨 {u}", (130, 235, 255)))
        for h in rw.get("highlights", []):
            chips.append(match.HIGHLIGHT_LABELS.get(h, (h, C_GOLD)))
        return rw, chips

    def _chip_lines(self, chips, max_w, font, max_lines=3):
        """칩을 폭에 맞춰 줄로 나눔. max_lines를 넘으면 마지막 칩을 '외 n개'로 바꿔 줄 수를 지킴"""
        lines, cur, w = [], [], 0
        for txt, col in chips:
            cw_ = font.size(txt)[0] + 22
            if cur and w + 8 + cw_ > max_w:
                lines.append(cur)
                cur, w = [], 0
            cur.append((txt, col, cw_))
            w += cw_ + (8 if len(cur) > 1 else 0)
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            rest = sum(len(l) for l in lines[max_lines - 1:])
            keep = lines[:max_lines - 1]
            last = lines[max_lines - 1]
            more = f"외 {rest - len(last) + 1}개"
            last = last[:-1] if last else last
            lines = keep + [last + [(more, C_DIM, font.size(more)[0] + 22)]]
        return lines

    def _result_layout(self, match, box_w):
        """탈락 결과 창의 세로 배치를 한 곳에서 계산 (그리기와 패널 높이가 어긋나지 않게). 모든 y는 패널 위쪽 기준"""
        pad, cont = 24, box_w - 48
        lh = self.font_small.get_height()
        lm = self.font_mid.get_height()
        L = {"pad": pad, "cont": cont, "lh": lh}
        L["card_y"] = 144
        y = 144 + 76 + 12                                           # 통계 카드 아래
        rw, chips = self._result_summary_items(match)
        L["rw"], L["chips"] = rw, chips
        xp = rw.get("xp") or {}
        tier, _, pct = match.get_badge_info()
        badge_txt = f"열기 Lv.{tier} · 공격력 +{pct}" if tier > 0 else "열기 Lv.0"
        if getattr(match, "local_assists", 0) > 0:
            badge_txt += f" · K.O. 기여 {match.local_assists}"
        L["badge_txt"] = badge_txt
        inner = 12
        sy = inner
        rows = {}
        rows["c1"] = sy                                              # 점수(왼쪽) + 열기 요약(오른쪽)
        sy += max(28, lm + 6)
        if xp.get("gain", 0) > 0:
            rows["c2"] = sy                                          # 경험치 바
            sy += 26
            if xp.get("parts"):
                segs = []
                for n, v in xp["parts"]:
                    segs.append((f"{n} +{v}", (255, 215, 90) if (n.startswith("오늘 첫") or "연속" in n) else C_ACCENT))
                L["xp_lines"] = self._seg_lines(segs, cont - 32)
                rows["c3"] = sy
                sy += len(L["xp_lines"]) * (lh + 2) + 6
        if chips:
            L["chip_lines"] = self._chip_lines(chips, cont - 32, self.font_small)
            rows["c4"] = sy
            sy += len(L["chip_lines"]) * 30
        sy += inner - 2
        L["rows"], L["sum_y"], L["sum_h"] = rows, y, sy
        y += sy + 12
        # 조언 상자: 패인(첫 줄 + 근거 + 팁) + 다음 목표
        loss = None if match.local_rank == 1 else match.defeat_summary()
        goal = getattr(match, "next_goal", None)
        adv = []
        if loss:
            lead, _, rest = loss[0].partition("  (")
            adv.append(("lead", [lead], C_TEXT))
            if rest:
                adv.append(("why", self._wrap_words(rest.rstrip(")").replace(" · ", "  ·  "), self.font_small, cont - 40), (225, 200, 185)))
            if len(loss) > 1:
                adv.append(("tip", self._wrap_words(loss[1], self.font_small, cont - 40), (170, 200, 235)))
        if goal:
            adv.append(("goal", self._wrap_words(f"다음 목표: {goal}", self.font_small, cont - 40), C_ACCENT))
        L["adv"] = adv
        if adv:
            ah = 24
            for kind, lines, _c in adv:
                ah += len(lines) * ((lm if kind == "lead" else lh) + 3) + (4 if kind != "lead" else 2)
            L["adv_y"], L["adv_h"] = y, ah
            y += ah + 16
        else:
            L["adv_y"], L["adv_h"] = y, 0
            y += 4
        L["btn_y"] = y
        y += 48 + 12
        L["foot_y"] = y
        L["box_h"] = y + lh + 20
        return L

    def _seg_lines(self, segs, max_w):
        """[(문구, 색)]을 ' · '로 이어 폭에 맞춰 줄로 나눔 -> [[(문구, 색), ...], ...]"""
        lines, cur, w = [], [], 0
        sep_w = self.font_small.size("  ·  ")[0]
        for txt, col in segs:
            tw = self.font_small.size(txt)[0]
            if cur and w + sep_w + tw > max_w:
                lines.append(cur)
                cur, w = [], 0
            w += tw + (sep_w if cur else 0)
            cur.append((txt, col))
        if cur:
            lines.append(cur)
        return lines

    def _draw_result_summary(self, match, L, bx, by, box_w, t, rec_t):
        """요약 상자: 점수/열기 한 줄, 경험치 바, 경험치 내역 한 줄, 칩 줄(기록·도전·업적·해금·명장면). 상자 하나에 왼쪽 정렬로 모아 가로줄 수를 줄임"""
        rw, xp = L["rw"], (L["rw"].get("xp") or {})
        pad = L["pad"]
        box = pygame.Rect(bx + pad, by + L["sum_y"], L["cont"], L["sum_h"])
        fade = _ease_out((t - rec_t + 0.15) / 0.3)
        if fade <= 0:
            return
        self._panel(box, border=(44, 56, 92), bg=(20, 25, 44), radius=12, alpha=int(240 * fade))
        x0, x1 = box.x + 16, box.right - 16
        rows = L["rows"]
        # 점수(왼쪽) + 개인 최고/점수표 알약, 열기 요약(오른쪽)
        cy = box.y + rows["c1"] + 14
        sc = rw.get("score")
        if sc:
            ks = _ease_out((t - rec_t) / 0.8)
            txt = f"SCORE  {int(sc['score'] * ks):,}"
            r = self._draw_text(txt, self.font_hud, C_TEXT, x0, cy, "midleft")
            note, ncol = None, C_DIM
            if sc.get("best"):
                note, ncol = "★ 개인 최고!", C_GOLD
            elif sc.get("place"):
                note, ncol = f"점수표 #{sc['place']}", C_ACCENT
            if note and ks >= 1.0:
                pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0) if sc.get("best") else 0.0
                self._draw_text(note, self.font_small, _mix(ncol, (255, 255, 255), 0.4 * pulse), r.right + 14, cy, "midleft")
        self._draw_text(L["badge_txt"], self.font_small, C_DIM, x1, cy, "midright")
        # 경험치 바
        if "c2" in rows and xp.get("gain", 0) > 0:
            cy = box.y + rows["c2"] + 13
            k = _ease_out((t - rec_t - 0.2) / 1.1)
            pos = xp["before"] + xp["gain"] * k
            lv, into, need = level_of(pos)
            self._draw_text(f"Lv.{lv}", self.font_mid, C_GOLD, x0, cy, "midleft")
            gtxt = f"+{int(xp['gain'] * k)} XP"
            right_w = 170 if xp["lv_after"] > xp["lv_before"] else 100
            bar = pygame.Rect(x0 + 62, cy - 5, (x1 - right_w) - (x0 + 62), 10)
            pygame.draw.rect(self.screen, (24, 29, 48), bar, border_radius=5)
            fw = int(bar.w * into / max(1, need))
            if fw > 0:
                pygame.draw.rect(self.screen, C_GOLD if lv > xp["lv_before"] else C_ACCENT, (bar.x, bar.y, max(fw, 8), bar.h), border_radius=5)
            pygame.draw.rect(self.screen, (60, 72, 108), bar, 1, border_radius=5)
            self._draw_text(gtxt, self.font_small, C_TEXT, x1, cy, "midright")
            if xp["lv_after"] > xp["lv_before"] and k >= 1.0:
                pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0)
                self._draw_text("LEVEL UP!", self.font_small, _mix(C_GOLD, (255, 255, 255), 0.5 * pulse), x1 - self.font_small.size(gtxt)[0] - 12, cy, "midright")
        # 경험치 내역: 테두리 없이 한 줄 (오늘 첫 판/연승만 금색), 하나씩 나타남
        if "c3" in rows:
            lh = L["lh"]
            n_seen = 0
            for li, line in enumerate(L["xp_lines"]):
                x = x0
                yy = box.y + rows["c3"] + li * (lh + 2) + lh // 2 + 2
                for si, (txt, col) in enumerate(line):
                    if si:
                        x += self._draw_text("  ·  ", self.font_small, (70, 82, 118), x, yy, "midleft").w
                    n_seen += 1
                    kk = _ease_out((t - rec_t - 0.1 - 0.08 * n_seen) / 0.18)
                    if kk > 0:
                        self._fade_text(txt, self.font_small, col, x, yy, 255 * kk, "midleft")
                    x += self.font_small.size(txt)[0]
        # 칩 줄
        if "c4" in rows:
            n_seen = 0
            for li, line in enumerate(L["chip_lines"]):
                x = x0
                for txt, col, cw_ in line:
                    n_seen += 1
                    kk = _ease_out((t - rec_t - 0.2 - 0.08 * n_seen) / 0.22)
                    if kk > 0:
                        r = pygame.Rect(x, box.y + rows["c4"] + li * 30 + int((1 - kk) * 8), cw_, 24)
                        CANVAS.alpha_rect(r, (22, 28, 48, int(235 * kk)), radius=12)
                        CANVAS.alpha_rect(r, (*col, int(200 * kk)), width=1, radius=12)
                        self._fade_text(txt, self.font_small, col, r.centerx, r.centery, 255 * kk, "center")
                    x += cw_ + 8

    def _draw_result_advice(self, match, L, bx, by, box_w, t):
        """조언 상자: 패인(제목 + 근거 + 팁)과 다음 목표를 둥근 상자 하나에 모음. 왼쪽 주황 띠. 줄바꿈으로 전부 보여 주고 '…'로 자르지 않음"""
        if not L["adv"] or t < 1.2:
            return
        fade = _ease_out((t - 1.2) / 0.35)
        pad = L["pad"]
        box = pygame.Rect(bx + pad, by + L["adv_y"], L["cont"], L["adv_h"])
        loss = any(k == "lead" for k, _l, _c in L["adv"])
        CANVAS.alpha_rect(box, (34, 24, 24, int(235 * fade)) if loss else (18, 30, 44, int(235 * fade)), radius=12)
        CANVAS.alpha_rect(pygame.Rect(box.x, box.y + 8, 4, box.h - 16), (*((255, 150, 90) if loss else C_ACCENT), int(255 * fade)), radius=2)
        y = box.y + 12
        lm, lh = self.font_mid.get_height(), L["lh"]
        for kind, lines, col in L["adv"]:
            for ln in lines:
                if kind == "lead":
                    self._fade_text(ln, self.font_mid, (255, 190, 150), box.x + 20, y, 255 * fade, "topleft")
                    y += lm + 3
                else:
                    self._fade_text(ln, self.font_small, col, box.x + 20, y, 255 * fade, "topleft")
                    y += lh + 3
            y += 2 if kind == "lead" else 4

    def _standings_info_lines(self, match):
        """순위표 머리에 붙일 한두 줄 [(문구, 색)]: ★ 최고 기록/클리어/업적, 다음 목표, (탈락했다면) 패인 첫 줄. 없으면 빈 목록"""
        won = match.local_rank == 1
        lines = []
        rw_ = self._reward_of(match)
        if rw_ and (rw_.get("grade") or rw_.get("score")):                  # 랭크 글자 + 점수(점수표 순위) + 경험치 한 줄
            bits = []
            if rw_.get("grade"):
                bits.append(f"랭크 {rw_['grade']}")
            sc_ = rw_.get("score")
            if sc_:
                bits.append(f"점수 {sc_['score']:,}" + (" ★ 개인 최고!" if sc_.get("best") else (f" (점수표 #{sc_['place']})" if sc_.get("place") else "")))
            lines.append(("  ·  ".join(bits), self.GRADE_COLORS.get(rw_.get("grade"), C_TEXT)))
        records = tuple(getattr(match, "new_records", ()) or ())
        ladder_clear = getattr(match, "ladder_clear", None)
        ach = tuple(getattr(match, "new_achievements", ()) or ())
        names = {"rank": "순위", "ko": "K.O.", "combo": "최대 콤보"}
        parts = []
        if records:
            parts.append("최고 기록 갱신!  " + " · ".join(names[k] for k in records if k in names))
        if ladder_clear:
            parts.append(f"난이도 클리어!  {LADDER_NAMES.get(ladder_clear, ladder_clear)}")
        if ach:
            titles = {a[0]: a[1] for a in ACHIEVEMENTS}
            parts.append("업적 달성!  " + " · ".join(titles.get(x, x) for x in ach[:2]) + (f" 외 {len(ach) - 2}개" if len(ach) > 2 else ""))
        csum = match.challenge_summary() if hasattr(match, "challenge_summary") else None
        if csum:
            parts.append(csum[0] if self.font_small.size(csum[0])[0] < 700 else csum[1])
        rw = self._reward_of(match)
        if rw and rw["unlocks"]:
            parts.append("새 스킨 해금!  " + " · ".join(rw["unlocks"]))
        if parts:
            lines.append(("★ " + "   ★ ".join(parts), C_GOLD))
        if rw and rw["xp"].get("gain", 0) > 0:
            xp = rw["xp"]
            up = xp["lv_after"] > xp["lv_before"]
            lines.append((f"경험치 +{xp['gain']} XP   ·   Lv.{xp['lv_after']}" + ("   ★ 레벨 업!" + (f" 칭호 '{__import__('stats_manager').level_title(xp['lv_after'])}'" if __import__('stats_manager').level_title(xp['lv_after']) != __import__('stats_manager').level_title(xp['lv_before']) else "") if up else "") + (f"   ·   다음 해금: {rw['next_unlock']}" if rw.get("next_unlock") else ""), C_GOLD if up else (170, 200, 235)))
            for perk in perks_unlocked_between(xp["lv_before"], xp["lv_after"]):                       # 레벨 보상(K.O. 구슬 색)을 얻었으면 알림
                lines.append((f"★ 새 효과 해금!  {perk}", (255, 225, 110)))
        if rw and rw["highlights"]:
            lines.append(("명장면:  " + " · ".join(match.HIGHLIGHT_LABELS.get(h, (h, None))[0] for h in rw["highlights"][:4]), (255, 215, 130)))
        if getattr(match, "prediction_reward", 0) > 0:                       # 탈락 뒤 우승 예측이 맞았으면 알림
            pn = match.players.get(match.prediction_id, {}).get("name", "")
            lines.append((f"우승 예측 적중!  {pn}  +{match.prediction_reward} XP", C_GREEN))
        goal = getattr(match, "next_goal", None)
        loss = None if won else match.defeat_summary()
        second = None
        if loss:
            second = (loss[0], (255, 190, 150))
        elif goal:
            second = (f"다음 목표: {goal}", C_DIM)
        if second:
            lines.append(second)
        out = []
        for txt, col in lines[:4]:
            for ln in self._wrap_words(txt, self.font_small, 1060):            # 길면 "…"로 자르지 않고 줄바꿈 (순위표 머리 줄 정리)
                out.append((ln, col))
        return out[:6]


    def _draw_timeline_graph(self, match, rect, legend_right=None, legend_y=None):
        """경기 흐름 미니 그래프: 주황=내 스택 높이(0~20줄), 파랑=생존자 비율. 범례는 그래프 안 위쪽 띠에 한 줄로 (다른 글자와 겹치지 않음). 점이 5개 미만이면 그리지 않음"""
        tl = getattr(match, "timeline", None)
        if not tl or len(tl) < 5:
            return
        pygame.draw.rect(self.screen, (18, 23, 40), rect, border_radius=8)
        pygame.draw.rect(self.screen, (44, 56, 92), rect, 1, border_radius=8)
        self._draw_text("━ 내 스택 높이", self.font_tiny, (255, 165, 70), rect.x + 8, rect.y + 4)
        self._draw_text("━ 생존자 비율", self.font_tiny, (90, 170, 255), rect.right - 8, rect.y + 4, "topright")
        inner = pygame.Rect(rect.x + 8, rect.y + 22, rect.w - 16, rect.h - 28)
        n = len(tl)
        total = max(1, match.total_players)

        def pts(fn):
            return [(inner.x + inner.w * i / max(1, n - 1), inner.bottom - inner.h * min(1.0, max(0.0, fn(t))))
                    for i, t in enumerate(tl)]
        pygame.draw.lines(self.screen, (90, 170, 255), False, pts(lambda t: t[1] / total), 2)          # 생존자 비율
        stack = pts(lambda t: t[2] / float(BOARD_HEIGHT))
        pygame.draw.lines(self.screen, (255, 165, 70), False, stack, 2)                                  # 내 스택 높이
        pygame.draw.circle(self.screen, (255, 90, 90), (int(stack[-1][0]), int(stack[-1][1])), 3)        # 탈락 지점

    killcam = None                       # 결과 창에서 재생 중인 마지막 8초 되감기 (앱이 매 프레임 지정)
    killcam_available = False

    def _draw_killcam(self, match, x, y):
        """결과 창 오른쪽: 되감기 안내 칩(V) / 켜면 내 보드의 마지막 8초를 작은 보드로 반복 재생 (패인 한 줄을 실제 장면으로 확인)"""
        if not self.killcam_available or x + 190 > self.width:
            return
        kc = self.killcam
        if kc is None:
            chip = pygame.Rect(x, y, 170, 30)
            self._panel(chip, border=(70, 110, 160), bg=(16, 22, 38), radius=10, alpha=235)
            self._draw_text("V  마지막 8초 보기" if not self.pad_ui else "LB  마지막 8초 보기", self.font_tiny, (170, 205, 240), chip.centerx, chip.centery, "center")
            return
        cs = 14
        pw, ph = cs * 10 + 24, cs * 20 + 86
        panel = pygame.Rect(x, y, pw, ph)
        self._panel(panel, border=(90, 130, 190), bg=(12, 16, 30), radius=12, alpha=245)
        self._draw_text("마지막 8초", self.font_tiny, (170, 205, 240), panel.centerx, panel.y + 8, "midtop")
        bx_, by_ = panel.x + 12, panel.y + 30
        pygame.draw.rect(self.screen, (10, 12, 22), (bx_ - 2, by_ - 2, cs * 10 + 4, cs * 20 + 4), border_radius=3)
        for yy in range(20):
            for xx in range(10):
                piece = kc.grid[yy][xx]
                if piece:
                    self._draw_cell(bx_ + xx * cs, by_ + yy * cs, cs, piece)
        last = kc.last
        if last is not None and kc.t - kc.last_t < 0.35 and last["k"] == "G":          # 쓰레기가 올라온 순간: 아래쪽이 붉게 번쩍
            a = int(150 * (1.0 - (kc.t - kc.last_t) / 0.35))
            CANVAS.alpha_rect((bx_, by_ + (20 - last["n"]) * cs, cs * 10, last["n"] * cs), (255, 90, 90, a), radius=2)
        frac = min(1.0, max(0.0, (kc.t - max(0.0, kc.duration - 8.0)) / 8.0))
        pygame.draw.rect(self.screen, (28, 34, 56), (bx_, by_ + cs * 20 + 10, cs * 10, 6), border_radius=3)
        pygame.draw.rect(self.screen, (120, 190, 255), (bx_, by_ + cs * 20 + 10, max(4, int(cs * 10 * frac)), 6), border_radius=3)
        self._draw_text("V 닫기" if not self.pad_ui else "LB 닫기", self.font_tiny, C_DIM, panel.centerx, panel.bottom - 8, "midbottom")

    def _render_result_overlay(self, match):
        """탈락 결과 창 (v1.1.13 재설계): 헤더(랭크 도장 / 제목 + 부제목 / 그래프) -> 통계 카드 6장 -> 요약 상자 -> 조언 상자 -> 버튼. 정보는 그대로, 구역 4개로 묶고 겹침 없이 배치"""
        if self._res_for is not match:
            self._res_for, self._res_t0 = match, time.time()
        r_age = time.time() - self._res_t0
        CANVAS.overlay((4, 6, 12, int(200 * min(1.0, r_age / 0.3))))                       # 배경이 서서히 어두워지고

        won = match.local_rank == 1
        accent = C_GOLD if won else C_DANGER
        records = tuple(getattr(match, "new_records", ()) or ())
        box_w = 760
        L = self._result_layout(match, box_w)
        box_h = min(L["box_h"], self.height - 24)
        bx = (self.width - box_w) // 2
        by = (self.height - box_h) // 2
        if self._motion > 0:
            by += int(70 * (1.0 - _ease_out((r_age - 0.1) / 0.35)))                       # 패널이 아래에서 튀어 올라옴
        self._panel((bx, by, box_w, box_h), border=accent, bg=(15, 19, 34), radius=18, alpha=248, border_w=2)
        pad = L["pad"]

        # ---- A. 헤더: 왼쪽 랭크 도장 / 가운데 제목 / 오른쪽 그래프, 아래 한 줄 부제목
        self._draw_grade_stamp(match, bx + pad + 36, by + 20 + 36, r_age - 0.9)
        stamp = _ease_out((r_age - 0.35) / 0.25)                                          # 제목은 1.25배에서 1.0배로 도장처럼 찍힘
        ttxt, tcol = ("로열 빅토리!", C_GOLD) if won else ("K.O.  경기 탈락", C_DANGER)
        team = bool(getattr(match, "teams", None))
        if team and match.team_won is not None:                                           # 팀전: 팀 승패가 정해졌으면 제목도 팀 결과로
            ttxt, tcol = ("팀 승리!", C_GOLD) if match.team_won else ("팀 패배", C_DANGER)
            accent = C_GOLD if match.team_won else C_DANGER
        if stamp < 1.0 and r_age > 0.3:
            tsurf = self._scaled_hi(self.font_title.render(ttxt, True, tcol), 1.0 + 0.25 * (1.0 - stamp))
            self.screen.blit(tsurf, tsurf.get_rect(midtop=(int(bx + box_w // 2), int(by + 24 - 4 * (1.0 - stamp)))))
        elif stamp >= 1.0:
            self._draw_text(ttxt, self.font_title, tcol, bx + box_w // 2, by + 24, "midtop", shadow=True)
        if won and not team:
            self._draw_text("최후의 1인으로 살아남았습니다", self.font_mid, C_GREEN, bx + box_w // 2, by + 100, "midtop")
        elif team and (won or match.team_won):
            self._draw_text("우리 팀이 끝까지 살아남았습니다", self.font_mid, C_GREEN, bx + box_w // 2, by + 100, "midtop")
        else:
            self._draw_timeline_graph(match, pygame.Rect(bx + box_w - pad - 208, by + 20, 208, 72))
            killer = getattr(match, "local_killer_id", None)
            tail = ""
            if killer and killer in match.players:
                kp = match.players[killer]
                kname = kp.get('name', '?')[:12] + (f"({_tr(kp['trait'])})" if kp.get("trait") else "")          # 특성 이름은 따로 번역 (합친 뒤에는 안쪽 단어를 번역할 수 없음)
                tail = " · " + _tr(f"{kname}에게 탈락")                                                           # 나를 K.O.한 상대 ("… eliminated by 이름")
            if team:                                                                      # 팀전: 팀 상황이 더 중요하므로 탈락시킨 상대 대신 팀 생존자 수
                mine, foes = match.team_alive_counts()
                tail = (" · 상대 팀 승리" if match.team_won is False else f" · 우리 팀 {mine}명 / 상대 팀 {foes}명 생존 (끝까지 지켜보세요)")
            head = f"최종 순위 {match.local_rank}위 / {match.total_players}명"
            wh, wt = self.font_mid.size(head)[0], self.font_mid.size(tail)[0]
            x0 = bx + (box_w - wh - wt) // 2
            self._draw_text(head, self.font_mid, C_TEXT, x0, by + 100, "topleft")
            if tail:
                self._draw_text(tail, self.font_mid, C_DIM, x0 + wh, by + 100, "topleft")
        pygame.draw.line(self.screen, (44, 56, 92), (bx + pad, by + 132), (bx + box_w - pad, by + 132), 1)

        # ---- B. 통계 카드: 왼쪽부터 차례로 미끄러져 들어오고 숫자는 카운트업 (순위는 꼴찌에서 최종 순위까지 카운트다운)
        if self._result_match is not match:
            self._result_match = match
            self._result_t0 = time.time()
        t = time.time() - self._result_t0
        apm, lpm, time_str = match.get_combat_stats()
        rank_now = int(match.local_rank)
        rank_shown = rank_now + int(round((match.total_players - rank_now) * (1.0 - _ease_out((t - 0.35) / 1.0))))
        rec_t = 1.45                                                    # 카드가 다 나온 뒤 요약 표시
        cards = [
            ("순위", f"#{rank_shown}", accent, "rank", None),
            ("K.O.", "{:d}", C_TEXT, "ko", match.local_ko_count),
            ("제거 라인", "{:d}", C_ACCENT, None, match.local_engine.lines_cleared_total),
            ("최대 콤보", "{:d}", C_ORANGE, "combo", match.local_engine.max_combo),
            ("APM", "{:.1f}", C_GOLD, None, apm),
            ("생존 시간", time_str, C_GREEN, None, None),
        ]
        cw, gap = 108, 12
        sx = bx + (box_w - (cw * len(cards) + gap * (len(cards) - 1))) // 2
        for i, (lbl, val, col, rec_key, num) in enumerate(cards):
            start = 0.20 + 0.09 * i
            if t < start:
                continue
            k = _ease_out((t - start) / 0.35)
            if num is not None:                                          # 등장한 뒤 0.6초 동안 0에서 목표 값까지 올라감
                val = val.format(num * _ease_out((t - start - 0.15) / 0.6) if "f" in val else int(round(num * _ease_out((t - start - 0.15) / 0.6))))
            r = pygame.Rect(sx + i * (cw + gap), by + L["card_y"] + int((1.0 - k) * 16), cw, 76)
            self._panel(r, border=(50, 62, 96), bg=(22, 27, 46), radius=10)
            self._draw_text(lbl, self.font_tiny, C_DIM, r.centerx, r.y + 10, "midtop")
            self._draw_text(val, self.font_big_num, col, r.centerx, r.y + 32, "midtop")
            if rec_key in records and t >= rec_t:                        # 이번 경기에서 최고 기록을 넘은 카드: 금색 테두리 + NEW (칩은 카드 아래 테두리에 얹음)
                pulse = 0.5 + 0.5 * math.sin(t * 6.0)
                pygame.draw.rect(self.screen, _mix(C_GOLD, (255, 255, 255), 0.45 * pulse), r, 2, border_radius=10)
                pill = pygame.Rect(0, 0, 42, 16)
                pill.midtop = (r.centerx, r.bottom - 8)
                pygame.draw.rect(self.screen, C_GOLD, pill, border_radius=8)
                self._draw_text("NEW", self.font_tiny, (24, 18, 4), pill.centerx, pill.centery, "center")

        self._draw_killcam(match, bx + box_w + 16, by + 24)

        # ---- C. 요약 상자 / D. 조언 상자
        self._draw_result_summary(match, L, bx, by, box_w, t, rec_t)
        self._draw_result_advice(match, L, bx, by, box_w, t)

        # ---- E. 버튼과 안내
        mx, my = pygame.mouse.get_pos()
        can_spectate = (not match.match_finished and match.alive_count > 1 and not match.local_is_alive)
        btn_y, btn_h = by + L["btn_y"], 48

        self.result_restart_btn = self.result_spectate_btn = self.result_return_btn = self.result_practice_btn = None
        net_on = match.net_mgr is not None and match.net_mgr.mode != "NONE"
        cont = L["cont"]
        if net_on and not match.match_finished:
            # 네트워크 경기 도중 탈락: 재도전은 없음 (경기가 끝나면 대기실로 복귀). 관전 / 메인 메뉴만.
            btn_w, g = 260, 16
            sbx = bx + (box_w - (btn_w * 2 + g)) // 2
            specs = []
            if can_spectate:
                specs.append(("spectate", pygame.Rect(sbx, btn_y, btn_w, btn_h), "경기 관전", "gold", "S"))
            specs.append(("return", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"))
        elif can_spectate:
            g = 12
            btn_w = (cont - g * 3) // 4
            sbx = bx + (box_w - (btn_w * 4 + g * 3)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("spectate", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "경기 관전", "gold", "S"),
                ("practice", pygame.Rect(sbx + (btn_w + g) * 2, btn_y, btn_w, btn_h), "연습하기", "blue", "P"),
                ("return", pygame.Rect(sbx + (btn_w + g) * 3, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]
        else:
            g = 12
            btn_w = (cont - g * 2) // 3
            sbx = bx + (box_w - (btn_w * 3 + g * 2)) // 2
            specs = [
                ("restart", pygame.Rect(sbx, btn_y, btn_w, btn_h), "재도전", "green", "R"),
                ("practice", pygame.Rect(sbx + btn_w + g, btn_y, btn_w, btn_h), "연습하기", "blue", "P"),
                ("return", pygame.Rect(sbx + (btn_w + g) * 2, btn_y, btn_w, btn_h), "메인 메뉴", "blue", "ESC"),
            ]

        ids = [s[0] for s in specs]
        if self.result_focus_id not in ids:
            self.result_focus_id = ids[0]
        res_moved = (mx, my) != getattr(self, "_result_last_mouse", None)        # 마우스가 실제로 움직였을 때만 호버로 포커스를 옮김
        self._result_last_mouse = (mx, my)
        for bid, rect, _label, _style, _hint in specs:
            if res_moved and rect.collidepoint(mx, my):       # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮김 (이중 하이라이트 방지)
                self.result_focus_id = bid
                break
        for bid, rect, label, style, hint in specs:
            if bid == "restart":
                self.result_restart_btn = rect
            elif bid == "spectate":
                self.result_spectate_btn = rect
            elif bid == "return":
                self.result_return_btn = rect
            elif bid == "practice":
                self.result_practice_btn = rect
            self._button(rect, label, style, self.result_focus_id == bid, hint)

        self._draw_text("← → 로 고르고 A 로 실행합니다" if self.pad_ui else "버튼을 클릭하거나 단축키로, ← → 와 Enter 로도 실행할 수 있습니다", self.font_small, C_DIM,
                        bx + box_w // 2, by + L["foot_y"], "midtop")
