"""
SteamOS/Proton 대응 테스트: 시작 단계 기록(startup.log) / 창·오디오 시작 재시도.
실행: python tests/test_steamos.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame


def _fresh_trace(tmp):
    os.environ["BR_DATA_DIR"] = tmp
    import startup_trace
    startup_trace._state.update(path=None, t0=0.0, done=False)
    return startup_trace


def test_unfinished_launch_is_reported_next_time():
    tmp = tempfile.mkdtemp()
    st = _fresh_trace(tmp)
    st.begin()
    st.mark("pygame init")
    st.mark("window created")                                  # 여기서 프로세스가 사라졌다고 가정 (OK 없음)
    st._state.update(path=None, done=False)
    st.begin()                                                 # 다음 실행
    err = open(os.path.join(tmp, "error.log"), encoding="utf-8").read()
    assert "Previous launch did not finish starting up" in err and "window created" in err
    st.mark("pygame init")
    st.finish()
    log = open(os.path.join(tmp, "startup.log"), encoding="utf-8").read()
    assert log.strip().splitlines()[-1].endswith("OK")
    n = len(err)
    st._state.update(path=None, done=False)
    st.begin()                                                 # 성공으로 끝난 기록은 다시 알리지 않음
    assert len(open(os.path.join(tmp, "error.log"), encoding="utf-8").read()) == n


def test_trace_is_noop_before_begin_and_never_raises():
    tmp = tempfile.mkdtemp()
    st = _fresh_trace(tmp)
    st.mark("x")
    st.finish()
    assert not os.path.exists(os.path.join(tmp, "startup.log"))
    os.environ["BR_DATA_DIR"] = os.path.join(tmp, "없는", "폴더")      # 만들 수 없는 폴더여도 예외 없이
    st._state.update(path=None, done=False)
    st.begin()
    st.mark("y")
    st.finish()


def test_set_mode_retries_then_falls_back():
    from screens.core import CoreMixin
    calls = []
    real = pygame.display.set_mode

    def flaky(size, flags=0):
        calls.append((size, flags))
        if len(calls) < 3:
            raise pygame.error("display not ready")
        return real((320, 200))
    pygame.display.set_mode = flaky
    try:
        surf = CoreMixin._set_mode_retry((1366, 768), pygame.RESIZABLE, tries=3)
        assert surf is not None and len(calls) == 3
        calls.clear()

        def always_bad(size, flags=0):
            calls.append((size, flags))
            if size != (1366, 768) or flags != 0:
                raise pygame.error("nope")
            return real((320, 200))
        pygame.display.set_mode = always_bad
        surf = CoreMixin._set_mode_retry((1200, 700), pygame.RESIZABLE, fallback=((1366, 768), 0), tries=2)
        assert surf is not None and calls[-1] == ((1366, 768), 0)
        pygame.display.set_mode = lambda *a, **k: (_ for _ in ()).throw(pygame.error("dead"))
        try:
            CoreMixin._set_mode_retry((1, 1), 0, tries=1)
            assert False
        except pygame.error:
            pass
    finally:
        pygame.display.set_mode = real


def test_mixer_init_retries():
    import sound_fx
    pygame.mixer.quit()
    real = pygame.mixer.init
    tries = []

    def flaky(*a, **k):
        tries.append(1)
        if len(tries) < 3:
            raise pygame.error("audio device not ready")
        return real(*a, **k)
    pygame.mixer.init = flaky
    try:
        sm = sound_fx.SoundManager(enabled=True)
        assert len(tries) == 3 and sm.enabled, "세 번째 시도에서 성공하면 소리가 켜진 채로 시작"
    finally:
        pygame.mixer.init = real
    pygame.mixer.quit()
    pygame.mixer.init = lambda *a, **k: (_ for _ in ()).throw(pygame.error("no audio"))
    try:
        sm = sound_fx.SoundManager(enabled=True)
        assert not sm.enabled, "끝까지 안 되면 소리 없이 계속 (예전과 같음)"
    finally:
        pygame.mixer.init = real


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL STEAMOS TESTS PASSED]")
