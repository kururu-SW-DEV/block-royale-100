"""
Block Royale 100 - Resolution-independent drawing layer

모든 UI 코드는 1366x768 "논리 좌표"로 작성되어 있습니다. 이 모듈은 실제 창/모니터 해상도에 맞춰
  - 도형(pygame.draw)은 좌표/두께/둥근 모서리를 배율만큼 키워서 네이티브 해상도로 그리고
  - 글꼴(HiFont)은 배율만큼 큰 크기로 렌더링하며
  - 미리 만든 패널/셀 캐시(HiSurf)는 네이티브 해상도로 생성합니다.
그래서 FHD/QHD/4K에서도 픽셀이 깨지지 않고 선명하게 보입니다. (단순 확대 방식과 달리 화면이 뭉개지지 않음)
16:9가 아닌 창에서는 가운데 정렬 + 검은 여백(레터박스)으로 표시합니다.
"""

import pygame

BASE_W, BASE_H = 1366, 768


class HiSurf(pygame.Surface):
    """네이티브(고해상도)로 그려진 서피스. 레이아웃용 크기는 논리 좌표(1366x768 기준)로 보고합니다."""

    def __init__(self, size, flags=0, scale=1.0):
        super().__init__(size, flags)
        self.scale = scale

    def get_width(self):
        return int(round(pygame.Surface.get_width(self) / self.scale))

    def get_height(self):
        return int(round(pygame.Surface.get_height(self) / self.scale))

    def get_size(self):
        return (self.get_width(), self.get_height())

    def get_rect(self, **kwargs):
        r = pygame.Rect(0, 0, self.get_width(), self.get_height())
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def get_bounding_rect(self, min_alpha=1):
        """실제로 그려진 픽셀의 범위를 논리 좌표로 반환 (다른 크기 정보와 같은 좌표계라 배율이 달라도 위치 계산이 맞음)"""
        r = pygame.Surface.get_bounding_rect(self, min_alpha)
        s = self.scale
        left, top, right, bottom = round(r.left / s), round(r.top / s), round(r.right / s), round(r.bottom / s)
        return pygame.Rect(left, top, right - left, bottom - top)


def mix_color(c1, c2, t):
    """두 색을 t(0~1) 비율로 섞음"""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3]))


class Canvas:
    """논리 좌표계(1366x768) -> 실제 디스플레이 서피스 변환기. pygame.Surface처럼 blit/fill 등을 제공."""

    def __init__(self):
        self.display = None
        self.S = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.version = 0     # 배율이 바뀔 때마다 증가 (캐시 무효화용)
        self._orig = {}

    # ------------------------------------------------------------ 설정
    def attach(self, surface):
        if isinstance(surface, Canvas):
            return surface
        self.display = surface
        self.resize()
        return self

    def resize(self):
        w, h = self.display.get_size()
        self.S = max(0.25, min(w / BASE_W, h / BASE_H))
        self.ox = (w - BASE_W * self.S) / 2.0
        self.oy = (h - BASE_H * self.S) / 2.0
        self.version += 1

    # ------------------------------------------------------------ 좌표 변환
    def X(self, x):
        return int(round(self.ox + x * self.S))

    def Y(self, y):
        return int(round(self.oy + y * self.S))

    def length(self, v, minimum=0):
        n = int(round(v * self.S))
        return max(minimum, n)

    def rect(self, r):
        r = pygame.Rect(r) if not isinstance(r, pygame.Rect) else r
        return self.rect_f(r.x, r.y, r.w, r.h)

    def rect_f(self, x, y, w, h):
        left, top = self.X(x), self.Y(y)
        right, bottom = self.X(x + w), self.Y(y + h)
        rw = right - left
        rh = bottom - top
        if w > 0 and rw < 1:
            rw = 1
        if h > 0 and rh < 1:
            rh = 1
        return pygame.Rect(left, top, rw, rh)

    def to_logical(self, pos):
        return (int((pos[0] - self.ox) / self.S), int((pos[1] - self.oy) / self.S))

    # ------------------------------------------------------------ Surface 호환 API
    def get_size(self):
        return (BASE_W, BASE_H)

    def get_width(self):
        return BASE_W

    def get_height(self):
        return BASE_H

    def get_flags(self):
        return self.display.get_flags()

    def fill(self, color, rect=None):
        if rect is None:
            self.display.fill(color)
        else:
            self.display.fill(color, self.rect(rect))

    def blit(self, src, dest=(0, 0), area=None):
        if hasattr(dest, "topleft"):
            dx, dy = dest.topleft
        else:
            dx, dy = dest[0], dest[1]
        if isinstance(src, HiSurf):
            self.display.blit(src, (self.X(dx), self.Y(dy)))
            return
        w, h = src.get_size()
        tw, th = self.length(w, 1), self.length(h, 1)
        if abs(self.S - 1.0) < 1e-3:
            scaled = src
        else:
            try:
                scaled = pygame.transform.smoothscale(src, (tw, th))
            except ValueError:
                scaled = pygame.transform.scale(src, (tw, th))
        self.display.blit(scaled, (self.X(dx), self.Y(dy)))

    # ------------------------------------------------------------ 알파 도형 (네이티브 해상도)
    def alpha_rect(self, rect, color, width=0, radius=0):
        """RGBA 색상의 사각형/테두리를 네이티브 해상도로 그림 (반투명 판, 딤 등)"""
        r = self.rect(rect)
        if r.w <= 0 or r.h <= 0:
            return
        surf = pygame.Surface(r.size, pygame.SRCALPHA)
        w = 0 if width == 0 else self.length(width, 1)
        self._orig["rect"](surf, color, (0, 0, r.w, r.h), w, border_radius=int(round(radius * self.S)))
        self.display.blit(surf, r.topleft)

    def overlay(self, color):
        """화면 전체(레터박스 포함)를 반투명 색으로 덮음 (같은 크기/색이면 서피스를 재사용)"""
        size = self.display.get_size()
        key = (size, tuple(color))
        cache = getattr(self, "_overlay_surf", None)
        if cache is None or cache[0] != key:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            surf.fill(color)
            cache = self._overlay_surf = (key, surf)
        self.display.blit(cache[1], (0, 0))

    def make_surface(self, w, h, alpha=True):
        """논리 크기 (w, h)에 해당하는 네이티브 해상도 HiSurf 생성"""
        return HiSurf((self.length(w, 1), self.length(h, 1)), pygame.SRCALPHA if alpha else 0, self.S)


