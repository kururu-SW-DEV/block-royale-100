"""
Block Royale 100 - Authentic Cyberpunk & Synthwave Sound Engine
외부 음원 및 저작권 침해 우려가 일체 없는 100% 자체 작곡 절차적 사운드 엔진입니다.
- 레트로 사이버펑크 / 신스웨이브 / 네오 아케이드 스타일의 풍성하고 세련된 일렉트로닉 음악
  * Supersaw(아날로그 톱니파 디튠) + 펀치감 넘치는 808/909 드럼 (헤비 킥 & 스네어 & 16비트 하이햇)
  * 질주하는 16비트 롤링 신스 베이스라인 (Rolling Synthwave Bass)
  * 감성적이고 광활한 네온 패드 화음 (Lush Stereo Pads) & 영롱한 플럭 리드
- 게임 진행도에 따른 동적 트랙:
  * ('menu'): [오프닝] "Neon Skyline" (114 BPM, Am / C) - 감성적이고 몽환적인 사이버펑크 오프닝
  * ('lobby'): [방 만들기/참가 대기] "Standby Frequency" (96 BPM, Fm) - 느긋한 신스 패드
  * 1/2/3단계(생존자 100~51/50~21/20 이하): 설정에서 고를 수 있는 5가지 세트(또는 매 판 랜덤), 각 세트마다 3곡
    - 세트0(오리지널): Cyber Rush(128) -> Hyperdrive Override(142) -> Apex Protocol(156)
    - 세트1: Neon Circuit(124) -> Circuit Breaker(138) -> Overclock(152)
    - 세트2: Pulse Overdrive(130) -> Redline(144) -> Terminal Velocity(158)
    - 세트3: Chrome Requiem(120) -> Ghost Protocol(134) -> Blackout Surge(148)
    - 세트4: Vector Surge(132) -> Quantum Drift(146) -> Singularity(160)
  * ('results'): [순위표] "Afterglow" (96 BPM, G) - 차분하게 여운을 남기는 마무리 곡
- 듀얼 채널 1.8초 무간극 크로스페이더 완비
- 블록 파괴(Shatter & Pop) 및 크리스탈 타격 효과음 탑재
"""

import os
import time
import threading
import hashlib
import json
import pygame
import random


class _LazyNumpy:
    """numpy는 소리를 새로 합성할 때만 필요함: 디스크 캐시로 시작하면 import 비용(약 150ms)과 메모리를 쓰지 않음. 처음 쓰는 순간 진짜 numpy로 바뀜"""
    def __getattr__(self, name):
        import numpy
        globals()["np"] = numpy
        return getattr(numpy, name)


np = _LazyNumpy()

NOTE_INDEX = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

# 스테이지(1/2/3단계) 배경음 세트 목록: 세트마다 1/2/3단계 3곡이 한 벌. 설정에서 고르거나 "랜덤"으로 매 판 하나를 뽑음
STAGE_SET_NAMES = [
    "Cyber Rush (오리지널)",
    "Neon Circuit",
    "Pulse Overdrive",
    "Chrome Requiem",
    "Vector Surge",
]


def get_freq(n_str):
    """음 이름('G5', 'F#4' ...) -> 주파수(Hz). 'R'/빈 값은 쉼표(0)"""
    if not n_str or n_str == 'R':
        return 0.0
    n = NOTE_INDEX[n_str[:-1]] + (int(n_str[-1]) - 4) * 12 - 9
    return 440.0 * (2.0 ** (n / 12.0))


# 최종 순위표 곡 "Afterglow" (G 장조, 4/4, 16마디). 마디마다 코드 하나: G D Em Bm | C G Am D | C G D Em | C D G G
RESULTS_MELODY = [
    # A 섹션
    ('B4', 1.0), ('D5', 1.0), ('G5', 1.5), ('F#5', 0.5),
    ('F#5', 1.0), ('E5', 0.5), ('D5', 0.5), ('A4', 2.0),
    ('G4', 1.0), ('B4', 1.0), ('E5', 1.5), ('D5', 0.5),
    ('D5', 1.0), ('B4', 1.0), ('F#4', 1.0), ('B4', 1.0),
    ('E5', 1.0), ('G5', 1.0), ('C6', 1.5), ('B5', 0.5),
    ('D6', 1.0), ('B5', 1.0), ('G5', 1.0), ('D5', 1.0),
    ('C6', 1.0), ('A5', 0.5), ('E5', 0.5), ('A5', 1.0), ('C6', 1.0),
    ('B5', 1.0), ('A5', 1.0), ('F#5', 2.0),
    # B 섹션 (한 옥타브 가까이 올라가며 고조 -> 마지막 마디에서 풀림)
    ('G5', 1.5), ('E5', 0.5), ('G5', 1.0), ('C6', 1.0),
    ('B5', 1.0), ('D6', 1.5), ('B5', 0.5), ('G5', 1.0),
    ('A5', 1.0), ('F#5', 1.0), ('A5', 1.0), ('D6', 1.0),
    ('B5', 1.5), ('G5', 0.5), ('E5', 1.0), ('G5', 1.0),
    ('E6', 1.0), ('D6', 0.5), ('C6', 0.5), ('G5', 1.0), ('E5', 1.0),
    ('F#5', 1.0), ('A5', 1.0), ('D6', 1.0), ('F#6', 1.0),
    ('G6', 1.5), ('D6', 0.5), ('B5', 1.0), ('D6', 1.0),
    ('G5', 3.0), ('R', 1.0),
]
_RB = {  # 마디당 베이스 4박: 근음-근음-5도-근음
    'G': ['G2', 'G2', 'D3', 'G2'], 'D': ['D2', 'D2', 'A2', 'D2'], 'Em': ['E2', 'E2', 'B2', 'E2'],
    'Bm': ['B1', 'B1', 'F#2', 'B1'], 'C': ['C2', 'C2', 'G2', 'C2'], 'Am': ['A1', 'A1', 'E2', 'A1'],
}
_RC = {  # 코드 구성음(패드)
    'G': ['G3', 'B3', 'D4'], 'D': ['D3', 'F#3', 'A3'], 'Em': ['E3', 'G3', 'B3'],
    'Bm': ['B2', 'D3', 'F#3'], 'C': ['C3', 'E3', 'G3'], 'Am': ['A2', 'C3', 'E3'],
}
_RESULTS_BARS = ['G', 'D', 'Em', 'Bm', 'C', 'G', 'Am', 'D', 'C', 'G', 'D', 'Em', 'C', 'D', 'G', 'G']
RESULTS_BASS = [n for bar in _RESULTS_BARS for n in _RB[bar]]                 # 64개(1박당 1개)
RESULTS_CHORDS = [_RC[bar] for bar in _RESULTS_BARS for _ in range(2)]        # 32개(2박당 1개)


