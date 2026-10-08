"""
성능 최적화 동등성 테스트 (v1.1.12): 좌표 변환 인라인이 예전 계산과 같은 결과인지, LED 도트 캐시, 흔들림 중 카드 레이어 재사용,
소리 디스크 캐시의 저장/불러오기/무효화/손상 처리, numpy 지연 import.
실행: python test_perf.py
"""
import os
import sys
import random
import subprocess
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import pygame
from gfx import CANVAS


def test_rect_f_matches_reference_formula():
    def ref(c, x, y, w, h):
        left, top = c.X(x), c.Y(y)
        right, bottom = c.X(x + w), c.Y(y + h)
        rw, rh = right - left, bottom - top
        if w > 0 and rw < 1:
            rw = 1
        if h > 0 and rh < 1:
            rh = 1
        return pygame.Rect(left, top, rw, rh)
    rng = random.Random(1)
    bad = 0
    for size in ((1366, 768), (1000, 620), (1920, 1080), (640, 400)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        for _ in range(4000):
            x, y = rng.uniform(-50, 1400), rng.uniform(-50, 800)
            w, h = rng.choice([0, 0.3, 1, rng.uniform(0, 400)]), rng.choice([0, 0.3, 1, rng.uniform(0, 300)])
            if CANVAS.rect_f(x, y, w, h) != ref(CANVAS, x, y, w, h):
                bad += 1
            if CANVAS.rect(pygame.Rect(int(x), int(y), int(w), int(h))) != ref(CANVAS, int(x), int(y), int(w), int(h)):
                bad += 1
    assert bad == 0, bad
    # pygame.draw.rect 래퍼: 폭 0/테두리 둥글기 0 빠른 경로도 같은 그림
    surf = pygame.Surface((300, 200))
    for br in (0, 6):
        for width in (0, 2):
            pygame.display.set_mode((1366, 768))
            CANVAS.attach(pygame.display.get_surface())
            CANVAS.display.fill((0, 0, 0))
            pygame.draw.rect(CANVAS, (200, 100, 50), (10, 10, 120, 60), width, border_radius=br)
            a = pygame.image.tobytes(CANVAS.display, "RGB")
            CANVAS.display.fill((0, 0, 0))
            CANVAS._orig["rect"](CANVAS.display, (200, 100, 50), CANVAS.rect_f(10, 10, 120, 60), 0 if width == 0 else CANVAS.length(width, 1),
                                 border_radius=int(round(br * CANVAS.S)) if br else 0)
            assert a == pygame.image.tobytes(CANVAS.display, "RGB"), (br, width)
    print("  OK 좌표 변환 동등")


def _app():
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    return app


def test_led_dot_cache_matches_direct_geometry():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(5):
        app._tick_game(1 / 60)
    m.add_commentary("테스트 소식", (255, 200, 80), prio=1)
    for _ in range(10):
        app._tick_game(1 / 60)
    cache = app.renderer.__dict__["_led_dot_cache"]
    assert cache["rects"], "도트 위치가 캐시됨"
    for (cx, cy), (g, c) in list(cache["rects"].items())[:200]:
        assert g == CANVAS.rect((cx - 1, cy - 1, 4, 4)) and c == CANVAS.rect((cx, cy, 2, 2))
    old_ver = cache["ver"]
    pygame.display.set_mode((1000, 620))
    CANVAS.attach(pygame.display.get_surface())                 # 해상도가 바뀌면 캐시를 비움
    app._tick_game(1 / 60)
    assert app.renderer.__dict__["_led_dot_cache"]["ver"] != old_ver
    print("  OK LED 도트 캐시")


def test_shake_reuses_layers_and_stays_aligned():
    app = _app()
    app.start_game(mode="SOLO", total_players=40)
    m = app.match
    r = app.renderer
    m.countdown_until = 0.0
    for _ in range(90):
        app._tick_game(1 / 60)
    m.screen_shake = 0.0
    r.render(m)
    before = {k: id(v[2]) for k, v in r._card_layers.items()}
    mini_before = {k: id(v[1]) for k, v in r._mini_layers.items()}
    assert before and mini_before
    m.screen_shake = 9.0
    for _ in range(6):
        r.render(m)
    assert {k: id(v[2]) for k, v in r._card_layers.items()} == before, "흔들림 중에도 카드 레이어를 다시 만들지 않음"
    assert {k: id(v[1]) for k, v in r._mini_layers.items()} == mini_before, "흔들림 중에도 미니 셀 레이어를 다시 만들지 않음"
    m.screen_shake = 0.0
    r.render(m)
    assert not r._loose
    print("  OK 흔들림 캐시 재사용")


class _FakeSnd:
    def __init__(self, raw):
        self._raw = raw

    def get_raw(self):
        return self._raw


def _bare_manager(path):
    from sound_fx import SoundManager
    sm = object.__new__(SoundManager)
    sm.sounds, sm.bgm_stages, sm._bgm_bake = {}, {}, 0.6
    sm._cache_file = lambda: path
    return sm


def test_audio_cache_roundtrip_invalidation_and_corruption():
    import sound_fx
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    path = os.path.join(tempfile.mkdtemp(), "cache.bin")
    sm = _bare_manager(path)
    mk = lambda n: pygame.mixer.Sound(buffer=bytes([n % 256]) * 4000)
    sm.sounds = {"lock": mk(1), "clear_c3": mk(2)}
    sm.bgm_stages = {"menu": mk(3), "results": mk(4), 1: [mk(5), mk(6)], 2: [mk(7)]}
    sm._save_audio_cache()
    assert os.path.exists(path) and not os.path.exists(path + ".tmp")
    sm2 = _bare_manager(path)
    assert sm2._load_audio_cache()
    assert set(sm2.sounds) == {"lock", "clear_c3"} and sm2.sounds["clear_c3"].get_raw() == bytes([2]) * 4000
    assert not isinstance(sm2.bgm_stages["menu"], list) and sm2.bgm_stages["results"].get_raw() == bytes([4]) * 4000
    assert [s.get_raw()[0] for s in sm2.bgm_stages[1]] == [5, 6], "단계 1은 여러 곡 목록"
    assert isinstance(sm2.bgm_stages[2], list) and len(sm2.bgm_stages[2]) == 1, "곡이 하나여도 목록이면 목록으로 복원"
    sm3 = _bare_manager(path)
    sm3._bgm_bake = 0.5                                          # 합성 설정이 다르면 무효
    assert not sm3._load_audio_cache() and not sm3.sounds
    with open(path, "r+b") as f:                                 # 손상된 파일: 예외 없이 무시
        f.seek(100)
        f.write(b"\xff" * 50)
        f.truncate(2000)
    sm4 = _bare_manager(path)
    assert not sm4._load_audio_cache() and not sm4.sounds and not sm4.bgm_stages
    assert not _bare_manager(os.path.join(tempfile.mkdtemp(), "none.bin"))._load_audio_cache()
    print("  OK 소리 캐시")


def test_numpy_is_lazy_in_sound_module():
    code = "import sys, sound_fx; print('numpy' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, env=dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")).stdout.strip().splitlines()[-1]
    assert out == "False", "sound_fx를 import해도 numpy를 바로 불러오지 않음"
    import sound_fx
    assert sound_fx.np.zeros(3).shape == (3,), "처음 쓰는 순간 진짜 numpy로 동작"
    print("  OK numpy 지연 import")


def test_bot_drop_matches_collide_loop():
    import bot_brain as B
    import bot_reference as R
    from config import TETROMINOES
    rng = random.Random(4)
    shapes = [TETROMINOES[k][r] for k in TETROMINOES for r in range(4)]
    n = 0
    for _ in range(6000):
        rows = [0] * B.H
        for y in range(B.H - rng.randint(0, B.H - 1), B.H):
            rows[y] = rng.getrandbits(B.W)
        cells, px, py = rng.choice(shapes), rng.randint(-2, B.W), rng.randint(-3, 6)
        if R._collide(rows, cells, px, py):
            continue
        ref = py
        while not R._collide(rows, cells, px, ref + 1):
            ref += 1
        assert R._drop(rows, cells, px, py) == ref
        n += 1
    assert n > 1000
    print("  OK 봇 낙하 계산 동등")


if __name__ == "__main__":
    pygame.init()
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    keep = {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in (SETTINGS_FILE, STATS_FILE)}
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL PERF TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
