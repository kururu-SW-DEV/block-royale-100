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

import time
import threading
import pygame
import numpy as np
import random

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
        self._results_due = None       # 순위표 곡을 시작할 시각(승/패 음악이 끝난 뒤)
        self._bgm_bake = 0.60          # BGM 합성 시 곡 자체에 반영하는 기준 음량 (재생 음량 설정과 무관하게 항상 동일)
        self._bgm_thread = None
        self.sfx_volume = 0.70
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
            
            # BGM 4곡(약 0.8초)은 백그라운드에서 합성하고, 그동안 효과음을 만듦 -> 창이 더 빨리 뜸
            self._bgm_thread = threading.Thread(target=self._generate_all_bgm_stages, daemon=True)
            self._bgm_thread.start()
            self._generate_all_arcade_sounds()
            self._generate_pitched_variants()
            self._wait_bgm('menu')                     # 타이틀 화면 음악만 준비되면 시작, 나머지 곡은 뒤에서 계속 생성
        except Exception as e:
            print(f"[SoundManager] Audio initialization failed: {e}. Audio disabled.")
            self.enabled = False

    def _wait_bgm(self, stage, timeout=6.0):
        """해당 BGM이 백그라운드 합성으로 준비될 때까지 잠깐 대기 (이미 준비됐으면 즉시 반환)"""
        t0 = time.time()
        while stage not in self.bgm_stages and time.time() - t0 < timeout:
            th = self._bgm_thread
            if th is None or not th.is_alive():
                break
            time.sleep(0.01)

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
        c_right = np.roll(clear_mono, int(sr * 0.012))
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
        t_right = np.roll(quad_mono, int(sr * 0.015))
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
        right = master_mono * 0.70 + np.roll(master_mono, delay_s) * 0.30

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
            self.bgm_stages[1] = self._synth_cyberpunk_track(128, m1, b1, c1, is_chill=False)

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
            self.bgm_stages[2] = self._synth_cyberpunk_track(142, m2, b2, c2, is_chill=False)

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
            self.bgm_stages[3] = self._synth_cyberpunk_track(156, m3, b3, c3, is_chill=False)

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
            self.bgm_stages[1] = [self.bgm_stages[1], self._synth_cyberpunk_track(124, m4_1, b4, c4, is_chill=False)]
            self.bgm_stages[2] = [self.bgm_stages[2], self._synth_cyberpunk_track(138, m4_2, b4, c4, is_chill=False)]
            self.bgm_stages[3] = [self.bgm_stages[3], self._synth_cyberpunk_track(152, m4_3, b4, c4, is_chill=False)]

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
        eff_vol = self.bgm_volume if (self.enabled and self.bgm_enabled) else 0.0
        if self.active_channel:
            self.active_channel.set_volume(eff_vol)

    def set_sfx_volume(self, volume):
        """효과음 음량 설정 (0.0 ~ 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, float(volume)))
        eff_vol = self.sfx_volume if (self.enabled and self.sfx_enabled) else 0.0
        for snd in self.sounds.values():
            try:
                snd.set_volume(eff_vol)
            except Exception:
                pass

    def set_bgm_enabled(self, enabled):
        """배경음악 ON / OFF 설정"""
        self.bgm_enabled = bool(enabled)
        eff_vol = self.bgm_volume if (self.enabled and self.bgm_enabled) else 0.0
        if self.active_channel:
            self.active_channel.set_volume(eff_vol)
        if self.bgm_enabled and self.enabled and not self.is_bgm_playing:
            self.play_bgm(self.current_bgm_stage or 'menu')

    def set_sfx_enabled(self, enabled):
        """효과음 ON / OFF 설정"""
        self.sfx_enabled = bool(enabled)
        self.set_sfx_volume(self.sfx_volume)

    def play_menu_bgm(self):
        """오프닝 / 타이틀 / 로비 BGM 재생"""
        self.play_bgm(stage='menu')

    def roll_stage_set(self, pref="random"):
        """매 판 시작 시 스테이지(1/2/3단계) 배경음 세트를 하나 고름. pref: "random" 또는 세트 번호(문자열/정수)"""
        n = len(STAGE_SET_NAMES)
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

        self._wait_bgm(stage)                          # 아직 합성 중인 곡이면 잠깐 기다림
        target_snd = self._resolve_bgm_sound(stage)
        if not target_snd:
            return
            
        if self.is_bgm_playing and self.current_bgm_stage == stage:
            if self.active_channel and self.active_channel.get_busy():
                return
                
        crossfade_ms = 1800
        old_channel = self.active_channel
        new_channel = self.bgm_ch_b if old_channel == self.bgm_ch_a else self.bgm_ch_a
        
        eff_vol = self.bgm_volume if (self.enabled and self.bgm_enabled) else 0.0
        new_channel.set_volume(eff_vol)

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
        if self.bgm_ch_a:
            self.bgm_ch_a.stop()
        if self.bgm_ch_b:
            self.bgm_ch_b.stop()
        self.is_bgm_playing = False
        self.current_bgm_stage = None

    def pause_bgm(self):
        """배경음악 일시정지"""
        if self.bgm_ch_a:
            self.bgm_ch_a.pause()
        if self.bgm_ch_b:
            self.bgm_ch_b.pause()

    def unpause_bgm(self):
        """배경음악 재개"""
        if not (self.enabled and self.bgm_enabled):
            return
        if self.bgm_ch_a:
            self.bgm_ch_a.unpause()
        if self.bgm_ch_b:
            self.bgm_ch_b.unpause()

    def toggle_sound(self):
        """마스터 사운드 토글 (SFX + BGM)"""
        self.enabled = not self.enabled
        eff_bgm_vol = self.bgm_volume if (self.enabled and self.bgm_enabled) else 0.0
        if self.active_channel:
            self.active_channel.set_volume(eff_bgm_vol)
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
        right = out * 0.78 + np.roll(out, delay) * 0.22
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
        right = out * 0.8 + np.roll(out, delay) * 0.2
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

    def play_defeat(self):
        """경기 종료(내가 우승하지 못함): 전투 BGM을 멈추고 종료 음악 재생 (이어서 순위표 곡)"""
        if not (self.enabled and self.sfx_enabled):
            self.stop_bgm()
            self._schedule_results_bgm('defeat')
            return
        self.stop_bgm()
        self._schedule_results_bgm('defeat')
        snd = self.sounds.get('defeat')
        if snd:
            try:
                ch = pygame.mixer.Channel(5)
                ch.set_volume(self.sfx_volume)
                ch.play(snd)
            except Exception:
                snd.set_volume(self.sfx_volume)
                snd.play()

    def play_victory(self):
        """1위 최종 우승 시 전투 BGM을 즉시 정지하고 화려한 챔피언 빅토리 팡파레 재생"""
        if not (self.enabled and self.sfx_enabled):
            self.stop_bgm()
            self._schedule_results_bgm('victory')
            return
        self.stop_bgm()
        self._schedule_results_bgm('victory')
        snd = self.sounds.get('victory')
        if snd:
            try:
                ch = pygame.mixer.Channel(5)
                ch.set_volume(self.sfx_volume)
                ch.play(snd)
            except Exception:
                snd.set_volume(self.sfx_volume)
                snd.play()

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

    def _pitch_variant(self, snd, semitones):
        """Sound를 반음 단위로 음높이 변경 (재생 속도 변경 방식: 높이면 짧아지고 낮추면 길어짐)"""
        arr = pygame.sndarray.array(snd).astype(np.float32)
        if arr.ndim == 1:
            arr = np.column_stack((arr, arr))
        factor = 2.0 ** (semitones / 12.0)
        n_out = max(2, int(len(arr) / factor))
        x_old = np.arange(len(arr), dtype=np.float32)
        x_new = np.linspace(0, len(arr) - 1, n_out, dtype=np.float32)
        out = np.column_stack([np.interp(x_new, x_old, arr[:, ch]) for ch in range(arr.shape[1])])
        return pygame.mixer.Sound(buffer=np.clip(out, -32767, 32767).astype(np.int16).tobytes())

    def _generate_pitched_variants(self):
        """블록별 착지/락 소리 + 콤보 단계별 삭제음/차임 생성"""
        for piece, st in self.PIECE_SEMITONES.items():
            for base in ('lock', 'lock2', 'land'):
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

    def play(self, sound_name, piece=None, combo=None):
        """효과음 재생. piece: 블록 종류에 따라 음높이 변경(lock/land), combo: 콤보 단계에 따라 음높이 변경(clear/quad/tspin)"""
        if piece and sound_name in ('lock', 'land'):
            if sound_name == 'lock':
                sound_name = random.choice(['lock', 'lock2']) + f"_{piece}"
            else:
                sound_name = f"land_{piece}"
        elif combo is not None and sound_name in ('clear', 'quad', 'tspin'):
            sound_name = f"{sound_name}_c{min(max(0, combo), len(self.COMBO_LADDER) - 1)}"
        elif sound_name == 'combo':
            sound_name = f"combo_{min(max(1, combo or 1), len(self.COMBO_LADDER) - 1)}"
        if not (self.enabled and self.sfx_enabled) or self.sfx_volume <= 0.001:
            return
        variants = self.SOUND_VARIANTS.get(sound_name)
        if variants:
            sound_name = random.choice(variants)
        snd = self.sounds.get(sound_name)
        if snd:
            try:
                snd.set_volume(self.sfx_volume)
                snd.play()
            except Exception:
                pass

