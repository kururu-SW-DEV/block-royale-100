"""
Block Royale 100 - Battle Royale Manager
참가자 관리, 타겟팅 로직, K.O. 및 순위 산정, 스크린 셰이크 및 이펙트 이벤트 연동
"""

import time
import math
import random
import challenges
from block_engine import BlockEngine
from ai_bot import AIBot
import bot_brain
import bot_pool
from config import bot_display_name, BOT_TRAITS, BOT_TRAIT_WEIGHTS, TARGET_MODES, DEFAULT_TARGET_MODE, BOARD_HEIGHT, ATTACKER_BONUS, BADGE_TIERS, MULTI_TARGET_MAX, MAX_INCOMING_GARBAGE

def get_badge_info(ko_count):
    """K.O. 수 -> (배지 단계, 공격력 보너스 배율, 표시 문자열). 단계별 기준은 config.BADGE_TIERS"""
    level = 0
    for lv, (need, _bonus) in enumerate(BADGE_TIERS):
        if ko_count >= need:
            level = lv
    bonus = BADGE_TIERS[level][1]
    return level, bonus, f"{int(round(bonus * 100))}%"


_CG_CHARS = set("IJLOSTZG.")


def grid_rows(grid):
    """엔진 보드 -> 문자열 20줄 (블록 종류 문자, 빈칸은 '.')"""
    return ["".join(c if c else "." for c in row) for row in grid]


def piece_state(engine):
    """조작 중인 블록 (종류, 회전, x, y). 없으면 None"""
    if engine.current_piece and not engine.game_over:
        return (engine.current_piece, engine.current_rot, engine.current_x, engine.current_y)
    return None


BOT_SEARCH_BUDGET = 0.008      # 프레임당 봇 전원의 탐색 시간 상한(초). 100명이 동시에 생각해도 화면이 끊기지 않게 함


