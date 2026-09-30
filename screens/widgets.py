"""
Block Royale 100 - 여러 화면이 함께 쓰는 UI 부품 (글자, 패널, 버튼, 색 선택, 채팅 패널 등)
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import C_ACCENT, C_DIM, C_PANEL_BORDER, C_TEXT, NAME_COLORS, SCREEN_WIDTH, _mix, pygame, time


class WidgetsMixin:
    def _draw_btn(self, rect, text, is_hover, base_bg, hover_bg, border_color, text_color, font=None):
        f = font or self.font_menu
        rect = pygame.Rect(rect)
        if is_hover:                                        # 호버 글로우: 크기/색별로 한 번만 만들어 재사용 (프레임마다 Surface 생성 안 함)
            gw, gh, gc = rect.w + 14, rect.h + 14, tuple(border_color[:3])
            self.renderer._blit_overlay(("btnglow", gw, gh, gc), (gw, gh),
                                        lambda surf: pygame.draw.rect(surf, (*gc, 46), (0, 0, gw, gh), border_radius=12), (rect.x - 7, rect.y - 7))
        pygame.draw.rect(self.screen, hover_bg if is_hover else base_bg, rect, border_radius=9)
        edge = _mix(border_color, (255, 255, 255), 0.3) if is_hover else _mix(border_color, base_bg, 0.4)
        pygame.draw.rect(self.screen, edge, rect, 2 if is_hover else 1, border_radius=9)
        self.renderer._draw_text(text, f, (255, 255, 255) if is_hover else text_color, rect.centerx, rect.centery, "center")

    def _t(self, text, font, color, x, y, anchor="topleft"):
        return self.renderer._draw_text(text, font, color, x, y, anchor)

    def _glass(self, rect, accent=C_PANEL_BORDER, radius=16, alpha=238, border_w=1):
        self.renderer._panel(rect, border=accent, bg=(15, 19, 34), radius=radius, alpha=alpha, border_w=border_w)

    def _menu_header(self, title, subtitle, accent=C_ACCENT, y=32):
        """모든 메뉴 화면 공통 헤더: 큰 제목 + 액센트 밑줄 + 보조 설명"""
        cx = SCREEN_WIDTH // 2
        rect = self._t(title.replace(" ", "  "), self.font_title, C_TEXT, cx, y, "midtop")      # 큰 글씨는 띄어쓰기 폭이 좁아 단어가 붙어 보이므로 넓힘
        pygame.draw.rect(self.screen, accent, (cx - 36, rect.bottom + 8, 72, 3), border_radius=2)
        if subtitle:
            self._t(subtitle, self.font_info, C_DIM, cx, rect.bottom + 22, "midtop")

    def _keycap_row(self, items, cx, y, gap=18, font=None, label_col=None):
        """[키] 설명 형태의 안내 줄을 가운데 정렬해서 그림 (font/label_col로 크기와 설명 글자색 지정)"""
        font = font or self.font_tiny
        parts = []
        total = 0
        for key, label in items:
            ks = self.renderer._text(key, font, (215, 225, 245))
            ls = self.renderer._text(label, font, label_col or C_DIM)
            w = ks.get_width() + 14 + 6 + ls.get_width()
            parts.append((ks, ls, w))
            total += w
        total += gap * (len(parts) - 1)
        x = cx - total // 2
        for ks, ls, w in parts:
            kr = pygame.Rect(x, y, ks.get_width() + 14, 20 if font is self.font_tiny else 24)
            pygame.draw.rect(self.screen, (36, 44, 70), kr, border_radius=5)
            pygame.draw.rect(self.screen, (78, 92, 132), kr, 1, border_radius=5)
            self.screen.blit(ks, (kr.x + 7, kr.centery - ks.get_height() // 2))
            self.screen.blit(ls, (kr.right + 6, kr.centery - ls.get_height() // 2))
            x += w + gap

    def _pill_btn(self, rect, label, hover, accent=C_ACCENT):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, (32, 40, 66) if hover else (22, 28, 48), rect, border_radius=rect.h // 2)
        pygame.draw.rect(self.screen, accent if hover else (56, 70, 108), rect, 1, border_radius=rect.h // 2)
        self._t(label, self.font_small, C_TEXT if hover else (190, 202, 228), rect.centerx, rect.centery, "center")

    def _draw_color_swatches(self, x, y, size=22, gap=6):
        """이름 색 선택 칸: 동그란 색 견본 (선택된 색은 흰 테두리)"""
        self.color_rects = self.color_rects or []
        rects = []
        for i, (label, rgb) in enumerate(NAME_COLORS):
            r = pygame.Rect(x + i * (size + gap), y, size, size)
            rects.append(r)
            pygame.draw.circle(self.screen, rgb, r.center, size // 2)
            if i == self.name_color:
                pygame.draw.circle(self.screen, (255, 255, 255), r.center, size // 2 + 3, 2)
            elif r.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.circle(self.screen, (170, 180, 205), r.center, size // 2 + 2, 1)
        return rects

    def _draw_chat_panel(self, rect):
        """대기실 채팅 패널: 내 이름/색 편집 + 메시지 목록 + 입력칸 (Tab 또는 클릭으로 입력, Enter 전송)"""
        r = self.renderer
        self._glass(rect, accent=(70, 100, 160), radius=16)
        self._t("채팅", self.font_menu, C_TEXT, rect.x + 20, rect.y + 14)
        self._t("Tab / 클릭: 입력  ·  Enter: 전송", self.font_tiny, C_DIM, rect.right - 18, rect.y + 22, "topright")

        # 내 프로필: 이름 입력칸 + 이름 색 선택
        prof_y = rect.y + 50
        self._t("내 이름", self.font_tiny, C_DIM, rect.x + 18, prof_y + 2)
        nbox = pygame.Rect(rect.x + 72, prof_y - 6, rect.w - 72 - 16, 32)
        self.text_rects["player_name"] = nbox
        editing = (self.text_focus == "player_name")
        pygame.draw.rect(self.screen, (11, 13, 24), nbox, border_radius=8)
        pygame.draw.rect(self.screen, C_ACCENT if editing else (60, 74, 110), nbox, 2 if editing else 1, border_radius=8)
        shown = (self.player_name_input + self.chat_comp) if editing else self.player_name
        tr = self._t(shown, self.font_small, NAME_COLORS[self.name_color][1], nbox.x + 10, nbox.centery, "midleft")
        if editing and int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_ACCENT, (tr.right + 3, nbox.y + 7, 2, nbox.h - 14))
        if not editing:
            self._t("클릭해서 수정", self.font_tiny, C_DIM, nbox.right - 8, nbox.centery, "midright")
        self._t("이름 색", self.font_tiny, C_DIM, rect.x + 18, prof_y + 42)
        self.color_rects = self._draw_color_swatches(rect.x + 72, prof_y + 36, size=20, gap=5)

        area = pygame.Rect(rect.x + 16, rect.y + 132, rect.w - 32, rect.h - 132 - 70)
        line_h = 20
        my_id = self.net_mgr.my_player_id or ""
        lines = r.chat_lines(self.net_mgr.chat_log[-40:], self.font_small, area.w - 4)
        lines = lines[-max(1, area.h // line_h):]
        if not lines:
            self._t("아직 메시지가 없습니다. 인사를 건네 보세요!", self.font_small, C_DIM, area.x, area.y + 4)
        for i, segs in enumerate(lines):
            r.draw_segments(segs, self.font_small, area.x, area.y + i * line_h)
        box = pygame.Rect(rect.x + 16, rect.bottom - 58, rect.w - 32, 42)
        self.text_rects["chat"] = box
        focused = (self.text_focus == "chat")
        pygame.draw.rect(self.screen, (11, 13, 24), box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT if focused else (60, 74, 110), box, 2 if focused else 1, border_radius=10)
        shown = self.chat_input + (self.chat_comp if focused else "")
        while shown and self.font_small.size(shown)[0] > box.w - 28:
            shown = shown[1:]
        if shown:
            t = self._t(shown, self.font_small, C_TEXT, box.x + 12, box.centery, "midleft")
            if focused and int(time.time() * 2) % 2 == 0:
                pygame.draw.rect(self.screen, C_ACCENT, (t.right + 3, box.y + 9, 2, box.h - 18))
        else:
            self._t("메시지를 입력하세요" if focused else "여기를 클릭하거나 Tab", self.font_small, C_DIM, box.x + 12, box.centery, "midleft")
            if focused and int(time.time() * 2) % 2 == 0:
                pygame.draw.rect(self.screen, C_ACCENT, (box.x + 12, box.y + 9, 2, box.h - 18))

    def _mode_card(self, btn_id, rect, title, desc, key, accent, mx, my):
        rect = pygame.Rect(rect)
        self.menu_buttons[btn_id] = rect
        hover = rect.collidepoint(mx, my) or (self.MENU_FOCUS_ORDER[self.menu_focus] == btn_id)
        if hover:
            glow = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, 40), glow.get_rect(), border_radius=16)
            self.screen.blit(glow, (rect.x - 8, rect.y - 8))
        pygame.draw.rect(self.screen, _mix((22, 28, 48), accent, 0.16 if hover else 0.05), rect, border_radius=12)
        pygame.draw.rect(self.screen, accent if hover else _mix(accent, (22, 28, 48), 0.6), rect, 2 if hover else 1, border_radius=12)
        pygame.draw.rect(self.screen, accent, (rect.x + 14, rect.y + 16, 5, rect.h - 32), border_radius=3)
        self._t(title, self.font_menu, C_TEXT, rect.centerx, rect.y + 13, "midtop")
        self._t(desc, self.font_small, C_DIM, rect.centerx, rect.y + 44, "midtop")
        kr = pygame.Rect(rect.right - 54, rect.centery - 13, 34, 26)
        pygame.draw.rect(self.screen, accent, kr, border_radius=7)
        self._t(key, self.font_mid, (12, 16, 28), kr.centerx, kr.centery, "center")

    def _stepper(self, buttons, prefix, y, x0, value_text, value_color, minus, plus):
        """[-10][-1] (값) [+1][+10] 형태의 증감 컨트롤. minus/plus: (id, 라벨, 폭) 리스트"""
        mx, my = pygame.mouse.get_pos()
        x = x0
        for bid, label, w in minus:
            rect = pygame.Rect(x, y, w, 34)
            buttons[bid] = rect
            self._draw_btn(rect, label, rect.collidepoint(mx, my), (44, 28, 38), (70, 40, 55), (150, 70, 100), (255, 180, 190), self.font_small)
            x += w + 6
        val = pygame.Rect(x + 4, y, 160, 34)
        pygame.draw.rect(self.screen, (12, 15, 27), val, border_radius=8)
        pygame.draw.rect(self.screen, value_color, val, 1, border_radius=8)
        self._t(value_text, self.font_mid, value_color, val.centerx, val.centery, "center")
        x = val.right + 10
        for bid, label, w in plus:
            rect = pygame.Rect(x, y, w, 34)
            buttons[bid] = rect
            self._draw_btn(rect, label, rect.collidepoint(mx, my), (28, 48, 40), (42, 75, 60), (70, 160, 110), (180, 255, 210), self.font_small)
            x += w + 6