class SoundManager:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.sounds = {}
        self.bgm_stages = {}
        self.current_bgm_stage = None
        self.current_set_idx = 0       # 이번 판에 쓸 스테이지 배경음 세트 번호 (0~4, roll_stage_set으로 매 판 시작 시 결정)
        
        # 듀얼 채널 크로스페이더 (채널 6, 7 교차)
        self.bgm_ch_a = None
        self.bgm_ch_b = None
        self.active_channel = None
        self.bgm_volume = 0.60
        self._pending_bgm = None       # 합성 중이라 대기 중인 BGM 단계
        self._bgm_paused = False       # pause_bgm으로 멈춘 상태 (일시정지된 채널도 get_busy()가 True라 이 플래그로 따로 기억)
        self._results_due = None       # 순위표 곡을 시작할 시각(승/패 음악이 끝난 뒤)
        self._bgm_bake = 0.60          # BGM 합성 시 곡 자체에 반영하는 기준 음량 (재생 음량 설정과 무관하게 항상 동일)
        self._bgm_thread = None
        self.sfx_volume = 0.70
        self.warn_scale = 1.0         # 경고음(피격 경보/심장 박동/경고) 상대 음량 0~1
        self.announcer = False        # 로봇 아나운서 외침 (설정의 '아나운서 콜')
        self._vo_last = 0.0
        self._layer_level = 0         # 콤보 층 단계 (0 꺼짐 / 1 / 2)
        self._layer_vol = 0.0
        self._duck = 1.0              # 위기 때 BGM을 낮추는 배율 (1.0 = 그대로)
        self._duck_target = 1.0
        self.bgm_enabled = True
        self.sfx_enabled = True
        self.is_bgm_playing = False
        
        if not self.enabled:
            return
            
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                
            pygame.mixer.set_num_channels(24)          # 효과음이 몰려도 부족하지 않게
            pygame.mixer.set_reserved(8)               # 0~7번 채널은 BGM/승패 음악 전용 (일반 효과음이 가로채지 못함)
            self.bgm_ch_a = pygame.mixer.Channel(6)
            self.bgm_ch_b = pygame.mixer.Channel(7)
            self.active_channel = self.bgm_ch_a
            
            if not self._load_audio_cache():           # 두 번째 실행부터는 저장해 둔 소리를 바로 불러옴
                # BGM은 백그라운드에서 합성하고, 그동안 효과음을 만듦 -> 창이 더 빨리 뜸
                self._generate_everything()
        except Exception as e:
            print(f"[SoundManager] Audio initialization failed: {e}. Audio disabled.")
            self.enabled = False

    # ---- 합성한 소리의 디스크 캐시 (두 번째 실행부터 합성 약 0.4초 + BGM 3.5~10초와 그동안의 프레임 끊김을 없앰)
    def _cache_file(self):
        try:
            from app_paths import data_path
            return data_path("sound_cache.bin")
        except Exception:
            return None

    def _cache_key(self):
        """소리를 만드는 코드(sound_fx.py)와 믹서 설정이 같을 때만 캐시를 씀. 코드를 고치면 자동으로 새로 합성"""
        try:
            with open(os.path.abspath(__file__), "rb") as f:
                src = f.read()
        except OSError:
            src = b""
        try:
            from config import APP_VERSION                    # exe로 묶이면 소스 파일을 읽을 수 없으므로 버전도 키에 넣음 (업데이트하면 소리를 새로 합성)
        except Exception:
            APP_VERSION = ""
        return hashlib.sha1(src + repr(pygame.mixer.get_init()).encode() + repr(self._bgm_bake).encode() + str(APP_VERSION).encode()).hexdigest()

    @staticmethod
    def _raw(snd):
        return snd.get_raw() if hasattr(snd, "get_raw") else None

    def _load_audio_cache(self):
        """캐시가 유효하면 효과음/BGM을 모두 채우고 True. 형식: [4바이트 헤더 길이][JSON 헤더][소리 원본 바이트들] (pickle을 쓰지 않아 파일이 바뀌어도 코드가 실행되지 않음)"""
        path = self._cache_file()
        if not path or not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                hlen = int.from_bytes(f.read(4), "little")
                head = json.loads(f.read(hlen).decode("utf-8"))
                if head.get("key") != self._cache_key() or not head.get("bgm_done"):
                    return False
                snd, bgm = {}, {}
                for kind, name, idx, n in head["items"]:
                    obj = pygame.mixer.Sound(buffer=f.read(n))
                    if kind == "s":
                        snd[name] = obj
                    else:
                        bgm.setdefault(name, []).append(obj)
            for k in list(bgm):
                if not head["bgm_lists"].get(str(k)):
                    bgm[k] = bgm[k][0]                      # 곡이 하나뿐인 단계(menu/results)는 리스트가 아니라 Sound 하나
            self.sounds.update(snd)
            self.bgm_stages.update(bgm)
            return True
        except Exception as e:
            print(f"[SoundManager] Sound cache ignored: {e}")
            self.sounds.clear()
            self.bgm_stages.clear()
            return False

    def _save_audio_cache(self):
        """합성이 모두 끝난 뒤 한 번 저장 (임시 파일에 쓰고 교체: 저장 도중 종료돼도 원본이 깨지지 않음)"""
        path = self._cache_file()
        if not path:
            return
        try:
            items, blobs, lists = [], [], {}
            for k, v in list(self.sounds.items()):
                raw = self._raw(v)
                items.append(["s", k, 0, len(raw)])
                blobs.append(raw)
            for k, v in list(self.bgm_stages.items()):
                seq = v if isinstance(v, list) else [v]
                lists[str(k)] = isinstance(v, list)
                for n, x in enumerate(seq):
                    raw = self._raw(x)
                    items.append(["b", k, n, len(raw)])
                    blobs.append(raw)
            head = json.dumps({"key": self._cache_key(), "bgm_done": True, "items": items, "bgm_lists": lists}).encode("utf-8")
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(len(head).to_bytes(4, "little"))
                f.write(head)
                for b in blobs:
                    f.write(b)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[SoundManager] Sound cache not saved: {e}")

    def _generate_everything(self):
        """캐시가 없을 때: BGM은 백그라운드로, 효과음은 바로 합성하고 끝나면 캐시에 저장"""
        self._bgm_thread = threading.Thread(target=self._bgm_then_save, daemon=True)
        self._bgm_thread.start()
        self._generate_all_arcade_sounds()
        self._generate_pitched_variants()
        self._wait_bgm('menu')                     # 타이틀 화면 음악만 준비되면 시작, 나머지 곡은 뒤에서 계속 생성

    def _bgm_then_save(self):
        self._generate_all_bgm_stages()
        th = self._sfx_ready_wait()
        if th and all(k in self.bgm_stages for k in ('menu', 'results', 'lobby', 1, 2, 3)) and isinstance(self.bgm_stages.get(1), list) and len(self.bgm_stages[1]) >= 5:
            self._save_audio_cache()

    def _sfx_ready_wait(self):
        """효과음 합성이 끝날 때까지 잠깐 기다림 (BGM 스레드가 먼저 끝났을 때 캐시에 효과음이 빠지지 않게)"""
        for _ in range(200):
            if 'combo_layer' in self.sounds and 'clear_c0' in self.sounds and 'vo_golden' in self.sounds:
                return True
            time.sleep(0.05)
        return False

    def _wait_bgm(self, stage, timeout=6.0):
        """해당 BGM이 백그라운드 합성으로 준비될 때까지 잠깐 대기 (이미 준비됐으면 즉시 반환)"""
        t0 = time.time()
        while stage not in self.bgm_stages and time.time() - t0 < timeout:
            th = self._bgm_thread
            if th is None or not th.is_alive():
                break
            time.sleep(0.01)

    def tick(self):
        """매 프레임 호출: 합성이 끝나 대기 중이던 BGM이 있으면 시작 (블로킹 없음)"""
        stage = self._pending_bgm
        if stage is not None and stage in self.bgm_stages:
            self.play_bgm(stage)
        if self.enabled:
            self._tick_layer()
        if self._duck != self._duck_target:                       # 위기 덕킹: 한 프레임에 조금씩 목표 음량으로
            step = 0.045 if self._duck_target < self._duck else 0.03
            self._duck = max(self._duck_target, self._duck - step) if self._duck_target < self._duck else min(self._duck_target, self._duck + step)
            self._apply_bgm_volume()

    def set_announcer(self, on):
        self.announcer = bool(on)

    def set_combo_layer(self, level):
        """콤보/B2B 층 단계(0~2): 올라가면 하이햇 층이 부드럽게 커지고, 콤보가 끊기면 꺼짐"""
        self._layer_level = max(0, min(2, int(level)))

    def _tick_layer(self):
        if self._bgm_paused:
            return                                              # 일시정지 중에는 콤보 층을 다시 켜거나 볼륨을 바꾸지 않음
        target = (0.0, 0.10, 0.17)[self._layer_level] * (self.bgm_volume / 0.6) if (self.enabled and self.bgm_enabled) else 0.0
        if abs(self._layer_vol - target) < 1e-4 and not (target > 0 and not self._layer_busy()):
            return
        step = 0.012 if target > self._layer_vol else 0.02
        self._layer_vol = min(target, self._layer_vol + step) if target > self._layer_vol else max(target, self._layer_vol - step)
        try:
            ch = pygame.mixer.Channel(3)
            snd = self.sounds.get('combo_layer')
            if self._layer_vol > 0.001 and snd is not None:
                if not ch.get_busy():
                    ch.play(snd, loops=-1)
                ch.set_volume(self._layer_vol)
            elif ch.get_busy():
                ch.stop()
        except Exception:
            pass

    def _layer_busy(self):
        try:
            return pygame.mixer.Channel(3).get_busy()
        except Exception:
            return True

    def _bgm_eff_volume(self):
        return self.bgm_volume * self._duck if (self.enabled and self.bgm_enabled) else 0.0

    def _apply_bgm_volume(self):
        if self.active_channel:
            try:
                self.active_channel.set_volume(self._bgm_eff_volume())
            except Exception:
                pass

    def set_duck(self, factor):
        """BGM을 factor배(0.3~1.0)로 낮추거나 되돌림 (위기에 들어가면 낮추고 탈출/종료 때 1.0). 음량은 tick()에서 부드럽게 바뀜"""
        self._duck_target = max(0.3, min(1.0, float(factor)))

    def reset_duck(self):
        self._duck = self._duck_target = 1.0

    def _pack_stereo(self, left_arr, right_arr):
        """좌우 채널 배열을 16비트 스테레오 pygame Sound로 패킹"""
        mx = max(np.max(np.abs(left_arr)), np.max(np.abs(right_arr)), 1e-4)
        if mx > 0.98:
            left_arr = (left_arr / mx) * 0.96
            right_arr = (right_arr / mx) * 0.96
        pcm_l = (np.clip(left_arr, -0.98, 0.98) * 32767).astype(np.int16)
        pcm_r = (np.clip(right_arr, -0.98, 0.98) * 32767).astype(np.int16)
        stereo = np.column_stack((pcm_l, pcm_r)).tobytes()
        return pygame.mixer.Sound(buffer=stereo)

    def _pack_sound(self, mono_arr):
        """넘파이 모노 배열을 16비트 스테레오 pygame Sound로 패킹"""
        clipped = np.clip(mono_arr, -0.98, 0.98)
        pcm = (clipped * 32767).astype(np.int16)
        stereo = np.column_stack((pcm, pcm)).tobytes()
        return pygame.mixer.Sound(buffer=stereo)

    def _generate_all_arcade_sounds(self):
        """블록 터질 때 속 시원한 아케이드 폭발 및 크리스탈 타격 효과음 생성"""
        sr = 44100
        
        # 1. Move: 경쾌하고 깔끔한 틱 (35ms)
        t1 = np.arange(int(sr * 0.035)) / sr
        click = np.sin(2 * np.pi * 540 * t1) * np.exp(-t1 * 160.0) * 0.38
        self.sounds['move'] = self._pack_sound(click)
        
        # 2. Rotate: 경쾌한 회전 상승 차임 (45ms)
        t2 = np.arange(int(sr * 0.045)) / sr
        f2 = 340.0 + (t2 / 0.045) * 360.0
        p2 = 2 * np.pi * np.cumsum(f2) / sr
        rot = (np.sin(p2) + 0.3 * np.sin(2 * p2)) * np.exp(-t2 * 70.0) * 0.45
        self.sounds['rotate'] = self._pack_sound(rot)

        # 2b. 스핀 성립: T 블록이 T-스핀 자세로 회전했을 때 (회전음 대신) 맑은 두 음 (90ms)
        t2b = np.arange(int(sr * 0.09)) / sr
        t2c = np.clip(t2b - 0.035, 0, None)
        spin = (np.sin(2 * np.pi * 1318.5 * t2b) * np.exp(-t2b * 34.0) + 0.8 * np.sin(2 * np.pi * 1760.0 * t2c) * (t2b >= 0.035) * np.exp(-t2c * 34.0)) * 0.34
        self.sounds['spin_ready'] = self._pack_sound(spin)
        
        # 3. Hard Drop: 짧고 단단한 임팩트 쿵 (85ms)
        t3 = np.arange(int(sr * 0.085)) / sr
        f3_sweep = 150.0 * np.exp(-t3 * 35.0) + 50.0
        thud = np.sin(2 * np.pi * np.cumsum(f3_sweep) / sr) * np.exp(-t3 * 26.0) * 0.70
        click3 = (np.random.rand(len(t3)) * 2 - 1) * np.exp(-t3 * 90.0) * 0.35
        self.sounds['drop'] = self._pack_sound(thud + click3)
        
        # 4. Hold: 산뜻한 아케이드 차임
        t4 = np.arange(int(sr * 0.12)) / sr
        h1 = np.sin(2 * np.pi * 440.0 * t4) * np.exp(-t4 * 18.0) * 0.4
        h2 = np.sin(2 * np.pi * 659.25 * t4) * np.exp(-t4 * 14.0) * 0.4
        self.sounds['hold'] = self._pack_sound(h1 + h2)
        
        # 4-1. Lock: 블록이 바닥에 확정되는 소리 - 단단한 "탁" (3가지 변형을 돌려가며 재생해 단조로움 방지)
        t_l = np.arange(int(sr * 0.095)) / sr
        for name, f_base in (('lock', 175.0), ('lock2', 205.0), ('lock3', 238.0)):
            f_l = f_base * np.exp(-t_l * 30.0) + 95.0
            body = np.sin(2 * np.pi * np.cumsum(f_l) / sr) * np.exp(-t_l * 36.0) * 0.60
            tick = np.sin(2 * np.pi * 1900.0 * t_l) * np.exp(-t_l * 260.0) * 0.20
            grit = (np.random.rand(len(t_l)) * 2 - 1) * np.exp(-t_l * 210.0) * 0.20
            self.sounds[name] = self._pack_sound(body + tick + grit)

        # 4-2. Land: 조작 중인 블록이 바닥/더미에 처음 닿는 아주 작은 틱
        t_ld = np.arange(int(sr * 0.045)) / sr
        land = np.sin(2 * np.pi * (620.0 - 2500.0 * t_ld) * t_ld) * np.exp(-t_ld * 95.0) * 0.30
        self.sounds['land'] = self._pack_sound(land)

        # 4-3. Rise: 쓰레기 줄이 아래에서 밀고 올라오는 둔탁한 진동
        t_r = np.arange(int(sr * 0.26)) / sr
        noise_r = np.convolve((np.random.rand(len(t_r)) * 2 - 1), np.ones(40) / 40.0, mode='same')
        rumble = np.sin(2 * np.pi * (85.0 - 45.0 * t_r) * t_r) * np.exp(-t_r * 9.0) * 0.55
        rise = rumble + noise_r * np.exp(-t_r * 12.0) * 1.6
        self.sounds['rise'] = self._pack_sound(rise)

        # 5. Line Clear: ★ 블록 터지는 소리 (크런치 폭발 + 크리스탈 챠랑 팝!)
        t5 = np.arange(int(sr * 0.32)) / sr
        crunch = (np.random.rand(len(t5)) * 2 - 1) * np.exp(-t5 * 38.0) * 0.65
        f5_sweep = 850.0 * np.exp(-t5 * 24.0) + 140.0
        sweep5 = np.sin(2 * np.pi * np.cumsum(f5_sweep) / sr) * np.exp(-t5 * 18.0) * 0.60
        c1 = np.sin(2 * np.pi * 659.25 * t5) * np.exp(-t5 * 9.0) * 0.45
        c2 = np.sin(2 * np.pi * 830.61 * t5) * np.exp(-t5 * 11.0) * 0.40
        c3 = np.sin(2 * np.pi * 1046.50 * t5) * np.exp(-t5 * 13.0) * 0.35
        c4 = np.sin(2 * np.pi * 1318.51 * t5) * np.exp(-t5 * 15.0) * 0.30
        clear_mono = crunch + sweep5 + c1 + c2 + c3 + c4
        c_left = clear_mono.copy()
        c_right = self._delayed(clear_mono, int(sr * 0.012))
        self.sounds['clear'] = self._pack_stereo(c_left, c_right)
        
        # 6. 쿼드 (4줄 클리어): ★ 초대형 폭발 콰광---!! + 축제 팡파레 챠라랑!!
        t6 = np.arange(int(sr * 0.75)) / sr
        f6_sub = 65.0 * np.exp(-t6 * 6.0) + 30.0
        sub_boom = np.sin(2 * np.pi * np.cumsum(f6_sub) / sr) * np.exp(-t6 * 4.0) * 0.85
        big_crunch = (np.random.rand(len(t6)) * 2 - 1) * np.exp(-t6 * 14.0) * 0.70
        arp = np.zeros(len(t6), dtype=np.float32)
        step_s = int(sr * 0.07)
        arp_notes = [523.25, 659.25, 783.99, 1046.50]
        for idx, freq in enumerate(arp_notes):
            st = idx * step_s
            dur = len(t6) - st
            if dur > 0:
                t_sub = np.arange(dur) / sr
                tone = (np.sin(2*np.pi*freq*t_sub) + 0.4*np.sin(4*np.pi*freq*t_sub)) * np.exp(-t_sub * 8.0) * 0.50
                arp[st:] += tone
        splash = (np.random.rand(len(t6)) * 2 - 1) * np.exp(-t6 * 4.5) * 0.35
        quad_mono = sub_boom + big_crunch + arp + splash
        t_left = quad_mono.copy()
        t_right = self._delayed(quad_mono, int(sr * 0.015))
        self.sounds['quad'] = self._pack_stereo(t_left, t_right)
        
        # 7. Attack Sent: 활기찬 레이저 빔 타격음
        t7 = np.arange(int(sr * 0.22)) / sr
        f7 = 950.0 * np.exp(-t7 * 20.0) + 200.0
        laser = np.sin(2 * np.pi * np.cumsum(f7) / sr) * np.exp(-t7 * 12.0) * 0.65
        thump7 = (np.random.rand(len(t7)) * 2 - 1) * np.exp(-t7 * 40.0) * 0.40
        self.sounds['attack'] = self._pack_sound(laser + thump7)
        
        # 8. Garbage Incoming: 긴박한 비프 알람
        t8 = np.arange(int(sr * 0.35)) / sr
        beep1 = np.sin(2 * np.pi * 880.0 * t8) * np.exp(-t8 * 14.0) * (t8 < 0.12)
        beep2 = np.sin(2 * np.pi * 1174.66 * (t8 - 0.15)) * np.exp(-(t8 - 0.15) * 14.0) * (t8 >= 0.15)
        self.sounds['warning'] = self._pack_sound((beep1 + beep2) * 0.65)
        
        # 8-0. 피격 경고음 3단계 (받은 공격 줄 수에 따라): 가볍게 1번 -> 다급한 2번 -> 사이렌+묵직한 충격
        def _hit_alarm(beeps, freq_a, freq_b, thud_amp, noise_amp, length):
            th = np.arange(int(sr * length)) / sr
            out = np.zeros_like(th)
            for i in range(beeps):
                t0 = i * 0.13
                tt = np.clip(th - t0, 0.0, None)
                f = freq_a + (freq_b - freq_a) * np.clip(tt / 0.11, 0.0, 1.0)            # 음이 살짝 올라가는 경고 톤
                out += np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 16.0) * (th >= t0) * (tt < 0.12) * 0.55
            out += np.sin(2 * np.pi * (60.0 + 70.0 * np.exp(-th * 25.0)) * th) * np.exp(-th * 14.0) * thud_amp    # 묵직한 충격
            out += (np.random.rand(len(th)) * 2 - 1) * np.exp(-th * 45.0) * noise_amp
            return out
        self.sounds['hit_1'] = self._pack_sound(_hit_alarm(1, 620.0, 700.0, 0.55, 0.10, 0.30))
        self.sounds['hit_2'] = self._pack_sound(_hit_alarm(2, 700.0, 880.0, 0.75, 0.16, 0.42))
        self.sounds['hit_3'] = self._pack_sound(_hit_alarm(3, 780.0, 1100.0, 1.00, 0.25, 0.55))

        # 8-1. Heartbeat: 스택이 위험하게 높을 때 반복 재생되는 낮은 박동음 ("쿵-쿵")
        t_h = np.arange(int(sr * 0.5)) / sr
        def _thump(t0, amp):
            tt = np.clip(t_h - t0, 0.0, None)
            return np.sin(2 * np.pi * (48.0 + 40.0 * np.exp(-tt * 30.0)) * tt) * np.exp(-tt * 16.0) * (t_h >= t0) * amp
        self.sounds['heartbeat'] = self._pack_sound(_thump(0.0, 0.9) + _thump(0.17, 0.6))

        # 9. KO (적 격파): 시원한 파쇄 임팩트 + 승리 타격
        t9 = np.arange(int(sr * 0.45)) / sr
        ko_thud = np.sin(2 * np.pi * 70.0 * np.exp(-t9 * 4.0) * t9) * np.exp(-t9 * 6.0) * 0.8
        ko_bell = np.sin(2 * np.pi * 880.0 * t9) * np.exp(-t9 * 8.0) * 0.5
        self.sounds['ko'] = self._pack_sound(ko_thud + ko_bell)
        
        # 10. Game Over: 아련한 종결 아르페지오
        t10 = np.arange(int(sr * 0.8)) / sr
        go_tone = (np.sin(2*np.pi*220.0*t10) + 0.5*np.sin(2*np.pi*330.0*t10)) * np.exp(-t10 * 2.0) * 0.6
        self.sounds['gameover'] = self._pack_sound(go_tone)
        
        # 11. Victory: 화려하고 웅장한 7.3초 챔피언 빅토리 팡파레 & 찬가
        self.sounds['victory'] = self._generate_victory_anthem(sr)
        self.sounds['defeat'] = self._generate_defeat_jingle(sr)
        self.sounds['perfect'] = self._generate_perfect_chime(sr)

        # 12. T-Spin: 미래지향적 사이버 테크 회전음
        t12 = np.arange(int(sr * 0.14)) / sr
        f12 = 440.0 + (t12 / 0.14) * 580.0 + 80.0 * np.sin(2 * np.pi * 35.0 * t12)
        p12 = 2 * np.pi * np.cumsum(f12) / sr
        w12 = (np.sin(p12) + 0.35 * np.sin(2 * p12)) * np.exp(-t12 * 10.0) * 0.55
        self.sounds['tspin'] = self._pack_sound(w12)

        # 13. Badge Up: 배지 승급 환희의 4음 팡파레 차임 (C5 -> E5 -> G5 -> C6)
        t13 = np.arange(int(sr * 0.45)) / sr
        b_wave = np.zeros(len(t13), dtype=np.float32)
        b_notes = [523.25, 659.25, 783.99, 1046.50]
        step13 = int(sr * 0.075)
        for idx, freq in enumerate(b_notes):
            st = idx * step13
            rem = len(t13) - st
            if rem > 0:
                t_sub = np.arange(rem) / sr
                tone = (np.sin(2 * np.pi * freq * t_sub) + 0.4 * np.sin(4 * np.pi * freq * t_sub)) * np.exp(-t_sub * 8.5)
                b_wave[st:] += tone * 0.45
        self.sounds['badge_up'] = self._pack_sound(b_wave)
        self._generate_juice_sounds(sr)
        self._generate_arcade_audio(sr)


    def _generate_juice_sounds(self, sr=44100):
        """도파민 연출용 효과음 (v1.1.6): 카운트다운/GO, 방어, 위기 탈출, 트리플 저음, T-스핀 대형, B2B 층층음, 페이즈/결승/TOP N 스팅, K.O. 구슬 도착, 콤보 끊김, 레벨 업, 복수, 도장"""
        def pack(arr):                                   # 최대 진폭을 0.9 이하로 (여러 소리를 더한 것이 클리핑돼 찢어지지 않게, 키우지는 않음)
            peak = float(np.max(np.abs(arr))) if len(arr) else 0.0
            return self._pack_sound(arr * min(1.0, 0.9 / peak) if peak > 1e-4 else arr)

        def T(sec):
            return np.arange(int(sr * sec)) / sr

        def bell(freq, t, decay, amp=0.5, t0=0.0):
            tt = np.clip(t - t0, 0.0, None)
            return (np.sin(2 * np.pi * freq * tt) + 0.35 * np.sin(4 * np.pi * freq * tt) + 0.15 * np.sin(6 * np.pi * freq * tt)) * np.exp(-tt * decay) * (t >= t0) * amp

        def boom(t, f0=70.0, decay=9.0, amp=0.7, t0=0.0):
            tt = np.clip(t - t0, 0.0, None)
            return np.sin(2 * np.pi * (f0 + 90.0 * np.exp(-tt * 28.0)) * tt) * np.exp(-tt * decay) * (t >= t0) * amp

        # 카운트다운 3/2/1: 짧은 비프, GO: 밝은 화음
        t = T(0.14)
        self.sounds['count'] = pack(np.sin(2 * np.pi * 440.0 * t) * np.exp(-t * 22.0) * 0.55 + np.sin(2 * np.pi * 880.0 * t) * np.exp(-t * 30.0) * 0.18)
        t = T(0.5)
        go = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 7.0) for f in (659.25, 830.61, 987.77, 1318.51)) * 0.2
        self.sounds['go'] = pack(go + boom(t, 90.0, 12.0, 0.35))

        # 방어(막은 줄): 금속성 방패 소리
        t = T(0.2)
        ping = np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 26.0) * 0.45 + np.sin(2 * np.pi * 2100 * t) * np.exp(-t * 34.0) * 0.28 + np.sin(2 * np.pi * 3150 * t) * np.exp(-t * 48.0) * 0.12
        self.sounds['shield'] = pack(ping + (np.random.rand(len(t)) * 2 - 1) * np.exp(-t * 95.0) * 0.22)

        # 위기 탈출: 조여 있던 것이 풀리는 상승 스윕 + 종소리
        t = T(0.8)
        sweep_f = 180.0 * np.exp(t * 2.3) * (t < 0.38) + 180.0 * np.exp(0.38 * 2.3) * (t >= 0.38)
        sweep = np.sin(2 * np.pi * np.cumsum(sweep_f) / sr) * np.exp(-t * 3.0) * (t < 0.5) * 0.45
        self.sounds['clutch'] = pack(sweep + bell(1046.5, t, 6.0, 0.5, 0.36) + bell(1568.0, t, 7.0, 0.3, 0.42) + boom(t, 60.0, 8.0, 0.5, 0.34))

        # 트리플 저음 / T-스핀 더블·트리플 대형음
        t = T(0.34)
        self.sounds['thump_s'] = pack(boom(t, 52.0, 10.0, 0.8))
        t = T(0.55)
        f = 440.0 + np.clip(t / 0.14, 0.0, 1.0) * 580.0
        spin = (np.sin(2 * np.pi * np.cumsum(f) / sr) + 0.35 * np.sin(4 * np.pi * np.cumsum(f) / sr)) * np.exp(-t * 7.0) * 0.4
        self.sounds['tspin_big'] = pack(spin + boom(t, 58.0, 8.0, 0.7) + bell(1318.5, t, 8.0, 0.3, 0.12) + bell(1760.0, t, 9.0, 0.22, 0.2))

        # B2B 층층음: 연속(1~5)일수록 높고 화려해지는 반짝임
        for i in range(1, 6):
            t = T(0.5)
            base = 880.0 * (2.0 ** (self.COMBO_LADDER[min(i, len(self.COMBO_LADDER) - 1)] / 12.0))
            shimmer = (np.sin(2 * np.pi * base * t) + 0.6 * np.sin(2 * np.pi * base * 1.5 * t + 3.0 * np.sin(2 * np.pi * 7.0 * t))) * np.exp(-t * 7.0) * 0.28
            self.sounds[f"b2b_{i}"] = pack(shimmer + bell(base * 2.0, t, 11.0, 0.14, 0.08))

        # 페이즈 전환 스팅 / 결승 스팅 / TOP N 상승음 / 복수
        t = T(0.9)
        notes = [(220.0, 0.0), (277.18, 0.18), (329.63, 0.36), (440.0, 0.54)]
        brass = sum((np.sin(2 * np.pi * f * np.clip(t - t0, 0, None)) + 0.5 * np.sin(4 * np.pi * f * np.clip(t - t0, 0, None)) + 0.25 * np.sin(6 * np.pi * f * np.clip(t - t0, 0, None))) * np.exp(-np.clip(t - t0, 0, None) * 4.5) * (t >= t0) for f, t0 in notes) * 0.22
        self.sounds['phase_up'] = pack(brass + boom(t, 55.0, 5.0, 0.55) + boom(t, 55.0, 5.0, 0.4, 0.36))
        t = T(1.1)
        pulse = boom(t, 48.0, 6.0, 0.8) + boom(t, 48.0, 6.0, 0.7, 0.28)
        self.sounds['final'] = pack(pulse + bell(880.0, t, 3.2, 0.32, 0.56) + bell(1318.5, t, 3.6, 0.22, 0.62) + bell(1760.0, t, 4.2, 0.14, 0.7))
        t = T(0.34)
        self.sounds['top_up'] = pack(bell(783.99, t, 10.0, 0.4, 0.0) + bell(987.77, t, 10.0, 0.4, 0.07) + bell(1174.66, t, 9.0, 0.45, 0.14) + bell(1567.98, t, 12.0, 0.2, 0.18))
        t = T(0.9)
        rev_f = 120.0 * np.exp(t * 3.0) * (t < 0.4) + 120.0 * np.exp(1.2) * (t >= 0.4)
        self.sounds['revenge'] = pack(np.sin(2 * np.pi * np.cumsum(rev_f) / sr) * np.exp(-t * 3.0) * (t < 0.5) * 0.4 + boom(t, 62.0, 6.0, 0.85, 0.0) + bell(1174.66, t, 4.5, 0.4, 0.4) + bell(1567.98, t, 5.0, 0.3, 0.46))

        # K.O. 구슬 도착(처치 수가 늘수록 높은 음) / 콤보 끊김 / 레벨 업 / 결과 도장
        for i in range(1, 9):
            t = T(0.32)
            f = 523.25 * (2.0 ** (self.COMBO_LADDER[min(i, len(self.COMBO_LADDER) - 1)] / 12.0))
            self.sounds[f"ko_orb_{i}"] = pack(bell(f, t, 9.0, 0.42) + bell(f * 2.0, t, 13.0, 0.16))
        t = T(0.34)
        self.sounds['combo_break'] = pack(bell(329.63, t, 11.0, 0.3) + bell(261.63, t, 9.0, 0.3, 0.1))
        t = T(1.3)
        lv = sum(bell(f, t, 4.0, 0.3, t0) for f, t0 in ((523.25, 0.0), (659.25, 0.1), (783.99, 0.2), (1046.5, 0.3), (1318.5, 0.42), (1568.0, 0.55)))
        self.sounds['levelup'] = pack(lv + boom(t, 70.0, 7.0, 0.4, 0.3))
        t = T(0.18)
        self.sounds['stamp'] = pack(boom(t, 80.0, 18.0, 0.7) + (np.random.rand(len(t)) * 2 - 1) * np.exp(-t * 80.0) * 0.25)

    # 로봇 목소리용 모음 포먼트 (F1, F2, F3 Hz)
    _VOWELS = {"a": (800, 1250, 2500), "o": (500, 900, 2400), "e": (550, 1850, 2500), "i": (300, 2200, 3000), "u": (330, 900, 2300), "r": (450, 1300, 1700), "A": (700, 1700, 2500)}

    def _synth_word(self, syllables, sr=44100, f0=125.0):
        """아주 단순한 포먼트 합성 단어 (로봇 아나운서). syllables: 문자열은 자음, (모음, 길이)는 모음"""
        pieces = []
        rng = np.random.RandomState(7)
        for item in syllables:
            if isinstance(item, tuple):
                v, dur = item
                n = int(sr * dur)
                t = np.arange(n) / sr
                f = f0 * (1.0 + 0.12 * np.sin(np.pi * np.clip(t / dur, 0, 1)))                  # 억양: 모음마다 살짝 올랐다 내려옴
                ph = np.cumsum(f) / sr
                src = np.zeros(n)
                f1, f2, f3 = self._VOWELS[v]
                for k in range(1, 40):
                    fk = k * f0 * 1.06
                    if fk > 4500:
                        break
                    amp = (np.exp(-((fk - f1) / 110.0) ** 2) * 1.0 + np.exp(-((fk - f2) / 170.0) ** 2) * 0.7 + np.exp(-((fk - f3) / 250.0) ** 2) * 0.4 + 0.02) / (k ** 0.35)
                    src += amp * np.sin(2 * np.pi * k * ph)
                env = np.clip(np.minimum(t / 0.012, (dur - t) / 0.03), 0, 1)
                pieces.append(src * env)
            else:
                c = item
                dur = {"k": 0.05, "t": 0.04, "p": 0.04, "d": 0.045, "b": 0.045, "s": 0.12, "f": 0.1, "m": 0.08, "n": 0.07, "l": 0.07, "w": 0.06}.get(c, 0.05)
                n = int(sr * dur)
                t = np.arange(n) / sr
                noise = rng.rand(n) * 2 - 1
                if c in "stpkf":                                                                  # 파열/마찰음: 고역 노이즈 (차분으로 저역 제거)
                    out = np.diff(noise, prepend=0.0) * np.exp(-t * (60.0 if c in "tpk" else 18.0)) * (1.6 if c in "tk" else 1.2)
                elif c in "mnl":                                                                  # 비음/유음: 낮은 울림
                    out = np.sin(2 * np.pi * f0 * 1.9 * t) * 0.9 * np.minimum(1.0, t / 0.01) * np.minimum(1.0, (dur - t) / 0.02)
                else:                                                                             # b/d/w: 짧은 유성 폭발
                    out = np.sin(2 * np.pi * f0 * 1.5 * t) * np.exp(-t * 35.0) * 1.2 + noise * np.exp(-t * 80.0) * 0.3
                pieces.append(out)
        wave = np.concatenate(pieces) if pieces else np.zeros(1)
        wave = wave / (np.max(np.abs(wave)) + 1e-6) * 0.85
        t = np.arange(len(wave)) / sr
        wave = wave * (0.9 + 0.1 * np.sin(2 * np.pi * 60.0 * t))                                  # 가벼운 로봇 느낌: 얕은 링 변조와 약한 에코
        echo = np.zeros(len(wave) + int(sr * 0.09))
        echo[:len(wave)] += wave
        echo[int(sr * 0.09):] += wave * 0.25
        return echo

    def _generate_arcade_audio(self, sr=44100):
        """아케이드 소리 (v1.1.11): 콤보/B2B가 이어질 때 BGM 위에 얹는 하이햇 층(음높이 없음: 어떤 곡과도 부딪치지 않음)과 로봇 아나운서 외침"""
        n = int(sr * 2.0)
        rng = np.random.RandomState(11)
        layer = np.zeros(n)
        for i in range(16):                                                                      # 2초 = 16개의 8분음표 (120BPM 기준): 강약이 있는 하이햇 + 2·4박 클랩
            t0 = int(i * n / 16)
            ln = int(sr * (0.07 if i % 2 else 0.04))
            nz = np.diff(rng.rand(ln) * 2 - 1, prepend=0.0) * np.exp(-np.arange(ln) / sr * (55.0 if i % 2 else 90.0))
            layer[t0:t0 + ln] += nz * (0.55 if i % 2 else 0.9)
            if i in (4, 12):
                lc = int(sr * 0.11)
                cl = (rng.rand(lc) * 2 - 1) * np.exp(-np.arange(lc) / sr * 38.0)
                layer[t0:t0 + lc] += cl * 0.6
        layer = layer / (np.max(np.abs(layer)) + 1e-6) * 0.7
        self.sounds['combo_layer'] = self._pack_sound(layer)
        words = {
            "vo_quad": ["k", ("o", 0.1), ("a", 0.07), "d"],
            "vo_tspin": ["t", ("i", 0.1), "s", "p", ("i", 0.09), "n"],
            "vo_combo": ["k", ("a", 0.1), "m", "b", ("o", 0.12)],
            "vo_perfect": ["p", ("r", 0.09), "f", ("e", 0.08), "k", "t"],
            "vo_bounty": ["b", ("A", 0.1), "n", "t", ("i", 0.12)],
            "vo_final": ["f", ("A", 0.12), "n", ("o", 0.07), "l"],
            "vo_top10": ["t", ("a", 0.09), "p", "t", ("e", 0.08), "n"],
            "vo_golden": ["d", ("o", 0.1), "l", "d", ("e", 0.08), "n"],
        }
        for name, syl in words.items():
            self.sounds[name] = self._pack_sound(self._synth_word(syl, sr))

    def _generate_victory_anthem(self, sr=44100):
        """
        1위 최종 우승 챔피언 빅토리 팡파레 & 찬가 (7.3초)
        - 당당하고 화려한 클래식 챔피언 브라스 팡파레 리드 (Supersaw Brass Lead)
        - 웅장한 대관식 오케스트라 화음 (G - D - Em - Am - C - D - D7 - G)
        - 팀파니 롤 & 축제 심벌즈 크래시 & 스네어 행진 퍼커션
        - 영롱하게 부서지는 크리스탈 벨 아르페지오 글리산도
        """
        bpm = 138
        beat = 60.0 / bpm

        # 자체 작곡: G 장조 상행 아르페지오로 시작해 정상(G6)까지 올라가는 대관식 팡파레 (총 16박)
        melody = [
            ('D5', 0.5), ('G5', 0.5), ('B5', 1.0), ('A5', 0.5), ('G5', 0.5), ('F#5', 1.0),
            ('E5', 0.5), ('A5', 0.5), ('C6', 1.0), ('B5', 0.5), ('A5', 0.5), ('G5', 1.0),
            ('G5', 0.5), ('A5', 0.5), ('B5', 0.5), ('D6', 0.5), ('E6', 1.0), ('D6', 1.0),
            ('B5', 0.5), ('C6', 0.5), ('D6', 1.0), ('G6', 2.0)
        ]

        chord_prog = [
            (['G3', 'B3', 'D4', 'G4'], 2.0),
            (['D4', 'F#4', 'A4', 'D5'], 2.0),
            (['E4', 'G4', 'B4', 'E5'], 2.0),
            (['A3', 'C4', 'E4', 'A4'], 2.0),
            (['C4', 'E4', 'G4', 'C5'], 2.0),
            (['D4', 'F#4', 'A4', 'D5'], 2.0),
            (['D4', 'F#4', 'A4', 'C5'], 2.0),
            (['G3', 'B3', 'D4', 'G4', 'B4', 'D5'], 2.0)
        ]

        bass_prog = [
            ('G1', 2.0), ('D2', 2.0), ('E2', 2.0), ('A1', 2.0),
            ('C2', 2.0), ('D2', 2.0), ('D2', 2.0), ('G1', 2.0)
        ]

        total_beats = sum(d for _, d in melody)
        total_samples = int(sr * total_beats * beat)

        lead = np.zeros(total_samples, dtype=np.float32)
        chords = np.zeros(total_samples, dtype=np.float32)
        bass = np.zeros(total_samples, dtype=np.float32)
        drums = np.zeros(total_samples, dtype=np.float32)
        bells = np.zeros(total_samples, dtype=np.float32)

        # 1. 브라스 팡파레 리드 (Supersaw Brass Lead)
        cur_pos = 0
        for n_str, dur_b in melody:
            dur_s = int(dur_b * beat * sr)
            f = get_freq(n_str)
            if f > 0 and dur_s > 0:
                t = np.arange(dur_s) / sr
                s1 = 2.0 * ((f * 0.997 * t) % 1.0) - 1.0
                s2 = 2.0 * ((f * 1.000 * t) % 1.0) - 1.0
                s3 = 2.0 * ((f * 1.003 * t) % 1.0) - 1.0
                body = np.sin(2 * np.pi * f * t) * 0.5
                wave = np.tanh((s1 + s2 + s3) * 0.40 + body)
                att = np.minimum(t / 0.015, 1.0)
                rel = np.exp(-t * (1.8 if dur_b < 1.0 else 0.8))
                lead[cur_pos:cur_pos + dur_s] = wave * att * rel * 0.65
            cur_pos += dur_s

        # 2. 오케스트라 팡파레 화음 (Backing Brass & String Chords)
        cur_pos = 0
        for triad, dur_b in chord_prog:
            dur_s = int(dur_b * beat * sr)
            if dur_s > 0:
                t = np.arange(dur_s) / sr
                chord_w = np.zeros(dur_s, dtype=np.float32)
                for cn in triad:
                    cf = get_freq(cn)
                    if cf > 0:
                        w1 = np.sin(2 * np.pi * cf * 0.998 * t)
                        w2 = np.sin(2 * np.pi * cf * 1.002 * t)
                        w3 = np.sin(4 * np.pi * cf * t) * 0.25
                        chord_w += (w1 + w2 + w3)
                chord_w = chord_w / max(1, len(triad))
                att_s = min(int(sr * 0.03), dur_s // 4)
                env = np.ones(dur_s, dtype=np.float32)
                if att_s > 0:
                    env[:att_s] = np.linspace(0.0, 1.0, att_s)
                env *= np.exp(-t * 0.7)
                chords[cur_pos:cur_pos + dur_s] = np.tanh(chord_w * 1.4) * env * 0.45
            cur_pos += dur_s

        # 3. 묵직하고 당당한 베이스 (Triumphant Bass)
        cur_pos = 0
        for bn, dur_b in bass_prog:
            dur_s = int(dur_b * beat * sr)
            f = get_freq(bn)
            if f > 0 and dur_s > 0:
                t = np.arange(dur_s) / sr
                sub = np.sin(2 * np.pi * f * t) * 0.65
                saw = (2.0 * ((f * t) % 1.0) - 1.0) * 0.4
                env = np.exp(-t * 1.5)
                bass[cur_pos:cur_pos + dur_s] = np.tanh((sub + saw) * 1.6) * env * 0.55
            cur_pos += dur_s

        # 4. 축제 퍼커션 (Timpani Roll, Kick, Snare March, Cymbal Crash)
        t_roll = np.arange(int(sr * 0.45)) / sr
        f_roll = 65.0 + (t_roll / 0.45) * 45.0
        roll = np.sin(2 * np.pi * np.cumsum(f_roll) / sr) * (t_roll / 0.45) * 0.65
        drums[:len(roll)] += roll
        
        kick_dur = 0.08
        t_k = np.arange(int(sr * kick_dur)) / sr
        kick_w = np.sin(2 * np.pi * (150.0 * np.exp(-t_k * 30.0) + 45.0) * t_k) * np.exp(-t_k * 18.0)
        kick_w = np.tanh(kick_w * 1.8) * 0.85

        crash_dur = 1.2
        t_cr = np.arange(int(sr * crash_dur)) / sr
        crash_w = (np.random.rand(len(t_cr)) * 2 - 1) * np.exp(-t_cr * 4.0) * 0.40

        snare_dur = 0.12
        t_sn = np.arange(int(sr * snare_dur)) / sr
        snare_w = ((np.random.rand(len(t_sn)) * 2 - 1) * 0.6 + np.sin(2 * np.pi * 200.0 * t_sn) * 0.4) * np.exp(-t_sn * 20.0)

        hit_beats = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0]
        for hb in hit_beats:
            pos = int(hb * beat * sr)
            if pos + len(kick_w) < total_samples:
                drums[pos:pos + len(kick_w)] += kick_w
            if hb in [0.0, 8.0, 14.0] and pos + len(crash_w) < total_samples:
                drums[pos:pos + len(crash_w)] += crash_w
            if hb not in [0.0, 14.0] and pos + len(snare_w) < total_samples:
                drums[pos:pos + len(snare_w)] += snare_w

        # 5. 최종 G6 피날레에서 찬란하게 울려퍼지는 크리스탈 차임 아르페지오
        final_start_pos = int(14.0 * beat * sr)
        final_dur_s = total_samples - final_start_pos
        if final_dur_s > 0:
            t_fin = np.arange(final_dur_s) / sr
            chime_notes = ['G5', 'B5', 'D6', 'G6', 'B6', 'D7', 'G7']
            step = int(sr * 0.08)
            for idx, cn in enumerate(chime_notes):
                c_pos = idx * step
                if c_pos < final_dur_s:
                    rem = final_dur_s - c_pos
                    t_c = np.arange(rem) / sr
                    cf = get_freq(cn)
                    c_wave = (np.sin(2 * np.pi * cf * t_c) + 0.3 * np.sin(4 * np.pi * cf * t_c)) * np.exp(-t_c * 5.0) * 0.35
                    bells[final_start_pos + c_pos:] += c_wave

        # 마스터 믹스 & 와이드 스테레오
        master_mono = lead * 0.65 + chords * 0.45 + bass * 0.50 + drums * 0.55 + bells * 0.40
        peak = np.max(np.abs(master_mono))
        if peak > 0.95:
            master_mono = (master_mono / peak) * 0.95

        delay_s = int(sr * 0.018)
        left = master_mono.copy()
        right = master_mono * 0.70 + self._delayed(master_mono, delay_s) * 0.30

        return self._pack_stereo(left * 0.85, right * 0.85)

    def _synth_cyberpunk_track(self, bpm, melody, bass_prog, chord_prog, sr=44100, is_chill=False, soft=False):
        """
        고급 사이버펑크 / 신스웨이브 아케이드 트랙 합성:
        - 펀치 808/909 킥 & 스네어 & 16비트 하이햇 그루브
        - 아날로그 롤링 신스 베이스 (Rolling Synthwave Bassline)
        - 디튠된 스테레오 아날로그 패드 (Lush Warm Analog Pads)
        - 펀치감 있는 신스 플럭 리드 (Punchy Supersaw Pluck Lead)
        soft=True: 순위표처럼 차분한 장면용 편성(킥은 마디 첫 박만, 스네어 없음, 하이햇은 여리게, 리드는 길게 울림)
        """

        beat = 60.0 / bpm
        total_beats = sum(d for _, d in melody)
        total_samples = int(sr * total_beats * beat)

        drums = np.zeros(total_samples, dtype=np.float32)
        bass = np.zeros(total_samples, dtype=np.float32)
        pads = np.zeros(total_samples, dtype=np.float32)
        lead = np.zeros(total_samples, dtype=np.float32)

        # ----------------------------------------------------
        # 1. 드럼 트랙 (단단한 일렉트로 킥, 스네어, 16비트 하이햇)
        # ----------------------------------------------------
        # Kick: 160Hz -> 48Hz 빠른 다운스윕과 포화
        kick_dur = 0.075
        t_k = np.arange(int(sr * kick_dur)) / sr
        f_k = 160.0 * np.exp(-t_k * 36.0) + 48.0
        kick_w = np.sin(2 * np.pi * np.cumsum(f_k) / sr) * np.exp(-t_k * 18.0)
        kick_w = np.tanh(kick_w * 1.8) * 0.82

        # Snare / Clap: 펀치 바디 + 바삭한 노이즈
        snare_dur = 0.12
        t_s = np.arange(int(sr * snare_dur)) / sr
        snare_body = np.sin(2 * np.pi * (210.0 * np.exp(-t_s * 25.0) + 120.0) * t_s) * 0.45
        snare_noise = (np.random.rand(len(t_s)) * 2 - 1) * 0.55
        snare_w = (snare_body + snare_noise) * np.exp(-t_s * 22.0)

        # Hi-Hats: 16비트 디테일
        hh_dur = 0.035
        t_hh = np.arange(int(sr * hh_dur)) / sr
        hh_w = (np.random.rand(len(t_hh)) * 2 - 1) * np.exp(-t_hh * 110.0) * 0.24

        open_hh_dur = 0.10
        t_ohh = np.arange(int(sr * open_hh_dur)) / sr
        open_hh_w = (np.random.rand(len(t_ohh)) * 2 - 1) * np.exp(-t_ohh * 32.0) * 0.28

        for b in range(int(total_beats)):
            pos = int(b * beat * sr)
            # 킥: 4-on-the-floor (칠 모드일 때는 1, 3 비트 중심, 소프트 모드는 마디 첫 박만)
            if (not is_chill or (b % 2 == 0)) and (not soft or b % 4 == 0):
                if pos + len(kick_w) < total_samples:
                    drums[pos:pos + len(kick_w)] += kick_w
            # 스네어: 2, 4박
            if b % 2 == 1 and not soft and pos + len(snare_w) < total_samples:
                drums[pos:pos + len(snare_w)] += snare_w
            
            # 16비트 하이햇 패턴
            for sub in range(4):
                sub_pos = pos + int(sub * (beat / 4.0) * sr)
                if soft and sub != 2:
                    continue                                     # 소프트 모드: 오프비트 하이햇만 여리게
                if sub == 2:  # 오프비트 하이햇
                    if sub_pos + len(open_hh_w) < total_samples:
                        drums[sub_pos:sub_pos + len(open_hh_w)] += open_hh_w * 0.7
                else:
                    if sub_pos + len(hh_w) < total_samples:
                        drums[sub_pos:sub_pos + len(hh_w)] += hh_w * (0.85 if sub == 0 else 0.55)

        # ----------------------------------------------------
        # 2. 아날로그 롤링 신스 베이스 (Rolling Synthwave Bass)
        # ----------------------------------------------------
        bass_step_beats = total_beats / len(bass_prog)
        cur_pos = 0
        for b_note in bass_prog:
            dur_s = int(bass_step_beats * beat * sr)
            f = get_freq(b_note)
            if f > 0 and dur_s > 0:
                t = np.arange(dur_s) / sr
                # 아날로그 톱니파 + 서브 오실레이터
                saw = 2.0 * ((f * t) % 1.0) - 1.0
                sub = np.sin(2 * np.pi * f * t)
                octave_saw = (2.0 * ((f * 2.0 * t) % 1.0) - 1.0) * 0.35
                tone = np.tanh((saw * 0.6 + sub * 0.55 + octave_saw) * 1.8)
                # 16비트 펄스 엔벨로프 (Driving 16th feel)
                pulse_period = beat / 4.0
                env_16 = np.exp(-((t % pulse_period) / pulse_period) * 5.0)
                bass[cur_pos:cur_pos + dur_s] = tone * env_16 * 0.52
            cur_pos += dur_s

        # ----------------------------------------------------
        # 3. 몽환적이고 풍성한 네온 패드 화음 (Lush Stereo Pads)
        # ----------------------------------------------------
        chord_dur_beats = total_beats / len(chord_prog)
        cur_pos = 0
        for triad in chord_prog:
            dur_s = int(chord_dur_beats * beat * sr)
            if dur_s > 0:
                t = np.arange(dur_s) / sr
                chord_wave = np.zeros(dur_s, dtype=np.float32)
                for c_note in triad:
                    cf = get_freq(c_note)
                    if cf > 0:
                        # 디튠 코러스 패드 (Juno-106 스타일)
                        w1 = np.sin(2 * np.pi * (cf * 0.997) * t)
                        w2 = np.sin(2 * np.pi * (cf * 1.003) * t)
                        w3 = np.sin(4 * np.pi * cf * t) * 0.25
                        chord_wave += (w1 + w2 + w3)
                chord_wave = chord_wave / max(1, len(triad))
                
                # 부드러운 어택 & 릴리즈 엔벨로프
                att_len = min(int(sr * 0.12), dur_s // 3)
                rel_len = min(int(sr * 0.16), dur_s // 3)
                env = np.ones(dur_s, dtype=np.float32)
                if att_len > 0:
                    env[:att_len] = np.linspace(0.0, 1.0, att_len)
                if rel_len > 0:
                    env[-rel_len:] = np.linspace(1.0, 0.0, rel_len)
                pads[cur_pos:cur_pos + dur_s] = np.tanh(chord_wave * 1.3) * env * 0.38
            cur_pos += dur_s

        # ----------------------------------------------------
        # 4. 세련된 신스 플럭 & 슈퍼소우 리드 (Punchy Pluck Lead)
        # ----------------------------------------------------
        cur_pos = 0
        for note, dur_b in melody:
            dur_s = int(dur_b * beat * sr)
            f = get_freq(note)
            if f > 0 and dur_s > 0:
                t = np.arange(dur_s) / sr
                # 디튠된 아날로그 슈퍼소우 리드
                s1 = 2.0 * ((f * 0.996 * t) % 1.0) - 1.0
                s2 = 2.0 * ((f * 1.000 * t) % 1.0) - 1.0
                s3 = 2.0 * ((f * 1.004 * t) % 1.0) - 1.0
                body = np.sin(2 * np.pi * f * t) * 0.4
                lead_wave = (s1 + s2 + s3) * 0.35 + body
                
                # 신스 플럭 필터 감쇠 엔벨로프 (Snappy Pluck Decay)
                decay = 1.7 if soft else (3.6 if is_chill else 4.6)
                env = np.minimum(t / 0.008, 1.0) * np.exp(-t * decay)
                lead[cur_pos:cur_pos + dur_s] = np.tanh(lead_wave * 1.4) * env * 0.55
            cur_pos += dur_s

        # ----------------------------------------------------
        # 5. 마스터 믹싱 & 와이드 스테레오 공간감
        # ----------------------------------------------------
        if soft:
            master_mono = drums * 0.34 + bass * 0.42 + pads * 0.55 + lead * 0.60
        else:
            master_mono = drums * 0.62 + bass * 0.48 + pads * 0.42 + lead * 0.52
        peak = np.max(np.abs(master_mono))
        if peak > 0.95:
            master_mono = (master_mono / peak) * 0.95
            
        # 16ms 딜레이 기반의 매끄러운 3D 스테레오 와이드닝
        delay_s = int(sr * 0.016)
        left = master_mono.copy()
        right = master_mono * 0.72 + np.roll(master_mono, delay_s) * 0.28
        
        return self._pack_stereo(left * self._bgm_bake, right * self._bgm_bake)

    def _generate_all_bgm_stages(self):
        """4가지 세련된 사이버펑크 / 신스웨이브 BGM 트랙 생성"""
        try:
            # ----------------------------------------------------
            # 0. Menu Opening: "Neon Skyline" (114 BPM, Am / C)
            # 감성적이고 몽환적인 사이버네틱 네온 스카이라인 (오프닝 & 로비)
            # Am -> F -> C -> G 클래식 신스웨이브 코드 진행
            # ----------------------------------------------------
            # 자체 작곡: Am-F-C-G 위에서 코드톤을 따라 내려오고 올라가는 아르페지오 중심 멜로디 (총 32박, 화음 1개 = 2박)
            m_menu = [
                # A 섹션 (Am F C G / Am F C G)
                ('E5', 1.0), ('C5', 0.5), ('A4', 0.5),
                ('C5', 0.5), ('A4', 0.5), ('F4', 1.0),
                ('G4', 0.5), ('C5', 0.5), ('E5', 1.0),
                ('D5', 0.75), ('B4', 0.25), ('G4', 1.0),
                ('A4', 0.5), ('C5', 0.5), ('E5', 0.5), ('A5', 0.5),
                ('G5', 1.0), ('F5', 0.5), ('C5', 0.5),
                ('E5', 0.5), ('G5', 0.5), ('E5', 0.5), ('C5', 0.5),
                ('D5', 1.0), ('R', 0.5), ('B4', 0.5),
                # B 섹션 (F G Am C / F G Am Am)
                ('A5', 0.75), ('F5', 0.25), ('C6', 1.0),
                ('B5', 0.5), ('D6', 0.5), ('B5', 1.0),
                ('C6', 1.0), ('A5', 0.5), ('E5', 0.5),
                ('G5', 0.5), ('E5', 0.5), ('C5', 1.0),
                ('F5', 0.5), ('A5', 0.5), ('C6', 0.5), ('A5', 0.5),
                ('G5', 0.75), ('D5', 0.25), ('B4', 1.0),
                ('C5', 0.5), ('E5', 0.5), ('A5', 1.0),
                ('A4', 2.0)
            ]
            b_menu = [
                'A1', 'A1', 'F1', 'F1', 'C2', 'C2', 'G1', 'G1',
                'A1', 'A1', 'F1', 'F1', 'C2', 'C2', 'G1', 'G1',
                'F1', 'F1', 'G1', 'G1', 'A1', 'A1', 'C2', 'C2',
                'F1', 'F1', 'G1', 'G1', 'A1', 'A1', 'A1', 'A1'
            ]
            c_menu = [
                ['A3', 'C4', 'E4'], ['F3', 'A3', 'C4'], ['C3', 'E3', 'G3'], ['G3', 'B3', 'D4'],
                ['A3', 'C4', 'E4'], ['F3', 'A3', 'C4'], ['C3', 'E3', 'G3'], ['G3', 'B3', 'D4'],
                ['F3', 'A3', 'C4'], ['G3', 'B3', 'D4'], ['A3', 'C4', 'E4'], ['C4', 'E4', 'G4'],
                ['F3', 'A3', 'C4'], ['G3', 'B3', 'D4'], ['A3', 'C4', 'E4'], ['A3', 'C4', 'E4']
            ]
            self.bgm_stages['menu'] = self._synth_cyberpunk_track(114, m_menu, b_menu, c_menu, is_chill=True)

            # ----------------------------------------------------
            # R. Results: "Afterglow" (96 BPM, G 장조) - 최종 순위표 화면 (자체 작곡, 64박 = 16마디)
            # G-D-Em-Bm / C-G-Am-D 로 시작해 C-G-D-Em / C-D-G-G 로 고조됐다가 풀리는 잔잔하고 따뜻한 곡
            # ----------------------------------------------------
            self.bgm_stages['results'] = self._synth_cyberpunk_track(96, RESULTS_MELODY, RESULTS_BASS, RESULTS_CHORDS, is_chill=True, soft=True)

            # ----------------------------------------------------
            # 1. Stage 1: "Cyber Rush" (128 BPM, Dm / F) - 100~51 생존
            # 4-on-the-floor 비트와 롤링 16비트 베이스, 활기찬 네온 드라이브
            # Dm -> Bb -> F -> C
            # ----------------------------------------------------
            # 자체 작곡: 16분음표가 섞인 아르페지오 중심의 질주감 있는 리드 (총 32박, 화음 1개 = 2박)
            m1 = [
                # A 섹션 (Dm Bb F C / Dm Bb F C)
                ('A4', 0.25), ('D5', 0.25), ('F5', 0.5), ('A5', 0.5), ('F5', 0.5),
                ('D5', 0.25), ('F5', 0.25), ('Bb5', 0.5), ('A5', 0.5), ('F5', 0.5),
                ('C5', 0.25), ('F5', 0.25), ('A5', 0.5), ('C6', 0.75), ('A5', 0.25),
                ('G5', 0.5), ('E5', 0.5), ('G5', 0.5), ('E5', 0.25), ('C5', 0.25),
                ('D6', 0.5), ('A5', 0.5), ('F5', 0.25), ('A5', 0.25), ('D6', 0.5),
                ('Bb5', 0.75), ('A5', 0.25), ('F5', 0.5), ('D5', 0.5),
                ('A5', 0.5), ('C6', 0.5), ('A5', 0.25), ('F5', 0.25), ('C5', 0.5),
                ('E5', 0.5), ('G5', 0.5), ('E5', 0.5), ('R', 0.5),
                # B 섹션 (Bb C Dm F / Bb C Dm Dm)
                ('F5', 0.25), ('Bb5', 0.25), ('D6', 0.5), ('C6', 0.5), ('Bb5', 0.5),
                ('G5', 0.5), ('C6', 0.5), ('E6', 0.5), ('D6', 0.5),
                ('D6', 0.75), ('C6', 0.25), ('A5', 0.5), ('F5', 0.5),
                ('A5', 0.25), ('C6', 0.25), ('F6', 0.5), ('E6', 0.5), ('C6', 0.5),
                ('D6', 0.5), ('Bb5', 0.5), ('F5', 0.5), ('D5', 0.5),
                ('E5', 0.25), ('G5', 0.25), ('C6', 0.5), ('G5', 0.5), ('E5', 0.5),
                ('F5', 0.5), ('A5', 0.5), ('D6', 1.0),
                ('A5', 0.5), ('F5', 0.5), ('D5', 1.0)
            ]
            b1 = [
                'D2', 'D2', 'A#1', 'A#1', 'F1', 'F1', 'C2', 'C2',
                'D2', 'D2', 'A#1', 'A#1', 'F1', 'F1', 'C2', 'C2',
                'A#1', 'A#1', 'C2', 'C2', 'D2', 'D2', 'F1', 'F1',
                'A#1', 'A#1', 'C2', 'C2', 'D2', 'D2', 'D2', 'D2'
            ]
            c1 = [
                ['D4', 'F4', 'A4'], ['A#3', 'D4', 'F4'], ['F3', 'A3', 'C4'], ['C4', 'E4', 'G4'],
                ['D4', 'F4', 'A4'], ['A#3', 'D4', 'F4'], ['F3', 'A3', 'C4'], ['C4', 'E4', 'G4'],
                ['A#3', 'D4', 'F4'], ['C4', 'E4', 'G4'], ['D4', 'F4', 'A4'], ['F3', 'A3', 'C4'],
                ['A#3', 'D4', 'F4'], ['C4', 'E4', 'G4'], ['D4', 'F4', 'A4'], ['D4', 'F4', 'A4']
            ]
            self.bgm_stages[1] = [self._synth_cyberpunk_track(128, m1, b1, c1, is_chill=False)]       # 처음부터 리스트: 메인 스레드가 읽는 도중 타입이 바뀌지 않게

            # ----------------------------------------------------
            # 2. Stage 2: "Hyperdrive Override" (142 BPM, Em / G) - 50~21 생존
            # 가속되는 템포, 레이저 신스 아르페지오와 공격적인 베이스라인
            # Em -> C -> G -> D
            # ----------------------------------------------------
            # 자체 작곡: 점음표와 스케일 런(음계를 타고 오르내림) 중심의 긴박한 리드 (총 32박, 화음 1개 = 2박)
            m2 = [
                # A 섹션 (Em C G D / Em C G D)
                ('B4', 0.75), ('E5', 0.25), ('G5', 0.5), ('F#5', 0.5),
                ('E5', 0.5), ('G5', 0.5), ('C6', 0.75), ('B5', 0.25),
                ('D6', 0.5), ('B5', 0.5), ('G5', 0.5), ('A5', 0.5),
                ('F#5', 0.75), ('A5', 0.25), ('D6', 1.0),
                ('E6', 0.5), ('D6', 0.25), ('B5', 0.25), ('G5', 0.5), ('E5', 0.5),
                ('G5', 0.5), ('E5', 0.5), ('C5', 0.5), ('E5', 0.5),
                ('B5', 0.75), ('A5', 0.25), ('G5', 0.5), ('D5', 0.5),
                ('F#5', 0.5), ('A5', 0.5), ('F#5', 0.5), ('R', 0.5),
                # B 섹션 (C D Em G / C D Em Em)
                ('C6', 0.75), ('B5', 0.25), ('G5', 0.5), ('E5', 0.5),
                ('D6', 0.5), ('A5', 0.5), ('F#5', 0.5), ('D5', 0.5),
                ('G5', 0.25), ('B5', 0.25), ('E6', 0.5), ('G6', 0.5), ('E6', 0.5),
                ('D6', 0.75), ('B5', 0.25), ('G5', 1.0),
                ('E6', 0.5), ('C6', 0.5), ('G5', 0.5), ('E5', 0.5),
                ('F#5', 0.5), ('A5', 0.5), ('D6', 0.5), ('F#6', 0.5),
                ('E6', 1.0), ('B5', 0.5), ('G5', 0.5),
                ('E5', 2.0)
            ]
            b2 = [
                'E2', 'E2', 'C2', 'C2', 'G1', 'G1', 'D2', 'D2',
                'E2', 'E2', 'C2', 'C2', 'G1', 'G1', 'D2', 'D2',
                'C2', 'C2', 'D2', 'D2', 'E2', 'E2', 'G1', 'G1',
                'C2', 'C2', 'D2', 'D2', 'E2', 'E2', 'E2', 'E2'
            ]
            c2 = [
                ['E4', 'G4', 'B4'], ['C4', 'E4', 'G4'], ['G3', 'B3', 'D4'], ['D4', 'F#4', 'A4'],
                ['E4', 'G4', 'B4'], ['C4', 'E4', 'G4'], ['G3', 'B3', 'D4'], ['D4', 'F#4', 'A4'],
                ['C4', 'E4', 'G4'], ['D4', 'F#4', 'A4'], ['E4', 'G4', 'B4'], ['G3', 'B3', 'D4'],
                ['C4', 'E4', 'G4'], ['D4', 'F#4', 'A4'], ['E4', 'G4', 'B4'], ['E4', 'G4', 'B4']
            ]
            self.bgm_stages[2] = [self._synth_cyberpunk_track(142, m2, b2, c2, is_chill=False)]

            # ----------------------------------------------------
            # 3. Stage 3: "Apex Protocol" (156 BPM, F#m / A) - 20인 이하 최후의 결전
            # 폭발적인 템포, 웅장한 신스 브라스와 긴박한 아드레날린 배틀
            # F#m -> D -> A -> E
            # ----------------------------------------------------
            # 자체 작곡: 넓은 도약과 긴 음가로 웅장함을 강조한 리드 (총 32박, 화음 1개 = 2박)
            m3 = [
                # A 섹션 (F#m D A E / F#m D A E)
                ('F#5', 1.0), ('C#6', 0.5), ('A5', 0.5),
                ('D6', 0.5), ('A5', 0.5), ('F#5', 0.75), ('A5', 0.25),
                ('E6', 1.0), ('C#6', 0.5), ('A5', 0.5),
                ('G#5', 0.5), ('B5', 0.5), ('E6', 0.75), ('C#6', 0.25),
                ('F#6', 1.0), ('E6', 0.5), ('C#6', 0.5),
                ('D6', 0.5), ('F#5', 0.5), ('A5', 1.0),
                ('C#6', 0.5), ('E6', 0.5), ('C#6', 0.5), ('A5', 0.5),
                ('B5', 0.75), ('G#5', 0.25), ('E5', 1.0),
                # B 섹션 (D E F#m A / D E F#m F#m)
                ('A5', 0.5), ('D6', 0.5), ('F#6', 1.0),
                ('E6', 0.5), ('B5', 0.5), ('G#5', 0.5), ('B5', 0.5),
                ('C#6', 0.75), ('A5', 0.25), ('F#5', 1.0),
                ('A5', 0.5), ('C#6', 0.5), ('E6', 1.0),
                ('F#6', 0.5), ('D6', 0.5), ('A5', 0.5), ('F#5', 0.5),
                ('G#5', 0.25), ('B5', 0.25), ('E6', 0.5), ('B5', 0.5), ('G#5', 0.5),
                ('A5', 0.5), ('C#6', 0.5), ('F#6', 1.0),
                ('C#6', 0.5), ('A5', 0.5), ('F#5', 1.0)
            ]
            b3 = [
                'F#2', 'F#2', 'D2', 'D2', 'A1', 'A1', 'E2', 'E2',
                'F#2', 'F#2', 'D2', 'D2', 'A1', 'A1', 'E2', 'E2',
                'D2', 'D2', 'E2', 'E2', 'F#2', 'F#2', 'A1', 'A1',
                'D2', 'D2', 'E2', 'E2', 'F#2', 'F#2', 'F#2', 'F#2'
            ]
            c3 = [
                ['F#4', 'A4', 'C#5'], ['D4', 'F#4', 'A4'], ['A3', 'C#4', 'E4'], ['E4', 'G#4', 'B4'],
                ['F#4', 'A4', 'C#5'], ['D4', 'F#4', 'A4'], ['A3', 'C#4', 'E4'], ['E4', 'G#4', 'B4'],
                ['D4', 'F#4', 'A4'], ['E4', 'G#4', 'B4'], ['F#4', 'A4', 'C#5'], ['A3', 'C#4', 'E4'],
                ['D4', 'F#4', 'A4'], ['E4', 'G#4', 'B4'], ['F#4', 'A4', 'C#5'], ['F#4', 'A4', 'C#5']
            ]
            self.bgm_stages[3] = [self._synth_cyberpunk_track(156, m3, b3, c3, is_chill=False)]

            # ======================================================
            # 스테이지 배경음 추가 4세트 (총 5세트, 설정에서 선택/랜덤 가능)
            # 세트0(오리지널) 위 Cyber Rush/Hyperdrive Override/Apex Protocol과
            # 같은 형식(i-bVI-bIII-bVII 진행, 2박마다 화음 전환)의 자체 작곡곡
            # ======================================================

            # ---- 세트1: "Neon Circuit" (Gm/Eb/Bb/F, 124/138/152 BPM) ----
            b4 = [
                'G1', 'G1', 'Eb2', 'Eb2', 'Bb1', 'Bb1', 'F2', 'F2',
                'G1', 'G1', 'Eb2', 'Eb2', 'Bb1', 'Bb1', 'F2', 'F2',
                'Eb2', 'Eb2', 'F2', 'F2', 'G1', 'G1', 'Bb1', 'Bb1',
                'Eb2', 'Eb2', 'F2', 'F2', 'G1', 'G1', 'G1', 'G1',
            ]
            c4 = [
                ['G3', 'Bb3', 'D4'], ['Eb4', 'G4', 'Bb4'],
                ['Bb3', 'D4', 'F4'], ['F4', 'A4', 'C5'],
                ['G3', 'Bb3', 'D4'], ['Eb4', 'G4', 'Bb4'],
                ['Bb3', 'D4', 'F4'], ['F4', 'A4', 'C5'],
                ['Eb4', 'G4', 'Bb4'], ['F4', 'A4', 'C5'],
                ['G3', 'Bb3', 'D4'], ['Bb3', 'D4', 'F4'],
                ['Eb4', 'G4', 'Bb4'], ['F4', 'A4', 'C5'],
                ['G3', 'Bb3', 'D4'], ['G3', 'Bb3', 'D4'],
            ]
            m4_1 = [
                ('G5', 0.5), ('Bb5', 0.5), ('D5', 0.5), ('Bb5', 0.5), ('Bb5', 0.5), ('G5', 0.5),
                ('Eb5', 0.5), ('G5', 0.5), ('Bb5', 0.5), ('D5', 0.5), ('F5', 0.5), ('D5', 0.5),
                ('F5', 0.25), ('A5', 0.25), ('C5', 0.5), ('A5', 0.5), ('F5', 0.5), ('D5', 0.5),
                ('Bb5', 0.5), ('G5', 0.5), ('Bb5', 0.5), ('Eb5', 0.5), ('G5', 0.5), ('Bb5', 0.5),
                ('G5', 0.5), ('D5', 0.75), ('F5', 0.25), ('D5', 0.5), ('Bb5', 0.5), ('F5', 0.25),
                ('A5', 0.25), ('C5', 0.5), ('A5', 0.5), ('F5', 0.5), ('Eb5', 0.5), ('G5', 0.5),
                ('Bb5', 0.5), ('G5', 0.5), ('F5', 0.25), ('A5', 0.25), ('C5', 0.5), ('A5', 0.5),
                ('F5', 0.5), ('D5', 0.5), ('Bb5', 0.5), ('G5', 0.5), ('Bb5', 0.5), ('D5', 0.75),
                ('F5', 0.25), ('D5', 0.5), ('Bb5', 0.5), ('Eb5', 0.5), ('G5', 0.5), ('Bb5', 0.5),
                ('G5', 0.5), ('C5', 0.5), ('A5', 0.5), ('F5', 0.5), ('A5', 0.5), ('Bb5', 0.75),
                ('D5', 0.25), ('Bb5', 0.5), ('G5', 0.5), ('G5', 0.25), ('Bb5', 0.25), ('D5', 0.5),
                ('Bb5', 0.5), ('G5', 0.5),
            ]
            m4_2 = [
                ('D5', 0.75), ('Bb5', 0.25), ('G5', 0.5), ('Bb5', 0.5), ('Eb5', 0.5), ('Bb5', 0.25),
                ('G5', 0.25), ('Bb5', 0.5), ('Eb5', 0.5), ('F5', 0.75), ('D5', 0.25), ('Bb5', 0.5),
                ('D5', 0.5), ('A5', 0.25), ('C5', 0.25), ('F5', 0.5), ('C5', 0.5), ('A5', 0.5),
                ('G5', 0.5), ('D5', 0.25), ('Bb5', 0.25), ('D5', 0.5), ('G5', 0.5), ('Bb5', 0.75),
                ('G5', 0.25), ('Eb5', 0.5), ('G5', 0.5), ('F5', 1.0), ('D5', 0.5), ('Bb5', 0.5),
                ('A5', 0.25), ('C5', 0.25), ('F5', 0.5), ('C5', 0.5), ('A5', 0.5), ('G5', 0.25),
                ('Bb5', 0.25), ('Eb5', 0.5), ('Bb5', 0.5), ('G5', 0.5), ('C5', 0.75), ('A5', 0.25),
                ('F5', 0.5), ('A5', 0.5), ('G5', 0.5), ('D5', 0.25), ('Bb5', 0.25), ('D5', 0.5),
                ('G5', 0.5), ('F5', 1.0), ('D5', 0.5), ('Bb5', 0.5), ('Bb5', 0.75), ('G5', 0.25),
                ('Eb5', 0.5), ('G5', 0.5), ('A5', 0.25), ('C5', 0.25), ('F5', 0.5), ('C5', 0.5),
                ('A5', 0.5), ('D5', 1.0), ('Bb5', 0.5), ('G5', 0.5), ('D5', 1.0), ('Bb5', 0.5),
                ('G5', 0.5),
            ]
            m4_3 = [
                ('G5', 1.0), ('D5', 0.5), ('Bb5', 0.5), ('Bb5', 1.0), ('G5', 0.5), ('Eb5', 0.5),
                ('Bb5', 1.0), ('F5', 0.5), ('D5', 0.5), ('C5', 1.0), ('A5', 0.5), ('F5', 0.5),
                ('G5', 0.5), ('Bb5', 0.5), ('D6', 1.0), ('Bb5', 1.0), ('G5', 0.5), ('Eb5', 0.5),
                ('Bb5', 1.0), ('F5', 0.5), ('D5', 0.5), ('C6', 1.5), ('F5', 0.5), ('Bb5', 1.0),
                ('G5', 0.5), ('Eb5', 0.5), ('F5', 1.0), ('C5', 0.5), ('A5', 0.5), ('G5', 0.5),
                ('Bb5', 0.5), ('D6', 1.0), ('F5', 1.0), ('D5', 0.5), ('Bb5', 0.5), ('Bb6', 1.5),
                ('Eb5', 0.5), ('F5', 0.5), ('A5', 0.5), ('C6', 1.0), ('G5', 1.0), ('D5', 0.5),
                ('Bb5', 0.5), ('G5', 1.0), ('D5', 0.5), ('Bb5', 0.5),
            ]
            self.bgm_stages[1].append(self._synth_cyberpunk_track(124, m4_1, b4, c4, is_chill=False))
            self.bgm_stages[2].append(self._synth_cyberpunk_track(138, m4_2, b4, c4, is_chill=False))
            self.bgm_stages[3].append(self._synth_cyberpunk_track(152, m4_3, b4, c4, is_chill=False))

            # ---- 세트2: "Pulse Overdrive" (Cm/Ab/Eb/Bb, 130/144/158 BPM) ----
            b5 = [
                'C2', 'C2', 'Ab1', 'Ab1', 'Eb2', 'Eb2', 'Bb1', 'Bb1',
                'C2', 'C2', 'Ab1', 'Ab1', 'Eb2', 'Eb2', 'Bb1', 'Bb1',
                'Ab1', 'Ab1', 'Bb1', 'Bb1', 'C2', 'C2', 'Eb2', 'Eb2',
                'Ab1', 'Ab1', 'Bb1', 'Bb1', 'C2', 'C2', 'C2', 'C2',
            ]
            c5 = [
                ['C4', 'Eb4', 'G4'], ['Ab3', 'C4', 'Eb4'],
                ['Eb4', 'G4', 'Bb4'], ['Bb3', 'D4', 'F4'],
                ['C4', 'Eb4', 'G4'], ['Ab3', 'C4', 'Eb4'],
                ['Eb4', 'G4', 'Bb4'], ['Bb3', 'D4', 'F4'],
                ['Ab3', 'C4', 'Eb4'], ['Bb3', 'D4', 'F4'],
                ['C4', 'Eb4', 'G4'], ['Eb4', 'G4', 'Bb4'],
                ['Ab3', 'C4', 'Eb4'], ['Bb3', 'D4', 'F4'],
                ['C4', 'Eb4', 'G4'], ['C4', 'Eb4', 'G4'],
            ]
            m5_1 = [
                ('C5', 0.5), ('Eb5', 0.5), ('G5', 0.5), ('Eb5', 0.5), ('Eb5', 0.5), ('C5', 0.5),
                ('Ab5', 0.5), ('C5', 0.5), ('Eb5', 0.5), ('G5', 0.5), ('Bb5', 0.5), ('G5', 0.5),
                ('Bb5', 0.25), ('D5', 0.25), ('F5', 0.5), ('D5', 0.5), ('Bb5', 0.5), ('G5', 0.5),
                ('Eb5', 0.5), ('C5', 0.5), ('Eb5', 0.5), ('Ab5', 0.5), ('C5', 0.5), ('Eb5', 0.5),
                ('C5', 0.5), ('G5', 0.75), ('Bb5', 0.25), ('G5', 0.5), ('Eb5', 0.5), ('Bb5', 0.25),
                ('D5', 0.25), ('F5', 0.5), ('D5', 0.5), ('Bb5', 0.5), ('Ab5', 0.5), ('C5', 0.5),
                ('Eb5', 0.5), ('C5', 0.5), ('Bb5', 0.25), ('D5', 0.25), ('F5', 0.5), ('D5', 0.5),
                ('Bb5', 0.5), ('G5', 0.5), ('Eb5', 0.5), ('C5', 0.5), ('Eb5', 0.5), ('G5', 0.75),
                ('Bb5', 0.25), ('G5', 0.5), ('Eb5', 0.5), ('Ab5', 0.5), ('C5', 0.5), ('Eb5', 0.5),
                ('C5', 0.5), ('F5', 0.5), ('D5', 0.5), ('Bb5', 0.5), ('D5', 0.5), ('Eb5', 0.75),
                ('G5', 0.25), ('Eb5', 0.5), ('C5', 0.5), ('C5', 0.25), ('Eb5', 0.25), ('G5', 0.5),
                ('Eb5', 0.5), ('C5', 0.5),
            ]
            m5_2 = [
                ('G5', 0.75), ('Eb5', 0.25), ('C5', 0.5), ('Eb5', 0.5), ('Ab5', 0.5), ('Eb5', 0.25),
                ('C5', 0.25), ('Eb5', 0.5), ('Ab5', 0.5), ('Bb5', 0.75), ('G5', 0.25), ('Eb5', 0.5),
                ('G5', 0.5), ('D5', 0.25), ('F5', 0.25), ('Bb5', 0.5), ('F5', 0.5), ('D5', 0.5),
                ('C5', 0.5), ('G5', 0.25), ('Eb5', 0.25), ('G5', 0.5), ('C5', 0.5), ('Eb5', 0.75),
                ('C5', 0.25), ('Ab5', 0.5), ('C5', 0.5), ('Bb5', 1.0), ('G5', 0.5), ('Eb5', 0.5),
                ('D5', 0.25), ('F5', 0.25), ('Bb5', 0.5), ('F5', 0.5), ('D5', 0.5), ('C5', 0.25),
                ('Eb5', 0.25), ('Ab5', 0.5), ('Eb5', 0.5), ('C5', 0.5), ('F5', 0.75), ('D5', 0.25),
                ('Bb5', 0.5), ('D5', 0.5), ('C5', 0.5), ('G5', 0.25), ('Eb5', 0.25), ('G5', 0.5),
                ('C5', 0.5), ('Bb5', 1.0), ('G5', 0.5), ('Eb5', 0.5), ('Eb5', 0.75), ('C5', 0.25),
                ('Ab5', 0.5), ('C5', 0.5), ('D5', 0.25), ('F5', 0.25), ('Bb5', 0.5), ('F5', 0.5),
                ('D5', 0.5), ('G5', 1.0), ('Eb5', 0.5), ('C5', 0.5), ('G5', 1.0), ('Eb5', 0.5),
                ('C5', 0.5),
            ]
            m5_3 = [
                ('C5', 1.0), ('G5', 0.5), ('Eb5', 0.5), ('Eb5', 1.0), ('C5', 0.5), ('Ab5', 0.5),
                ('Eb5', 1.0), ('Bb5', 0.5), ('G5', 0.5), ('F5', 1.0), ('D5', 0.5), ('Bb5', 0.5),
                ('C5', 0.5), ('Eb5', 0.5), ('G6', 1.0), ('Eb5', 1.0), ('C5', 0.5), ('Ab5', 0.5),
                ('Eb5', 1.0), ('Bb5', 0.5), ('G5', 0.5), ('F6', 1.5), ('Bb5', 0.5), ('Eb5', 1.0),
                ('C5', 0.5), ('Ab5', 0.5), ('Bb5', 1.0), ('F5', 0.5), ('D5', 0.5), ('C5', 0.5),
                ('Eb5', 0.5), ('G6', 1.0), ('Bb5', 1.0), ('G5', 0.5), ('Eb5', 0.5), ('Eb6', 1.5),
                ('Ab5', 0.5), ('Bb5', 0.5), ('D5', 0.5), ('F6', 1.0), ('C5', 1.0), ('G5', 0.5),
                ('Eb5', 0.5), ('C5', 1.0), ('G5', 0.5), ('Eb5', 0.5),
            ]
            self.bgm_stages[1].append(self._synth_cyberpunk_track(130, m5_1, b5, c5, is_chill=False))
            self.bgm_stages[2].append(self._synth_cyberpunk_track(144, m5_2, b5, c5, is_chill=False))
            self.bgm_stages[3].append(self._synth_cyberpunk_track(158, m5_3, b5, c5, is_chill=False))

            # ---- 세트3: "Chrome Requiem" (Bm/G/D/A, 120/134/148 BPM) ----
            b6 = [
                'B1', 'B1', 'G1', 'G1', 'D2', 'D2', 'A1', 'A1',
                'B1', 'B1', 'G1', 'G1', 'D2', 'D2', 'A1', 'A1',
                'G1', 'G1', 'A1', 'A1', 'B1', 'B1', 'D2', 'D2',
                'G1', 'G1', 'A1', 'A1', 'B1', 'B1', 'B1', 'B1',
            ]
            c6 = [
                ['B3', 'D4', 'F#4'], ['G3', 'B3', 'D4'],
                ['D4', 'F#4', 'A4'], ['A3', 'C#4', 'E4'],
                ['B3', 'D4', 'F#4'], ['G3', 'B3', 'D4'],
                ['D4', 'F#4', 'A4'], ['A3', 'C#4', 'E4'],
                ['G3', 'B3', 'D4'], ['A3', 'C#4', 'E4'],
                ['B3', 'D4', 'F#4'], ['D4', 'F#4', 'A4'],
                ['G3', 'B3', 'D4'], ['A3', 'C#4', 'E4'],
                ['B3', 'D4', 'F#4'], ['B3', 'D4', 'F#4'],
            ]
            m6_1 = [
                ('B5', 0.5), ('D5', 0.5), ('F#5', 0.5), ('D5', 0.5), ('D5', 0.5), ('B5', 0.5),
                ('G5', 0.5), ('B5', 0.5), ('D5', 0.5), ('F#5', 0.5), ('A5', 0.5), ('F#5', 0.5),
                ('A5', 0.25), ('C#5', 0.25), ('E5', 0.5), ('C#5', 0.5), ('A5', 0.5), ('F#5', 0.5),
                ('D5', 0.5), ('B5', 0.5), ('D5', 0.5), ('G5', 0.5), ('B5', 0.5), ('D5', 0.5),
                ('B5', 0.5), ('F#5', 0.75), ('A5', 0.25), ('F#5', 0.5), ('D5', 0.5), ('A5', 0.25),
                ('C#5', 0.25), ('E5', 0.5), ('C#5', 0.5), ('A5', 0.5), ('G5', 0.5), ('B5', 0.5),
                ('D5', 0.5), ('B5', 0.5), ('A5', 0.25), ('C#5', 0.25), ('E5', 0.5), ('C#5', 0.5),
                ('A5', 0.5), ('F#5', 0.5), ('D5', 0.5), ('B5', 0.5), ('D5', 0.5), ('F#5', 0.75),
                ('A5', 0.25), ('F#5', 0.5), ('D5', 0.5), ('G5', 0.5), ('B5', 0.5), ('D5', 0.5),
                ('B5', 0.5), ('E5', 0.5), ('C#5', 0.5), ('A5', 0.5), ('C#5', 0.5), ('D5', 0.75),
                ('F#5', 0.25), ('D5', 0.5), ('B5', 0.5), ('B5', 0.25), ('D5', 0.25), ('F#5', 0.5),
                ('D5', 0.5), ('B5', 0.5),
            ]
            m6_2 = [
                ('F#5', 0.75), ('D5', 0.25), ('B5', 0.5), ('D5', 0.5), ('G5', 0.5), ('D5', 0.25),
                ('B5', 0.25), ('D5', 0.5), ('G5', 0.5), ('A5', 0.75), ('F#5', 0.25), ('D5', 0.5),
                ('F#5', 0.5), ('C#5', 0.25), ('E5', 0.25), ('A5', 0.5), ('E5', 0.5), ('C#5', 0.5),
                ('B5', 0.5), ('F#5', 0.25), ('D5', 0.25), ('F#5', 0.5), ('B5', 0.5), ('D5', 0.75),
                ('B5', 0.25), ('G5', 0.5), ('B5', 0.5), ('A5', 1.0), ('F#5', 0.5), ('D5', 0.5),
                ('C#5', 0.25), ('E5', 0.25), ('A5', 0.5), ('E5', 0.5), ('C#5', 0.5), ('B5', 0.25),
                ('D5', 0.25), ('G5', 0.5), ('D5', 0.5), ('B5', 0.5), ('E5', 0.75), ('C#5', 0.25),
                ('A5', 0.5), ('C#5', 0.5), ('B5', 0.5), ('F#5', 0.25), ('D5', 0.25), ('F#5', 0.5),
                ('B5', 0.5), ('A5', 1.0), ('F#5', 0.5), ('D5', 0.5), ('D5', 0.75), ('B5', 0.25),
                ('G5', 0.5), ('B5', 0.5), ('C#5', 0.25), ('E5', 0.25), ('A5', 0.5), ('E5', 0.5),
                ('C#5', 0.5), ('F#5', 1.0), ('D5', 0.5), ('B5', 0.5), ('F#5', 1.0), ('D5', 0.5),
                ('B5', 0.5),
            ]
            m6_3 = [
                ('B5', 1.0), ('F#5', 0.5), ('D5', 0.5), ('D5', 1.0), ('B5', 0.5), ('G5', 0.5),
                ('D5', 1.0), ('A5', 0.5), ('F#5', 0.5), ('E5', 1.0), ('C#5', 0.5), ('A5', 0.5),
                ('B5', 0.5), ('D5', 0.5), ('F#6', 1.0), ('D5', 1.0), ('B5', 0.5), ('G5', 0.5),
                ('D5', 1.0), ('A5', 0.5), ('F#5', 0.5), ('E6', 1.5), ('A5', 0.5), ('D5', 1.0),
                ('B5', 0.5), ('G5', 0.5), ('A5', 1.0), ('E5', 0.5), ('C#5', 0.5), ('B5', 0.5),
                ('D5', 0.5), ('F#6', 1.0), ('A5', 1.0), ('F#5', 0.5), ('D5', 0.5), ('D6', 1.5),
                ('G5', 0.5), ('A5', 0.5), ('C#5', 0.5), ('E6', 1.0), ('B5', 1.0), ('F#5', 0.5),
                ('D5', 0.5), ('B5', 1.0), ('F#5', 0.5), ('D5', 0.5),
            ]
            self.bgm_stages[1].append(self._synth_cyberpunk_track(120, m6_1, b6, c6, is_chill=False))
            self.bgm_stages[2].append(self._synth_cyberpunk_track(134, m6_2, b6, c6, is_chill=False))
            self.bgm_stages[3].append(self._synth_cyberpunk_track(148, m6_3, b6, c6, is_chill=False))

            # ---- 세트4: "Vector Surge" (C#m/A/E/B, 132/146/160 BPM) ----
            b7 = [
                'C#2', 'C#2', 'A1', 'A1', 'E2', 'E2', 'B1', 'B1',
                'C#2', 'C#2', 'A1', 'A1', 'E2', 'E2', 'B1', 'B1',
                'A1', 'A1', 'B1', 'B1', 'C#2', 'C#2', 'E2', 'E2',
                'A1', 'A1', 'B1', 'B1', 'C#2', 'C#2', 'C#2', 'C#2',
            ]
            c7 = [
                ['C#4', 'E4', 'G#4'], ['A3', 'C#4', 'E4'],
                ['E4', 'G#4', 'B4'], ['B3', 'D#4', 'F#4'],
                ['C#4', 'E4', 'G#4'], ['A3', 'C#4', 'E4'],
                ['E4', 'G#4', 'B4'], ['B3', 'D#4', 'F#4'],
                ['A3', 'C#4', 'E4'], ['B3', 'D#4', 'F#4'],
                ['C#4', 'E4', 'G#4'], ['E4', 'G#4', 'B4'],
                ['A3', 'C#4', 'E4'], ['B3', 'D#4', 'F#4'],
                ['C#4', 'E4', 'G#4'], ['C#4', 'E4', 'G#4'],
            ]
            m7_1 = [
                ('C#5', 0.5), ('E5', 0.5), ('G#5', 0.5), ('E5', 0.5), ('E5', 0.5), ('C#5', 0.5),
                ('A5', 0.5), ('C#5', 0.5), ('E5', 0.5), ('G#5', 0.5), ('B5', 0.5), ('G#5', 0.5),
                ('B5', 0.25), ('D#5', 0.25), ('F#5', 0.5), ('D#5', 0.5), ('B5', 0.5), ('G#5', 0.5),
                ('E5', 0.5), ('C#5', 0.5), ('E5', 0.5), ('A5', 0.5), ('C#5', 0.5), ('E5', 0.5),
                ('C#5', 0.5), ('G#5', 0.75), ('B5', 0.25), ('G#5', 0.5), ('E5', 0.5), ('B5', 0.25),
                ('D#5', 0.25), ('F#5', 0.5), ('D#5', 0.5), ('B5', 0.5), ('A5', 0.5), ('C#5', 0.5),
                ('E5', 0.5), ('C#5', 0.5), ('B5', 0.25), ('D#5', 0.25), ('F#5', 0.5), ('D#5', 0.5),
                ('B5', 0.5), ('G#5', 0.5), ('E5', 0.5), ('C#5', 0.5), ('E5', 0.5), ('G#5', 0.75),
                ('B5', 0.25), ('G#5', 0.5), ('E5', 0.5), ('A5', 0.5), ('C#5', 0.5), ('E5', 0.5),
                ('C#5', 0.5), ('F#5', 0.5), ('D#5', 0.5), ('B5', 0.5), ('D#5', 0.5), ('E5', 0.75),
                ('G#5', 0.25), ('E5', 0.5), ('C#5', 0.5), ('C#5', 0.25), ('E5', 0.25), ('G#5', 0.5),
                ('E5', 0.5), ('C#5', 0.5),
            ]
            m7_2 = [
                ('G#5', 0.75), ('E5', 0.25), ('C#5', 0.5), ('E5', 0.5), ('A5', 0.5), ('E5', 0.25),
                ('C#5', 0.25), ('E5', 0.5), ('A5', 0.5), ('B5', 0.75), ('G#5', 0.25), ('E5', 0.5),
                ('G#5', 0.5), ('D#5', 0.25), ('F#5', 0.25), ('B5', 0.5), ('F#5', 0.5), ('D#5', 0.5),
                ('C#5', 0.5), ('G#5', 0.25), ('E5', 0.25), ('G#5', 0.5), ('C#5', 0.5), ('E5', 0.75),
                ('C#5', 0.25), ('A5', 0.5), ('C#5', 0.5), ('B5', 1.0), ('G#5', 0.5), ('E5', 0.5),
                ('D#5', 0.25), ('F#5', 0.25), ('B5', 0.5), ('F#5', 0.5), ('D#5', 0.5), ('C#5', 0.25),
                ('E5', 0.25), ('A5', 0.5), ('E5', 0.5), ('C#5', 0.5), ('F#5', 0.75), ('D#5', 0.25),
                ('B5', 0.5), ('D#5', 0.5), ('C#5', 0.5), ('G#5', 0.25), ('E5', 0.25), ('G#5', 0.5),
                ('C#5', 0.5), ('B5', 1.0), ('G#5', 0.5), ('E5', 0.5), ('E5', 0.75), ('C#5', 0.25),
                ('A5', 0.5), ('C#5', 0.5), ('D#5', 0.25), ('F#5', 0.25), ('B5', 0.5), ('F#5', 0.5),
                ('D#5', 0.5), ('G#5', 1.0), ('E5', 0.5), ('C#5', 0.5), ('G#5', 1.0), ('E5', 0.5),
                ('C#5', 0.5),
            ]
            m7_3 = [
                ('C#5', 1.0), ('G#5', 0.5), ('E5', 0.5), ('E5', 1.0), ('C#5', 0.5), ('A5', 0.5),
                ('E5', 1.0), ('B5', 0.5), ('G#5', 0.5), ('F#5', 1.0), ('D#5', 0.5), ('B5', 0.5),
                ('C#5', 0.5), ('E5', 0.5), ('G#6', 1.0), ('E5', 1.0), ('C#5', 0.5), ('A5', 0.5),
                ('E5', 1.0), ('B5', 0.5), ('G#5', 0.5), ('F#6', 1.5), ('B5', 0.5), ('E5', 1.0),
                ('C#5', 0.5), ('A5', 0.5), ('B5', 1.0), ('F#5', 0.5), ('D#5', 0.5), ('C#5', 0.5),
                ('E5', 0.5), ('G#6', 1.0), ('B5', 1.0), ('G#5', 0.5), ('E5', 0.5), ('E6', 1.5),
                ('A5', 0.5), ('B5', 0.5), ('D#5', 0.5), ('F#6', 1.0), ('C#5', 1.0), ('G#5', 0.5),
                ('E5', 0.5), ('C#5', 1.0), ('G#5', 0.5), ('E5', 0.5),
            ]
            self.bgm_stages[1].append(self._synth_cyberpunk_track(132, m7_1, b7, c7, is_chill=False))
            self.bgm_stages[2].append(self._synth_cyberpunk_track(146, m7_2, b7, c7, is_chill=False))
            self.bgm_stages[3].append(self._synth_cyberpunk_track(160, m7_3, b7, c7, is_chill=False))

            # ----------------------------------------------------
            # 로비 대기실 전용: "Standby Frequency" (96 BPM, Fm) - 방 만들기/참가 대기 화면
            # 전투곡보다 느긋하고 몽환적인 신스 패드 중심 편성 (soft=True)
            # ----------------------------------------------------
            b_lobby = [
                'F2', 'F2', 'Db2', 'Db2', 'Ab1', 'Ab1', 'Eb2', 'Eb2',
                'F2', 'F2', 'Db2', 'Db2', 'Ab1', 'Ab1', 'Eb2', 'Eb2',
                'Db2', 'Db2', 'Eb2', 'Eb2', 'F2', 'F2', 'Ab1', 'Ab1',
                'Db2', 'Db2', 'Eb2', 'Eb2', 'F2', 'F2', 'F2', 'F2',
            ]
            c_lobby = [
                ['F4', 'Ab4', 'C5'], ['Db4', 'F4', 'Ab4'],
                ['Ab3', 'C4', 'Eb4'], ['Eb4', 'G4', 'Bb4'],
                ['F4', 'Ab4', 'C5'], ['Db4', 'F4', 'Ab4'],
                ['Ab3', 'C4', 'Eb4'], ['Eb4', 'G4', 'Bb4'],
                ['Db4', 'F4', 'Ab4'], ['Eb4', 'G4', 'Bb4'],
                ['F4', 'Ab4', 'C5'], ['Ab3', 'C4', 'Eb4'],
                ['Db4', 'F4', 'Ab4'], ['Eb4', 'G4', 'Bb4'],
                ['F4', 'Ab4', 'C5'], ['F4', 'Ab4', 'C5'],
            ]
            m_lobby = [
                ('F5', 1.0), ('Ab5', 1.0), ('Ab5', 1.0), ('F5', 1.0), ('Ab5', 1.0), ('C5', 1.0),
                ('G5', 0.5), ('Bb5', 0.5), ('Eb6', 1.0), ('C5', 1.0), ('Ab5', 1.0), ('Db5', 1.0),
                ('F5', 1.0), ('Ab5', 1.5), ('C5', 0.5), ('G5', 0.5), ('Bb5', 0.5), ('Eb6', 1.0),
                ('F5', 0.5), ('Ab5', 0.5), ('Db6', 1.0), ('Eb5', 1.0), ('G5', 1.0), ('C5', 1.0),
                ('Ab5', 1.0), ('Ab5', 1.5), ('C5', 0.5), ('Db5', 1.0), ('F5', 1.0), ('Bb5', 1.0),
                ('G5', 1.0), ('F5', 1.5), ('Ab5', 0.5), ('Ab5', 0.5), ('C5', 0.5), ('F6', 1.0),
            ]
            self.bgm_stages['lobby'] = self._synth_cyberpunk_track(96, m_lobby, b_lobby, c_lobby, is_chill=True, soft=True)

        except Exception as e:
            print(f"[SoundManager] Cyberpunk BGM synthesis error: {e}")

    def set_bgm_volume(self, volume):
        """배경음악 음량 설정 (0.0 ~ 1.0)"""
        self.bgm_volume = max(0.0, min(1.0, float(volume)))
        self._apply_bgm_volume()

    def set_sfx_volume(self, volume):
        """효과음 음량 설정 (0.0 ~ 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, float(volume)))
        eff_vol = self.sfx_volume if (self.enabled and self.sfx_enabled) else 0.0
        for name, snd in self.sounds.items():
            try:
                snd.set_volume(1.0 if name == 'combo_layer' else eff_vol)      # 콤보 층은 BGM의 일부(채널 볼륨 _layer_vol로 조절): 효과음을 꺼도/줄여도 같이 죽지 않게
            except Exception:
                pass

    def set_bgm_enabled(self, enabled):
        """배경음악 ON / OFF 설정"""
        self.bgm_enabled = bool(enabled)
        self._apply_bgm_volume()
        if self.bgm_enabled and self.enabled and not self.is_bgm_playing:
            self.play_bgm(self.current_bgm_stage or 'menu')

    def set_sfx_enabled(self, enabled):
        """효과음 ON / OFF 설정"""
        self.sfx_enabled = bool(enabled)
        self.set_sfx_volume(self.sfx_volume)

    def play_menu_bgm(self):
        """오프닝 / 타이틀 / 로비 BGM 재생"""
        self.play_bgm(stage='menu')

    def _sets_ready(self):
        """세 단계(1/2/3) 모두 합성이 끝난 세트 수. 첫 실행처럼 뒤에서 아직 합성 중이면 완성된 세트만 고르게 해서, 한 판 안에서 단계마다 다른 세트가 섞이지 않게 함"""
        counts = []
        for st in (1, 2, 3):
            raw = self.bgm_stages.get(st)
            counts.append(len(raw) if isinstance(raw, list) else (1 if raw is not None else 0))
        return max(1, min(counts))

    def roll_stage_set(self, pref="random"):
        """매 판 시작 시 스테이지(1/2/3단계) 배경음 세트를 하나 고름. pref: "random" 또는 세트 번호(문자열/정수)"""
        n = min(len(STAGE_SET_NAMES), self._sets_ready())
        if pref == "random":
            self.current_set_idx = random.randrange(n)
        else:
            try:
                idx = int(pref)
            except (TypeError, ValueError):
                idx = 0
            self.current_set_idx = max(0, min(n - 1, idx))
        return self.current_set_idx

    def _resolve_bgm_sound(self, stage):
        """bgm_stages[stage]가 세트 목록(리스트)이면 현재 선택된 세트를, 아니면 그대로 반환"""
        raw = self.bgm_stages.get(stage, self.bgm_stages.get(1))
        if isinstance(raw, list):
            if not raw:
                return None
            idx = max(0, min(self.current_set_idx, len(raw) - 1))
            return raw[idx]
        return raw

    def play_bgm(self, stage=1):
        """듀얼 채널 1.8초 부드러운 크로스페이드로 BGM 전환"""
        self._results_due = None
        if not self.bgm_ch_a or not self.bgm_ch_b:
            return
        if stage in (1, "menu", "lobby"):
            self.stop_stingers()                       # 새 판/메뉴 음악이 시작되면 이전 판의 팡파레(승리/패배/탈락)가 겹쳐 울리지 않게
        if self.current_bgm_stage != stage:
            self.reset_duck()                          # 곡이 바뀌면(경기 시작/단계 전환/결과) 덕킹 해제: 위기 중이면 다음 프레임에 다시 걸림

        th = self._bgm_thread
        if stage not in self.bgm_stages and th is not None and th.is_alive():
            self._pending_bgm = stage                  # 아직 합성 중: UI를 멈추지 않고 준비되면 tick()이 시작
            return
        self._pending_bgm = None
        target_snd = self._resolve_bgm_sound(stage)
        if not target_snd:
            return
            
        if self.is_bgm_playing and self.current_bgm_stage == stage:
            if self.active_channel and self.active_channel.get_busy():
                if self._bgm_paused:
                    self.unpause_bgm()                 # 일시정지 중 '다시 시작': 멈춘 채널은 busy로 보이므로 여기서 재개하지 않으면 다음 단계까지 무음
                return
                
        crossfade_ms = 1800
        old_channel = self.active_channel
        new_channel = self.bgm_ch_b if old_channel == self.bgm_ch_a else self.bgm_ch_a
        
        if self._bgm_paused:
            self.unpause_bgm()                         # 멈춰 있던 채널이 남지 않게 (곡 전환 때 이전 채널이 페이드아웃되려면 재생 상태여야 함)
        new_channel.set_volume(self._bgm_eff_volume())

        if not self.is_bgm_playing:
            # 최초 재생 시에는 즉시 시작
            new_channel.play(target_snd, loops=-1)
        else:
            # 곡 전환 시 부드러운 1.8초 크로스페이드
            if old_channel and old_channel.get_busy():
                old_channel.fadeout(crossfade_ms)
            new_channel.play(target_snd, loops=-1, fade_ms=crossfade_ms)
            
        self.active_channel = new_channel
        self.current_bgm_stage = stage
        self.is_bgm_playing = True

    @staticmethod
    def stage_for_alive(alive_count, total_players=100):
        """생존자 '비율'에 따른 BGM 단계: 절반 이하 -> 2단계, 20% 이하 -> 3단계.
        (예전에는 절대 인원(50명/20명)이라 2인 대전도 시작부터 가장 급박한 곡이 나왔음)"""
        ratio = alive_count / max(1, total_players)
        if ratio <= 0.2:
            return 3
        if ratio <= 0.5:
            return 2
        return 1

    def update_bgm_for_alive(self, alive_count, total_players=100):
        """생존자 비율에 따라 동적으로 BGM 악장 전환 (전체의 50% -> 20% 이하)"""
        due = self._results_due
        if due is not None and time.time() >= due:
            self.play_results_bgm()                    # 승/패 음악이 끝났으면 순위표 곡 시작
            return
        if not self.is_bgm_playing:
            return

        # 인게임 상태가 아닌 경우(메뉴 BGM, 순위표 곡)는 생존자 체크로 덮어쓰지 않음
        if self.current_bgm_stage in ('menu', 'results'):
            return
            
        target_stage = self.stage_for_alive(alive_count, total_players)

        if target_stage != self.current_bgm_stage:
            self.play_bgm(stage=target_stage)

    def stop_bgm(self):
        """모든 BGM 채널 정지"""
        self._results_due = None
        self._pending_bgm = None
        if self.bgm_ch_a:
            self.bgm_ch_a.stop()
        if self.bgm_ch_b:
            self.bgm_ch_b.stop()
        self.is_bgm_playing = False
        self.current_bgm_stage = None
        self._bgm_paused = False
        self.reset_duck()
        self._layer_level = 0                                  # 콤보 층도 함께 정리
        self._layer_vol = 0.0
        try:
            pygame.mixer.Channel(3).stop()
        except Exception:
            pass

    def stop_stingers(self):
        """승리/패배 팡파레(채널 5)와 탈락 소리(채널 4)를 멈춤 (새 판/메뉴 음악이 시작될 때)"""
        for n in (4, 5):
            try:
                pygame.mixer.Channel(n).stop()
            except Exception:
                pass

    def pause_bgm(self):
        """배경음악 일시정지 (콤보 하이햇 층도 함께: 안 그러면 멜로디만 멈추고 드럼만 혼자 울림)"""
        self._bgm_paused = True
        if self.bgm_ch_a:
            self.bgm_ch_a.pause()
        if self.bgm_ch_b:
            self.bgm_ch_b.pause()
        try:
            pygame.mixer.Channel(3).pause()
        except Exception:
            pass

    def unpause_bgm(self):
        """배경음악 재개"""
        self._bgm_paused = False
        try:
            pygame.mixer.Channel(3).unpause()
        except Exception:
            pass
        if not (self.enabled and self.bgm_enabled):
            return
        if self.bgm_ch_a:
            self.bgm_ch_a.unpause()
        if self.bgm_ch_b:
            self.bgm_ch_b.unpause()

    def toggle_sound(self):
        """마스터 사운드 토글 (SFX + BGM)"""
        self.enabled = not self.enabled
        self._apply_bgm_volume()
        if self.enabled and self.bgm_enabled and not self.is_bgm_playing:
            self.play_bgm(self.current_bgm_stage or 'menu')
        self.set_sfx_volume(self.sfx_volume)
        return self.enabled

    def _generate_perfect_chime(self, sr=44100):
        """퍼펙트 클리어: 밝게 올라가는 C장조 아르페지오 + 반짝이는 벨 잔향 (자체 합성, 약 1.5초)"""
        notes = [(523.25, 0.00), (659.25, 0.07), (783.99, 0.14), (1046.50, 0.21), (1318.51, 0.30), (1567.98, 0.40), (2093.00, 0.52)]
        total = 1.9
        t = np.arange(int(sr * total)) / sr
        out = np.zeros(len(t), dtype=np.float32)
        for f, start in notes:
            i0 = int(start * sr)
            tt = np.arange(len(t) - i0) / sr
            tone = np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.005 * tt) + 0.15 * np.sin(2 * np.pi * f * 3.01 * tt)
            out[i0:] += (tone * np.exp(-tt * 2.6) * np.minimum(tt / 0.004, 1.0) * 0.26).astype(np.float32)
        for f in (523.25, 659.25, 783.99):                       # 뒤에서 받쳐 주는 C 메이저 코드
            pad = np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.003 * t)
            out += (pad * np.minimum(t / 0.05, 1.0) * np.exp(-t * 1.7) * 0.08).astype(np.float32)
        delay = int(sr * 0.018)
        left = out
        right = out * 0.78 + self._delayed(out, delay) * 0.22
        return self._pack_stereo(left * 0.9, right * 0.9)

    def _generate_defeat_jingle(self, sr=44100):
        """경기가 끝났지만 우승하지 못했을 때: 차분하게 내려오다 마무리되는 짧은 종료 음악 (자체 작곡, Dm 아르페지오 + 패드)"""
        notes = [(587.33, 0.0), (440.00, 0.30), (349.23, 0.60), (293.66, 0.90), (220.00, 1.30)]   # D5 A4 F4 D4 A3
        total = 3.4
        t = np.arange(int(sr * total)) / sr
        out = np.zeros(len(t), dtype=np.float32)
        for f, start in notes:
            i0 = int(start * sr)
            tt = np.arange(len(t) - i0) / sr
            tone = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt) + 0.12 * np.sin(6 * np.pi * f * tt))
            out[i0:] += (tone * np.exp(-tt * 2.2) * np.minimum(tt / 0.01, 1.0) * 0.32).astype(np.float32)
        for f in (146.83, 174.61, 220.00):                    # Dm 패드 (D3 F3 A3)
            pad = np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.004 * t)
            env = np.minimum(t / 0.6, 1.0) * np.exp(-np.maximum(t - 1.0, 0) * 1.1)
            out += (pad * env * 0.10).astype(np.float32)
        delay = int(sr * 0.021)
        left = out
        right = out * 0.8 + self._delayed(out, delay) * 0.2
        return self._pack_stereo(left * 0.9, right * 0.9)

    def _schedule_results_bgm(self, sting_name):
        """승/패 짧은 음악이 끝난 직후부터 순위표 곡(Afterglow)이 서서히 켜지도록 예약 (update_bgm_for_alive가 매 프레임 확인)"""
        snd = self.sounds.get(sting_name)
        length = snd.get_length() if (snd and self.sfx_enabled) else 0.0
        self._results_due = time.time() + length + 0.4

    def play_results_bgm(self):
        """최종 순위표 곡을 3초에 걸쳐 서서히 켬 (이미 재생 중이면 그대로)"""
        self._results_due = None
        if not (self.enabled and self.bgm_enabled) or not self.bgm_ch_a or not self.bgm_ch_b:
            return
        if self.is_bgm_playing and self.current_bgm_stage == 'results':
            return
        self._wait_bgm('results')
        snd = self.bgm_stages.get('results')
        if not snd:
            return
        old = self.active_channel
        ch = self.bgm_ch_b if old == self.bgm_ch_a else self.bgm_ch_a
        for c in (self.bgm_ch_a, self.bgm_ch_b):
            if c is not ch:
                c.stop()
        ch.set_volume(self.bgm_volume)
        ch.play(snd, loops=-1, fade_ms=3000)
        self.active_channel = ch
        self.current_bgm_stage = 'results'
        self.is_bgm_playing = True

    def _play_ending_sting(self, name):
        """경기 종료 음악(승리/패배): 전투 BGM을 멈추고 채널 5에서 재생한 뒤 이어서 순위표 곡을 예약"""
        self.stop_bgm()
        self._schedule_results_bgm(name)
        if not (self.enabled and self.sfx_enabled):
            return
        snd = self.sounds.get(name)
        if snd:
            try:
                ch = pygame.mixer.Channel(5)
                ch.set_volume(self.sfx_volume)
                ch.play(snd)
            except Exception:
                snd.set_volume(self.sfx_volume)
                snd.play()

    def play_defeat(self):
        """경기 종료(내가 우승하지 못함): 전투 BGM을 멈추고 종료 음악 재생 (이어서 순위표 곡)"""
        self._play_ending_sting('defeat')

    def play_victory(self):
        """1위 최종 우승 시 전투 BGM을 즉시 정지하고 화려한 챔피언 빅토리 팡파레 재생"""
        self._play_ending_sting('victory')

    def play_gameover(self):
        """탈락 시 전투 BGM 볼륨을 낮추고 게임 오버 사운드 재생"""
        if not (self.enabled and self.sfx_enabled):
            return
        snd = self.sounds.get('gameover')
        if snd:
            try:
                ch = pygame.mixer.Channel(4)
                ch.set_volume(self.sfx_volume)
                ch.play(snd)
            except Exception:
                snd.set_volume(self.sfx_volume)
                snd.play()

    # 블록 종류별 음높이 (반음 단위): 낮은 I부터 높은 L까지 - 착지 소리만으로도 어떤 블록인지 어렴풋이 느껴짐
    SOUND_VARIANTS = {'lock': ['lock', 'lock2', 'lock3']}   # 블록 정보 없이 호출될 때만 사용

    PIECE_SEMITONES = {'I': -4, 'O': -2, 'T': 0, 'S': 2, 'Z': 3, 'J': 5, 'L': 7}
    # 콤보 단계별 음높이 사다리 (장음계): 콤보가 이어질수록 소리가 한 음씩 올라감 (최대 8콤보 단계)
    COMBO_LADDER = [0, 2, 4, 5, 7, 9, 11, 12, 14]

    @staticmethod
    def _delayed(mono, n):
        """mono를 n샘플 늦춤 (앞은 0으로 채움). np.roll은 끝 소리를 맨 앞으로 돌려 붙여 오른쪽 채널 첫 순간에 '틱'이 났음"""
        n = int(n)
        if n <= 0:
            return mono.copy()
        out = np.zeros_like(mono)
        out[n:] = mono[:-n]
        return out

    def _pitch_variant(self, snd, semitones):
        """Sound를 반음 단위로 음높이 변경 (재생 속도 변경 방식: 높이면 짧아지고 낮추면 길어짐)"""
        arr = pygame.sndarray.array(snd).astype(np.float32)
        if arr.ndim == 1:
            arr = np.column_stack((arr, arr))
        factor = 2.0 ** (semitones / 12.0)
        n_out = max(2, int(len(arr) / factor))
        x_old = np.arange(len(arr), dtype=np.float32)
        x_new = np.linspace(0, len(arr) - 1, n_out, dtype=np.float32)
        if arr.shape[1] == 2 and np.array_equal(arr[:, 0], arr[:, 1]):
            ch0 = np.interp(x_new, x_old, arr[:, 0])                   # 좌우가 같은 소리는 한 채널만 계산해 복사 (결과는 같고 계산은 절반)
            out = np.column_stack((ch0, ch0))
        else:
            out = np.column_stack([np.interp(x_new, x_old, arr[:, ch]) for ch in range(arr.shape[1])])
        return pygame.mixer.Sound(buffer=np.clip(out, -32767, 32767).astype(np.int16).tobytes())

    def _generate_pitched_variants(self):
        """블록별 착지/락 소리 + 콤보 단계별 삭제음/차임 생성"""
        for piece, st in self.PIECE_SEMITONES.items():
            for base in ('lock', 'lock2', 'lock3', 'land'):
                self.sounds[f"{base}_{piece}"] = self._pitch_variant(self.sounds[base], st)
        for name in ('clear', 'quad', 'tspin'):
            for i, st in enumerate(self.COMBO_LADDER):
                self.sounds[f"{name}_c{i}"] = self._pitch_variant(self.sounds[name], st)
        # 콤보 차임: 콤보가 오를수록 음이 올라가는 짧은 종소리
        sr = 44100
        t = np.arange(int(sr * 0.24)) / sr
        for i in range(1, len(self.COMBO_LADDER)):
            f = 523.25 * (2.0 ** (self.COMBO_LADDER[i] / 12.0))
            bell = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t)
                    + 0.15 * np.sin(6 * np.pi * f * t)) * np.exp(-t * 13.0) * 0.33
            self.sounds[f"combo_{i}"] = self._pack_sound(bell)

    WARN_SOUNDS = frozenset({'warning', 'hit_1', 'hit_2', 'hit_3', 'heartbeat'})

    def _dedicated_channel(self, name):
        """예약해 두고 쓰지 않던 채널 0~2: 0 = 줄 삭제/쿼드/T-스핀, 1 = 경보/피격, 2 = 로봇 아나운서. 해당 없으면 None (빈 채널에서 재생)"""
        try:
            if name.startswith(("clear_c", "quad_c", "tspin_c")) or name in ("clear", "quad", "tspin"):
                return pygame.mixer.Channel(0)
            if name in self.WARN_SOUNDS:
                return pygame.mixer.Channel(1)
            if name.startswith("vo_"):
                return pygame.mixer.Channel(2)
        except Exception:
            pass
        return None

    def set_warn_scale(self, scale):
        self.warn_scale = max(0.0, min(1.0, float(scale)))

    def play(self, sound_name, piece=None, combo=None):
        """효과음 재생. piece: 블록 종류에 따라 음높이 변경(lock/land), combo: 콤보 단계에 따라 음높이 변경(clear/quad/tspin)"""
        if piece and sound_name in ('lock', 'land'):
            if sound_name == 'lock':
                sound_name = random.choice(['lock', 'lock2', 'lock3']) + f"_{piece}"
            else:
                sound_name = f"land_{piece}"
        elif combo is not None and sound_name in ('clear', 'quad', 'tspin'):
            sound_name = f"{sound_name}_c{min(max(0, combo), len(self.COMBO_LADDER) - 1)}"
        elif sound_name == 'combo':
            sound_name = f"combo_{min(max(1, combo or 1), len(self.COMBO_LADDER) - 1)}"
        elif sound_name == 'b2b':
            sound_name = f"b2b_{min(max(1, combo or 1), 5)}"
        elif sound_name == 'ko_orb':
            sound_name = f"ko_orb_{min(max(1, combo or 1), 8)}"
        if not (self.enabled and self.sfx_enabled) or self.sfx_volume <= 0.001:
            return
        if sound_name.startswith("vo_"):                          # 로봇 아나운서: 설정이 켜져 있을 때만, 0.8초 쿨다운
            now_ = time.time()
            if not self.announcer or now_ - self._vo_last < 0.8:
                return
            self._vo_last = now_
        vol = self.sfx_volume * (self.warn_scale if sound_name in self.WARN_SOUNDS else 1.0)
        if vol <= 0.001:
            return
        variants = self.SOUND_VARIANTS.get(sound_name)
        if variants:
            sound_name = random.choice(variants)
        snd = self.sounds.get(sound_name)
        if snd:
            try:
                snd.set_volume(vol)
                ch = self._dedicated_channel(sound_name)
                if ch is not None:
                    ch.play(snd)                                      # 예약 채널: 같은 계열의 앞 소리는 끊고 새 소리를 바로 냄
                else:
                    snd.play()
            except Exception:
                pass