class BattleRoyaleMatch:
    def __init__(self, total_players=100, local_player_id="P1", local_player_name="Player", net_mgr=None, initial_players=None, sound_mgr=None, bot_difficulty="mixed", attacks_enabled=True,
                 practice=False, seed=None, daily=None, weekly=None, mutator=None, rival_id=None, ghost=None, challenge=None, team_mode=False):
        self.race_ghost = None                         # 고스트 레이스: 내 최고 판을 재생하는 ReplayPlayer (앱이 지정, 없으면 None)
        self.team_mode = bool(team_mode) and not practice and total_players >= 4      # 팀전(2팀, 혼자 하는 배틀로얄만)
        self.teams = {}                                # 팀전일 때 플레이어 id -> 0/1 (나는 0)
        self.team_won = None                           # 팀전 결과: 내 팀이 이겼는지 (끝나기 전에는 None)
        self.practice = bool(practice)                 # 연습 모드: 봇 없이 혼자 (쓰레기 줄을 직접 넣어 보며 연습), 전적에 기록 안 함, 죽으면 판이 초기화
        self.daily = daily                             # 오늘의 도전 날짜 키("YYYYMMDD") 또는 None. 같은 날은 같은 블록 순서와 상대 구성
        self.weekly = weekly                           # 주간 변형 규칙의 주 키("2026W40") 또는 None
        self.mutator = dict(mutator) if mutator else None   # 이번 경기에 적용 중인 변형 규칙 (config.WEEKLY_MUTATORS 항목)
        self.rival_id = rival_id                       # 나를 자주 탈락시킨 라이벌 봇 id (없으면 None)
        self.challenge = challenge                     # challenges.ChallengeTracker (연습/오늘의 도전/주간 변형일 때만, 없으면 None)
        self.challenge_kind = None                     # "practice" / "daily" / "weekly" (앱이 지정)
        self.brief_open = False                        # 시작 전 브리핑 카드가 열려 있는 동안 경기는 시작하지 않음
        self.practice_focus = None                     # 연습: N 키로 고른 과제 id (없으면 못 깬 첫 과제)
        self.ta_mode = None                            # 연습 타임어택 종류 (challenges.TA_MODES의 id, 꺼져 있으면 None). Y 키로 바꿈
        self.ta_t0 = None                              # 타임어택 시작 시각
        self.ta_n = 0                                  # 타임어택 진행량 (쿼드 수 / 지운 줄 / T-스핀 수)
        self.ta_last = None                            # 방금 끝난 타임어택 기록(초)
        self.ta_bests = {}                             # 종류별 최고 기록(초), 앱이 저장된 값을 넣어 줌
        self._prac_locks = 0                           # 연습: 이미 센 블록 고정 횟수 (엔진의 lock_events와 비교)
        self._ta_auto_done = False                     # 모든 과제를 깬 뒤 타임어택을 자동으로 켠 적이 있는가 (한 경기에 한 번)
        self.challenge_saved = []                       # 새로 달성해 앱이 저장해야 하는 과제 id 목록
        self.rival_defeated = False                    # 이번 경기에서 라이벌을 내가 처치했는가 (복수 성공)
        # ---- v1.1.6 도파민 연출 상태
        self._prev_combo = -1                          # 콤보 끊김 알림용 (이전 프레임의 콤보)
        self._ko_events = []                           # 예약된 K.O. 후속 연출 (구슬이 K.O. 칸에 도착하는 시점에 소리/배지 승급)
        self._top_announced = set()                    # 이미 알린 TOP N
        self._final_announced = False
        self.final_opp_id = None                       # 결승 1:1 상대 (카드에 금빛 맥박)
        self.live_ach = {}                             # {업적 id: 이름} 경기 중에 알려 줄 수 있는 아직 못 얻은 업적 (앱이 지정, 저장은 경기 끝에)
        self.live_ach_done = set()
        self.first_ko_ever = False                     # 평생 첫 K.O.를 기다리는 중인가 (앱이 지정)
        self.cancel_seq = 0                            # 줄 지우기로 막은 공격 피드백 (렌더러가 읽음): 횟수와 (시각, 막은 줄 수)
        self.cancel_last = (0.0, 0)
        self.impact_t = 0.0                            # 아주 큰 순간의 짧은 번쩍임 (렌더러가 읽음)
        self.impact_power = 0.0
        self.pc_count = 0                              # 퍼펙트 클리어 횟수 / 마지막 시각 (금빛 쓸어올림 연출)
        self.pc_t = 0.0
        self.max_b2b_chain = 0
        self.shake_dir = None                          # 방향성 흔들림 (None이면 방향 없는 떨림)
        self.shake_t0 = 0.0
        self.ko_times = []                             # 내 K.O. 경기 시각 (명장면 판정)
        self.clutch_times = []                         # 내 위기 탈출 경기 시각
        self.bounty_id = None                          # 현상금 봇 (처치하면 보너스)
        self.bounty_claimed = False
        self.net_unstable = set()                      # (호스트) 신호가 끊긴 참가자 ID: 미니 카드에 '연결 불안정' 표시
        self.net_unstable_self = False                 # (참가자) 호스트에게서 몇 초째 신호가 없음: 화면 아래에 안내
        self.custom_rules = None                       # 커스텀 규칙(쓰레기 배율/낙하 속도/배지). 기본값이 아닐 때만 dict, 이 경기는 전적/점수표/경험치에 기록하지 않음
        self.bounty_kills = 0                          # 이번 판에 처치한 골든 타깃 수 (경험치 +30씩, 공격력 보너스는 없음)
        self._bounty_rng = random.Random()
        self.bests = {}                                # 시작 때의 개인 기록 {"max_ko", "best_rank", "best_score"} (경기 중 근접 실패/돌파 알림용)
        self._live_rec = set()                         # 이미 알린 기록 알림 키
        self._layer_seen = -1                          # 콤보 음악 층 단계
        self.ghost = ghost                             # 오늘의 도전 지난 최고 기록 {"rank","secs","tries"} 또는 None (경기 중 비교 표시용)
        if seed is not None:
            random.seed(seed)                          # 봇 구성/난이도 선택이 같은 날 같게
        self.attacks_enabled = bool(attacks_enabled) and not self.practice   # False: 서바이벌 모드 (서로 공격/쓰레기 줄/K.O. 없이 각자 끝까지 생존)
        self.total_players = max(2, min(100, total_players))
        self.local_player_id = local_player_id
        self.local_player_name = local_player_name
        self.net_mgr = net_mgr
        self.initial_players = initial_players  # 클라이언트가 호스트로부터 전달받은 슬롯 목록
        self.sound_mgr = sound_mgr
        self.bot_difficulty = bot_difficulty
        
        # 로컬 플레이어 블록 엔진
        self.local_engine = BlockEngine(seed=seed)
        self.local_color = 0           # 내 이름 색 번호 (main에서 설정)
        self.local_target_mode = DEFAULT_TARGET_MODE
        self.local_manual_target_id = None
        self.local_ko_count = 0
        self.local_is_alive = True
        self.local_rank = 0
        self.is_paused = False
        
        # 관전 모드 상태
        self.is_spectating = False
        self.spectate_target_id = None
        self.spectate_notice = None       # 관전 대상이 탈락해 다른 대상으로 넘어갔을 때의 알림 {text, sub, t0}
        
        # 참가자 슬롯 관리
        self.players = {}
        
        # 탈락 순서 기록 (마지막 남은 사람이 1위)
        self.alive_count = self.total_players
        self.next_rank_to_assign = self.total_players
        self.match_finished = False
        self.winner_id = None
        
        # 공격 궤적 이펙트 리스트: [(from_id, to_id, lines, start_time, duration)]
        self.attack_effects = []
        self.fx_low = False                        # True면 화면이 느려 봇끼리의 공격 연출을 생략 (앱이 프레임 시간을 보고 설정)
        
        # e-스포츠 통계 및 페이즈 마일스톤 관리
        self._bot_rr = 0
        self.elapsed = 0.0  # 경기 진행 시간 (dt 누적: 일시정지 시 멈춤)
        self.local_survival_sec = None   # 내가 탈락/우승한 순간의 시간 (이후 통계는 이 값으로 고정)
        self.frozen_stats = None         # 탈락/우승 순간의 (APM, LPM) 스냅샷
        self.total_attacks_sent = 0
        self.phase = 1
        
        # 위기 탈출(마지막 버티기) 보상 추적
        self._danger_since = None         # 스택이 위험 높이 이상이 된 경기 시각 (아니면 None)
        self._last_clutch = -1e9          # 마지막으로 보상을 준 경기 시각
        self._last_beat = -1e9            # 마지막 위기 박동음 재생 시각
        self.local_killer_id = None       # 나를 탈락시킨 상대 (없으면 None: 자멸/시간 압박 등)
        self.timeline = []                # 1초마다 (경기 시각, 생존자 수, 내 스택 높이, 받을 공격) — 결과 화면 그래프용
        self._tl_t = 0.0

        # 시각 연출: 화면 흔들림 및 팝업 텍스트
        self.screen_shake = 0.0
        self.ko_orbs = []         # K.O. 연출: 처치한 상대 카드에서 K.O. 칸으로 날아가는 빛 구슬 [{"victim": id, "t0": 시각}]
        self.floating_texts = []  # dict: text, color, birth, duration, size
        self.local_assists = 0            # K.O. 기여 횟수: 내가 4줄 이상 보내 둔 상대를 다른 플레이어가 마무리한 경우 (배지 보상은 없음)
        self._auto_lock = None            # 자동 조준 락온: (대상 id, 고정한 시각)
        self.practice_done = set()        # 연습 과제 중 완료한 번호
        self.drill_on = False             # 연습 압박 드릴: 시간이 지날수록 더 큰 쓰레기 줄이 주기적으로 들어옴 (V 키)
        self.drill_t0 = 0.0               # 이번 드릴 시작 시각(elapsed 기준)
        self.drill_next = 0.0             # 다음 공격 시각
        self.drill_best = 0               # 가장 오래 버틴 시간(초): 앱이 설정에서 읽어 넣고 갱신분을 저장
        self.drill_last = 0               # 방금 끝난 드릴에서 버틴 시간(초)
        self.local_hits_from = {}         # 내가 받은 공격 줄 수: 보낸 사람 id -> 합계 (결과 화면 "패인 한 줄"용)
        self._hit_agg = None              # 1초 안에 연달아 받은 피격을 한 토스트로 합치기 위한 상태
        self.events = []                  # 사람 테스트용 경기 로그(설정에서 켠 경우만 기록): (경기 시각, 종류, 내용)
        self.log_enabled = False
        self.commentary = []      # 전광판 중계 기록: dict(text, color, birth)
        
        self._setup_participants()
        self._assign_teams()
        self._apply_mutator()
        if self.practice:                                  # 연습은 내부적으로 더미 상대 1명을 둔 2인 구성이라 인원 수를 보여 주면 틀린 안내가 됨
            self.add_commentary("연습 시작!  G로 쓰레기 받기 · N으로 과제 고르기 · Y로 타임어택", (120, 235, 255))
        elif not self.attacks_enabled:
            self.add_commentary(f"서바이벌 시작!  {self.total_players}명 중 끝까지 생존", (120, 235, 255))
        else:
            self.add_commentary(f"경기 시작!  {self.total_players}명 배틀로얄", (120, 235, 255))
        if self.mutator:
            self.add_commentary(f"주간 변형: {self.mutator['name']} - {self.mutator['desc']}", (255, 190, 90), prio=1)
        if self.daily and self.ghost:
            gs = int(self.ghost["secs"])
            self.add_commentary(f"오늘의 도전 {self.ghost['tries'] + 1}회째 · 지난 최고 {self.ghost['rank']}위 ({gs // 60}:{gs % 60:02d})  생존자 칸에서 기록과 비교", (255, 215, 90), prio=1)
        if self.rival_id in self.players and not self.practice:
            self.add_commentary(f"라이벌 등장!  {self._short_name(self.rival_id)} (◆ 표시)", (255, 170, 80), prio=1)

    def _apply_mutator(self):
        """주간 변형 규칙 적용 (후반 증폭 시작 시각, 퍼펙트 클리어 공격 줄 수). NEXT 개수는 렌더러가 mutator를 읽어 처리"""
        m = self.mutator
        if not m:
            return
        if "escalation_start" in m:
            self.ESCALATION_START = float(m["escalation_start"])      # 인스턴스 값으로 덮어씀 (클래스 값은 그대로)
        if "perfect_attack" in m:
            self.local_engine.perfect_clear_attack = int(m["perfect_attack"])
            for p in self.players.values():
                bot = p.get("bot")
                eng = getattr(bot, "engine", None)
                if eng is not None:
                    eng.perfect_clear_attack = int(m["perfect_attack"])

    def get_combat_stats(self):
        """실시간 e-스포츠 지표 (APM: 분당 공격력, LPM: 분당 라인 클리어, 경기 시간) 산출"""
        if self.frozen_stats is not None:      # 탈락/우승 후에는 기록을 그대로 고정
            apm, lpm = self.frozen_stats
            elapsed = max(1.0, self.local_survival_sec)
        else:
            elapsed = max(1.0, self.elapsed)
            apm = (self.total_attacks_sent / elapsed) * 60.0
            lpm = (self.local_engine.lines_cleared_total / elapsed) * 60.0
        m = int(elapsed // 60)
        s = int(elapsed % 60)
        return apm, lpm, f"{m:02d}:{s:02d}"

    def freeze_local_stats(self):
        """내 경기가 끝난 순간(탈락 또는 우승)의 시간과 지표를 고정"""
        if self.local_survival_sec is not None:
            return
        elapsed = max(1.0, self.elapsed)
        self.local_survival_sec = self.elapsed
        self.frozen_stats = ((self.total_attacks_sent / elapsed) * 60.0,
                             (self.local_engine.lines_cleared_total / elapsed) * 60.0)

    def survival_seconds(self):
        return self.local_survival_sec if self.local_survival_sec is not None else self.elapsed

    def add_floating_text(self, text, color, duration=2.0, size=24, category="normal", tier=None):
        """tier: 액션 배너의 크기 단계 (1 작게 / 2 크게 / 3 가장 크게+금빛). 안 주면 size로 정함(30 이상 2, 40 이상 3). 같은 순간에 여러 배너가 나오면 tier가 높은 것이 메인"""
        if tier is None:
            tier = 3 if size >= 40 else (2 if size >= 30 else 1)
        self.floating_texts.append({
            "text": text,
            "color": color,
            "birth": time.time(),
            "duration": duration,
            "size": size,
            "category": category,
            "tier": tier,
        })

    def log_event(self, kind, **info):
        """사람 테스트용 경기 로그에 이벤트 한 줄 기록 (log_enabled일 때만, 최대 3000개)"""
        if self.log_enabled and len(self.events) < 3000:
            self.events.append({"t": round(self.elapsed, 1), "kind": kind, **info})

    def match_log(self):
        """경기 로그 내용 (JSON 저장용): 설정/규칙 값, 1초 타임라인, 이벤트, 결과"""
        return {
            "version": 1, "total_players": self.total_players, "bot_difficulty": self.bot_difficulty, "attacks": bool(self.attacks_enabled),
            "target_mode_final": self.local_target_mode, "elapsed": round(self.elapsed, 1), "alive_at_end": self.alive_count,
            "rank": getattr(self, "local_rank", 0), "kos": self.local_ko_count, "assists": self.local_assists,
            "hits_from": {self._short_name(k): v for k, v in self.local_hits_from.items()},
            "death_attackers": getattr(self, "local_death_attackers", None),
            "timeline_fields": ["t", "alive", "my_stack", "incoming"], "timeline": [list(x) for x in (getattr(self, "timeline", None) or [])],
            "events": self.events,
        }

    def add_commentary(self, text, color=(255, 190, 70), prio=0, mine=False):
        """상단 전광판에 표시할 경기 중계 한 줄. prio=1(결승/우승/페이즈 등 중요 소식)은 대기 중인 일반 소식보다 먼저 방송됨. mine=True(내 기술/내 K.O.)는 대기열이 밀려도 일반 소식보다 나중에 버려짐"""
        self._commentary_seq = getattr(self, "_commentary_seq", 0) + 1
        self.commentary.append({"text": text, "color": color, "birth": time.time(), "seq": self._commentary_seq, "prio": prio, "mine": bool(mine)})
        if len(self.commentary) > 40:
            del self.commentary[:-40]

    def _short_name(self, pid, n=9):
        return str(self.players.get(pid, {}).get("name", "?"))[:n]

    shake_scale = 1.0                  # 설정의 화면 흔들림 배율 (0=끔, 0.4=약하게, 1.0=보통). 앱이 경기 시작 때 지정

    def trigger_screen_shake(self, amount=8.0, direction=None):
        """화면 흔들림. direction=(dx, dy)면 그 축으로 감쇠 사인파처럼 떨림(쿼드는 세로 펀치, 피격은 아래쪽), 없으면 방향 없는 떨림"""
        amt = amount * self.shake_scale
        if amount >= 8.0 and self.shake_scale > 0 and self.local_is_alive and getattr(self, "rumble_cb", None) is not None:
            self.rumble_cb(min(1.0, amount / 18.0))                    # 큰 순간(쿼드/T-스핀/K.O./피격)은 패드도 진동: 흔들림 '약하게'에서도 같은 세기 (흔들림이 '끔'이면 진동도 없음), 탈락 뒤 관전 중에는 없음
        if amt >= self.screen_shake:
            self.screen_shake = amt
            self.shake_dir = direction if (direction and amt > 0) else None
            self.shake_t0 = time.time()

    def trigger_impact(self, power=1.0):
        """아주 큰 순간(퍼펙트/T-스핀 트리플/결승/첫 K.O.)에 화면을 아주 짧게(약 70ms) 번쩍이고 파티클을 잠깐 늦춤. 경기 로직은 멈추지 않음. 렌더러가 흔들림 설정이 '끔'이면 그리지 않음"""
        self.impact_t = time.time()
        self.impact_power = float(power)

    def _duck_bgm(self, factor):
        fn = getattr(self.sound_mgr, "set_duck", None) if self.sound_mgr else None
        if fn:
            fn(factor)

    # 배틀로얄 후반 공격력 증폭: 강한 봇끼리 오래 버티는 교착을 막기 위해, 이 시간(초)이 지나면 1분마다 공격 줄 수가 20%씩 늘어남 (최대 3배). None이면 끔
    BATTLE_PRESSURE_START = 540.0     # 배틀로얄 후반 시간 압박 시작(초)
    MAX_BOT_FX = 8                     # 나와 무관한 봇끼리의 공격 빔을 동시에 그릴 최대 개수
    ESCALATION_START = 300.0
    ESCALATION_PER_MIN = 0.20
    ESCALATION_MAX = 3.0

    CUSTOM_GARBAGE = {"half": 0.5, "normal": 1.0, "heavy": 1.5}
    CUSTOM_GRAVITY = {"slow": 1.4, "normal": 1.0, "fast": 0.7}          # 낙하 간격에 곱함 (느리게 = 간격이 길어짐)

    def _custom(self, key, default=None):
        return (self.custom_rules or {}).get(key, default)

    def attack_multiplier(self):
        if self.ESCALATION_START is None or self.elapsed < self.ESCALATION_START:
            return 1.0
        return min(self.ESCALATION_MAX, 1.0 + (self.elapsed - self.ESCALATION_START) / 60.0 * self.ESCALATION_PER_MIN)

    SURVIVAL_PRESSURE_START = 180.0      # 이 시간(초) 이후부터 압박 시작
    SURVIVAL_PRESSURE_MIN_INTERVAL = 5.0
    SURVIVAL_PRESSURE_RAMP = 20.0        # 이 시간(초)마다 간격이 1초씩 줄어듦

    def _survival_pressure(self, dt, start=None, label="서바이벌 압박"):
        """시간 압박: start초 뒤부터 생존자 전원에게 쓰레기 줄을 주기적으로 올림. 간격은 20초에서 RAMP초마다 1초씩 줄어 5초까지 (서바이벌 3분 뒤, 배틀로얄은 후반 9분 뒤)"""
        start = self.SURVIVAL_PRESSURE_START if start is None else start
        if self.elapsed < start:
            return
        if not getattr(self, "_pressure_announced", False):
            self._pressure_announced = True
            self.add_floating_text(f"[경고] {label} 시작! 쓰레기 줄이 주기적으로 올라옵니다", (255, 190, 90), duration=3.5, size=26, category="action")
            self.add_commentary(f"{label} 시작 - 쓰레기 줄이 주기적으로 올라옵니다", (255, 190, 90), prio=1)
        self._pressure_t = getattr(self, "_pressure_t", 0.0) + dt
        interval = max(self.SURVIVAL_PRESSURE_MIN_INTERVAL, 20.0 - (self.elapsed - start) / self.SURVIVAL_PRESSURE_RAMP)
        if self._pressure_t < interval:
            return
        self._pressure_t = 0.0
        # 간격이 최소에 닿은 뒤에도 15초마다 한 번에 올라오는 줄이 1줄씩 늘어남(최대 10줄) (강한 봇도 결국 끝나도록)
        ramp_end = start + (20.0 - self.SURVIVAL_PRESSURE_MIN_INTERVAL) * self.SURVIVAL_PRESSURE_RAMP
        rows = min(10, 1 + int(max(0.0, self.elapsed - ramp_end) / 15.0))
        if self.local_is_alive:
            self.local_engine.queue_garbage(rows, source="PRESSURE", instant=True)      # 시간 압박은 공격이 아니므로 차징 없이 바로 올라올 수 있음
        for p in self.players.values():
            if p["is_alive"] and p.get("bot"):
                eng = p["bot"].engine
                eng.queue_garbage(rows, source="PRESSURE", instant=True)
                # 만약 대기열이 이미 24줄 상한까지 차 있다면 시간 압박 시 대기 쓰레기를 직접 보드로 밀어올려 서든데스 유도 (v1.4.27부터 스폰 자리가 막히거나 다음 고정에서 탈락)
                if eng.incoming_garbage >= MAX_INCOMING_GARBAGE:
                    push = min(eng.incoming_garbage, rows)
                    eng.incoming_garbage -= push
                    eng._push_garbage(push)
                    if eng.game_over:
                        p["bot"].is_alive = False

    def _get_dynamic_fall_speed(self):
        """생존자 비율에 따라 부드럽게 빨라지는 중력 (초 단위, 0.80s -> 0.16s)"""
        ratio = max(0.0, min(1.0, (self.alive_count - 1) / max(1, self.total_players - 1)))
        return (0.16 + (0.80 - 0.16) * (ratio ** 0.8)) * self.CUSTOM_GRAVITY.get(self._custom("gravity", "normal"), 1.0)

    @staticmethod
    def _new_player(pid, name, is_ai, bot, compact_grid):
        """참가자 한 명의 초기 상태 (모든 등록 경로가 같은 필드를 갖도록 한 곳에서 생성)"""
        return {
            "id": pid,
            "name": name,
            "is_ai": is_ai,
            "bot": bot,
            "is_alive": True,
            "ko_count": 0,
            "badge_extra": 0,                # K.O.로 흡수한 상대 배지 점수
            "rank": 0,
            "target_id": None,
            "trait": "",                    # 봇 성향 (반격형/저격형/균형형, 사람은 빈 문자열)
            "last_attacker": None,
            "last_attack_t": -1e9,          # 마지막으로 공격받은 경기 시각 (K.O. 인정은 최근 공격자에게만)
            "attacks": 0,
            "survival": None,
            "score": 0,
            "lines": 0,
            "compact_grid": compact_grid,
            "highest_y": 20,
        }

    def _difficulty_choices(self):
        """봇 난이도 설정에 따라 봇마다 무작위로 고를 난이도 목록"""
        if self.bot_difficulty in ("easy", "normal", "hard", "master"):
            return [self.bot_difficulty]
        return ["easy", "easy", "normal", "normal", "hard"]      # mixed (배틀로얄 표준 혼합)

    def _setup_participants(self):
        # 클라이언트 모드이고 호스트가 정해준 초기 참가자 명단이 있는 경우
        if self.initial_players:
            # 호스트만 봇을 직접 시뮬레이션한다. (클라이언트는 호스트가 보내는 월드 상태로 봇 화면만 표시)
            is_host = bool(self.net_mgr and self.net_mgr.mode == "HOST")
            diff_choices = self._difficulty_choices()
            for pinfo in self.initial_players:
                pid = pinfo["id"]
                pname = pinfo["name"]
                is_me = (pid == self.local_player_id)
                is_ai = pinfo.get("is_ai", False)
                bot = AIBot(bot_id=pid, name=pname, difficulty=random.choice(diff_choices)) if (is_host and is_ai) else None
                self.players[pid] = self._new_player(pid, pname, is_ai, bot, self.local_engine.get_compact_grid() if is_me else (bot.engine.get_compact_grid() if bot else [0] * BOARD_HEIGHT))
                if bot:
                    self.players[pid]["trait"] = random.choices(BOT_TRAITS, weights=BOT_TRAIT_WEIGHTS)[0]
            self.total_players = len(self.players)
            self.alive_count = self.total_players
            self.next_rank_to_assign = self.total_players
            return

        # 1. 로컬 플레이어 등록
        self.players[self.local_player_id] = self._new_player(self.local_player_id, self.local_player_name, False, None, self.local_engine.get_compact_grid())
        
        # 2. 네트워크 플레이어들 등록 (호스트 모드)
        registered_count = 1
        if self.net_mgr and self.net_mgr.mode == "HOST":
            for addr, cinfo in list(self.net_mgr.clients.items()):
                cid = cinfo["id"]
                cname = cinfo["name"]
                self.players[cid] = self._new_player(cid, cname, False, None, [0] * BOARD_HEIGHT)
                registered_count += 1
                if registered_count >= self.total_players:
                    break
                    
        # 3. 부족한 슬롯을 사람다운 AI 봇으로 충원
        bot_idx = 1
        diff_choices = self._difficulty_choices()

        while registered_count < self.total_players:
            bid = f"BOT_{bot_idx:02d}"
            bname = bot_display_name(bot_idx)
            diff = random.choice(diff_choices)
            bot = AIBot(bot_id=bid, name=bname, difficulty=diff)
            self.players[bid] = self._new_player(bid, bname, True, bot, bot.engine.get_compact_grid())
            self.players[bid]["trait"] = random.choices(BOT_TRAITS, weights=BOT_TRAIT_WEIGHTS)[0]
            bot_idx += 1
            registered_count += 1

        # 현상금 봇: 솔로 배틀로얄에서 봇 한 명에게 표식을 붙임 (처치하면 보너스). 전용 Random이라 전역 난수(봇 구성/오늘의 도전)는 건드리지 않음
        if self.attacks_enabled and not self.practice and not (self.net_mgr and self.net_mgr.mode in ("HOST", "CLIENT")) and self.total_players >= 8:
            cands = [pid for pid, p in self.players.items() if p["is_ai"] and pid != self.rival_id]
            if cands:
                rng = random.Random(int(self.daily) * 31 + 5) if (self.daily and str(self.daily).isdigit()) else random.Random()
                self._bounty_rng = rng
                self.bounty_id = rng.choice(sorted(cands))

    def take_over_with_bot(self, pid, snap=None):
        """(호스트) 연결이 끊긴 참가자의 자리를 봇이 이어받음: 마지막 보드(스냅샷이 없으면 미니 보드 격자)에서 계속 플레이. 이미 탈락했으면 아무 일도 안 함"""
        p = self.players.get(pid)
        if not p or not p["is_alive"] or p.get("bot") or pid == self.local_player_id:
            return False
        diff = self.bot_difficulty if self.bot_difficulty in ("easy", "normal", "hard", "master") else "normal"      # 방 난이도를 따름 (혼합이면 보통)
        bot = AIBot(bot_id=pid, name=p["name"], difficulty=diff)
        eng = bot.engine
        loaded = False
        if isinstance(snap, dict):
            try:
                eng.load_snapshot(snap)
                loaded = True
            except Exception:
                eng = bot.engine = BlockEngine()
        if not loaded:
            rows = p.get("cg")
            if isinstance(rows, list) and len(rows) == BOARD_HEIGHT:
                for y, row in enumerate(rows):
                    for x, ch in enumerate(str(row)[:eng.width]):
                        eng.grid[y][x] = ch if ch in "IJLOSTZG" else None
        eng.score = max(eng.score, int(p.get("score", 0) or 0))
        if (not loaded or eng.current_piece is None) and not eng.game_over:
            eng.current_piece = None
            eng.spawn_piece()                                   # 스냅샷에 조작 중 블록이 없거나(보드 격자만 복원) 격자를 덮어쓴 경우: 새로 내려보냄 (블록 없이 탐색하면 KeyError로 호스트가 종료됨)
        p["bot"] = bot
        p["is_ai"] = True
        p["trait"] = ""
        self.add_commentary(f"{self._short_name(pid)} 연결 끊김 · 봇이 대신 플레이", (255, 190, 90), prio=1)
        return True

    def _assign_teams(self):
        """팀전: 나는 0팀, 나머지는 1, 0, 1, 0… 순서로 번갈아 나눔 (인원 차이가 1명 이하)"""
        if not self.team_mode:
            return
        if self.net_mgr is not None:
            # LAN: 모든 컴퓨터가 같은 팀 배정을 가져야 하므로 id 순서만으로 정함 (난수 없음). 사람끼리 번갈아, 봇은 이어서 번갈아 -> 인원 차이 1명 이하
            humans = sorted(pid for pid, p in self.players.items() if not p["is_ai"])
            bots = sorted(pid for pid, p in self.players.items() if p["is_ai"])
            self.teams = {pid: i % 2 for i, pid in enumerate(humans)}
            self.teams.update({pid: (len(humans) + j) % 2 for j, pid in enumerate(bots)})
        else:
            others = [pid for pid in self.players if pid != self.local_player_id]
            random.shuffle(others)                       # 혼자 하기: 매 판 같은 봇끼리 같은 편이 되지 않도록 섞음 (나는 항상 0팀)
            self.teams = {self.local_player_id: 0}
            for n, pid in enumerate(others, 1):
                self.teams[pid] = n % 2
        mine, foes = self.team_alive_counts()
        self.add_commentary(f"팀전 · 내 팀 {mine}명 vs 상대 팀 {foes}명 (같은 편은 공격하지 않아요)", (110, 235, 255), prio=1)

    def _team_alerts(self, now):
        """팀전: 같은 편이 탈락 직전(쌓인 높이 + 받을 공격이 판 높이에 가까움)이면 알려 줌. 한 명당 12초에 한 번"""
        if now < getattr(self, "_team_alert_check", 0.0) or self.match_finished or not self.local_is_alive:
            return
        self._team_alert_check = now + 0.5
        seen = self.__dict__.setdefault("_team_alert_seen", {})
        for pid, p in self.players.items():
            if not p["is_alive"] or not self.is_ally(self.local_player_id, pid) or now < seen.get(pid, 0.0):
                continue
            if self._danger(p) >= BOARD_HEIGHT - 3:
                seen[pid] = now + 12.0
                self.add_floating_text(f"♥ 아군 위기!  {self._short_name(pid)}", (120, 235, 170), duration=2.2, size=24, category="alert")
                return

    def team_alive_counts(self):
        """팀전: (우리 팀 생존자 수, 상대 팀 생존자 수)"""
        my = self.teams.get(self.local_player_id)
        mine = sum(1 for pid, p in self.players.items() if p["is_alive"] and self.teams.get(pid) == my)
        foes = sum(1 for pid, p in self.players.items() if p["is_alive"] and self.teams.get(pid) != my)
        return mine, foes

    def is_ally(self, a, b):
        """팀전에서 두 플레이어가 같은 편인가 (팀전이 아니면 항상 False)"""
        return bool(self.teams) and a != b and self.teams.get(a) is not None and self.teams.get(a) == self.teams.get(b)

    def set_target_mode(self, mode):
        """조준 모드를 바로 지정 (숫자키). 수동으로 찍어 둔 대상은 해제"""
        if mode in TARGET_MODES:
            self.local_target_mode = mode
            self.local_manual_target_id = None
            self.log_event("target_mode", mode=mode)
        return self.local_target_mode

    def cycle_target_mode(self):
        """타겟팅 모드 순환 (config.TARGET_MODES 순서: AUTO -> KO -> ATTACKERS -> BADGES -> RANDOM -> AUTO)"""
        idx = TARGET_MODES.index(self.local_target_mode)
        self.local_target_mode = TARGET_MODES[(idx + 1) % len(TARGET_MODES)]
        self.local_manual_target_id = None
        self.log_event("target_mode", mode=self.local_target_mode)
        return self.local_target_mode

    def release_manual_target(self):
        """수동으로 찍어 둔 대상만 해제 (조준 모드는 그대로). 해제했으면 True"""
        if self.local_manual_target_id:
            self.local_manual_target_id = None
            self.log_event("target_manual_release")
            return True
        return False

    def set_manual_target(self, target_id):
        """특정 플레이어 클릭 시 수동 타겟 지정"""
        if target_id in self.players and self.players[target_id]["is_alive"] and target_id != self.local_player_id and not self.is_ally(self.local_player_id, target_id):
            self.local_manual_target_id = target_id
            return True
        return False

    def get_attackers_count_for(self, pid):
        """특정 플레이어를 조준 중인 살아있는 상대방 수 계산 (카운터 보너스 산정용)"""
        return sum(1 for p in self.players.values() if p["is_alive"] and p.get("target_id") == pid)

    BADGE_ABSORB_MAX = 2         # K.O.로 상대에게서 흡수하는 배지 점수 상한 (상대 실제 K.O. 수의 절반, 최대 2. 눈덩이를 막으려고 흡수분은 다시 흡수되지 않고, 흡수 누적은 내 실제 K.O. 수 이하)

    def badge_points(self, pid=None):
        """배지 단계 계산에 쓰는 점수 = 실제 K.O. 수 + 처치한 상대에게서 흡수한 점수 (전적/업적의 K.O. 수에는 흡수분이 들어가지 않음)"""
        pid = self.local_player_id if pid is None else pid
        p = self.players.get(pid, {})
        ko = self.local_ko_count if pid == self.local_player_id else p.get("ko_count", 0)
        return ko + p.get("badge_extra", 0)

    def get_badge_info(self, ko_count=None):
        """로컬 플레이어 또는 지정된 플레이어의 배지 등급 및 버프율 반환"""
        if ko_count is None:
            ko_count = self.badge_points()
        if self._custom("badges", True) is False:
            return get_badge_info(0)                                        # 커스텀 규칙: 배지 보너스 없음
        return get_badge_info(ko_count)

    def get_attacker_bonus(self, count):
        """다수의 적에게 동시 조준당할 때의 반격 보너스 라인 반환"""
        return ATTACKER_BONUS.get(min(6, count), 0)

    def get_name_colors(self):
        """{플레이어 ID: 이름 색 번호} - 호스트는 참가자 목록, 클라이언트는 호스트가 보낸 명단에서 가져옴 (봇은 기본색)"""
        d = {}
        nm = self.net_mgr
        if nm:
            if nm.mode == "HOST":
                d[nm.my_player_id or "HOST_P1"] = nm.my_color
                for c in list(nm.clients.values()):
                    d[c["id"]] = c.get("color", 0)
            elif nm.mode == "CLIENT":
                for e in nm.roster:
                    d[e["id"]] = e.get("color", 0)
        d[self.local_player_id] = self.local_color
        return d

    def player_stats(self, pid):
        """플레이어 한 명의 성적: 시간(생존), APM, LPM, 점수, 라인, K.O. (관전 화면과 최종 순위표에서 사용)"""
        p = self.players.get(pid)
        if not p:
            return {"time": 0.0, "apm": 0.0, "lpm": 0.0, "score": 0, "lines": 0, "attacks": 0, "ko": 0}
        if pid == self.local_player_id:
            t = self.survival_seconds()
            lines, score, attacks = self.local_engine.lines_cleared_total, self.local_engine.score, self.total_attacks_sent
            ko = self.local_ko_count
        else:
            t = p["survival"] if p.get("survival") is not None else self.elapsed
            lines, score, ko = p.get("lines", 0), p.get("score", 0), p.get("ko_count", 0)
            bot = p.get("bot")
            # 봇은 상쇄로 소모된 공격력도 생성치로 집계 (들어오는 쓰레기를 막아내느라 APM이 0에 묶이는 것 방지)
            attacks = bot.engine.attack_generated_total if bot else p.get("attacks", 0)
        t = float(t)
        te = max(1.0, t)
        return {"time": t, "apm": attacks / te * 60.0, "lpm": lines / te * 60.0,
                "score": score, "lines": lines, "attacks": attacks, "ko": ko}

    def standings(self):
        """최종 순위표: 순위 오름차순. 순위가 없는 생존자는 점수 순으로 앞쪽에 둠."""
        rows = []
        for pid, p in self.players.items():
            st = self.player_stats(pid)
            rows.append({"id": pid, "name": p["name"], "is_local": pid == self.local_player_id, "is_ai": p.get("is_ai", False),
                         "rank": p.get("rank", 0), "alive": p["is_alive"], **st})
        rows.sort(key=lambda r: (r["rank"] if r["rank"] > 0 else 0, -r["score"]))
        return rows

    def get_spectate_engine(self, pid):
        """관전 대상의 '실제 플레이 화면'용 엔진.
        - 호스트에서 돌아가는 봇: 봇 엔진 그대로
        - 그 외(클라이언트 화면의 봇/다른 사람, 호스트 화면의 원격 사람): 네트워크로 받은 스냅샷을 복원한 엔진
        - 스냅샷이 아직 없으면 None (압축 그리드로 임시 표시)"""
        p = self.players.get(pid)
        if not p:
            return None
        if p.get("bot"):
            return p["bot"].engine
        snap = None
        if self.net_mgr:
            snap = self.net_mgr.remote_details.get(pid)
            if snap is None:
                snap = self.net_mgr.remote_players_state.get(pid, {}).get("snap")
        if snap is None:
            return None
        if not hasattr(self, "_spectate_engines"):
            self._spectate_engines = {}
        eng = self._spectate_engines.get(pid)
        if eng is None:
            eng = self._spectate_engines[pid] = BlockEngine(seed=0)
        try:
            eng.load_snapshot(snap)
        except Exception:
            return None
        return eng

    def snapshot_for(self, pid):
        """(호스트) pid 플레이어의 관전용 스냅샷"""
        if pid == self.local_player_id:
            return self.local_engine.snapshot()
        p = self.players.get(pid)
        if p and p.get("bot"):
            return p["bot"].engine.snapshot()
        if self.net_mgr:
            return self.net_mgr.remote_players_state.get(pid, {}).get("snap")
        return None

    SPECTATE_SWITCH_DELAY = 1.2        # 관전 대상이 탈락한 뒤 다음 대상으로 넘기기까지 (탈락 장면을 볼 시간)

    def _check_spectate_target(self, now):
        """관전 중인 상대가 탈락하면 1.2초 뒤 패배를 알리고, 그 상대를 처치한 생존자(없으면 플레이어 순서상 다음 생존자)로 자동 전환"""
        if not getattr(self, "is_spectating", False) or self.match_finished:
            return
        tid = self.spectate_target_id
        if tid not in self.players or self.players[tid]["is_alive"]:
            self._spec_dead = None
            return
        if getattr(self, "_spec_dead", None) is None or self._spec_dead[0] != tid:
            self._spec_dead = (tid, now)                     # 대상이 탈락한 순간: 바로 넘기지 않고 탈락 장면을 잠깐 보여 줌
        if now - self._spec_dead[1] < self.SPECTATE_SWITCH_DELAY:
            return
        ids = [pid for pid in self.players if pid != self.local_player_id]
        alive = [pid for pid in ids if self.players[pid]["is_alive"]]
        if not alive:
            return
        killer = self.players[tid].get("ko_by")
        if killer in alive:
            nxt = killer                                     # 그 상대를 처치한 쪽을 이어서 봄
        else:
            after = ids[ids.index(tid) + 1:] + ids[:ids.index(tid)] if tid in ids else ids
            nxt = next((pid for pid in after if self.players[pid]["is_alive"]), alive[0])
        self._spec_dead = None
        dead_name = self.players[tid]["name"]
        self.spectate_target_id = nxt
        self.spectate_notice = {"text": f"{dead_name} 패배!", "sub": f"관전 대상을 {self.players[nxt]['name']}(으)로 전환합니다", "t0": now}
        if self.sound_mgr:
            self.sound_mgr.play('ko')

    def cycle_spectate_target(self, direction=1):
        """탈락 후 관전 모드에서 다른 생존자 전환 (방향키 조작)"""
        alive_ids = [pid for pid, p in self.players.items() if p["is_alive"] and pid != self.local_player_id]
        if not alive_ids:
            return None
        if self.spectate_target_id in alive_ids:
            idx = alive_ids.index(self.spectate_target_id)
            self.spectate_target_id = alive_ids[(idx + direction) % len(alive_ids)]
        else:
            killer = self.local_killer_id
            self.spectate_target_id = killer if killer in alive_ids else alive_ids[0]      # 관전은 나를 탈락시킨 상대부터
        return self.spectate_target_id

    def get_target_for(self, attacker_id, strategy=None):
        """전략에 따른 대상 플레이어 ID 계산 (AUTO 모드 시 사람 플레이어 최우선 자동 조준)"""
        strat = strategy or self.local_target_mode
        alive_candidates = [
            pid for pid, p in self.players.items()
            if p["is_alive"] and pid != attacker_id and not self.is_ally(attacker_id, pid)
        ]
        if not alive_candidates:
            return None
            
        if attacker_id == self.local_player_id and self.local_manual_target_id:
            if self.local_manual_target_id in alive_candidates:
                return self.local_manual_target_id
            else:
                self.local_manual_target_id = None
                
        # AUTO 모드: 호스트-클라이언트 모드에서 다른 사람 플레이어를 무조건 자동 타겟팅!
        if strat == "AUTO":
            other_humans = [
                pid for pid in alive_candidates
                if not self.players[pid].get("is_ai", False)
            ]
            pool = other_humans or alive_candidates          # 사람 상대가 있으면 그 중에서, 없거나 솔로면 전체에서 가장 위험한(높이 쌓인) 상대
            if attacker_id == self.local_player_id:
                return self._auto_lock_target(pool)
            return self._most_endangered(pool)
            
        elif strat == "KO":
            return self._most_endangered(alive_candidates)
        elif strat == "ATTACKERS":
            attackers = [pid for pid in alive_candidates if self.players[pid].get("target_id") == attacker_id]
            if attackers:
                cur = self.players.get(attacker_id, {}).get("target_id")
                if cur in attackers:
                    return cur                                   # 이미 겨누던 공격자가 계속 나를 노리면 유지 (조준선이 프레임마다 흔들리지 않게)
                return random.choice(attackers)
            return self._most_endangered(alive_candidates)
        elif strat == "BADGES":
            return max(alive_candidates, key=lambda pid: self.badge_points(pid))
        elif strat == "RANDOM":
            current_target = self.players[attacker_id].get("target_id")
            if current_target and current_target in alive_candidates:
                return current_target
            return random.choice(alive_candidates)
            
        return random.choice(alive_candidates)

    # 봇 조준 분산: 한 명에게 봇이 몰려 일점 타격이 되면 사람이 도저히 못 버티므로, 이미 노리는 봇이 많은 대상은 점수를 깎고 상한을 둠
    FOCUS_CAP = 3                    # 한 플레이어를 동시에 노릴 수 있는 봇 수의 기본 상한
    RETALIATE_CHANCE = {"반격형": 0.6, "저격형": 0.0}       # 강한 봇이 조준을 다시 뽑을 때 나를 노리는 상대에게 되갚는 확률 (성향별)
    RETALIATE_DEFAULT = 0.25
    SMART_TARGET_CHANCE = {"저격형": 0.85}                 # 보통 난이도 봇이 위험도 기반 조준을 쓰는 확률 (성향별)
    SMART_TARGET_DEFAULT = 0.5
    BOT_BADGE_CAP = 0.5              # 봇에게 적용하는 배지 공격력 증폭 상한 (+50%)
    KO_CREDIT_WINDOW = 15.0          # 마지막 공격 후 이 시간(초) 안에 탈락해야 그 공격자에게 K.O.를 인정
    HUMAN_FOCUS_CAP = 2              # 사람 플레이어에게는 더 낮은 상한 (봇보다 상쇄 능력이 낮아 같은 압박이 훨씬 무겁기 때문)
    KILL_EXTRA = 2                   # 탈락시킬 수 있는 마무리 공격은 상한을 이만큼까지만 초과 허용
    FOCUS_PENALTY = 2.5              # 이미 노리는 봇 1명당 조준 점수 감점

    def _focus_cap(self, p):
        return self.FOCUS_CAP if p.get("is_ai") else self.HUMAN_FOCUS_CAP

    AUTO_LOCK_SECS = 0.8             # 자동 조준: 한 번 고른 대상을 최소 이 시간(초) 유지 (조준선/상단 이름이 프레임마다 옮겨 다니지 않게)
    AUTO_SWITCH_MARGIN = 3           # 그 뒤에도 새 후보의 위험도가 지금 대상보다 이만큼 이상 커야 바꿈

    def _auto_lock_target(self, pool):
        """내 자동 조준: 위험도가 가장 큰 상대를 고르되 락온을 유지하고, 대기열이 가득 찬 상대(더 보내도 버려짐)는 다른 후보가 있으면 건너뜀.
        K.O. 모드는 이 유지/건너뜀 없이 항상 그 순간 가장 위험한 상대를 겨눔"""
        def full(q):
            return self.alive_count > 3 and self.players[q].get("ig", 0) >= MAX_INCOMING_GARBAGE
        cand = [q for q in pool if not full(q)] or pool
        best = self._most_endangered(cand)
        lock = self._auto_lock
        if lock and lock[0] in pool and self.players[lock[0]]["is_alive"] and lock[0] in cand:
            cur = lock[0]
            if self.elapsed - lock[1] < self.AUTO_LOCK_SECS:
                return cur
            if self._danger(self.players[best]) < self._danger(self.players[cur]) + self.AUTO_SWITCH_MARGIN:
                return cur
        self._auto_lock = (best, self.elapsed)
        return best

    def _most_endangered(self, pids):
        """K.O. 직전에 가장 가까운 후보: 쌓인 높이 + 곧 올라올 쓰레기가 가장 큰 상대 (봇의 위험도 계산과 같은 기준)"""
        return max(pids, key=lambda pid: self._danger(self.players[pid]))

    @staticmethod
    def _danger(p):
        """쌓인 높이 + 들어올 쓰레기 (한계에 가까울수록 큼)"""
        return (BOARD_HEIGHT - p.get("highest_y", BOARD_HEIGHT)) + p.get("ig", 0)

    @staticmethod
    def _spawn_danger(p):
        """스폰 열(새 블록이 나오는 자리) 기준의 쌓인 높이 + 들어올 쓰레기: 가장자리 탑이 천장에 닿아도 죽지 않으므로 탈락 가능성은 이 값으로 가늠"""
        cg = p.get("compact_grid")
        top = BOARD_HEIGHT
        if isinstance(cg, (list, tuple)) and len(cg) == BOARD_HEIGHT and any(cg):      # 보드 그림이 비어 있으면(아직 상태가 안 온 경우) 높이 값으로
            for y, row in enumerate(cg):
                if row & 0x78:                                     # 열 3~6 (왼쪽 열이 높은 비트)
                    top = y
                    break
        else:
            top = p.get("highest_y", BOARD_HEIGHT)
        return (BOARD_HEIGHT - top) + p.get("ig", 0)

    def _target_loads(self, attacker_id):
        """지금 각 플레이어를 노리고 있는 (살아 있는) 봇 수"""
        loads = {}
        for q, pp in self.players.items():
            if q != attacker_id and pp["is_alive"] and pp.get("bot") is not None:
                t = pp.get("target_id")
                if t:
                    loads[t] = loads.get(t, 0) + 1
        return loads

    def _smart_target(self, attacker_id, attack=0):
        """봇의 조준 대상 선택: 위험도(쌓인 높이 + 들어올 쓰레기)가 높을수록, 나를 노리는 상대일수록, 이번 공격으로 탈락시킬 수 있을수록 우선.
        이미 노리는 봇이 많은 상대는 점수를 깎고 상한을 넘으면 제외(사람은 상한이 더 낮음). 대기 쓰레기가 이미 상한(MAX_INCOMING_GARBAGE)까지 찬 상대는
        더 보내도 버려지므로 뒤로 미루되, 고를 수 있는 상대가 그뿐이면 그래도 그 상대를 노림 (조준 대상이 없어져 공격이 사라지는 일 방지)"""
        loads = self._target_loads(attacker_id)
        best, best_s = None, -1e9
        fallback, fb_load = None, 1e9                    # 상한/포화로 못 고른 상대 중 노리는 봇이 가장 적은 상대
        for q, p in self.players.items():
            if not p["is_alive"] or q == attacker_id or self.is_ally(attacker_id, q):
                continue
            danger = self._danger(p)
            load = loads.get(q, 0)
            cap = self._focus_cap(p)
            full = p.get("ig", 0) >= MAX_INCOMING_GARBAGE   # 대기열이 가득 참: 더 보내도 버려짐
            key_load = load + (100 if full else 0)
            if key_load < fb_load:
                fallback, fb_load = q, key_load
            if full and self.alive_count > 3:
                continue
            kill = bool(attack) and attack >= 3 and self._spawn_danger(p) + attack >= BOARD_HEIGHT - 1      # 스폰 열 기준으로 마무리 가능한지
            if load >= cap + (self.KILL_EXTRA if kill else 0):
                continue                                         # 동시에 노리는 봇이 상한에 찼음 (마무리 공격만 KILL_EXTRA명까지 더 허용)
            sc = danger + self.badge_points(q) * 0.7 + random.uniform(0.0, 1.5) - load * self.FOCUS_PENALTY
            if p.get("target_id") == attacker_id:
                sc += 4.0                                        # 나를 노리는 상대를 견제
            if kill:
                sc += 8.0                                        # 이번 공격으로 마무리 가능
            if sc > best_s:
                best, best_s = q, sc
        return best if best is not None else fallback

    def _spread_random_target(self, attacker_id):
        """무작위 조준(쉬움/보통 봇): 상한 안에서 노리는 봇이 적은 상대들 중에서 고름 (대기열이 가득 찬 상대는 후순위)"""
        loads = self._target_loads(attacker_id)
        alive = [(q, p) for q, p in self.players.items() if p["is_alive"] and q != attacker_id and not self.is_ally(attacker_id, q)]
        if not alive:
            return None
        live = [(q, p) for q, p in alive if p.get("ig", 0) < MAX_INCOMING_GARBAGE] or alive
        allowed = [q for q, p in live if loads.get(q, 0) < self._focus_cap(p)]
        if not allowed:
            low = min(loads.get(q, 0) for q, _ in live)
            allowed = [q for q, _ in live if loads.get(q, 0) <= low]
        return random.choice(allowed)

    def _clear_origin_row(self):
        """내가 방금 지운 줄들의 평균 행 번호 (없으면 None): 공격 빔의 출발 높이"""
        rows = (getattr(self.local_engine, "last_clear_info", None) or {}).get("cleared_rows") or []
        return (sum(rows) / len(rows)) if rows else None

    def apply_attack(self, from_id, to_id, lines, from_network=False, multi=1, order=0):
        """공격 라인 전달 및 궤적 이펙트 생성 (from_network: 네트워크로 수신한 공격은 재전송하지 않음)"""
        if lines <= 0 or not self.attacks_enabled or self.is_ally(from_id, to_id):
            return                                                     # 서바이벌 모드(공격 없음) / 같은 편에게는 어떤 공격도 전달/표시하지 않음
        if not from_network:
            mult = self.attack_multiplier()
            if mult > 1.0:
                lines = int(math.ceil(lines * mult))                   # 후반 공격력 증폭 (네트워크로 받은 공격은 보낸 쪽에서 이미 반영됨)
            gm = self.CUSTOM_GARBAGE.get(self._custom("garbage", "normal"), 1.0)
            if gm != 1.0:
                lines = max(1, int(math.ceil(lines * gm)))              # 커스텀 규칙: 쓰레기 줄 배율
        if to_id in self.players and not self.players[to_id]["is_alive"]:
            return                                                     # 이미 탈락한 대상에게는 공격/이펙트를 보내지 않음 (죽은 카드가 번쩍이며 흔들리는 것 방지)
        if to_id in self.players:
            self.players[to_id]["last_attacker"] = from_id
            self.players[to_id]["last_attack_t"] = self.elapsed
            if from_id == self.local_player_id and to_id != from_id:
                hist = self.players[to_id].setdefault("from_local", [])           # K.O. 기여 판정용: 내가 이 상대에게 보낸 (시각, 줄 수)
                hist.append((self.elapsed, lines))
                del hist[:-12]
        if from_id in self.players:
            self.players[from_id]["attacks"] += lines          # 플레이어별 공격력 합계 (APM 계산용)
            
        now = time.time()
        local_fx = from_id == self.local_player_id or to_id == self.local_player_id
        # 봇끼리의 공격 빔은 동시에 그리는 수를 제한 (마스터 100명일 때 화면 부하/프레임 저하 방지). 공격 자체(줄 전달, 네트워크 전송)는 그대로 처리됨
        if local_fx or (not self.fx_low and sum(1 for e in self.attack_effects if not e.get("local")) < self.MAX_BOT_FX):
            self.attack_effects.append({
                "local": local_fx,
                "from_id": from_id,
                "to_id": to_id,
                "lines": lines,
                "start_time": now + order * 0.07,                          # 다중 포격: 빔이 순서대로 부채꼴로 발사되는 연출
                "multi": multi,
                "duration": 0.58,
                "impacted": False,
                "origin_row": self._clear_origin_row() if from_id == self.local_player_id else None      # 빔이 지운 줄 높이에서 출발
            })

        if lines >= (4 if self.total_players > 10 else 3) and from_id in self.players and to_id in self.players:
            self.add_commentary(f"{self._short_name(from_id)} → {self._short_name(to_id)}  {lines}줄 공격!", (255, 150, 80))

        # 1. 로컬 플레이어가 피격 대상인 경우
        if to_id == self.local_player_id and self.local_is_alive:
            self.local_engine.queue_garbage(lines, source=from_id)
            self.trigger_screen_shake(min(14.0, 5.0 + lines * 2.2))
            self._play_hit_alarm(lines)
            attacker_p = self.players.get(from_id, {})
            attacker_name = attacker_p.get("name", "적 플레이어")
            self.local_hits_from[from_id] = self.local_hits_from.get(from_id, 0) + lines          # 결과 화면 "패인 한 줄"용: 누가 얼마나 보냈나
            self.log_event("hit", frm=from_id, lines=lines)
            agg = self._hit_agg
            now_t = time.time()
            if agg and now_t - agg["t"] <= 1.0 and agg["ft"] in self.floating_texts:
                agg["lines"] += lines                                                  # 1초 안에 연달아 맞으면 한 줄로 합쳐 토스트 칸을 아낌
                agg["senders"].add(from_id)
                n_s = len(agg["senders"])
                agg["ft"]["text"] = f"[피격 경고] {n_s}명 +{agg['lines']}줄 공격 받음" if n_s > 1 else f"[피격 경고] +{agg['lines']}줄 공격 받음 (보낸이: {attacker_name})"
                agg["ft"]["birth"] = now_t
                agg["t"] = now_t
            else:
                self.add_floating_text(f"[피격 경고] +{lines}줄 공격 받음 (보낸이: {attacker_name})", (255, 75, 75), duration=2.4, size=22, category="alert")
                self._hit_agg = {"t": now_t, "lines": lines, "senders": {from_id}, "ft": self.floating_texts[-1]}
            
        # 2. 로컬에서 관리하는 AI 봇이 피격 대상인 경우
        elif to_id in self.players:
            p = self.players[to_id]
            if p["is_ai"] and p["bot"] and p["is_alive"]:
                p["bot"].engine.queue_garbage(lines, source=from_id)
                
        # 3. 네트워크 모드일 경우 원격 클라이언트에 패킷 전송
        if self.net_mgr and self.net_mgr.running:
            if not from_network and (from_id == self.local_player_id or self.net_mgr.mode == "HOST"):
                self.net_mgr.send_attack(from_id, to_id, lines)

    def _eliminate_player(self, victim_id, killer_id=None):
        """플레이어 탈락 처리"""
        if victim_id not in self.players or not self.players[victim_id]["is_alive"]:
            return
        # 킬러 미지정 시 최근(KO_CREDIT_WINDOW초 안)에 이 플레이어를 마지막으로 공격한 생존자에게 K.O. 부여
        # (오래전에 한 번 공격했을 뿐인 봇이 후반 압박/자멸로 끝난 상대의 K.O.를 가져가지 않게)
        if killer_id is None:
            last = self.players[victim_id].get("last_attacker")
            recent = self.elapsed - self.players[victim_id].get("last_attack_t", -1e9) <= self.KO_CREDIT_WINDOW
            if last and recent and last != victim_id and self.players.get(last, {}).get("is_alive"):
                killer_id = last
            
        if victim_id == self.rival_id and killer_id == self.local_player_id and not self.rival_defeated and not self.practice:
            self.rival_defeated = True                                 # 복수 성공: 전적/업적은 경기 종료 때 반영
            self.add_floating_text(f"복수 성공!  라이벌 {self._short_name(victim_id)} 처치", (255, 215, 90), duration=3.0, size=28, category="action", tier=3)
            self.trigger_impact(0.8)
            if self.sound_mgr:
                self.sound_mgr.play('revenge')
        if victim_id == self.local_player_id:
            self.local_death_attackers = self.get_attackers_count_for(victim_id)
            self.log_event("death", rank=self.next_rank_to_assign, attackers=self.local_death_attackers, killer=killer_id)      # 결과 화면의 "패인 한 줄"용: 탈락 순간 나를 노리던 상대 수
        self.players[victim_id]["is_alive"] = False
        self.players[victim_id]["ko_t"] = time.time()               # 탈락 연출(카드가 무너지고 처치자가 나면 K.O. 도장) 시작 시각
        self.players[victim_id]["ko_by"] = killer_id
        self.players[victim_id]["survival"] = self.elapsed
        self.players[victim_id]["rank"] = self.next_rank_to_assign
        self.next_rank_to_assign -= 1
        self.alive_count -= 1

        vn = self._short_name(victim_id)
        if killer_id and killer_id in self.players:
            self.add_commentary(f"{self._short_name(killer_id)} → {vn} K.O.", (255, 110, 110), mine=(killer_id == self.local_player_id or victim_id == self.local_player_id))
        else:
            self.add_commentary(f"{vn} 탈락", (255, 110, 110))
        team_done = bool(self.teams) and self._round_over()          # 팀전에서 마지막 적이 쓰러졌으면 '최후의 2인' 같은 안내를 하지 않음 (남은 2명이 아군일 수 있음)
        if self.total_players > self.alive_count >= 2 and self.alive_count in (2, 3, 5, 10) and not team_done:
            self.add_commentary("결승전!  최후의 2인" if self.alive_count == 2 else f"생존자 {self.alive_count}명!  접전", (255, 215, 90), prio=1)

        if victim_id == self.local_player_id:
            self.local_killer_id = killer_id if (killer_id in self.players and killer_id != victim_id) else None
            self._record_timeline(final=True)
            self.freeze_local_stats()
            self.local_is_alive = False
            self.local_rank = self.players[victim_id]["rank"]
            self._duck_bgm(1.0)
            self.trigger_screen_shake(18.0)
            
        # K.O. 기여: 내가 막 보내 둔 상대를 다른 플레이어가 마무리했을 때 알려 줌 (배지/K.O. 수에는 반영 안 함)
        if (killer_id != self.local_player_id and victim_id != self.local_player_id and self.local_is_alive and self.attacks_enabled):
            sent = sum(n for t, n in self.players[victim_id].get("from_local", ()) if self.elapsed - t <= self.KO_CREDIT_WINDOW)
            if sent >= 4:
                self.local_assists += 1
                self.log_event("assist", victim=victim_id, lines=sent)
                self.add_floating_text(f"[처치 기여] {self._short_name(victim_id)}에게 {sent}줄 보냄", (255, 200, 120), duration=2.2, size=22, category="ko")

        # 킬러에게 K.O. 부여 및 배지 등급 승급 판정
        if killer_id and killer_id in self.players:
            old_lvl, _, _ = get_badge_info(self.badge_points(killer_id))
            gain = 0
            if self.attacks_enabled and not self.practice and killer_id != victim_id and self._custom("badges", True) is not False:
                gain = min(self.BADGE_ABSORB_MAX, int(self.players.get(victim_id, {}).get("ko_count", 0)) // 2)      # 처치한 상대 K.O. 수의 절반(최대 2)만큼 배지 점수 흡수
            self.players[killer_id]["ko_count"] += 1
            room = max(0, self.players[killer_id]["ko_count"] - self.players[killer_id].get("badge_extra", 0))      # 흡수 누적은 내 실제 K.O. 수 이하
            gain = min(gain, room)
            self.players[killer_id]["badge_extra"] = self.players[killer_id].get("badge_extra", 0) + gain
            if killer_id == self.local_player_id and self.challenge is not None:
                self.challenge.on_ko()
                self._challenge_events()
            if killer_id == self.local_player_id:
                self.local_ko_count += 1
                self.ko_times.append(self.elapsed)
                gold = (victim_id == self.bounty_id and not self.bounty_claimed)
                for i in range(1 + gain):                                  # 구슬은 1개 + 흡수한 점수만큼 (0.1초 간격으로 쏟아짐)
                    self.ko_orbs.append({"victim": victim_id, "t0": time.time() + 0.1 * i, "gold": gold})
                new_lvl, _, new_pct = get_badge_info(self.badge_points())
                self.trigger_screen_shake(10.0, (0, 1))
                self.trigger_impact(0.4)                                   # K.O. 결정타: 약한 번쩍임 (첫 K.O.는 아래에서 더 강하게)
                victim_name = self.players.get(victim_id, {}).get("name", "상대")
                self.add_floating_text(f"[K.O. 처치!] +{1 + gain} 배지 획득 >> {victim_name}" + (f"  (상대 배지 {gain} 흡수)" if gain else ""), (255, 220, 50), duration=2.5, size=24, category="ko")
                # 보상을 두 번에 나눠 줌: 처치 순간(위) + 구슬이 K.O. 칸에 도착하는 순간(소리와 배지 승급, 0.7초 뒤)
                self._ko_events.append({"due": time.time() + 0.7 + 0.1 * gain, "n": self.local_ko_count, "lvl_up": new_lvl > old_lvl, "lvl": new_lvl, "pct": new_pct})
                if gold:
                    self.bounty_claimed = True
                    self.bounty_kills += 1
                    self.add_floating_text(f"★ 현상금 사냥 성공! {victim_name} ★", (255, 200, 60), duration=3.0, size=30, category="action", tier=2)
                    if self.sound_mgr:
                        self.sound_mgr.play('top_up')
                        self.sound_mgr.play('vo_bounty')
                self._check_kill_records()
                if self.first_ko_ever and self.local_ko_count == 1:
                    self.trigger_impact(0.7)
                    self.add_floating_text("★ 첫 K.O.! 축하해요 ★", (255, 225, 90), duration=3.4, size=40, category="action", tier=3)
                    if self.sound_mgr:
                        self.sound_mgr.play('levelup')
                self._check_live_achievements()
                
        if not team_done:
            self._announce_milestones(victim_id)

        # 승자 판정 (최후의 1인, 팀전은 한 팀만 남았을 때)
        if self._round_over():
            self.match_finished = True
            if self.teams:
                self._finish_team_match()
                return
            for pid, p in self.players.items():
                if p["is_alive"]:
                    p["rank"] = 1
                    p["survival"] = self.elapsed
                    self.winner_id = pid
                    self.add_commentary(f"★ {self._short_name(pid)} 최종 우승! ★", (255, 230, 80), prio=1)
                    if pid == self.local_player_id:
                        self.freeze_local_stats()
                        self.local_rank = 1
                        self.trigger_screen_shake(20.0)
                        self.trigger_impact(1.0)
                        self.add_floating_text("★ 1위 최종 우승 로열 빅토리! ★", (255, 230, 80), duration=3.5, size=34, category="action", tier=3)
                    break

    def _round_over(self):
        """경기가 끝났는가: 생존자가 1명 이하, 또는 팀전에서 남은 생존자가 모두 한 팀"""
        if self.alive_count <= 1:
            return True
        if self.teams:
            return len({self.teams.get(pid) for pid, p in self.players.items() if p["is_alive"]}) <= 1
        return False

    def _finish_team_match(self):
        """팀전 종료: 남은 팀 전원이 1위. 내 팀이 이겼으면 승리 연출, 졌으면 (이미 탈락한) 내 순위 그대로"""
        winners = [pid for pid, p in self.players.items() if p["is_alive"]]
        win_team = self.teams.get(winners[0]) if winners else None
        for pid in winners:
            self.players[pid]["rank"] = 1
            self.players[pid]["survival"] = self.elapsed
        self.winner_id = self.local_player_id if self.local_player_id in winners else (winners[0] if winners else None)
        self.team_won = (win_team == self.teams.get(self.local_player_id))
        if self.team_won:
            if self.local_player_id in winners:
                self.freeze_local_stats()
                self.local_rank = 1
            self.trigger_screen_shake(20.0)
            self.trigger_impact(1.0)
            self.add_commentary("★ 내 팀 승리! ★", (255, 230, 80), prio=1)
            self.add_floating_text("★ 팀 승리! 우리 팀이 끝까지 살아남았습니다 ★", (255, 230, 80), duration=3.5, size=32, category="action", tier=3)
        else:
            self.add_commentary("상대 팀 승리", (255, 120, 110), prio=1)
            self.add_floating_text("상대 팀이 승리했습니다", (255, 130, 120), duration=3.2, size=28, category="action", tier=2)

    # 위기 탈출: 스택이 CLUTCH_DANGER_H줄 이상인 채로 CLUTCH_MIN_SECS초 넘게 버티다가 줄을 지워 CLUTCH_SAFE_H줄 이하로 내려오면 작은 보상 (일부러 위기를 만들어 반복하지 못하게 쿨다운)
    CLUTCH_DANGER_H = 16
    CLUTCH_SAFE_H = 13
    CLUTCH_MIN_SECS = 1.0
    CLUTCH_COOLDOWN = 20.0
    CLUTCH_BONUS = 2

    HIT_ALARM_MIN_GAP = 0.22          # 피격 경고음 사이 최소 간격(초): 여러 명에게 동시에 맞아도 소리가 뭉개지지 않게 (더 센 경고는 간격 무시)

    @staticmethod
    def hit_alarm_tier(lines):
        """받은 공격 줄 수 -> 경고음 단계 (1: 1~2줄, 2: 3~5줄, 3: 6줄 이상)"""
        return 3 if lines >= 6 else (2 if lines >= 3 else 1)

    def _play_hit_alarm(self, lines):
        if not self.sound_mgr:
            return
        tier = self.hit_alarm_tier(lines)
        now = time.time()
        if tier > getattr(self, "_last_hit_tier", 0) or now - getattr(self, "_last_hit_t", 0.0) >= self.HIT_ALARM_MIN_GAP:
            self._last_hit_t, self._last_hit_tier = now, tier
            self.sound_mgr.play(f"hit_{tier}")
        elif now - getattr(self, "_last_hit_t", 0.0) > 1.0:
            self._last_hit_tier = 0

    def practice_inject_garbage(self, lines):
        """연습 모드: 쓰레기 줄을 직접 받아 보기 (실제 공격처럼 차징 후 올라옴)"""
        if self.practice and self.local_is_alive:
            self.local_engine.queue_garbage(lines, source="연습")

    DRILL_LINES = (2, 3, 4, 5, 6)             # 30초마다 한 단계씩 커지는 공격 줄 수
    DRILL_STEP_SECS = 30.0

    def drill_level(self):
        return min(len(self.DRILL_LINES) - 1, int((self.elapsed - self.drill_t0) // self.DRILL_STEP_SECS))

    def drill_interval(self):
        return max(5.0, 9.0 - self.drill_level())

    def drill_seconds(self):
        return max(0, int(self.elapsed - self.drill_t0)) if self.drill_on else 0

    def practice_toggle_drill(self):
        """연습 모드: 압박 드릴 켜기/끄기. 켜면 보드를 새로 시작하고 처음부터 버팀 시간을 잼"""
        if not self.practice:
            return False
        self.drill_on = not self.drill_on
        if self.drill_on:
            self.practice_reset(announce=False)
            self.drill_t0 = self.elapsed
            self.drill_next = self.elapsed + 8.0
            self.add_floating_text("압박 드릴 시작!  쓰레기 줄이 주기적으로 들어옵니다. 줄을 지워 막으세요 (V로 끄기)", (255, 190, 90), duration=3.2, size=24, category="action")
        else:
            self.add_floating_text("압박 드릴 종료", (140, 230, 255), duration=1.8, size=24, category="action")
        return self.drill_on

    def _drill_tick(self):
        if not (self.practice and self.drill_on and self.local_is_alive) or self.elapsed < self.drill_next:
            return
        lines = self.DRILL_LINES[self.drill_level()]
        self.local_engine.queue_garbage(lines, source="드릴")
        self._play_hit_alarm(lines)
        self.drill_next = self.elapsed + self.drill_interval()

    def _drill_on_death(self):
        """드릴 중 보드가 끝까지 쌓임: 버틴 시간 기록 후 새 판으로 이어서 계속"""
        secs = self.drill_seconds()
        self.drill_last = secs
        new_best = secs > self.drill_best
        if new_best:
            self.drill_best = secs
        self.add_floating_text(f"드릴 종료: {secs}초 버팀  ·  막은 줄 {int(self.local_engine.garbage_canceled_total)}" + ("  ★ 최고 기록!" if new_best else f"  (최고 {self.drill_best}초)"),
                               (255, 215, 90) if new_best else (140, 230, 255), duration=3.6, size=24, category="action")
        self.practice_reset(announce=False)
        self.drill_t0 = self.elapsed
        self.drill_next = self.elapsed + 8.0

    PRACTICE_TASKS = tuple(g["text"] for g in challenges.PRACTICE_GOALS)       # 연습 과제 40개 (기초/중급/고급/마스터, 쉬운 순서, 앱이 달성 기록을 저장)

    def practice_current_task(self):
        """연습 과제: (번호, 문구). N 키로 고른 과제가 아직 안 끝났으면 그것, 아니면 못 깬 첫 과제. 모두 끝났으면 None"""
        ch = self.challenge
        if ch is None or self.challenge_kind != "practice":
            return None
        ids = ch.order
        if self.practice_focus in ids and self.practice_focus not in ch.done:
            i = ids.index(self.practice_focus)
        else:
            i = next((k for k, gid in enumerate(ids) if gid not in ch.done), None)
        return None if i is None else (i, ch.by_id[ids[i]]["text"])

    def practice_next_task(self, step=1):
        """N 키: 아직 못 깬 과제 중 다음/이전 과제로 (연습)"""
        ch = self.challenge
        if ch is None or self.challenge_kind != "practice":
            return
        todo = [gid for gid in ch.order if gid not in ch.done]
        if not todo:
            return
        cur = self.practice_current_task()
        cur_id = ch.order[cur[0]] if cur else todo[0]
        i = todo.index(cur_id) if cur_id in todo else 0
        self.practice_focus = todo[(i + step) % len(todo)]

    def practice_all_done(self):
        ch = self.challenge
        return ch is not None and self.challenge_kind == "practice" and len(ch.done) >= len(ch.order)

    @property
    def ta_best(self):
        """지금 고른 타임어택 종류의 최고 기록(초), 없으면 0"""
        return int(self.ta_bests.get(self.ta_mode or "quad", 0))

    def practice_cycle_ta(self):
        """Y 키: 타임어택 끄기 -> 쿼드 5번 -> 40줄 스프린트 -> T-스핀 3번 -> 더블 10번 -> T-스핀 더블 2번 -> 콤보 6 -> 끄기. 켤 때는 보드를 새로 시작해 공정하게 잼"""
        if not self.practice:
            return
        ids = [None] + [m[0] for m in challenges.TA_MODES]
        self.ta_mode = ids[(ids.index(self.ta_mode) + 1) % len(ids)]
        self.ta_n = 0
        if self.ta_mode is None:
            self.ta_t0 = None
            self.add_floating_text("타임어택 끔", (140, 230, 255), duration=1.6, size=24, category="action")
            return
        self.practice_reset(announce=False)
        self.ta_t0 = self.elapsed
        _id, name, goal, unit = challenges.TA_BY_ID[self.ta_mode]
        self.add_floating_text(f"타임어택: {name}  (목표 {goal}{unit} · Y로 종류 변경)", (255, 215, 90), duration=2.6, size=24, category="action")

    def _practice_check(self, info=None):
        """연습: 줄을 지울 때마다 과제 지표를 갱신하고 새로 달성한 과제를 알림. 타임어택이 켜져 있으면 진행량을 올림 (모든 과제를 깨면 쿼드 5번이 자동으로 켜짐)"""
        if not self.practice or self.challenge is None:
            return
        if info:
            self.challenge.on_clear(info)
            if self._auto_ta_start():
                pass
            elif self.ta_mode and self.ta_t0 is not None:
                self.ta_n = challenges.ta_next(self.ta_mode, self.ta_n, info)
                _id, name, goal, _unit = challenges.TA_BY_ID[self.ta_mode]
                if self.ta_n >= goal:
                    secs = max(1, int(self.elapsed - self.ta_t0))
                    self.ta_last = secs
                    best = int(self.ta_bests.get(self.ta_mode, 0))
                    new_best = best == 0 or secs < best
                    if new_best:
                        self.ta_bests[self.ta_mode] = secs
                        best = secs
                    self.add_floating_text(f"{name} {secs}초" + ("  ★ 최고 기록!" if new_best else f"  (최고 {best}초)"),
                                           (255, 215, 90) if new_best else (140, 230, 255), duration=3.2, size=26, category="action")
                    self.ta_t0, self.ta_n = self.elapsed, 0
        self._challenge_events()

    def _auto_ta_start(self):
        """연습 과제를 모두 깼으면 쿼드 타임어택을 자동으로 켬 (마지막 과제가 줄 지우기가 아니라 블록 수/드릴로 달성돼도 켜지도록 _challenge_events에서도 부름)"""
        if self.practice and self.challenge is not None and self.ta_mode is None and not self._ta_auto_done and self.practice_all_done():
            self._ta_auto_done = True
            self.add_floating_text("수련 완료!  타임어택을 시작합니다 (Y로 종류 변경)", (255, 215, 90), duration=3.2, size=24, category="action")
            self.ta_mode, self.ta_t0, self.ta_n = "quad", self.elapsed, 0
            return True
        return False

    def challenge_summary(self):
        """결과 화면용 (긴 문구, 짧은 문구). 오늘의 도전/주간 변형이 아니면 None. 예: ('오늘의 도전 ★★☆  쿼드 2회 ● · K.O. 3 ● · 10위 안 ○', '오늘의 도전 ★2/3')"""
        ch = self.challenge
        if ch is None or self.challenge_kind not in ("daily", "weekly"):
            return None
        label = "오늘의 도전" if self.challenge_kind == "daily" else f"주간 변형 · {(self.mutator or {}).get('name', '')}"
        stars = "".join("★" if gid in ch.done else "☆" for gid in ch.order)
        items = " · ".join(f"{ch.by_id[gid]['short']} {'●' if gid in ch.done else '○'}" for gid in ch.order)
        return f"{label} {stars}  {items}", f"{label} ★{len(ch.done)}/{len(ch.order)}"

    def _challenge_events(self):
        """추적기가 새로 달성한 과제를 꺼내 알림 (토스트/효과음). 저장은 앱이 challenge_saved 목록을 비우며 처리"""
        ch = self.challenge
        if ch is None:
            return
        for gid in ch.pop_new():
            g = ch.by_id[gid]
            self.challenge_saved.append(gid)
            if self.challenge_kind == "practice":
                nxt = self.practice_current_task()
                self.add_floating_text(f"★ 과제 완료!  {g['text']}" + (f"  → 다음: {nxt[1]}" if nxt else "  (모든 과제 완료!)"), (140, 255, 170), duration=2.8, size=26, category="action")
            else:
                n = len(ch.done)
                self.add_floating_text(f"★ 도전 달성!  {g['text']}  ({n}/{len(ch.order)})", (140, 255, 170), duration=3.0, size=26, category="action")
                self.add_commentary(f"{self._short_name(self.local_player_id)}  도전 달성! {g['short']}", (140, 255, 170), mine=True)
            if self.sound_mgr:
                self.sound_mgr.play('badge_up')
        self._auto_ta_start()

    def practice_reset(self, announce=True):
        """연습 모드: 보드를 새로 시작 (직접 초기화하거나 블록이 끝까지 쌓였을 때)"""
        if self.practice and self.challenge is not None:
            for _ in range(max(0, self.local_engine.lock_events - self._prac_locks)):
                self.challenge.on_lock(self.elapsed)         # 엔진을 바꾸기 전에 아직 세지 않은 블록 고정을 과제 추적기에 알림
        self.local_engine = BlockEngine()
        self._prac_locks = 0
        self._danger_since = None
        if self.ta_mode and self.ta_t0 is not None:
            self.ta_t0, self.ta_n = self.elapsed, 0             # 보드를 초기화하면 타임어택도 처음부터
        if announce:
            self.add_floating_text("연습 보드를 새로 시작했습니다", (140, 230, 255), duration=1.8, size=24, category="action")

    def _record_timeline(self, final=False):
        """1초마다 한 점 (경기 시각, 생존자 수, 내 스택 높이, 받을 공격). 최대 1800점(30분)"""
        if len(self.timeline) >= 1800 and not final:
            return
        self.timeline.append((round(self.elapsed, 1), self.alive_count, self._local_stack_height(), self.local_engine.incoming_garbage))

    def _local_stack_height(self):
        return BOARD_HEIGHT - self.local_engine.get_highest_block_row()

    DANGER_BEAT_H = 15                # 스택이 이 높이 이상이면 위기 박동음 재생 (18줄 이상이면 더 빠르게)

    def _track_danger(self):
        """매 프레임: 내 스택이 위험 높이에 들어온 시각을 기록하고, 위험하게 높으면 박동음을 울림"""
        h = self._local_stack_height()
        self._duck_bgm(0.55 if (h >= self.CLUTCH_DANGER_H and self.local_is_alive and not self.match_finished) else 1.0)      # 위기 동안 BGM을 낮춰 심장 박동이 또렷하게, 탈출하면 풀림
        if self.sound_mgr and h >= self.DANGER_BEAT_H:
            if self.elapsed - self._last_beat >= (0.8 if h >= 18 else 1.3):
                self._last_beat = self.elapsed
                self.sound_mgr.play('heartbeat')
        if h >= self.CLUTCH_DANGER_H:
            if self._danger_since is None:
                self._danger_since = self.elapsed
        elif h <= self.CLUTCH_SAFE_H:
            self._danger_since = None

    def _check_clutch_save(self):
        h = self._local_stack_height()
        if (self._danger_since is None or h > self.CLUTCH_SAFE_H
                or self.elapsed - self._danger_since < self.CLUTCH_MIN_SECS
                or self.elapsed - self._last_clutch < self.CLUTCH_COOLDOWN):
            return
        self._last_clutch = self.elapsed
        self._danger_since = None
        if self.challenge is not None:
            self.challenge.on_clutch()
            self._challenge_events()
        if self.attacks_enabled:
            self.local_engine.garbage_to_send += self.CLUTCH_BONUS
        bonus = f" +{self.CLUTCH_BONUS}줄" if self.attacks_enabled else ""
        self.add_floating_text(f"★ 위기 탈출!{bonus} ★", (255, 215, 0), duration=2.2, size=30, category="action", tier=2)
        self.add_commentary(f"{self._short_name(self.local_player_id)}  위기 탈출!", (255, 215, 0), mine=True)
        self.trigger_screen_shake(8.0)
        self.clutch_times.append(self.elapsed)
        self._duck_bgm(1.0)                                      # 조여 있던 BGM이 풀리면서 위기 탈출 효과음
        if self.sound_mgr:
            self.sound_mgr.play('clutch')

    def on_lines_cleared(self, cleared):
        """라인 클리어 공통 핸들러 (하드 드롭, 소프트 드롭, 자연 낙하 공통 처리)"""
        if cleared <= 0:
            return
        self._check_clutch_save()
            
        info = getattr(self.local_engine, 'last_clear_info', None) or {}
        is_tspin = info.get('is_tspin', False)
        is_b2b = info.get('is_b2b', False)
        chain = info.get('b2b_chain', 0)
        if self.practice:
            self._practice_check(dict(info, cleared=cleared))
        elif self.challenge is not None:
            self.challenge.on_clear(dict(info, cleared=cleared))
            self._challenge_events()
        
        if self.sound_mgr:
            combo = max(0, self.local_engine.combo)          # 0 = 첫 클리어, 이어질수록 증가 -> 삭제음이 한 음씩 올라감
            if is_tspin:
                self.sound_mgr.play('tspin', combo=combo)
                if cleared >= 2:
                    self.sound_mgr.play('tspin_big')          # T-스핀 더블/트리플: 저음 붐을 겹쳐 짧은 tspin 음보다 크게
            elif cleared >= 4:
                self.sound_mgr.play('quad', combo=combo)
            else:
                self.sound_mgr.play('clear', combo=combo)
                if cleared == 3:
                    self.sound_mgr.play('thump_s')            # 트리플: 저음을 겹쳐 싱글/더블과 귀로 구분
            if is_b2b and chain >= 1:
                self.sound_mgr.play('b2b', combo=chain)       # B2B가 이어질수록 높고 화려해지는 반짝임
            if combo >= 1:
                self.sound_mgr.play('combo', combo=combo)    # 콤보 차임 (콤보 단계에 맞는 음)
            if is_tspin and cleared >= 2:                    # 로봇 아나운서 (설정이 켜져 있을 때만, 큰 순간에만)
                self.sound_mgr.play('vo_tspin')
            elif cleared >= 4:
                self.sound_mgr.play('vo_quad')
            elif combo in (5, 8, 12):
                self.sound_mgr.play('vo_combo')
        self._check_score_record()
        self.max_b2b_chain = max(self.max_b2b_chain, chain if is_b2b else 0)
        canceled = int(info.get('canceled', 0) or 0)
        if canceled > 0:                                         # 줄을 지워 막은 공격: 토스트 + 받을 공격 칸 반응(렌더러) + 방패음
            self.cancel_seq += 1
            self.cancel_last = (time.time(), canceled)
            self.add_floating_text(f"방어 −{canceled}줄", (110, 235, 255), duration=1.6, size=22, category="attack")
            if self.sound_mgr and canceled >= 2:
                self.sound_mgr.play('shield')
                
        me = self._short_name(self.local_player_id)
        if info.get('is_pc'):
            self.pc_count += 1
            self.pc_t = time.time()
            self.trigger_screen_shake(18.0)
            self.trigger_impact(1.0)
            self.add_commentary(f"★ {me}  PERFECT CLEAR! ★", (255, 225, 90), prio=1)
            if self.sound_mgr:
                self.sound_mgr.play('perfect')
                self.sound_mgr.play('vo_perfect')
        # T-스핀/쿼드는 같은 순간의 액션 배너가 이미 보여 주므로 전광판 중계는 생략 (한 사건에 같은 말이 여러 곳에 뜨지 않게)
        if self.local_engine.combo >= 4:
            self.add_commentary(f"{me}  {self.local_engine.combo}연속 콤보!", (255, 120, 220), mine=True)

        if is_tspin:
            self.trigger_screen_shake(14.0, (1, 0))
            prefix = f"★ B2B x{chain} " if (is_b2b and chain >= 1) else ("★ B2B " if is_b2b else "★ ")
            if cleared == 3:
                self.trigger_impact(0.8)
                self.add_floating_text(f"{prefix}T-스핀 트리플! ★", (255, 130, 255), duration=2.5, size=32, category="action", tier=3)
            elif cleared == 2:
                self.trigger_impact(0.45)                                  # 쿼드·T-스핀 더블도 약하게 번쩍임 (트리플/퍼펙트는 더 강하게)
                self.add_floating_text(f"{prefix}T-스핀 더블! ★", (255, 150, 255), duration=2.2, size=30, category="action", tier=2)
            elif cleared == 1:
                self.add_floating_text(f"{prefix}T-스핀 싱글! ★", (255, 180, 255), duration=1.8, size=26, category="action", tier=1)
            else:
                self.add_floating_text("★ T-스핀 보너스! ★", (255, 180, 255), duration=1.4, size=22, category="action")
        elif cleared >= 4:
            self.trigger_screen_shake(14.0, (0, 1))
            self.trigger_impact(0.45)
            if is_b2b:
                self.add_floating_text(f"★ B2B x{chain} 쿼드! ★" if chain >= 1 else "★ B2B 쿼드! ★", (255, 235, 80), duration=2.4, size=34, category="action", tier=2)
            else:
                self.add_floating_text("★ 쿼드! ★", (255, 215, 0), duration=2.2, size=32, category="action", tier=2)
        elif cleared == 3:
            self.add_floating_text("★ 트리플 클리어! ★", (100, 240, 255), duration=1.8, size=28, category="action", tier=1)
        # 싱글/더블은 자주 나오고 공격도 약해서 배너를 띄우지 않음 (위기 때 보드를 가리고 정말 큰 기술의 배너가 묻힘)
            
        if self.local_engine.combo > 0:
            self.add_floating_text(f"[{self.local_engine.combo}연속 콤보!]", (255, 120, 220), duration=1.8, size=22, category="combo")
        if info.get('is_pc'):                                                    # 일반 클리어 문구보다 나중에 넣어 가장 눈에 띄게 표시
            self.add_floating_text("★ PERFECT CLEAR! ★", (255, 225, 90), duration=3.2, size=44, category="action", tier=3)
        self._check_live_achievements()

    def _process_ko_events(self):
        """K.O. 구슬이 K.O. 칸에 도착하는 시점: 처치 수에 맞는 높이의 '띵' 소리, 배지 승급이면 승급음/배너"""
        if not self._ko_events:
            return
        now = time.time()
        due = [e for e in self._ko_events if now >= e["due"]]
        if not due:
            return
        self._ko_events = [e for e in self._ko_events if now < e["due"]]
        for e in due:
            if self.sound_mgr:
                self.sound_mgr.play('ko_orb', combo=e["n"])
            if e["lvl_up"]:
                if self.sound_mgr:
                    self.sound_mgr.play('badge_up')
                self.add_floating_text(f"★ 배지 승급 Lv.{e['lvl']}! 공격력 +{e['pct']} 강화! ★", (255, 235, 100), duration=3.0, size=26, category="action", tier=2)

    def _announce_milestones(self, victim_id):
        """누군가 탈락한 뒤: 내가 살아 있을 때 TOP N 진입과 결승 1:1을 알림 (조용히 숫자만 줄어들던 순위가 보상이 되게)"""
        if victim_id == self.local_player_id or not self.local_is_alive or not self.attacks_enabled or self.practice or self.total_players < 8:
            return
        n = self.alive_count
        if n == 2 and not self._final_announced:
            self._final_announced = True
            self.final_opp_id = next((pid for pid, p in self.players.items() if p["is_alive"] and pid != self.local_player_id and not self.is_ally(self.local_player_id, pid)), None)
            opp = self._short_name(self.final_opp_id) if self.final_opp_id else ""
            self.trigger_screen_shake(8.0)
            self.trigger_impact(0.6)
            self.add_floating_text(f"★ FINAL DUEL ★  vs {opp}" if opp else "★ FINAL DUEL ★", (255, 215, 90), duration=3.2, size=40, category="action", tier=3)
            if self.sound_mgr:
                self.sound_mgr.play('final')
                self.sound_mgr.play('vo_final')
            return
        p2_thr = int(self.total_players * 0.5)
        p3_thr = max(2, int(round(self.total_players * 0.1)))
        if n in (50, 25, 10, 5, 3) and n < self.total_players and n not in self._top_announced and n not in (p2_thr, p3_thr):      # 페이즈 배너와 같은 인원이면 중복 안내하지 않음
            self._top_announced.add(n)
            self.add_floating_text(f"★ TOP {n} 진입! ★", (255, 225, 110), duration=2.4, size=30, category="action", tier=2)
            if self.sound_mgr:
                self.sound_mgr.play('top_up')
                if n == 10:
                    self.sound_mgr.play('vo_top10')
        self._check_rank_records(n)

    def _new_golden_target(self):
        """2·3단계가 시작될 때 살아 있는 봇 한 명을 새 골든 타깃으로 지정 (현재 타깃을 못 잡았어도 교체). 처치하면 경험치만 +30, 공격력 보너스 없음"""
        if self.bounty_id is None or not self.attacks_enabled or self.practice:
            return                                                  # 현상금 봇이 없는 경기(네트워크/연습/서바이벌)는 골든 타깃도 없음
        cands = sorted(pid for pid, p in self.players.items() if p["is_ai"] and p["is_alive"] and pid != self.rival_id and pid != self.bounty_id)
        if not cands:
            return
        self.bounty_id = self._bounty_rng.choice(cands)
        self.bounty_claimed = False
        self.add_floating_text("★ 새 골든 타깃 지정! 금빛 $ 카드를 노리세요 ★", (255, 210, 90), duration=2.6, size=22, category="action", tier=1)
        if self.sound_mgr:
            self.sound_mgr.play('vo_golden')

    def _live_record_toast(self, key, text, tier=2):
        if key in self._live_rec:
            return
        self._live_rec.add(key)
        self.add_floating_text(text, (255, 225, 110), duration=2.6, size=26, category="action", tier=tier)
        if self.sound_mgr:
            self.sound_mgr.play('top_up')

    def _check_kill_records(self):
        """K.O.를 낼 때마다: 개인 최고 K.O. 기록까지 1명 / 기록 돌파"""
        mk = (self.bests or {}).get("max_ko", 0)
        if mk < 2 or self.practice or not self.attacks_enabled:
            return
        if self.local_ko_count == mk - 1:
            self._live_record_toast("ko_near", f"K.O. 개인 최고({mk}명)까지 1명!", tier=1)
        elif self.local_ko_count == mk + 1:
            self._live_record_toast("ko_new", f"★ K.O. 개인 최고 기록 돌파! ({self.local_ko_count}명)", tier=2)

    def _check_rank_records(self, alive_n):
        """생존자 수가 줄 때마다: 개인 최고 순위 타이 / 돌파 (내가 살아 있을 때만 호출됨)"""
        br = (self.bests or {}).get("best_rank", 0)
        if br <= 2 or self.practice or not self.attacks_enabled:
            return
        if alive_n == br:
            self._live_record_toast("rank_tie", f"최고 순위 #{br} 타이! 한 명만 더!", tier=1)
        elif alive_n == br - 1:
            self._live_record_toast("rank_new", f"★ 개인 최고 순위 갱신! (기존 #{br})", tier=2)

    def _check_score_record(self):
        bs = (self.bests or {}).get("best_score", 0)
        if bs > 0 and self.local_engine.score > bs and not self.practice and self.attacks_enabled:
            self._live_record_toast("score_new", "★ 개인 최고 점수 돌파!", tier=2)

    def _update_combo_layer(self):
        """콤보 5 이상 / B2B 3 이상이면 BGM 위에 하이햇 층 (콤보 8 이상이면 더 크게), 콤보가 끊기면 꺼짐"""
        if not self.sound_mgr:
            return
        e = self.local_engine
        if self.match_finished or not self.local_is_alive or self.practice:
            lvl = 0
        else:
            lvl = 2 if e.combo >= 8 else (1 if (e.combo >= 5 or (e.b2b and e.b2b_chain >= 3)) else 0)
        if lvl != self._layer_seen:
            self._layer_seen = lvl
            self.sound_mgr.set_combo_layer(lvl)

    # 경기 중에 알려 줄 수 있는 업적 조건 (저장과 정식 판정은 경기가 끝날 때 stats_manager가 함. 여기서는 달성 순간의 기쁨만 먼저 보여 줌)
    LIVE_ACH = {
        "first_ko": lambda m: m.local_ko_count >= 1,
        "ko5": lambda m: m.local_ko_count >= 5,
        "ko10": lambda m: m.local_ko_count >= 10,
        "ko15": lambda m: m.local_ko_count >= 15,
        "combo8": lambda m: getattr(m.local_engine, "max_combo", 0) >= 8,
        "combo12": lambda m: getattr(m.local_engine, "max_combo", 0) >= 12,
        "top10": lambda m: m.total_players >= 30 and m.alive_count <= 10 and m.local_is_alive,
        "marathon": lambda m: m.local_is_alive and m.elapsed >= 420,
        "ironman": lambda m: m.local_is_alive and m.elapsed >= 540,
    }

    def _check_live_achievements(self):
        if not self.live_ach or self.practice or not self.attacks_enabled:
            return
        for aid, title in list(self.live_ach.items()):
            if aid in self.live_ach_done:
                continue
            fn = self.LIVE_ACH.get(aid)
            if fn and fn(self):
                self.live_ach_done.add(aid)
                if aid == "first_ko" and self.first_ko_ever:
                    continue                                       # 평생 첫 K.O.는 전용 큰 배너가 있음
                self.add_floating_text(f"★ 업적 달성!  {title}", (255, 215, 90), duration=2.8, size=30, category="action", tier=2)
                if self.sound_mgr:
                    self.sound_mgr.play('badge_up')

    HIGHLIGHT_LABELS = {"perfect": ("퍼펙트 클리어", (255, 225, 90)), "comeback": ("역전승", (255, 150, 90)), "chain_ko": ("K.O. 연쇄", (255, 110, 110)),
                        "combo10": ("콤보 폭주", (255, 120, 220)), "b2b5": ("B2B 장인", (255, 215, 0)), "wall": ("철벽 수비", (110, 235, 255)),
                        "bounty": ("현상금 사냥", (255, 200, 60)), "revenge": ("복수 성공", (255, 190, 80))}

    def highlights(self):
        """이번 경기의 '명장면' id 목록 (결과 화면 도장 / 기록 집계용)"""
        out = []
        if self.pc_count > 0:
            out.append("perfect")
        if getattr(self, "local_rank", 0) == 1 and self.match_finished and any(self.elapsed - t <= 60.0 for t in self.clutch_times):
            out.append("comeback")                                  # 마지막 1분 안에 위기를 넘기고 우승
        kt = self.ko_times
        if any(kt[i + 2] - kt[i] <= 10.0 for i in range(len(kt) - 2)):
            out.append("chain_ko")                                  # 10초 안에 3킬
        if getattr(self.local_engine, "max_combo", 0) >= 10:
            out.append("combo10")
        if self.max_b2b_chain >= 5:
            out.append("b2b5")
        if getattr(self.local_engine, "garbage_canceled_total", 0) >= 40:
            out.append("wall")
        if self.bounty_claimed:
            out.append("bounty")
        if self.rival_defeated:
            out.append("revenge")
        return out

    def defeat_summary(self):
        """결과 화면 "패인 한 줄"(+ 다음에 해 볼 한 줄): 탈락 직전 10초 동안 무슨 일이 있었는지 (타임라인: 1초마다 (시각, 생존자, 내 스택, 받을 공격)).
        반환: [첫째 줄, 둘째 줄(없으면 생략)] 또는 근거가 부족하면 None"""
        tl = getattr(self, "timeline", None) or []
        if self.local_is_alive or len(tl) < 3:
            return None
        last = tl[-10:]
        peak_in = max(x[3] for x in last)
        peak_h = max(x[2] for x in last)
        atk = getattr(self, "local_death_attackers", 0)
        top = max(self.local_hits_from.items(), key=lambda kv: kv[1]) if self.local_hits_from else None
        mult = self.attack_multiplier() if self.attacks_enabled else 1.0
        if peak_in >= 8 or atk >= 3:
            lead = "집중 공격에 밀렸어요"
            tip = ("줄을 지우면 받을 공격이 먼저 깎여요. '연습하기' 버튼으로 쓰레기를 받으며 막는 연습을 해 보세요" if getattr(self, "pad_ui", False)
                   else "줄을 지우면 받을 공격이 먼저 깎여요. 연습 모드(P)에서 G키로 쓰레기를 받으며 막는 연습을 해 보세요")
        elif peak_in < 4 and peak_h >= 16:
            lead = "스스로 쌓은 높이가 문제였어요"
            tip = ("높게 쌓기 전에 줄을 먼저 지워 보세요. '연습하기' 버튼으로 판을 비우며 연습할 수 있어요" if getattr(self, "pad_ui", False)
                   else "높게 쌓기 전에 줄을 먼저 지워 보세요. 연습 모드(P)에서 B키로 판을 비우며 연습할 수 있어요")
        else:
            lead = "버티지 못했어요"
            tip = "탈락 직전 받은 공격을 줄 지우기로 상쇄하는 것을 노려 보세요 (" + ("'연습하기' 버튼" if getattr(self, "pad_ui", False) else "연습 모드 P · G키") + ")"
        bits = [f"받을 공격 최대 {peak_in}줄"]
        if atk >= 1:
            bits.append(f"나를 노린 상대 {atk}명")
        if top and top[1] >= 4:
            bits.append(f"가장 많이 보낸 {self._short_name(top[0])} {top[1]}줄")
        if mult > 1.0:
            bits.append(f"후반전 ×{mult:.1f}")
        return [f"탈락 직전 10초: {lead}  ({' · '.join(bits)})", tip]

    COUNTDOWN_SECS = 3.0               # 혼자 하는 경기 시작 전 3-2-1 (그동안 경기 정지)

    def countdown_left(self):
        """시작 카운트다운이 남은 시간(초). 0이면 경기 진행 중"""
        return max(0.0, getattr(self, "countdown_until", 0.0) - time.time())

    ESCALATION_WARN_LEAD = 30.0        # 후반 공격력 증폭 시작 이 시간(초) 전에 미리 알림

    def _announce_escalation(self):
        """보이지 않던 규칙(5분 뒤 매분 공격력 +20%)을 미리 예고하고, 단계가 오를 때마다 알림"""
        if not self.attacks_enabled or self.practice or self.ESCALATION_START is None:
            return
        if not getattr(self, "_esc_warned", False) and self.elapsed >= self.ESCALATION_START - self.ESCALATION_WARN_LEAD:
            self._esc_warned = True
            start_min = f"{self.ESCALATION_START / 60:.0f}" if self.ESCALATION_START % 60 == 0 else f"{self.ESCALATION_START / 60:.1f}"
            self.add_commentary(f"곧 후반전: {start_min}분부터 매분 공격력 +20% (최대 3배)", (255, 190, 90), prio=1)
            self.add_floating_text(f"곧 후반전! {start_min}분부터 매분 공격력이 20%씩 강해집니다", (255, 190, 90), duration=4.0, size=22, category="pin")
        mult = self.attack_multiplier()
        lvl = int((mult - 1.0) / self.ESCALATION_PER_MIN + 1e-9) if mult > 1.0 else 0      # 20% 단계가 오를 때만 알림
        if lvl > getattr(self, "_esc_level", 0):
            self._esc_level = lvl
            self.add_commentary(f"후반전 공격력 ×{1.0 + lvl * self.ESCALATION_PER_MIN:.1f}", (255, 170, 80))
            self.add_floating_text(f"후반전: 모든 공격력 ×{1.0 + lvl * self.ESCALATION_PER_MIN:.1f}", (255, 170, 80), duration=3.5, size=22, category="pin")

    def update(self, dt):
        """매칭 전체 프레임 업데이트"""
        # 스크린 셰이크 감쇠 (경기가 끝난 뒤에도 줄어들어야 함: 우승/마지막 탈락의 흔들림이 순위표 뒤에서 계속 남던 버그)
        if self.screen_shake > 0:
            self.screen_shake = max(0.0, self.screen_shake - dt * 25.0)
        if self.screen_shake <= 0:
            self.shake_dir = None
        self._process_ko_events()                                # (경기가 끝난 뒤에도 마지막 K.O.의 구슬 도착 연출은 마저 처리)
        self._update_combo_layer()
        if self.match_finished:
            return
            
        now = time.time()
        self.elapsed += dt
        self._announce_escalation()
        
        # 플로팅 텍스트 수명 체크
        self.floating_texts = [ft for ft in self.floating_texts if now - ft["birth"] < ft["duration"]]
        
        # 1. 로컬 플레이어 중력 동적 조절 및 엔진 틱 업데이트 (자연 낙하)
        if self.local_is_alive:
            self.local_engine.badge_rate = self.get_badge_info()[1]
            self.local_engine.fall_speed = self._get_dynamic_fall_speed()
            cleared = self.local_engine.update(dt)
            if cleared > 0:
                self.on_lines_cleared(cleared)
            self._track_danger()
            if self.attacks_enabled and not self.practice:
                c = self.local_engine.combo                      # 콤보 끊김: 3 이상 쌓아 둔 콤보가 이번 블록에서 줄을 못 지워 끝남
                if self._prev_combo >= 3 and c < 0:
                    self.add_floating_text(f"콤보 끝 ×{self._prev_combo}", (170, 180, 205), duration=1.4, size=22, category="combo")
                    if self.sound_mgr:
                        self.sound_mgr.play('combo_break')
                self._prev_combo = c
            if self.elapsed - self._tl_t >= 1.0:
                self._tl_t = self.elapsed
                self._record_timeline()
                self._check_live_achievements()                  # 생존 시간/TOP 10 같은 시간 기반 업적은 1초마다 확인

        # 2. 로컬 플레이어 타겟 갱신
        self.players[self.local_player_id]["target_id"] = self.get_target_for(self.local_player_id, self.local_target_mode)
        
        if self.challenge is not None and not self.practice:
            self.challenge.tick(self.elapsed, self.local_is_alive, self.alive_count, self.attack_multiplier())
            self._challenge_events()
        self._drill_tick()
        if self.practice and self.challenge is not None:                 # 연습: 블록이 고정된 횟수를 추적기에 알림 (블록 수/초당 개수 과제)
            ev = self.local_engine.lock_events
            if ev < self._prac_locks:
                self._prac_locks = 0
            for _ in range(ev - self._prac_locks):
                self.challenge.on_lock(self.elapsed)
            if ev != self._prac_locks:
                self._prac_locks = ev
                self._challenge_events()
        if self.practice and self.challenge is not None and self.drill_on:
            self.challenge.on_drill(self.drill_seconds(), self.drill_level() + 1)
            self._challenge_events()
        # 3. 로컬 플레이어 게임 오버 검사
        if self.local_is_alive and self.local_engine.game_over:
            if self.practice:
                if self.drill_on:
                    self._drill_on_death()
                else:
                    self.practice_reset()
            else:
                self._eliminate_player(self.local_player_id)
            
        # 4. 로컬 플레이어 공격 발생 처리 (오토매틱 공격 + 배지 증폭 + 카운터 보너스)
        if self.local_engine.garbage_to_send > 0:
            target = self.players[self.local_player_id]["target_id"] if self.attacks_enabled else None
            if target:
                target_p = self.players.get(target, {})
                target_name = target_p.get("name", target)
                
                # 배지 증폭은 엔진에서 상쇄 이전에 이미 적용됨
                base_garbage = self.local_engine.garbage_to_send
                badge_lvl, badge_rate, badge_pct = self.get_badge_info()
                
                # 조준당하고 있을 때 공격자 카운터 보너스
                att_count = self.get_attackers_count_for(self.local_player_id)
                attacker_bonus = ATTACKER_BONUS.get(min(6, att_count), 0)
                
                total_attack = base_garbage + attacker_bonus
                mult = self.attack_multiplier()
                shown_attack = int(math.ceil(total_attack * mult)) if mult > 1.0 else total_attack      # apply_attack이 실제로 보내는 줄 수 (표시와 같게)
                gm = self.CUSTOM_GARBAGE.get(self._custom("garbage", "normal"), 1.0)
                if gm != 1.0:
                    shown_attack = max(1, int(math.ceil(shown_attack * gm)))                          # 커스텀 규칙의 쓰레기 배율도 같게
                # 반격(ATTACKERS) 모드: 나를 노리는 플레이어가 둘 이상이면 전원에게 동시에 같은 공격을 보냄 (역전 기회)
                targets = [target]
                if self.local_target_mode == "ATTACKERS" and not self.local_manual_target_id:
                    attackers = [pid for pid, p in self.players.items()
                                 if p["is_alive"] and pid != self.local_player_id and p.get("target_id") == self.local_player_id]
                    if len(attackers) >= 2:
                        targets = attackers[:MULTI_TARGET_MAX]
                for i, t in enumerate(targets):
                    self.apply_attack(self.local_player_id, t, total_attack, multi=len(targets), order=i)
                self.total_attacks_sent += total_attack * len(targets)
                if self.challenge is not None:
                    self.challenge.on_attack(shown_attack, len(targets))
                if self.sound_mgr:
                    self.sound_mgr.play('attack')
                if len(targets) >= 2:
                    self.add_floating_text(f"★ 다중 포격! +{shown_attack}줄 × {len(targets)}명 ★", (255, 170, 90), duration=2.6, size=28, category="action")
                    self.add_commentary(f"{self._short_name(self.local_player_id)}  {len(targets)}명에게 동시 포격! {shown_attack}줄", (255, 170, 90), mine=True)
                    self.trigger_screen_shake(10.0)
                
                lbl = "[자동 반격]" if (self.local_target_mode == "ATTACKERS" and target_p.get("target_id") == self.local_player_id) else "[공격 발송]"
                tags = []                                                  # 괄호 하나에 짧게: "(배지2 · 역습+3 · ×1.4)"
                if badge_lvl > 0:
                    tags.append(f"배지{badge_lvl}")
                if attacker_bonus > 0:
                    tags.append(f"역습+{attacker_bonus}")
                if mult > 1.0:
                    tags.append(f"×{mult:.1f}")                            # 후반 증폭이 걸린 상태임을 알림
                bonus_str = f" ({' · '.join(tags)})" if tags else ""
                self.log_event("attack", to=target, lines=shown_attack, mult=round(mult, 2))

                if len(targets) < 2:                             # 다중 포격은 위의 전용 알림만 표시 (중복 방지)
                    self.add_floating_text(f"{lbl} +{shown_attack}줄 >> {target_name}{bonus_str}", (255, 130, 130), duration=2.4, size=22, category="attack")
            elif not self.attacks_enabled:
                self.total_attacks_sent += self.local_engine.garbage_to_send     # 서바이벌: 실제로 보내지는 않지만 만들어 낸 공격력은 APM에 반영
                if self.practice:
                    self.add_floating_text(f"[연습] 이 클리어의 공격력 +{self.local_engine.garbage_to_send}줄 (실제로는 보내지 않아요)", (150, 220, 255), duration=2.2, size=22, category="attack")
            self.local_engine.garbage_to_send = 0
            
        # 로컬 플레이어 상태 갱신
        self.players[self.local_player_id]["compact_grid"] = self.local_engine.get_compact_grid()
        self.players[self.local_player_id]["highest_y"] = self.local_engine.get_highest_block_row()
        self.players[self.local_player_id]["is_alive"] = self.local_is_alive
        self.players[self.local_player_id]["ko_count"] = self.local_ko_count
        self.players[self.local_player_id]["score"] = self.local_engine.score
        self.players[self.local_player_id]["cg"] = grid_rows(self.local_engine.grid)
        self.players[self.local_player_id]["ig"] = self.local_engine.incoming_garbage
        self.players[self.local_player_id]["cpiece"] = piece_state(self.local_engine)
        self.players[self.local_player_id]["next"] = list(self.local_engine.next_queue[:3])
        self.players[self.local_player_id]["hold"] = self.local_engine.hold_piece
        self.players[self.local_player_id]["lines"] = self.local_engine.lines_cleared_total
        self.players[self.local_player_id]["attacks"] = self.total_attacks_sent

        # 서바이벌 모드: 공격이 없어 경기가 끝나지 않을 수 있으므로, 일정 시간 뒤부터 모두에게 주기적으로 쓰레기 줄이 올라옴 (상대의 공격이 아니라 시간 압박)
        if not self.attacks_enabled and not self.match_finished and not self.practice:
            self._survival_pressure(dt)
        elif self.attacks_enabled and not self.match_finished and self.elapsed >= self.BATTLE_PRESSURE_START:
            self._survival_pressure(dt, self.BATTLE_PRESSURE_START, "서든 데스")      # 배틀로얄도 9분이 지나면 시간 압박: 소수의 봇이 서로 끝내지 못해도 경기가 반드시 끝남

        # 생존자 수에 따른 페이즈 전환 마일스톤 연출
        # (인원이 적은 대전에서는 시작부터 '최후의 결전'이 되지 않도록 전체 인원 대비 비율로 판정. 8명 미만은 연출 없음)
        p2_thr = int(self.total_players * 0.5)
        p3_thr = max(2, int(round(self.total_players * 0.1)))
        if self.total_players >= 8 and self.alive_count <= p2_thr and self.phase < 2:
            self.phase = 2
            self.trigger_screen_shake(10.0)
            if self.sound_mgr:
                self.sound_mgr.play('phase_up')
            self.add_commentary("PHASE 2 돌입  ·  생존자 절반", (255, 215, 0), prio=1)
            self.add_floating_text(f"★ [PHASE 2] 생존자 {p2_thr}인 돌파! ★", (255, 215, 0), duration=3.0, size=32, category="action", tier=2)
            self._new_golden_target()
        if self.total_players >= 8 and self.alive_count <= p3_thr and self.phase < 3:
            self.phase = 3
            self.trigger_screen_shake(16.0)
            self.trigger_impact(0.6)
            if self.sound_mgr:
                self.sound_mgr.play('phase_up')
            self.add_commentary(f"FINAL {p3_thr}  ·  최후의 결전", (255, 90, 90), prio=1)
            self.add_floating_text(f"★ [FINAL {p3_thr}] 최후의 결전! ★", (255, 75, 75), duration=3.5, size=34, category="action", tier=3)
            self._new_golden_target()

        # 5. 네트워크 수신 공격 처리
        if self.net_mgr and self.net_mgr.incoming_attacks:
            while self.net_mgr.incoming_attacks:
                from_id, to_id, lines = self.net_mgr.incoming_attacks.pop(0)
                if from_id != self.local_player_id:
                    self.apply_attack(from_id, to_id, lines, from_network=True)

        # 6. AI 봇들 업데이트 (분산 실행 및 실시간 난이도 스케일링)
        bot_pool.pump()                                 # 작업 프로세스가 끝낸 봇 계산 결과를 받아옴
        bot_brain.begin_frame(BOT_SEARCH_BUDGET * getattr(self, "budget_share", 1.0))       # 이번 프레임에 봇 전원이 함께 쓸 수 있는 탐색 시간
        items = list(self.players.items())
        if items:                                        # 예산이 모자라도 특정 봇만 굶지 않도록 시작 위치를 돌려 가며 처리
            off = self._bot_rr % len(items)
            items = items[off:] + items[:off]
            self._bot_rr += 5
        for pid, p in items:
            if self.match_finished:
                break                                  # 승자가 정해졌으면 남은 봇을 더 처리하지 않음
            if not p["is_alive"] or not p["is_ai"] or not p["bot"] or self.practice:
                continue                               # 연습 모드: 상대 자리는 움직이지 않는 빈 보드 (경기가 끝나지 않게)
                
            # 봇 난이도 가속도 인원 비율 기준 (100인 대전 기준으로 환산)
            p["bot"].adjust_for_alive_count(int(round(self.alive_count / max(1, self.total_players) * 100)))
                
            # AI 타겟팅
            if not p["target_id"] or random.random() < 0.03:
                trait = p.get("trait", "")
                if p["bot"].difficulty in ("hard", "master"):
                    # 강한 봇: 가끔은 나를 노리는 상대에게 반격(반격형은 자주, 저격형은 안 함), 대부분은 위험도(높이+들어올 쓰레기)가 높은 상대를 골라 마무리
                    retaliate = self.RETALIATE_CHANCE.get(trait, self.RETALIATE_DEFAULT)
                    attackers = [q for q, pp in self.players.items() if pp["is_alive"] and q != pid and pp.get("target_id") == pid] if random.random() < retaliate else []
                    p["target_id"] = random.choice(attackers) if attackers else self._smart_target(pid)
                elif p["bot"].difficulty == "normal" and random.random() < self.SMART_TARGET_CHANCE.get(trait, self.SMART_TARGET_DEFAULT):
                    p["target_id"] = self._smart_target(pid)
                else:
                    p["target_id"] = self._spread_random_target(pid)
                
            # 봇도 K.O.를 쌓으면 배지로 공격력이 오름 (BADGES 조준 모드가 봇 상대로도 의미가 있도록). 봇 상한은 BOT_BADGE_CAP
            if p.get("_badge_ko") != p.get("ko_count", 0) + p.get("badge_extra", 0):      # 배지 점수가 바뀔 때만 다시 계산 (프레임마다 100번 부르지 않게)
                p["_badge_ko"] = p.get("ko_count", 0) + p.get("badge_extra", 0)
                p["_badge_rate"] = min(self.BOT_BADGE_CAP, get_badge_info(p["_badge_ko"])[1]) if (self.attacks_enabled and self._custom("badges", True) is not False) else 0.0
            p["bot"].engine.badge_rate = p.get("_badge_rate", 0.0)
            # AI 틱
            att = p["bot"].update(dt)
            if att > 0 and not self.attacks_enabled:
                p["attacks"] += att                                  # 서바이벌: 봇이 만들어 낸 공격력도 APM에 반영 (전달은 안 됨)
            if att >= 3 and p["bot"].difficulty in ("hard", "master"):
                p["target_id"] = self._smart_target(pid, att) or p["target_id"]      # 큰 공격은 탈락시킬 수 있는 상대에게 몰아줌
            if att > 0 and p["target_id"]:
                tgt = p["target_id"]
                if tgt not in self.players or not self.players[tgt]["is_alive"]:
                    tgt = p["target_id"] = self.get_target_for(pid, "KO")      # 조준하던 상대가 방금 탈락했으면 즉시 다시 조준
                if tgt:
                    self.apply_attack(pid, tgt, att)
            if p["bot"].engine.perfect_clears > p.get("_pc_seen", 0):
                p["_pc_seen"] = p["bot"].engine.perfect_clears
                self.add_commentary(f"★ {self._short_name(pid)}  PERFECT CLEAR! ★", (255, 225, 90), prio=1)
                
            # 상태 동기화
            p["score"] = p["bot"].engine.score
            p["lines"] = p["bot"].engine.lines_cleared_total
            p["ig"] = p["bot"].engine.incoming_garbage
            eng = p["bot"].engine
            gkey = (eng.lock_events, eng.garbage_pushed_total, eng.lines_cleared_total)
            if p.get("_cg_key") != gkey or "cg" not in p:              # 격자는 고정/쓰레기/줄 제거 때만 바뀜
                p["cg"] = grid_rows(eng.grid)                          # 미니 보드에 실제 블록 색/모양으로 표시
                p["_cg_key"] = gkey
                p["compact_grid"] = eng.get_compact_grid()             # 압축 격자/최고 높이도 보드가 바뀔 때만 다시 계산
                p["highest_y"] = eng.get_highest_block_row()
            p["cpiece"] = piece_state(p["bot"].engine)                 # 조작 중인 블록
            p["next"] = list(p["bot"].engine.next_queue[:3])           # 다음 블록 / 홀드 (미니 보드 옆에 표시)
            p["hold"] = p["bot"].engine.hold_piece
            
            # AI 게임 오버 검사
            if not p["bot"].is_alive:
                self._eliminate_player(pid)

        # 7. 네트워크 플레이어들의 상태 반영
        if self.net_mgr and self.net_mgr.remote_players_state:
            def _rank_key(item):                                    # 한 패킷에 여럿이 탈락했으면 호스트가 정한 낮은 순위(큰 번호)부터 처리
                hr_ = item[1].get("rank") if isinstance(item[1], dict) else None
                return -hr_ if isinstance(hr_, int) and not isinstance(hr_, bool) else 0
            for r_id, r_state in sorted(list(self.net_mgr.remote_players_state.items()), key=_rank_key):
                if r_id in self.players and not self.players[r_id].get("bot"):       # 봇이 이어받은 자리는 늦게 도착한 원격 상태로 덮어쓰지 않음
                    self.players[r_id]["compact_grid"] = r_state.get("compact_grid", self.players[r_id]["compact_grid"])
                    self.players[r_id]["highest_y"] = r_state.get("highest_y", 20)
                    for key, src in (("score", "score"), ("lines", "lines"), ("attacks", "atk"), ("ko_count", "ko_count"), ("badge_extra", "bx")):   # 호스트/클라이언트가 보낸 성적
                        v = r_state.get(src)
                        if isinstance(v, int) and not isinstance(v, bool):
                            self.players[r_id][key] = v
                    # 색이 있는 보드: 클라이언트가 보낸 스냅샷(호스트) 또는 호스트가 보낸 cg 문자열(클라이언트)
                    snap = r_state.get("snap")
                    cg = r_state.get("cg")
                    cp = snap.get("p") if isinstance(snap, dict) else r_state.get("cp")
                    if isinstance(cp, (list, tuple)) and len(cp) == 4 and cp[0] in "IJLOSTZ" and all(isinstance(v, int) for v in cp[1:]):
                        self.players[r_id]["cpiece"] = tuple(cp)
                    elif cp is None:
                        self.players[r_id]["cpiece"] = None
                    if isinstance(snap, dict):
                        nx, hd = snap.get("n"), snap.get("h")
                    else:
                        nx, hd = r_state.get("nx"), r_state.get("hd")
                    if isinstance(nx, str):
                        nx = list(nx)
                    if isinstance(nx, list) and all(isinstance(c, str) and c in "IJLOSTZ" for c in nx):
                        self.players[r_id]["next"] = nx[:3]
                    if hd is None or (isinstance(hd, str) and (hd == "" or hd in "IJLOSTZ")):
                        self.players[r_id]["hold"] = hd or None
                    if isinstance(snap, dict) and isinstance(snap.get("g"), list):
                        self.players[r_id]["cg"] = snap["g"]
                    elif isinstance(cg, str) and len(cg) == 200 and set(cg) <= _CG_CHARS:
                        self.players[r_id]["cg"] = [cg[i * 10:(i + 1) * 10] for i in range(20)]
                    ig = snap.get("ig") if isinstance(snap, dict) else r_state.get("ig")
                    if isinstance(ig, int) and not isinstance(ig, bool):
                        self.players[r_id]["ig"] = max(0, min(400, ig))
                    sv = r_state.get("surv")
                    if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                        self.players[r_id]["survival"] = float(sv)
                    if not r_state.get("is_alive", True) and self.players[r_id]["is_alive"]:
                        self._eliminate_player(r_id)
                    hr = r_state.get("rank")               # (클라이언트) 호스트가 정한 순위를 따름: 여러 명이 한 패킷에 탈락해도 호스트와 같은 순위
                    if (self.net_mgr.mode == "CLIENT" and isinstance(hr, int) and not isinstance(hr, bool)
                            and 1 <= hr <= self.total_players and not self.players[r_id]["is_alive"]):
                        self.players[r_id]["rank"] = hr
                        self.next_rank_to_assign = min(self.next_rank_to_assign, hr - 1)

        if self.net_mgr and self.net_mgr.mode == "CLIENT" and not self.local_is_alive:
            hv = getattr(self.net_mgr, "host_view_of_me", None)      # 내 순위도 호스트 기준으로 맞춤 (내가 탈락한 뒤에만)
            hr = hv.get("rank") if isinstance(hv, dict) else None
            if (isinstance(hr, int) and not isinstance(hr, bool) and 1 <= hr <= self.total_players and hv.get("is_alive") is False
                    and self.local_player_id in self.players):
                self.local_rank = hr
                self.players[self.local_player_id]["rank"] = hr

        self._check_spectate_target(now)
        if self.teams:
            self._team_alerts(now)

        # 8. 이펙트 수명 정리
        self.attack_effects = [e for e in self.attack_effects if now - e["start_time"] < e["duration"]]
