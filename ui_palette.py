"""
Block Royale 100 - UI 공통 색과 보조 함수 (ui_renderer / ui_results가 함께 씀)
"""

C_BG_TOP = (14, 17, 30)
C_BG_BOTTOM = (8, 9, 16)
C_PANEL = (20, 25, 42)
C_PANEL_BORDER = (52, 64, 98)
C_TEXT = (235, 240, 252)
C_DIM = (130, 142, 170)
C_ACCENT = (90, 205, 255)
C_GOLD = (255, 205, 90)
C_GREEN = (95, 235, 165)
C_DANGER = (255, 85, 95)
C_ORANGE = (255, 165, 70)


def ease_out(x):
    """0~1 진행도를 처음엔 빠르게 끝에선 천천히 (연출용)"""
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return 1.0 - (1.0 - x) ** 3
