"""
Block Royale 100 - 메인 화면 배경 (떠다니는 블록 애니메이션)
"""

from app_common import CANVAS, TETROMINOES, _mix, math, pygame, random
from ui_glow import FX_NORMAL, FX_FANCY, add_glow


class NeonMenuBackground:
    """메뉴 공통 배경: 어두운 그라데이션 + 로고 스포트라이트 + 비네트, 그리고 천천히 떨어지는 블록(시차)"""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.renderer = None            # 앱이 UIRenderer 생성 후 연결 (블록 셀 재사용)
        # 메인 화면의 빛 연출 (앱이 프레임마다 지정: set_fx). 기본은 꺼짐이라 다른 화면(설정/기록/로비)에서는 예전과 같음
        self.fx_mode = 0                # 0 최소 / 1 보통 / 2 화려하게
        self.motion = True              # 화면 흔들림 설정이 꺼져 있으면 시차/빛 띠 이동 없음
        self.flash_ok = True            # 번쩍임 설정이 꺼져 있으면 밝기 상한을 낮춤
        self.beat = None                # (박자 위상 0~1, 박자 번호) 또는 None
        self.mouse = None               # 논리 좌표 마우스 위치 (시차)
        self._streak = None             # 가끔 지나가는 빛 띠 {"t0", "y"}
        self._next_streak = 6.0
        self._clock = 0.0
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

    def set_fx(self, mode, motion, flash_ok, beat, mouse):
        self.fx_mode, self.motion, self.flash_ok, self.beat, self.mouse = mode, motion, flash_ok, beat, mouse

    def update(self, dt):
        self._clock += dt
        if self.fx_mode >= FX_NORMAL and self.motion:                      # 8~12초마다 지나가는 빛 띠는 보통 이상 (박자에 맞춘 밝기 변화와는 별개)
            if self._streak is None and self._clock >= self._next_streak:                # 8~12초마다 한 번, 줄이 '지워지듯' 지나가는 빛 띠 (0.9초)
                self._streak = {"t0": self._clock, "y": random.uniform(self.height * 0.35, self.height * 0.9)}
                self._next_streak = self._clock + random.uniform(8.0, 12.0)
        if self._streak is not None and self._clock - self._streak["t0"] > 0.9:
            self._streak = None
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
        fx = self.fx_mode
        beat_up = 0
        if fx >= FX_FANCY and self.beat is not None and self.motion:          # 음악에 맞춘 밝기 변화는 '화려하게'에서만
            beat_up = int(round(3 * (1.0 - self.beat[0]) ** 3))               # 박자 직후 3 -> 0 (박자 주파수 2Hz 안팎: 3Hz 미만)
            if not self.flash_ok:
                beat_up = min(beat_up, 1)
        if fx >= FX_NORMAL:                                                    # 로고 뒤 후광 (박자에 맞춰 숨 쉼, 화려하게는 더 큼)
            lv = min(4, 1 + beat_up) if self.flash_ok else 1
            wd, ht = (880, 330) if fx >= FX_FANCY else (700, 260)
            add_glow("orb", self.width / 2 - wd / 2, 150 - ht / 2, wd, ht, (110, 90, 230), lv)
        # 마우스에 따른 미세 시차 (가까운 블록일수록 많이 움직임)
        px = py = 0.0
        if fx >= FX_NORMAL and self.motion and self.mouse is not None:
            px = max(-1.0, min(1.0, (self.mouse[0] - self.width / 2) / (self.width / 2)))
            py = max(-1.0, min(1.0, (self.mouse[1] - self.height / 2) / (self.height / 2)))
        # 떨어지는 테트로미노 (셀은 네이티브 해상도 캐시를 재사용하므로 선명함)
        for f in self.floaters:
            size = f["size"]
            near = f["alpha"] > 40
            alpha = f["alpha"] + (beat_up * 8 if near else beat_up * 4)       # 박자에 맞춰 블록이 살짝 밝아짐 (캐시 키는 알파 단계 4개)
            cell = r._cell_surface(f["piece"], size, alpha=alpha, skin="classic")
            ox = f["x"] + math.sin(f["phase"]) * size * 0.6 - px * (16 if near else 6)
            oy = f["y"] - py * (10 if near else 4)
            for bx, by in TETROMINOES[f["piece"]][f["rot"]]:
                screen.blit(cell, (int(ox + bx * size), int(oy + by * size)))
        st = self._streak
        if st is not None:                                                     # 지나가는 빛 띠: 왼쪽에서 오른쪽으로 0.9초
            u = (self._clock - st["t0"]) / 0.9
            lv = max(0, min(2 if self.flash_ok else 1, int((1.0 - abs(u * 2 - 1)) * 2.99)))
            if lv > 0:
                add_glow("band", -300 + u * (self.width + 600), st["y"] - 24, 460, 48, (120, 200, 255), lv)
