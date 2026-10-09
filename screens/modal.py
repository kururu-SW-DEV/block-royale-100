"""
Block Royale 100 - 확인/알림 창
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import CANVAS, C_ACCENT, C_DANGER, C_DIM, C_TEXT, SCREEN_HEIGHT, SCREEN_WIDTH, pygame


class ModalMixin:
    def _confirm_leave_network_game(self):
        """네트워크 게임 중 ESC: 바로 나가지 않고 확인 창을 띄움 (게임은 계속 진행됨)"""
        self._clear_input_state()
        if self.net_mgr.mode == "NONE":
            lines = ["진행 중인 경기는 저장되지 않고 메인 메뉴로 돌아갑니다.", "정말 나가시겠습니까?"]
        elif self.net_mgr.mode == "HOST":
            lines = ["방장이 나가면 방이 닫히고 모든 참가자의 게임이 종료됩니다.", "정말 나가시겠습니까?"]
        else:
            lines = ["게임에서 나가면 탈락 처리되고 메인 메뉴로 돌아갑니다.", "정말 나가시겠습니까?"]
        self._open_modal("게임에서 나갈까요?", lines,
                         [("stay", "계속 플레이", "blue", "ESC"), ("leave", "나가기", "red", "Y")])

    def _confirm_quit_app(self):
        self._clear_input_state()
        self._auto_pause_solo()                                # 솔로 게임은 확인 창이 떠 있는 동안 멈춤
        self._open_modal("게임을 종료할까요?", ["프로그램을 완전히 종료합니다."],
                         [("stay", "취소", "blue", "ESC"), ("quit_app", "종료", "red", "Y")])

    def _open_modal(self, title, lines, buttons):
        ids = [b[0] for b in buttons]
        focus = ids.index("stay") if "stay" in ids else 0        # 기본 포커스는 항상 안전한 쪽
        self.modal = {"title": title, "lines": lines, "buttons": buttons, "rects": {}, "focus": focus,
                      "last_mouse": pygame.mouse.get_pos()}
        self.sound_mgr.play('warning')

    def _modal_choose(self, bid):
        self.modal = None
        self.sound_mgr.play('move')
        if bid in ("leave", "ok_menu"):
            self.return_to_menu()
        elif bid == "close_room":
            self.net_mgr.stop()
            self.state = "MENU"
        elif bid == "restart_ok":
            self._restart_after_match()
        elif bid == "quit_app":
            self._quit_confirmed = True
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif bid == "reset_stats_ok":
            self.sound_mgr.play('clear')
            self.stats_mgr.reset_stats()
        elif bid == "reset_practice_ok":
            self.sound_mgr.play('clear')
            self.stats_mgr.reset_practice()
        elif bid == "reset_defaults_ok":
            self._do_reset_defaults()
        if self.modal is None and self._pending_quit:
            self._pending_quit = False
            self._confirm_quit_app()

    def _handle_modal_event(self, event):
        buttons = self.modal["buttons"]
        if event.type == pygame.KEYDOWN:
            ids = [b[0] for b in buttons]
            if event.key == pygame.K_ESCAPE:
                self._modal_choose("stay" if "stay" in ids else ids[0])      # ESC는 항상 안전한 쪽 (포커스 위치와 무관)
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = -1 if event.key == pygame.K_LEFT else 1
                self.modal["focus"] = (self.modal["focus"] + step) % len(buttons)
                self.sound_mgr.play('move')
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._modal_choose(ids[self.modal["focus"]])
            elif event.key == pygame.K_y and "leave" in ids:
                self._modal_choose("leave")
            elif event.key == pygame.K_y:
                for b in buttons:
                    if b[0] != "stay" and b[2] == "red":
                        self._modal_choose(b[0])
                        break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for bid, rect in self.modal["rects"].items():
                if rect.collidepoint(event.pos):
                    self._modal_choose(bid)
                    return

    def _render_modal(self):
        m = self.modal
        r = self.renderer
        CANVAS.overlay((4, 6, 12, 175))
        w, h = 620, 250
        x, y = (SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2
        danger = any(b[2] == "red" for b in m["buttons"])
        accent = C_DANGER if danger else C_ACCENT
        r._panel((x, y, w, h), border=accent, bg=(16, 20, 36), radius=18, alpha=248, border_w=2)
        r._draw_text(m["title"], r.font_large, C_TEXT, x + w // 2, y + 28, "midtop")
        for i, line in enumerate(m["lines"]):
            r._draw_text(line, r.font_mid, C_DIM if i else (215, 222, 240), x + w // 2, y + 84 + i * 28, "midtop")
        mx, my = pygame.mouse.get_pos()
        n = len(m["buttons"])
        bw, gap = 230, 20
        sx = x + (w - (bw * n + gap * (n - 1))) // 2
        m["rects"] = {}
        rects = [pygame.Rect(sx + i * (bw + gap), y + h - 84, bw, 52) for i in range(n)]
        moved = (mx, my) != m.get("last_mouse")      # 마우스가 실제로 움직였을 때만 포커스를 옮김 (가만히 있는 마우스 때문에 Space/Enter가 엉뚱한 버튼을 누르지 않게)
        m["last_mouse"] = (mx, my)
        for i, rect in enumerate(rects):
            if moved and rect.collidepoint(mx, my):       # 마우스가 다른 버튼 위에 있으면 키보드 포커스도 그쪽으로 옮김 (이중 하이라이트 방지)
                m["focus"] = i
                break
        for i, (bid, label, style, hint) in enumerate(m["buttons"]):
            rect = rects[i]
            m["rects"][bid] = rect
            r._button(rect, label, style, m["focus"] == i, hint)