CANVAS = Canvas()


# ---------------------------------------------------------------- pygame.draw 패치
_orig_draw = {name: getattr(pygame.draw, name) for name in ("rect", "line", "lines", "circle", "ellipse")}
CANVAS._orig = _orig_draw


def _w(c, width):
    return 0 if width == 0 else c.length(width, 1)


def _rect(surface, color, rect, width=0, border_radius=0):
    if not isinstance(surface, Canvas):
        return _orig_draw["rect"](surface, color, rect, width, border_radius=border_radius)
    if isinstance(rect, pygame.Rect):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
    else:
        x, y, w, h = rect
    return _orig_draw["rect"](surface.display, color, surface.rect_f(x, y, w, h), _w(surface, width),
                              border_radius=int(round(border_radius * surface.S)))


def _line(surface, color, start, end, width=1):
    if not isinstance(surface, Canvas):
        return _orig_draw["line"](surface, color, start, end, width)
    return _orig_draw["line"](surface.display, color,
                              (surface.X(start[0]), surface.Y(start[1])),
                              (surface.X(end[0]), surface.Y(end[1])), max(1, _w(surface, width)))


def _lines(surface, color, closed, points, width=1):
    if not isinstance(surface, Canvas):
        return _orig_draw["lines"](surface, color, closed, points, width)
    pts = [(surface.X(x), surface.Y(y)) for x, y in points]
    return _orig_draw["lines"](surface.display, color, closed, pts, max(1, _w(surface, width)))


def _circle(surface, color, center, radius, width=0):
    if not isinstance(surface, Canvas):
        return _orig_draw["circle"](surface, color, center, radius, width)
    return _orig_draw["circle"](surface.display, color, (surface.X(center[0]), surface.Y(center[1])),
                                max(1, int(round(radius * surface.S))), _w(surface, width))


def _ellipse(surface, color, rect, width=0):
    if not isinstance(surface, Canvas):
        return _orig_draw["ellipse"](surface, color, rect, width)
    return _orig_draw["ellipse"](surface.display, color, surface.rect(pygame.Rect(rect)), _w(surface, width))


pygame.draw.rect = _rect
pygame.draw.line = _line
pygame.draw.lines = _lines
pygame.draw.circle = _circle
pygame.draw.ellipse = _ellipse

# 마우스 좌표도 논리 좌표로 변환
_orig_get_pos = pygame.mouse.get_pos
pygame.mouse.get_pos = lambda: CANVAS.to_logical(_orig_get_pos())


# ---------------------------------------------------------------- 글꼴
class HiFont:
    """논리 크기(pt)로 지정하되 실제로는 배율만큼 큰 글꼴로 렌더링하는 글꼴 래퍼"""
    _fonts = {}

    def __init__(self, names, size, bold=False):
        self.names = names
        self.size_pt = size
        self.bold = bold

    def _real(self):
        px = max(6, int(round(self.size_pt * CANVAS.S)))
        key = (self.names, px, self.bold)
        font = HiFont._fonts.get(key)
        if font is None:
            font = pygame.font.SysFont(self.names, px, bold=self.bold)
            HiFont._fonts[key] = font
        return font

    def render(self, text, antialias=True, color=(255, 255, 255), background=None):
        rendered = self._real().render(text, True, color)
        surf = HiSurf(rendered.get_size(), pygame.SRCALPHA, CANVAS.S)
        surf.blit(rendered, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return surf

    def size(self, text):
        w, h = self._real().size(text)
        return (int(round(w / CANVAS.S)), int(round(h / CANVAS.S)))

    def get_height(self):
        return int(round(self._real().get_height() / CANVAS.S))
