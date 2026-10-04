"""
Block Royale 100 - 전적 기록실 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from stats_manager import SIZE_BUCKETS, SIZE_BUCKET_IDS, ACHIEVEMENTS, ACH_CATEGORIES, ACH_CATEGORY
from app_common import BOT_DIFFICULTY_LABELS, C_ACCENT, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, SCREEN_WIDTH, _mix, pygame


RECORDS_DIFF_OPTIONS = (None, "mixed", "easy", "normal", "hard", "master")
RECORDS_SIZE_KEYS = {pygame.K_1: None, pygame.K_2: "small", pygame.K_3: "mid", pygame.K_4: "large",
                     pygame.K_KP1: None, pygame.K_KP2: "small", pygame.K_KP3: "mid", pygame.K_KP4: "large"}


class RecordsMixin:
    def _records_set_filter(self, size=..., diff=...):
        """전적 필터 변경 (인원 규모 / 난이도). ...은 '바꾸지 않음'"""
        new_size = self.records_size if size is ... else size
        new_diff = self.records_diff if diff is ... else diff
        if (new_size, new_diff) != (self.records_size, self.records_diff):
            self.sound_mgr.play('move')
            self.records_size, self.records_diff = new_size, new_diff
            self.records_scroll = 0

    def _records_cycle_diff(self):
        i = RECORDS_DIFF_OPTIONS.index(self.records_diff) if self.records_diff in RECORDS_DIFF_OPTIONS else 0
        self._records_set_filter(diff=RECORDS_DIFF_OPTIONS[(i + 1) % len(RECORDS_DIFF_OPTIONS)])

    def _records_set_ach_page(self, page):
        page = max(0, min(len(ACH_CATEGORIES) - 1, int(page)))
        if page != self.records_ach_page:
            self.sound_mgr.play('move')
            self.records_ach_page = page

    def _handle_records_event(self, event):
        if self.records_mode == "achv":                                  # 업적 탭: 스크롤 없이 페이지(카테고리) 단위로 넘김
            if event.type == pygame.MOUSEWHEEL:
                self._records_set_ach_page(self.records_ach_page - (1 if event.y > 0 else -1))
                return
            if event.type == pygame.KEYDOWN:
                page_keys = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
                             pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP4: 3, pygame.K_KP5: 4}
                if event.key in page_keys:
                    self._records_set_ach_page(page_keys[event.key])
                    return
                if event.key in (pygame.K_PAGEUP, pygame.K_UP, pygame.K_KP8):
                    self._records_set_ach_page(self.records_ach_page - 1)
                    return
                if event.key in (pygame.K_PAGEDOWN, pygame.K_DOWN, pygame.K_KP2):
                    self._records_set_ach_page(self.records_ach_page + 1)
                    return
                if event.key == pygame.K_HOME:
                    self._records_set_ach_page(0)
                    return
                if event.key == pygame.K_END:
                    self._records_set_ach_page(len(ACH_CATEGORIES) - 1)
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for btn_id, rect in self.records_buttons.items():
                    if rect.collidepoint(event.pos) and btn_id.startswith("ach_"):
                        if btn_id == "ach_prev":
                            self._records_set_ach_page(self.records_ach_page - 1)
                        elif btn_id == "ach_next":
                            self._records_set_ach_page(self.records_ach_page + 1)
                        else:
                            self._records_set_ach_page(int(btn_id[4:]))
                        return
        if event.type == pygame.KEYDOWN and event.key in RECORDS_SIZE_KEYS:
            self._records_set_filter(size=RECORDS_SIZE_KEYS[event.key])
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self._records_cycle_diff()
            return
        if event.type == pygame.MOUSEWHEEL:
            self.records_scroll = max(0, min(self.records_max_scroll, self.records_scroll - event.y * 2))
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN,
                                                          pygame.K_HOME, pygame.K_END, pygame.K_KP8, pygame.K_KP2):
            step = {pygame.K_UP: -1, pygame.K_KP8: -1, pygame.K_DOWN: 1, pygame.K_KP2: 1, pygame.K_PAGEUP: -8, pygame.K_PAGEDOWN: 8}.get(event.key)
            if step is None:
                self.records_scroll = 0 if event.key == pygame.K_HOME else self.records_max_scroll
            else:
                self.records_scroll = max(0, min(self.records_max_scroll, self.records_scroll + step))
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB, pygame.K_a, pygame.K_d):
            order = ("battle", "survival", "trend", "score", "achv")
            step = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
            self._records_set_mode(order[(order.index(self.records_mode) + step) % len(order)] if self.records_mode in order else "battle")
            return
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_ESCAPE, pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE]:
                self.sound_mgr.play('move')
                self.state = "MENU"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for btn_id, rect in self.records_buttons.items():
                if rect.collidepoint(mx, my):
                    if btn_id in ("mode_battle", "mode_survival", "mode_trend", "mode_score", "mode_achv"):
                        self._records_set_mode(btn_id[5:])
                    elif btn_id.startswith("size_"):
                        self._records_set_filter(size=None if btn_id == "size_all" else btn_id[5:])
                    elif btn_id == "diff_cycle":
                        self._records_cycle_diff()
                    elif btn_id == "back_to_menu":
                        self.sound_mgr.play('move')
                        self.state = "MENU"
                    elif btn_id == "reset_stats":
                        self._open_modal("전적 기록을 초기화할까요?", ["배틀로얄·서바이벌 전적과 도전 과제(별·연습 과제) 기록이 모두 삭제됩니다.", "되돌릴 수 없습니다."],
                                         [("stay", "취소", "blue", "ESC"), ("reset_stats_ok", "초기화", "red", "Y")])
                    break

    def _records_set_mode(self, mode):
        if mode != self.records_mode:
            self.sound_mgr.play('move')
            self.records_mode = mode
            self.records_scroll = 0

    def _update_records(self, dt):
        self.menu_bg.update(dt)

    def _render_records(self):
        self.menu_bg.draw(self.screen)
        mx, my = pygame.mouse.get_pos()
        self.records_buttons.clear()
        
        self._menu_header("전적 기록실", None, accent=C_GOLD, y=14)      # 제목 밑줄이 모드 탭에 가리지 않게 제목을 위로
        box_w, box_h = 1040, 580
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 132
        self._glass((box_x, box_y, box_w, box_h), accent=(170, 140, 60), radius=18)

        # 2. 모드 탭 (배틀로얄 / 서바이벌): 전적은 모드별로 따로 집계
        tab_y = box_y - 34
        for i, (mid, label, col) in enumerate((("battle", "배틀로얄", C_GOLD), ("survival", "서바이벌", C_GREEN), ("trend", "추이", C_ACCENT), ("score", "점수표", (255, 150, 90)), ("achv", "업적", C_ORANGE))):
            r = pygame.Rect(box_x + i * 98, tab_y, 92, 30)
            self.records_buttons["mode_" + mid] = r
            on = self.records_mode == mid
            hov = r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _mix((16, 20, 34), col, 0.30 if on else (0.14 if hov else 0.05)), r, border_radius=8)
            pygame.draw.rect(self.screen, col if on else (60, 72, 104), r, 2 if on else 1, border_radius=8)
            self._t(label, self.font_small, col if on else C_DIM, r.centerx, r.centery, "center")
        self._t("1~4 규모 · F 난이도" if self.records_mode not in ("achv", "score") else ("← → 위 탭 이동  ·  1~5 · PgUp/PgDn 업적 페이지" if self.records_mode == "achv" else "← → 위 탭 이동  ·  1~4 규모"), self.font_tiny, C_DIM, box_x + box_w, tab_y + 15, "midright")
        if self.records_mode == "score":
            self._render_scores(box_x, box_y, box_w, tab_y, mx, my)
            self._records_bottom_buttons(mx, my, box_x, box_y, box_w)
            return
        if self.records_mode == "achv":
            self._render_achievements(box_x, box_y, box_w)
            self._records_bottom_buttons(mx, my, box_x, box_y, box_w)
            return
        # 필터 칩: 인원 규모(1~4) / 난이도(F). 필터를 걸면 전체 누적이 아니라 최근 100경기 중 조건에 맞는 경기로 다시 집계
        chip_x = box_x + 498
        size_chips = [("size_all", "전체", None)] + [("size_" + b[0], f"{b[3].split(' ')[0][0]} {b[1]}~{b[2]}", b[0]) for b in SIZE_BUCKETS]
        for cid, label, val in size_chips:
            w = 46 if val is None else 76
            r = pygame.Rect(chip_x, tab_y, w, 30)
            self.records_buttons[cid] = r
            on = self.records_size == val
            hov = r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _mix((16, 20, 34), C_ACCENT, 0.28 if on else (0.14 if hov else 0.04)), r, border_radius=8)
            pygame.draw.rect(self.screen, C_ACCENT if on else (60, 72, 104), r, 2 if on else 1, border_radius=8)
            self._t(label, self.font_tiny, C_ACCENT if on else C_DIM, r.centerx, r.centery, "center")
            chip_x += w + 6
        r = pygame.Rect(chip_x + 4, tab_y, 126, 30)
        self.records_buttons["diff_cycle"] = r
        on = self.records_diff is not None
        pygame.draw.rect(self.screen, _mix((16, 20, 34), C_ORANGE, 0.28 if on else (0.14 if r.collidepoint(mx, my) else 0.04)), r, border_radius=8)
        pygame.draw.rect(self.screen, C_ORANGE if on else (60, 72, 104), r, 2 if on else 1, border_radius=8)
        diff_txt = "난이도: 전체" if self.records_diff is None else "난이도: " + BOT_DIFFICULTY_LABELS.get(self.records_diff, "-").split(" (")[0]
        self._t(diff_txt, self.font_tiny, C_ORANGE if on else C_DIM, r.centerx, r.centery, "center")

        # 3. 상단 4대 통계 요약 카드 (Summary Cards)
        sm = self.stats_mgr.get_summary("survival" if (self.records_mode == "trend" and self.settings.get("game_mode") == "survival") else ("battle" if self.records_mode == "trend" else self.records_mode),
                                        size=self.records_size, difficulty=self.records_diff)
        if self.records_mode == "trend":
            self._render_trend(box_x, box_y, box_w, sm)
            self._records_bottom_buttons(mx, my, box_x, box_y, box_w)
            return
        if sm.get("filtered"):
            self._t("필터 적용 중 · 최근 100경기 중 조건에 맞는 경기만 집계합니다", self.font_tiny, C_ORANGE, box_x + 25, box_y + 4)
        card_w = (box_w - 75) // 4
        card_h = 95
        hl_n = sum(self.stats_mgr.data.get("highlights", {}).values()) if self.records_mode == "battle" else 0      # 명장면 누적 횟수 / 레벨 (경기 종료 정산에서 쌓임)
        lv_now = self.stats_mgr.level()[0]
        card_y = box_y + 20
        
        cards_data = [
            ("로열 빅토리 (우승)" if self.records_mode == "battle" else "서바이벌 우승", f"{sm['victories']}승 / {sm['total_games']}전", f"승률 {sm['win_rate']:.1f}%", (255, 215, 60), (45, 38, 18)),
            ("최고 순위 (RANK)", sm['best_rank_str'], f"TOP 5: {sm['top_5']}회  |  TOP 10: {sm['top_10']}회", (100, 220, 255), (18, 40, 60)),
            (("처치 (K.O.) 기록", f"총 {sm['total_kos']}명 KO", f"단일 경기 최다: {sm['max_ko']}명" + (f" · 명장면 {hl_n}회" if hl_n else ""), (255, 110, 130), (50, 20, 28))
             if self.records_mode == "battle" else
             ("누적 플레이 시간", f"{sm['play_time_sec'] // 3600}시간 {sm['play_time_sec'] // 60 % 60}분", "공격 없이 버틴 시간", (255, 110, 130), (50, 20, 28))),
            ("블록 기술 기록", f"최대 {sm['max_combo']} 콤보", f"누적 {sm['total_lines']}줄 제거" + (f" · Lv.{lv_now}" if self.records_mode == "battle" and not sm.get("filtered") else ""), (120, 255, 160), (20, 48, 30))
        ]
        
        for i, (c_title, c_val, c_sub, c_col, c_bg) in enumerate(cards_data):
            cx = box_x + 25 + i * (card_w + 10)
            c_rect = pygame.Rect(cx, card_y, card_w, card_h)
            pygame.draw.rect(self.screen, c_bg, c_rect, border_radius=8)
            pygame.draw.rect(self.screen, c_col, c_rect, 1, border_radius=8)
            
            t_surf = self.font_small.render(c_title, True, (210, 230, 255))
            self.screen.blit(t_surf, (cx + 12, card_y + 10))
            
            v_surf = self.font_menu.render(c_val, True, c_col)
            self.screen.blit(v_surf, (cx + 12, card_y + 34))
            
            s_surf = self.font_tiny.render(c_sub, True, (160, 190, 220))
            self.screen.blit(s_surf, (cx + 12, card_y + 68))
            
        # 4. 최근 경기 매치 히스토리 테이블
        tbl_y = box_y + 130
        tbl_w = box_w - 50
        ix = box_x + 25
        columns = [("#", 50), ("난이도", 90), ("일시", 150), ("최종 순위", 150), ("K.O.", 90),
                   ("제거 줄", 90), ("최대 콤보", 100), ("생존 시간", 100), ("결과", 170)]

        self._t("최근 경기" if not sm.get("filtered") else f"최근 경기 ({len(sm['recent_matches'])}경기)", self.font_mid, C_TEXT, ix, tbl_y)
        self._t("최근 100경기 · 휠 / ↑↓ 로 스크롤", self.font_tiny, C_DIM, ix + tbl_w, tbl_y + 4, "topright")

        head_y = tbl_y + 32
        hx = ix
        for h_txt, h_w in columns:
            self._t(h_txt, self.font_tiny, C_DIM, hx + h_w // 2, head_y, "midtop")
            hx += h_w
        pygame.draw.line(self.screen, (48, 62, 98), (ix, head_y + 22), (ix + tbl_w, head_y + 22), 1)

        recent = sm['recent_matches']
        row_h = 38
        start_ry = head_y + 28

        if not recent:
            empty = pygame.Rect(ix, start_ry + 20, tbl_w, 150)
            pygame.draw.rect(self.screen, (18, 23, 40), empty, border_radius=12)
            pygame.draw.rect(self.screen, (40, 52, 84), empty, 1, border_radius=12)
            if sm.get("filtered"):
                self._t("조건에 맞는 경기가 없습니다", self.font_menu, C_TEXT, empty.centerx, empty.y + 42, "midtop")
                self._t("위의 규모/난이도 필터를 바꿔 보세요 (1~4 / F)", self.font_small, C_DIM, empty.centerx, empty.y + 82, "midtop")
            else:
                self._t("아직 완료된 경기가 없습니다" if self.records_mode == "battle" else "아직 서바이벌 경기가 없습니다", self.font_menu, C_TEXT, empty.centerx, empty.y + 42, "midtop")
                self._t("배틀로얄에 참가해 첫 승리에 도전해 보세요" if self.records_mode == "battle" else "설정 > 게임 > 게임 모드에서 서바이벌을 골라 도전해 보세요", self.font_small, C_DIM, empty.centerx, empty.y + 82, "midtop")
        else:
            visible = 8
            self.records_max_scroll = max(0, len(recent) - visible)
            self.records_scroll = max(0, min(self.records_max_scroll, self.records_scroll))
            rows_list = list(reversed(recent))
            if self.records_max_scroll:                       # 스크롤바
                track = pygame.Rect(ix + tbl_w + 8, start_ry, 6, visible * row_h - 4)
                pygame.draw.rect(self.screen, (28, 36, 60), track, border_radius=3)
                th = max(24, int(track.h * visible / len(recent)))
                ty = track.y + int((track.h - th) * self.records_scroll / self.records_max_scroll)
                pygame.draw.rect(self.screen, C_ACCENT, (track.x, ty, track.w, th), border_radius=3)
            for idx, m in enumerate(rows_list):
                if idx < self.records_scroll or idx >= self.records_scroll + visible:
                    continue
                ry = start_ry + (idx - self.records_scroll) * row_h
                row_rect = pygame.Rect(ix, ry, tbl_w, row_h - 4)
                is_won = m.get("won", False)
                rank = m.get("rank", 100)
                if is_won:
                    pygame.draw.rect(self.screen, (44, 38, 18), row_rect, border_radius=9)
                    pygame.draw.rect(self.screen, (150, 120, 40), row_rect, 1, border_radius=9)
                elif idx % 2 == 0:
                    pygame.draw.rect(self.screen, (20, 26, 44), row_rect, border_radius=9)

                sec = int(m.get("survival_sec", 0))
                if is_won:
                    rank_str, rank_col = "1위", C_GOLD
                    result_str, result_col = "로열 빅토리", C_GOLD
                elif rank <= 10:
                    rank_str, rank_col = f"{rank}위 / {m.get('total_players', 100)}", C_GREEN
                    result_str, result_col = "TOP 10", C_ACCENT
                else:
                    rank_str, rank_col = f"{rank}위 / {m.get('total_players', 100)}", C_TEXT
                    result_str, result_col = "탈락", (200, 110, 120)

                diff_str = BOT_DIFFICULTY_LABELS.get(m.get("difficulty"), "-").split(" (")[0]
                cells = [
                    (f"{len(recent) - idx}", 50, C_DIM),
                    (diff_str, 90, C_ACCENT),
                    (str(m.get("date", "-")), 150, (185, 200, 228)),
                    (rank_str, 150, rank_col),
                    (str(m.get("kos", 0)), 90, C_TEXT),
                    (str(m.get("lines", 0)), 90, C_TEXT),
                    (str(m.get("max_combo", 0)), 100, C_ORANGE),
                    (f"{sec // 60}:{sec % 60:02d}", 100, (185, 200, 228)),
                ]
                cx = ix
                for c_txt, c_w, c_col in cells:
                    self._t(c_txt, self.font_info, c_col, cx + c_w // 2, row_rect.centery, "center")
                    cx += c_w
                # 결과 칩
                chip = pygame.Rect(cx + 20, row_rect.y + 6, 130, row_rect.h - 12)
                pygame.draw.rect(self.screen, _mix((16, 20, 34), result_col, 0.22), chip, border_radius=chip.h // 2)
                pygame.draw.rect(self.screen, result_col, chip, 1, border_radius=chip.h // 2)
                self._t(result_str, self.font_small, result_col, chip.centerx, chip.centery, "center")

        self._records_bottom_buttons(mx, my, box_x, box_y, box_w)

    @staticmethod
    def trend_points(recent):
        """최근 경기(오래된 것부터)를 (0~1 상위 비율 점수, 우승 여부, 순위, 인원) 목록으로. 점수 1.0 = 1위, 0.0 = 꼴찌 (인원 규모가 달라도 비교 가능)"""
        pts = []
        for m in recent:
            total = max(2, int(m.get("total_players", 100) or 100))
            rank = max(1, min(total, int(m.get("rank", total) or total)))
            pts.append((1.0 - (rank - 1) / (total - 1), bool(m.get("won")), rank, total))
        return pts

    @staticmethod
    def trend_summary(pts):
        """(최근 10판 평균 점수, 그 이전 10판 평균 점수 또는 None). 경기가 없으면 (None, None)"""
        if not pts:
            return None, None
        last = [p[0] for p in pts[-10:]]
        prev = [p[0] for p in pts[-20:-10]]
        return sum(last) / len(last), (sum(prev) / len(prev) if prev else None)

    def _render_trend(self, box_x, box_y, box_w, sm):
        """순위 추이: 최근 경기마다 '상위 몇 %였는지'를 꺾은선으로 (위로 갈수록 좋음). 인원 규모가 달라도 비교할 수 있게 정규화"""
        pts = self.trend_points(sm["recent_matches"])
        ix, iw = box_x + 30, box_w - 60
        self._t("순위 추이" + (" (필터 적용)" if sm.get("filtered") else ""), self.font_mid, C_TEXT, ix, box_y + 20)
        self._t("최근 경기 · 위로 갈수록 좋은 성적 (인원 규모로 보정)", self.font_tiny, C_DIM, ix + iw, box_y + 24, "topright")
        if len(pts) < 2:
            empty = pygame.Rect(ix, box_y + 80, iw, 200)
            pygame.draw.rect(self.screen, (18, 23, 40), empty, border_radius=12)
            pygame.draw.rect(self.screen, (40, 52, 84), empty, 1, border_radius=12)
            self._t("추이를 그리려면 경기가 2판 이상 필요합니다", self.font_menu, C_TEXT, empty.centerx, empty.y + 70, "midtop")
            self._t("경기를 더 하거나 위의 규모/난이도 필터를 바꿔 보세요", self.font_small, C_DIM, empty.centerx, empty.y + 112, "midtop")
            return
        gx, gy, gw, gh = ix + 54, box_y + 64, iw - 70, 330
        pygame.draw.rect(self.screen, (14, 18, 32), (gx - 10, gy - 12, gw + 20, gh + 24), border_radius=10)
        for frac, label in ((1.0, "1위"), (0.75, "상위 25%"), (0.5, "50%"), (0.25, "하위 25%"), (0.0, "꼴찌")):
            yy = gy + int(gh * (1.0 - frac))
            pygame.draw.line(self.screen, (40, 52, 84) if frac not in (0.0, 1.0) else (66, 82, 124), (gx, yy), (gx + gw, yy), 1)
            self._t(label, self.font_tiny, C_DIM, gx - 10, yy, "midright")
        n = len(pts)
        xs = [gx + int(gw * (i / (n - 1))) for i in range(n)]
        ys = [gy + int(gh * (1.0 - p[0])) for p in pts]
        pygame.draw.lines(self.screen, (70, 96, 150), False, list(zip(xs, ys)), 1)
        avg = []                                                # 5판 이동 평균
        for i in range(n):
            w = pts[max(0, i - 4):i + 1]
            avg.append(sum(p[0] for p in w) / len(w))
        pygame.draw.lines(self.screen, C_ACCENT, False, [(xs[i], gy + int(gh * (1.0 - avg[i]))) for i in range(n)], 3)
        for i, p in enumerate(pts):
            pygame.draw.circle(self.screen, C_GOLD if p[1] else (150, 170, 215), (xs[i], ys[i]), 5 if p[1] else 3)
        last, prev = self.trend_summary(pts)
        pct = int(round((1.0 - last) * 100)) if last is not None else None
        parts = [f"최근 {min(10, n)}판 평균: 상위 {max(1, pct)}%"]
        if prev is not None:
            d = (last - prev) * 100
            parts.append(f"이전 {min(10, n - 10)}판보다 {'+' if d >= 0 else ''}{d:.0f}%p " + ("상승" if d > 1 else ("하락" if d < -1 else "비슷")))
        wins = sum(1 for p in pts if p[1])
        parts.append(f"우승 {wins}회 / {n}판")
        self._t("   ·   ".join(parts), self.font_info, C_GREEN if (prev is None or last >= prev) else C_ORANGE, ix, gy + gh + 30)
        self._t("● 우승   파란 선: 5판 이동 평균", self.font_tiny, C_DIM, ix + iw, gy + gh + 34, "topright")

    def _render_scores(self, box_x, box_y, box_w, tab_y, mx, my):
        """점수표 탭: 아케이드식 TOP 10 (점수 내림차순, 이니셜 / 최종 순위 / 인원 / K.O. / 날짜). 규모 칩(1~4)으로 거르고, 전체는 모든 규모를 합쳐 보여 줌"""
        chip_x = box_x + 498
        size_chips = [("size_all", "전체", None)] + [("size_" + b[0], f"{b[3].split(' ')[0][0]} {b[1]}~{b[2]}", b[0]) for b in SIZE_BUCKETS]
        for cid, label, val in size_chips:
            w = 46 if val is None else 76
            r = pygame.Rect(chip_x, tab_y, w, 30)
            self.records_buttons[cid] = r
            on = self.records_size == val
            pygame.draw.rect(self.screen, _mix((16, 20, 34), C_ACCENT, 0.28 if on else (0.14 if r.collidepoint(mx, my) else 0.04)), r, border_radius=8)
            pygame.draw.rect(self.screen, C_ACCENT if on else (60, 72, 104), r, 2 if on else 1, border_radius=8)
            self._t(label, self.font_tiny, C_ACCENT if on else C_DIM, r.centerx, r.centery, "center")
            chip_x += w + 6
        hs = self.stats_mgr.data.get("hiscores", {})
        rows = []
        for b, lst in hs.items():
            if self.records_size is None or b == self.records_size:
                rows += [dict(e, bucket=b) for e in lst]
        rows.sort(key=lambda e: -e["score"])
        rows = rows[:10]
        self._t("HIGH SCORES", self.font_title, (255, 205, 90), box_x + 28, box_y + 20)
        best = self.stats_mgr.data.get("best_score", 0)
        self._t(f"개인 최고 점수  {best:,}" if best else "아직 기록이 없습니다. 배틀로얄을 끝까지 해 보세요!", self.font_mid, C_TEXT, box_x + box_w - 28, box_y + 26, "topright")
        head_y = box_y + 80
        cols = [("순위", 60, "center"), ("이니셜", 150, "center"), ("점수", 360, "topright"), ("최종 순위", 520, "center"), ("규모", 650, "center"), ("K.O.", 760, "center"), ("날짜", 920, "center")]
        for label, cx_, anc in cols:
            self._t(label, self.font_tiny, C_DIM, box_x + cx_, head_y, anc if anc != "center" else "midtop")
        pygame.draw.line(self.screen, (70, 84, 120), (box_x + 28, head_y + 22), (box_x + box_w - 28, head_y + 22), 1)
        names = {"small": "소", "mid": "중", "large": "대"}
        for i in range(10):
            y = head_y + 34 + i * 36
            e = rows[i] if i < len(rows) else None
            rank_col = (255, 215, 90) if i == 0 else ((210, 220, 240) if i == 1 else ((235, 160, 110) if i == 2 else C_TEXT))
            if i % 2 == 0:
                pygame.draw.rect(self.screen, (20, 25, 44), (box_x + 24, y - 4, box_w - 48, 33), border_radius=8)
            self._t(f"{i + 1}", self.font_mid, rank_col if e else (70, 78, 100), box_x + 60, y + 14, "center")
            if e is None:
                self._t("- - -", self.font_mid, (70, 78, 100), box_x + 150, y + 14, "center")
                continue
            self._t(e["ini"], self.font_mid, rank_col, box_x + 150, y + 14, "center")
            self._t(f"{e['score']:,}", self.font_mid, rank_col, box_x + 360, y + 3, "topright")
            self._t(f"{e['rank']}위 / {e['total']}명", self.font_small, C_TEXT, box_x + 520, y + 14, "center")
            self._t(names.get(e["bucket"], "-"), self.font_small, C_DIM, box_x + 650, y + 14, "center")
            self._t(str(e["kos"]), self.font_small, (255, 150, 150), box_x + 760, y + 14, "center")
            self._t(e["date"], self.font_small, C_DIM, box_x + 920, y + 14, "center")

    def _render_achievements(self, box_x, box_y, box_w):
        """업적 탭: 카테고리(대전/누적/도전/연습·기술)별 한 페이지에 카드 최대 10개 (한 줄 5개 x 2줄). 달성은 밝게, 미달성은 흐리게 + 조건/진행도"""
        mx, my = pygame.mouse.get_pos()
        done = set(self.stats_mgr.achievements_done())
        prog = self.stats_mgr.achievement_progress()
        n_pages = len(ACH_CATEGORIES)
        self.records_ach_page = max(0, min(n_pages - 1, self.records_ach_page))
        self._t(f"달성한 업적  {len(done)} / {len(ACHIEVEMENTS)}", self.font_mid, C_TEXT, box_x + 25, box_y + 20)
        self._t("배틀로얄 경기와 연습·도전 기록으로 달성합니다 (한 번 달성하면 유지)", self.font_tiny, C_DIM, box_x + box_w - 25, box_y + 26, "topright")

        # 페이지 탭 (카테고리): 이름 + 달성 수 + 얇은 진행 바
        gap = 10
        tw = (box_w - 50 - gap * (n_pages - 1)) // n_pages
        for i, (cid, cname) in enumerate(ACH_CATEGORIES):
            ids = [a[0] for a in ACHIEVEMENTS if ACH_CATEGORY.get(a[0]) == cid]
            n_got = sum(1 for x in ids if x in done)
            r = pygame.Rect(box_x + 25 + i * (tw + gap), box_y + 56, tw, 42)
            self.records_buttons[f"ach_{i}"] = r
            on = i == self.records_ach_page
            hov = r.collidepoint(mx, my)
            full = n_got == len(ids)
            col = C_GOLD if (on or full) else C_DIM
            pygame.draw.rect(self.screen, _mix((16, 20, 34), C_GOLD, 0.26 if on else (0.14 if hov else 0.04)), r, border_radius=10)
            pygame.draw.rect(self.screen, C_GOLD if on else (60, 72, 104), r, 2 if on else 1, border_radius=10)
            self._t(f"{i + 1}  {cname}", self.font_small, col, r.x + 14, r.y + 12)
            self._t(f"{n_got} / {len(ids)}", self.font_small, C_TEXT if on else C_DIM, r.right - 14, r.y + 12, "topright")
            pygame.draw.rect(self.screen, (28, 34, 56), (r.x + 12, r.bottom - 8, r.w - 24, 3), border_radius=1)
            if n_got:
                pygame.draw.rect(self.screen, C_GOLD, (r.x + 12, r.bottom - 8, max(3, int((r.w - 24) * n_got / max(1, len(ids)))), 3), border_radius=1)

        # 카드 (이 페이지의 업적)
        cat = ACH_CATEGORIES[self.records_ach_page][0]
        items = [a for a in ACHIEVEMENTS if ACH_CATEGORY.get(a[0]) == cat]
        cols = 5
        cgap = 10
        cw = (box_w - 50 - cgap * (cols - 1)) // cols
        ch = 174
        for i, (aid, title, desc, _ok) in enumerate(items):
            r = pygame.Rect(box_x + 25 + (i % cols) * (cw + cgap), box_y + 110 + (i // cols) * (ch + cgap), cw, ch)
            got = aid in done
            col = C_GOLD if got else (80, 92, 126)
            pygame.draw.rect(self.screen, (44, 38, 18) if got else (16, 20, 34), r, border_radius=12)
            pygame.draw.rect(self.screen, col, r, 2 if got else 1, border_radius=12)
            self._t("★" if got else "☆", self.font_title, C_GOLD if got else (70, 80, 110), r.centerx, r.y + 6, "midtop")
            self._t(title, self.font_mid, C_TEXT if got else (140, 152, 185), r.centerx, r.y + 60, "midtop")
            for li, line in enumerate(self._wrap_text(desc, self.font_tiny, cw - 20)[:3]):
                self._t(line, self.font_tiny, (185, 200, 228) if got else (110, 122, 156), r.centerx, r.y + 92 + li * 18, "midtop")
            if got:
                self._t("달성!", self.font_tiny, C_GOLD, r.centerx, r.bottom - 24, "midtop")
            elif aid in prog:                                           # 근접 진행도 (예: 최고 3 / 5)
                cur, goal = prog[aid]
                txt = (f"진행 {cur // 60}:{cur % 60:02d} / {goal // 60}:{goal % 60:02d}" if aid in ("marathon", "ironman")
                       else f"진행 {cur} / {goal}" + ("분" if aid == "playtime" else ""))
                self._t(txt, self.font_tiny, C_ORANGE if cur else (90, 100, 130), r.centerx, r.bottom - 24, "midtop")
                pygame.draw.rect(self.screen, (28, 34, 56), (r.x + 14, r.bottom - 9, r.w - 28, 3), border_radius=1)
                if cur:
                    pygame.draw.rect(self.screen, C_ORANGE, (r.x + 14, r.bottom - 9, max(3, int((r.w - 28) * cur / max(1, goal))), 3), border_radius=1)
            else:
                self._t("미달성", self.font_tiny, (90, 100, 130), r.centerx, r.bottom - 24, "midtop")

        # 페이지 이동 줄: ◀ 이전 / n / N / 다음 ▶
        ny = box_y + 110 + 2 * (ch + cgap) - 2
        cx = box_x + box_w // 2
        for bid, label, bx, enabled in (("ach_prev", "◀ 이전", cx - 190, self.records_ach_page > 0), ("ach_next", "다음 ▶", cx + 70, self.records_ach_page < n_pages - 1)):
            r = pygame.Rect(bx, ny, 120, 30)
            self.records_buttons[bid] = r
            hov = enabled and r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _mix((16, 20, 34), C_GOLD, 0.2 if hov else 0.05), r, border_radius=8)
            pygame.draw.rect(self.screen, C_GOLD if enabled else (50, 60, 88), r, 1, border_radius=8)
            self._t(label, self.font_small, C_GOLD if enabled else (70, 80, 110), r.centerx, r.centery, "center")
        for i in range(n_pages):                                         # 가운데: 점 표시
            pygame.draw.circle(self.screen, C_GOLD if i == self.records_ach_page else (70, 80, 110), (cx - 36 + i * 24, ny + 15), 5 if i == self.records_ach_page else 4)
        self._t("PgUp / PgDn · 휠", self.font_tiny, C_DIM, box_x + box_w - 25, ny + 15, "midright")

    def _wrap_text(self, text, font, max_w):
        """글자 단위 줄바꿈 (한글 포함)"""
        lines, cur = [], ""
        for ch in text:
            if cur and font.size(cur + ch)[0] > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    def _records_bottom_buttons(self, mx, my, box_x, box_y, box_w):
        ix = box_x + 25
        # 5. 하단 액션 버튼들
        btn_y = box_y + 520
        self.records_buttons['reset_stats'] = pygame.Rect(ix + 20, btn_y, 220, 48)
        self._draw_btn(self.records_buttons['reset_stats'], "전적 기록 초기화",
                       self.records_buttons['reset_stats'].collidepoint(mx, my),
                       (45, 30, 35), (70, 45, 55), (160, 80, 95), (255, 190, 200), self.font_mid)
                       
        self.records_buttons['back_to_menu'] = pygame.Rect(box_x + box_w - 330, btn_y, 300, 48)
        self._draw_btn(self.records_buttons['back_to_menu'], "메인 메뉴로 (ESC)",
                       self.records_buttons['back_to_menu'].collidepoint(mx, my),
                       (20, 65, 85), (32, 100, 130), (70, 200, 255), (220, 250, 255), self.font_mid)
