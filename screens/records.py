"""
Block Royale 100 - 전적 기록실 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import BOT_DIFFICULTY_LABELS, C_ACCENT, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, SCREEN_WIDTH, _mix, pygame


class RecordsMixin:
    def _handle_records_event(self, event):
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
            self._records_set_mode("survival" if self.records_mode == "battle" else "battle")
            return
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_ESCAPE, pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE]:
                self.sound_mgr.play('move')
                self.state = "MENU"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for btn_id, rect in self.records_buttons.items():
                if rect.collidepoint(mx, my):
                    if btn_id in ("mode_battle", "mode_survival"):
                        self._records_set_mode(btn_id[5:])
                    elif btn_id == "back_to_menu":
                        self.sound_mgr.play('move')
                        self.state = "MENU"
                    elif btn_id == "reset_stats":
                        self._open_modal("전적 기록을 초기화할까요?", ["배틀로얄·서바이벌 전적이 모두 삭제됩니다.", "되돌릴 수 없습니다."],
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
        
        self._menu_header("전적 기록실", None, accent=C_GOLD)
        box_w, box_h = 1040, 580
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 120
        self._glass((box_x, box_y, box_w, box_h), accent=(170, 140, 60), radius=18)

        # 2. 모드 탭 (배틀로얄 / 서바이벌): 전적은 모드별로 따로 집계
        tab_y = box_y - 34
        for i, (mid, label, col) in enumerate((("battle", "배틀로얄", C_GOLD), ("survival", "서바이벌", C_GREEN))):
            r = pygame.Rect(box_x + i * 150, tab_y, 140, 30)
            self.records_buttons["mode_" + mid] = r
            on = self.records_mode == mid
            hov = r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _mix((16, 20, 34), col, 0.30 if on else (0.14 if hov else 0.05)), r, border_radius=8)
            pygame.draw.rect(self.screen, col if on else (60, 72, 104), r, 2 if on else 1, border_radius=8)
            self._t(label, self.font_small, col if on else C_DIM, r.centerx, r.centery, "center")
        self._t("← → / Tab 으로 전환", self.font_tiny, C_DIM, box_x + box_w, tab_y + 15, "midright")

        # 3. 상단 4대 통계 요약 카드 (Summary Cards)
        sm = self.stats_mgr.get_summary(self.records_mode)
        card_w = (box_w - 75) // 4
        card_h = 95
        card_y = box_y + 20
        
        cards_data = [
            ("로열 빅토리 (우승)" if self.records_mode == "battle" else "서바이벌 우승", f"{sm['victories']}승 / {sm['total_games']}전", f"승률 {sm['win_rate']:.1f}%", (255, 215, 60), (45, 38, 18)),
            ("최고 순위 (RANK)", sm['best_rank_str'], f"TOP 5: {sm['top_5']}회  |  TOP 10: {sm['top_10']}회", (100, 220, 255), (18, 40, 60)),
            (("처치 (K.O.) 기록", f"총 {sm['total_kos']}명 KO", f"단일 경기 최다: {sm['max_ko']}명", (255, 110, 130), (50, 20, 28))
             if self.records_mode == "battle" else
             ("누적 플레이 시간", f"{sm['play_time_sec'] // 3600}시간 {sm['play_time_sec'] // 60 % 60}분", "공격 없이 버틴 시간", (255, 110, 130), (50, 20, 28))),
            ("블록 기술 기록", f"최대 {sm['max_combo']} 콤보", f"누적 {sm['total_lines']}줄 제거", (120, 255, 160), (20, 48, 30))
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

        self._t("최근 경기", self.font_mid, C_TEXT, ix, tbl_y)
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
