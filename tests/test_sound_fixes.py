"""
사운드 재생 버그 수정 확인 (SDL 더미 오디오: 실제로 소리가 나는지는 귀로 확인해야 하고, 여기서는 채널 상태/호출만 검사)
- ① 일시정지 중 같은 단계로 play_bgm(다시 시작)을 부르면 멈춘 채널을 재개함 (일시정지된 채널도 get_busy()가 True)
- ② 일시정지는 콤보 하이햇 층(채널 3)도 멈추고, 멈춘 동안 tick이 다시 켜지 않음
- ③ 새 판/메뉴 음악이 시작되면 이전 판의 팡파레(채널 4, 5)를 멈춤
- ④ 새 판/메뉴로 가면 이전 판 결과 화면에 예약된 효과음을 비움
실행: python tests/test_sound_fixes.py
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pygame


def _tone(seconds=2.0):
    t = np.linspace(0, 440 * 2 * np.pi * seconds, int(44100 * seconds))
    mono = (np.sin(t) * 6000).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack((mono, mono)))


class _Chan:
    """실제 채널을 감싸 pause/unpause 호출을 기록"""

    def __init__(self, real):
        self.real = real
        self.calls = []

    def pause(self):
        self.calls.append("pause")
        self.real.pause()

    def unpause(self):
        self.calls.append("unpause")
        self.real.unpause()

    def __getattr__(self, name):
        return getattr(self.real, name)


def _mgr():
    from sound_fx import SoundManager
    if not pygame.mixer.get_init():
        pygame.mixer.init(44100, -16, 2, 512)
    sm = SoundManager()
    snd = _tone()
    sm.bgm_stages = {1: snd, 2: snd, "menu": snd, "results": snd, "lobby": snd}
    sm.bgm_enabled = True
    sm.enabled = True
    sm._bgm_thread = None
    sm.sounds["combo_layer"] = snd
    return sm, snd


def test_restart_while_paused_resumes_the_music():
    sm, snd = _mgr()
    sm.bgm_ch_a, sm.bgm_ch_b = _Chan(sm.bgm_ch_a), _Chan(sm.bgm_ch_b)
    sm.play_bgm(1)
    active = sm.active_channel
    sm.pause_bgm()
    assert active.get_busy(), "전제: 일시정지된 채널도 busy로 보임"
    assert sm._bgm_paused
    sm.play_bgm(1)                                              # 일시정지 메뉴에서 '다시 시작' -> start_game이 부름
    assert "unpause" in active.calls, "멈춘 채널을 재개하지 않아 새 판이 무음"
    assert not sm._bgm_paused


def test_pause_also_stops_the_combo_layer_and_tick_does_not_restart_it():
    sm, snd = _mgr()
    sm.play_bgm(1)
    sm.set_combo_layer(2)
    for _ in range(40):
        sm.tick()
    ch3 = pygame.mixer.Channel(3)
    assert ch3.get_busy(), "전제: 콤보 층이 재생 중"
    sm.pause_bgm()
    vol_before = sm._layer_vol
    sm.set_combo_layer(0)                                        # 멈춘 동안 콤보가 끊겨도
    for _ in range(40):
        sm.tick()                                                # 일시정지 중에는 볼륨/재생 상태를 건드리지 않음
    assert sm._layer_vol == vol_before
    sm.unpause_bgm()
    for _ in range(80):
        sm.tick()
    assert not ch3.get_busy() or sm._layer_vol <= vol_before, "재개 뒤에는 콤보가 끊긴 상태로 정리됨"
    # 멈춘 동안 새로 켜지지 않음: 정지 상태에서 레이어를 켜고 tick해도 채널 3이 시작되지 않아야 함
    sm.stop_bgm()
    sm.play_bgm(1)
    sm.pause_bgm()
    sm.set_combo_layer(2)
    for _ in range(40):
        sm.tick()
    assert not pygame.mixer.Channel(3).get_busy(), "일시정지 중에 콤보 층이 혼자 울림"
    sm.unpause_bgm()
    sm.stop_bgm()


def test_new_music_stops_previous_fanfares():
    sm, snd = _mgr()
    for n in (4, 5):
        pygame.mixer.Channel(n).play(snd)
    assert pygame.mixer.Channel(4).get_busy() and pygame.mixer.Channel(5).get_busy()
    sm.play_bgm(1)
    assert not pygame.mixer.Channel(4).get_busy() and not pygame.mixer.Channel(5).get_busy(), "새 판 음악과 이전 팡파레가 겹침"
    pygame.mixer.Channel(5).play(snd)
    sm.play_bgm("menu")
    assert not pygame.mixer.Channel(5).get_busy(), "메뉴 음악과 팡파레가 겹침"
    pygame.mixer.Channel(5).play(snd)
    sm.play_bgm(2)                                               # 경기 중 단계 전환은 건드리지 않음
    assert pygame.mixer.Channel(5).get_busy()
    pygame.mixer.Channel(5).stop()
    sm.stop_bgm()


def test_scheduled_result_sounds_are_cleared_on_new_match_and_menu():
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    app.start_game(mode="SOLO", total_players=10)
    app._sound_due = [(time.time() + 1.5, "stamp"), (time.time() + 2.5, "levelup")]
    app.start_game(mode="SOLO", total_players=10)                # 재도전
    assert app._sound_due == [], "재도전했는데 이전 판 결과 효과음이 남음"
    app._sound_due = [(time.time() + 1.5, "stamp")]
    app.return_to_menu()
    assert app._sound_due == [], "메뉴로 갔는데 이전 판 결과 효과음이 남음"


def test_one_shot_sounds_do_not_wrap_their_tail_to_the_front():
    """np.roll은 곡 끝 소리를 오른쪽 채널 맨 앞으로 돌려 붙여 첫 순간에 틱이 났음: 지연 구간은 0이어야 함"""
    from sound_fx import SoundManager
    x = np.arange(1, 101, dtype=np.float32)
    d = SoundManager._delayed(x, 10)
    assert (d[:10] == 0).all() and (d[10:] == x[:-10]).all() and len(d) == len(x)
    sm = SoundManager.__new__(SoundManager)
    sm.sounds = {}
    snd = sm._generate_victory_anthem()
    arr = pygame.sndarray.array(snd).astype(np.float32)
    n = int(44100 * 0.018)
    left, right = arr[:n, 0], arr[:n, 1]
    assert np.allclose(right, 0.7 * left, atol=2.5), "승리 음악 오른쪽 채널 앞부분에 끝 소리가 섞임"


def test_background_stage_tracks_start_as_lists():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sound_fx.py"), encoding="utf-8").read()
    import re
    assert not re.search(r"bgm_stages\[[123]\] = self\._synth", src), "1~3단계 곡이 Sound 하나로 먼저 들어가면 읽는 쪽에서 타입이 바뀜"
    assert "'lobby', 1, 2, 3" in src


def test_key_effects_use_their_own_reserved_channels():
    sm, snd = _mgr()
    sm.announcer = True
    for n in (0, 1, 2):
        pygame.mixer.Channel(n).stop()
    sm.play("quad", combo=0)
    assert pygame.mixer.Channel(0).get_busy(), "줄 삭제 계열이 채널 0에서 재생되지 않음"
    sm.play("hit_2")
    assert pygame.mixer.Channel(1).get_busy(), "경보/피격이 채널 1에서 재생되지 않음"
    sm._vo_last = 0.0
    sm.play("vo_golden")
    assert pygame.mixer.Channel(2).get_busy(), "아나운서가 채널 2에서 재생되지 않음"
    pygame.mixer.Channel(0).stop()
    sm.play("move")                                              # 그 밖의 소리는 예약 채널을 쓰지 않음
    assert not pygame.mixer.Channel(0).get_busy()
    for n in (0, 1, 2):
        pygame.mixer.Channel(n).stop()


def test_lock3_is_part_of_the_pitched_variants():
    sm, snd = _mgr()
    assert "lock3_T" in sm.sounds and "lock3" in sm.sounds, "세 번째 착지 소리가 블록별 변형에 없음"


def test_pitch_variant_shortcut_matches_two_channel_interpolation():
    sm, snd = _mgr()
    mono = (np.sin(np.linspace(0, 200, 4000)) * 5000).astype(np.int16)
    sym = pygame.sndarray.make_sound(np.column_stack((mono, mono)))
    out = pygame.sndarray.array(sm._pitch_variant(sym, 3)).astype(np.int32)
    arr = pygame.sndarray.array(sym).astype(np.float32)
    f = 2.0 ** (3 / 12.0)
    n_out = max(2, int(len(arr) / f))
    xo = np.arange(len(arr), dtype=np.float32)
    xn = np.linspace(0, len(arr) - 1, n_out, dtype=np.float32)
    ref = np.column_stack([np.interp(xn, xo, arr[:, c]) for c in range(2)])
    ref = np.clip(ref, -32767, 32767).astype(np.int16).astype(np.int32)
    assert out.shape == ref.shape and (out == ref).all(), "좌우가 같은 소리의 피치 변형 결과가 달라짐"


def test_ending_stings_share_one_path():
    sm, snd = _mgr()
    sm.sounds["victory"] = snd
    sm.sounds["defeat"] = snd
    pygame.mixer.Channel(5).stop()
    sm.play_victory()
    assert pygame.mixer.Channel(5).get_busy() and not sm.is_bgm_playing
    pygame.mixer.Channel(5).stop()
    sm.sfx_enabled = False
    sm.play_defeat()                                              # 효과음이 꺼져 있으면 소리는 내지 않고 BGM만 정리
    assert not pygame.mixer.Channel(5).get_busy()
    sm.sfx_enabled = True


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
        print("[ALL SOUND FIX TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)
