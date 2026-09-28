"""
Block Royale 100 - 메인 화면 배경 (떠다니는 블록 애니메이션)
"""

from app_common import CANVAS, TETROMINOES, _mix, math, pygame, random


class NeonMenuBackground:
    """메뉴 공통 배경: 어두운 그라데이션 + 로고 스포트라이트 + 비네트, 그리고 천천히 떨어지는 블록(시차)"""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.renderer = None            # 앱이 UIRenderer 생성 후 연결 (블록 셀 재사용)
        piece_types = list(TETROMINOES.keys())
        self.floaters = []
        for i in range(34):
            far = i % 3 != 0            # 2/3는 멀리(작고 흐림), 1/3은 가까이(크고 선명)
            size = random.choice([9, 11, 13]) if far else random.choice([20, 24, 28])
            self.floaters.append({
                "piece": random.choice(piece_types),
                "rot": random.randint(0, 3),
                "x": random.uniform(0, width),
                "y": random.uniform(-100, height),
                "size": size,
                "vy": (14 + size * 0.9) * random.uniform(0.8, 1.2),
                "phase": random.uniform(0, 6.28),
                "alpha": 34 if far else 58,
            })

    def update(self, dt):
        for f in self.floaters:
            f["y"] += f["vy"] * dt
            f["phase"] += dt * 0.6
            if f["y"] > self.height + f["size"] * 4:
                f["y"] = -f["size"] * 4
                f["x"] = random.uniform(0, self.width)
                f["piece"] = random.choice(list(TETROMINOES.keys()))
                f["rot"] = random.randint(0, 3)

    # ---------------------------------------------------------- 정적 배경 (네이티브 해상도 1회 생성)
    def _build_static(self):
        S = CANVAS.S
        px = lambda v: int(round(v * S))
        W, H = self.width, self.height
        hi = CANVAS.make_surface(W, H, alpha=False)
        hw, hh = pygame.Surface.get_size(hi)

        # 1. 세로 그라데이션
        for y in range(hh):
            pygame.draw.line(hi, _mix((17, 20, 38), (7, 8, 15), y / hh), (0, y), (hw, y))

        # 2. 컬러 글로우 (작게 그린 뒤 부드럽게 확대)
        def glow(cx, cy, rad, color, strength):
            sr = max(6, rad // 5)
            small = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
            for r in range(sr, 0, -1):
                a = int(strength * (1 - r / sr) ** 1.7)
                pygame.draw.circle(small, (*color, a), (sr, sr), r)
            big = pygame.transform.smoothscale(small, (px(rad * 2), px(rad * 2)))
            hi.blit(big, (px(cx - rad), px(cy - rad)))
        glow(W * 0.5, 150, 560, (110, 80, 230), 60)        # 로고 스포트라이트
        glow(W * 0.16, 130, 430, (40, 120, 220), 44)
        glow(W * 0.88, 720, 470, (170, 60, 210), 46)
        glow(W * 0.5, 760, 520, (40, 90, 200), 30)

        # 3. 비네트 (가장자리를 어둡게)
        vw, vh = 96, 54
        vig = pygame.Surface((vw, vh), pygame.SRCALPHA)
        for yy in range(vh):
            for xx in range(vw):
                dx = (xx / (vw - 1) - 0.5) * 2
                dy = (yy / (vh - 1) - 0.5) * 2
                d = math.sqrt(dx * dx * 0.8 + dy * dy)
                vig.set_at((xx, yy), (0, 0, 8, int(max(0.0, min(1.0, (d - 0.55) / 0.85)) * 170)))
        hi.blit(pygame.transform.smoothscale(vig, (hw, hh)), (0, 0))
        return hi

    def draw(self, screen):
        if getattr(self, "_static_ver", None) != CANVAS.version:
            self._static = self._build_static()
            self._static_ver = CANVAS.version
        CANVAS.display.fill((0, 0, 0))
        screen.blit(self._static, (0, 0))

        r = self.renderer
        if r is None:
            return
        # 떨어지는 테트로미노 (셀은 네이티브 해상도 캐시를 재사용하므로 선명함)
        for f in self.floaters:
            size = f["size"]
            cell = r._cell_surface(f["piece"], size, alpha=f["alpha"])
            ox = f["x"] + math.sin(f["phase"]) * size * 0.6
            for bx, by in TETROMINOES[f["piece"]][f["rot"]]:
                screen.blit(cell, (int(ox + bx * size), int(f["y"] + by * size)))
