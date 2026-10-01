"""
Block Royale 100 - Humanlike AI Bot Engine
사람 수준의 반응 속도, 생각하는 시간, 자연스러운 이동 및 실수 확률을 갖춘 휴리스틱 AI
"""

import random
import time
from block_engine import BlockEngine
from config import BOARD_WIDTH, BOARD_HEIGHT, TETROMINOES
import bot_brain
import bot_pool

STUCK_LIMIT = 6.0            # 살아 있는데 이 시간(봇 시계 기준 초) 동안 블록을 하나도 못 놓으면 워치독이 강제로 풀어 줌 (어떤 원인이든 봇이 멈춘 채 남지 않게)
EARLY_TEMPO = 3.0           # 생존자가 절반을 넘는 초반에 봇의 생각/입력 시간에 곱하는 배율 (클수록 초반이 느슨함). 1.8(25~50%) -> 1.25(10~25%) -> 1.0으로 줄어듦
STARVE_LIMIT = 0.3          # 탐색 예산을 이 시간(봇 시계 기준 초) 넘게 못 받으면 예산과 무관하게 가볍게 계산
POOL_WAIT_TIMEOUT = 0.8      # 작업 프로세스 결과를 이 시간(봇 시계 기준 초)까지 기다리고, 그래도 안 오면 직접 계산

# 쉬움을 뺀 난이도는 bot_brain(탐색형 계획기)으로 둠. think: 새 블록을 보고 고민하는 시간, interval: 입력 1개당 간격
# depth: 내다보는 블록 수(1=지금 블록만, 2=+다음 블록 ...), beam: 다음 단계로 확장할 후보 수
BRAIN_TIERS = {
    "normal": dict(think=(0.20, 0.45), interval=0.13, error=0.10, depth=1, beam=4, tspin=False, attack=True),
    "hard":   dict(think=(0.05, 0.12), interval=0.06, error=0.008, depth=2, beam=3, tspin=True, attack=True),
    "master": dict(think=(0.02, 0.06), interval=0.03, error=0.0, depth=3, beam=3, tspin=True, attack=True),
}
_avg_cost = {1: 0.002, 2: 0.010, 3: 0.030}       # 깊이별 평균 탐색 시간(초): 예산 안에서 쓸 수 있는 깊이를 고르는 데 사용

class AIBot:
    def __init__(self, bot_id, name="AI_Player", difficulty="normal", seed=None):
        self.bot_id = bot_id
        self.name = name
        self.difficulty = difficulty
        self.engine = BlockEngine(seed=seed)
        
        # 난이도별 파라미터 (초 단위)
        self.brain = BRAIN_TIERS.get(difficulty)          # 쉬움은 None: 예전 방식(현재 블록만 보는 휴리스틱)
        self.depth = self.brain["depth"] if self.brain else 1
        if self.brain:
            self.think_duration = self.brain["think"]
            self.action_interval = self.brain["interval"]
            self.error_chance = self.brain["error"]
        else:
            self.think_duration = (0.50, 0.90)
            self.action_interval = 0.32
            self.error_chance = 0.30
        self.plan_hold = False        # 이번 배치를 위해 먼저 홀드를 쓸지
        self.plan_path = None         # T-스핀 등 특수 입력 경로 ('L','R','D','cw','ccw')
        self.plan_stuck = 0
        self.params = None            # 이 봇만 쓸 가중치(자체 대전 튜닝용). None이면 기본값
        self._wd_lock = 0             # 워치독: 마지막으로 확인한 블록 고정 횟수/시각/연속 복구 횟수
        self._wd_t = 0.0
        self._wd_hits = 0
        self.free_fall = False        # 워치독이 이 블록만큼은 중력/락 딜레이로 저절로 떨어지게 풀어 둠
        self.watchdog_recoveries = 0
        self.pool_rid = None          # 작업 프로세스에 맡긴 탐색 요청 번호
        self.pool_t = 0.0
        self.pool_lock = 0
        self.pool_off_until = 0.0     # 이 시각까지는 작업 프로세스를 쓰지 않음(응답이 늦었을 때)

        # AI 상태 머신: "THINKING" -> "MOVING" -> "DROPPING"
        # 봇 전용 시계: 실제 시간이 아닌 누적 dt 사용 (일시정지/프레임 지연에도 일관된 동작)
        self.clock = 0.0
        self.state = "THINKING"
        self.think_until = self.clock + random.uniform(*self.think_duration)
        self.last_action_time = self.clock
        
        self.target_x = 3
        self.target_rot = 0
        
        # 배틀로얄 통계
        self.ko_count = 0
        self.target_player_id = None
        self.is_alive = True
        self.rank = 0
        if self.brain:
            self.adjust_for_alive_count(100)     # 시작은 초반(인원 많음) 속도: 생존자가 줄수록 빨라짐

    def adjust_for_alive_count(self, alive_count):
        """생존자 비율(100인 기준 환산)에 따라 속도/정확도를 동적으로 조절: 초반엔 여유 있게, 후반엔 최고 속도로"""
        if self.brain:
            t = self.brain
            f = EARLY_TEMPO if alive_count > 50 else (1.8 if alive_count > 25 else (1.25 if alive_count > 10 else 1.0))
            self.think_duration = (t["think"][0] * f, t["think"][1] * f)
            self.action_interval = t["interval"] * f
            self.error_chance = t["error"] * (2.0 if alive_count > 50 else 1.0)
            self.depth = t["depth"] if (alive_count <= 25 or self.difficulty != "master") else min(2, t["depth"])
            return
        if alive_count <= 10:
            self.think_duration = (0.24, 0.45)
            self.action_interval = 0.20
            self.error_chance = 0.14
        elif alive_count <= 25:
            self.think_duration = (0.32, 0.60)
            self.action_interval = 0.24
            self.error_chance = 0.18
        elif alive_count <= 50:
            self.think_duration = (0.40, 0.75)
            self.action_interval = 0.28
            self.error_chance = 0.22

    def _plan_brain(self):
        """탐색형 계획: 지금 블록/홀드/다음 블록들을 함께 보고 최선의 배치(와 필요하면 입력 경로)를 고름. 예산이 없으면 None"""
        left = bot_brain.budget_left()
        depth = self.depth
        if left <= 0:
            if self.clock - self.think_until < STARVE_LIMIT:
                return None                                   # 이번 프레임 예산이 없으면 잠깐 기다림
            depth = 1                                         # 너무 오래 기다린 봇은 예산과 상관없이 가볍게(깊이 1) 계산: 멈춰 있지 않게
            left = 1e9
        if depth > self.depth:
            depth = self.depth
        while depth > 1 and _avg_cost[depth] * 0.6 > left:
            depth -= 1                                    # 이번 프레임 예산이 모자라면 얕게 (보드가 위험하면 아래에서 다시 깊게)
        e = self.engine
        t0 = time.perf_counter()
        results = bot_brain.plan(e.grid, e.current_piece, e.hold_piece, list(e.next_queue[:5]), e.can_hold,
                                 e.combo, e.b2b, e.incoming_garbage, depth=depth, beam=self.brain["beam"],
                                 attack_style=self.brain["attack"], use_tspin=self.brain["tspin"], params=self.params)
        cost = time.perf_counter() - t0
        bot_brain.spend(cost)
        _avg_cost[depth] = _avg_cost[depth] * 0.9 + cost * 0.1
        return self._apply_results(results)

    def _apply_results(self, results):
        """계산 결과(점수 순 후보들)에서 실제로 둘 수를 고름"""
        if not results:
            return False
        pick = results[0]
        if random.random() < self.error_chance and len(results) > 1:
            pick = results[min(random.randint(1, 3), len(results) - 1)]      # 인간적인 실수: 2~4위 수
        _score, use_hold, rot, px, path = pick
        self.plan_hold = use_hold
        self.plan_path = list(path) if path else None
        self.target_rot, self.target_x = rot, px
        return True

    def _submit_to_pool(self):
        """탐색을 작업 프로세스에 맡김. 맡겼으면 True"""
        if self.pool_off_until > self.clock or self.depth < 2 or not bot_pool.enabled():
            return False
        e = self.engine
        rid = bot_pool.submit(bot_brain.rows_from_grid(e.grid), e.current_piece, e.hold_piece, list(e.next_queue[:5]),
                              e.can_hold, e.combo, e.b2b, e.incoming_garbage, self.depth, self.brain["beam"],
                              self.brain["attack"], self.brain["tspin"], dict(self.params or bot_brain.PARAMS))
        if rid is None:
            return False
        self.pool_rid = rid
        self.pool_t = self.clock
        self.pool_lock = e.lock_events
        return True

    @property
    def stuck_limit(self):
        """현재 속도와 생각 시간에 맞춘 워치독 타임아웃: 초반엔 여유(최대 6.0초), 후반엔 신속(1.5~2.5초)"""
        return max(1.5, min(STUCK_LIMIT, self.think_duration[1] + self.action_interval * 10.0 + 1.0))

    def _recover(self, now):
        """오래 멈춘 봇을 풀어 줌: 기다리던 계산/경로를 버리고 단순 최고 위치 시도 -> 그래도 안 되면 즉시 하드 드롭"""
        e = self.engine
        self._finish_wait()
        self._wd_hits += 1
        self.watchdog_recoveries += 1
        self.pool_off_until = now + 5.0                   # 잠시 작업 프로세스 없이 직접 계산
        self.plan_path, self.plan_hold = None, False
        if e.current_piece is None and not e.game_over:
            e.spawn_piece()
            
        if self._wd_hits >= 2 and not e.game_over:
            # 2회차 이상 지연 시 즉시 강제 하드드롭으로 락다운
            e.hard_drop()
            self._wd_lock = e.lock_events
            self._wd_t = now
            self._wd_hits = 0
            self.free_fall = False
            self.state = "THINKING"
            self.think_until = now
            return

        # 1회차 지연: 복잡한 탐색/경로를 버리고 단순 최고 위치(_find_best_move)로 전환
        self.target_x, self.target_rot = self._find_best_move()
        self._wd_t = now - self.stuck_limit + 0.8              # 0.8초 뒤 여전히 고정 못했으면 2회차(강제 드롭)
        self.free_fall = True
        self.state = "DROPPING" if (e.current_x == self.target_x and e.current_rot == self.target_rot) else "MOVING"
        self.last_action_time = now

    def _finish_wait(self):
        if self.pool_rid is not None:
            bot_pool.cancel(self.pool_rid)
            self.pool_rid = None

    def _evaluate_board(self, grid, lines_cleared):
        """보드 상태 평가 휴리스틱 (Dellacherie 가중치)"""
        cur_h = len(grid)
        if cur_h == 0:
            return lines_cleared * 4.0
            
        col_heights = [0] * BOARD_WIDTH
        for x in range(BOARD_WIDTH):
            for y in range(cur_h):
                if grid[y][x] is not None:
                    col_heights[x] = cur_h - y
                    break
                    
        total_height = sum(col_heights)
        max_height = max(col_heights) if col_heights else 0
        
        holes = 0
        for x in range(BOARD_WIDTH):
            found_block = False
            for y in range(cur_h):
                if grid[y][x] is not None:
                    found_block = True
                elif found_block:
                    holes += 1
                    
        bumpiness = 0
        for x in range(BOARD_WIDTH - 1):
            bumpiness += abs(col_heights[x] - col_heights[x + 1])
            
        score = (
            lines_cleared * 4.0
            - total_height * 0.55
            - max_height * 1.4
            - holes * 4.2
            - bumpiness * 0.75
        )
        return score

    def _find_best_move(self):
        """현재 피스에 대해 가능한 모든 배치를 시뮬레이션하고 점수 순 정렬"""
        piece = self.engine.current_piece
        if not piece:
            return 3, 0
            
        candidates = []
        num_rotations = len(TETROMINOES[piece])
        
        for rot in range(num_rotations):
            shape = TETROMINOES[piece][rot]
            min_px = min(x for x, y in shape)
            max_px = max(x for x, y in shape)
            
            for px in range(-min_px, BOARD_WIDTH - max_px):
                if self.engine._check_collision(px, 0, rot):
                    continue
                    
                py = 0
                while not self.engine._check_collision(px, py + 1, rot):
                    py += 1
                    
                # 전체 그리드를 복사하지 않고, 피스가 닿는 행만 복사 (100인 성능 최적화)
                temp_grid = list(self.engine.grid)
                blocks = self.engine._get_blocks(piece, rot, px, py)
                for by in {by for _, by in blocks if 0 <= by < BOARD_HEIGHT}:
                    temp_grid[by] = temp_grid[by][:]
                for bx, by in blocks:
                    if 0 <= by < BOARD_HEIGHT and 0 <= bx < BOARD_WIDTH:
                        temp_grid[by][bx] = piece
                        
                surviving_rows = [r for r in temp_grid if any(c is None for c in r)]
                cleared = BOARD_HEIGHT - len(surviving_rows)
                score = self._evaluate_board(surviving_rows, cleared)
                
                candidates.append((score, px, rot))
                
        if not candidates:
            return 3, 0
            
        # 점수 내림차순 정렬
        candidates.sort(key=lambda item: item[0], reverse=True)
        
        # 인간적인 실수 확률: 일정 확률로 1위가 아닌 2~3위 수 선택
        if random.random() < self.error_chance and len(candidates) > 1:
            idx = min(random.randint(1, 3), len(candidates) - 1)
            return candidates[idx][1], candidates[idx][2]
            
        return candidates[0][1], candidates[0][2]

    def update(self, dt):
        """인간적인 AI 프레임 업데이트"""
        if not self.is_alive or self.engine.game_over:
            self.is_alive = False
            self._finish_wait()
            return 0
            
        self.clock += dt
        now = self.clock
        attack_sent = 0

        # 워치독: 살아 있는데 STUCK_LIMIT 동안 블록을 놓지 못하면 강제로 풀어 줌 (모든 봇 적용)
        if self.engine.lock_events != self._wd_lock:
            self._wd_lock, self._wd_t, self._wd_hits, self.free_fall = self.engine.lock_events, now, 0, False
        elif now - self._wd_t > self.stuck_limit:
            self._recover(now)

        # 이동/드롭 도중 중력으로 블록이 먼저 고정됐다면(새 블록이 나옴) 이전 목표를 버리고 다시 생각
        if self.state in ("MOVING", "DROPPING") and self.engine.lock_events != getattr(self, "_move_lock", self.engine.lock_events):
            self.state = "THINKING"
            self.think_until = now + random.uniform(*self.think_duration)
        
        # 1. 생각 단계 (새 피스가 나왔을 때 잠깐 고민)
        if self.state == "WAITING":
            res = bot_pool.take(self.pool_rid)
            if res is not None:
                self.pool_rid = None
                if not self._apply_results(res):
                    self.target_x, self.target_rot = self._find_best_move()
                    self.plan_hold, self.plan_path = False, None
                self.state = "MOVING"
                self._move_lock = self.engine.lock_events
                self.last_action_time = now
            elif self.engine.lock_events != self.pool_lock:
                self._finish_wait()                          # 기다리는 사이 블록이 이미 고정됨: 낡은 계산은 버림
                self.state = "THINKING"
                self.think_until = now
            elif now - self.pool_t > POOL_WAIT_TIMEOUT:
                self._finish_wait()                          # 응답이 늦으면 잠시 작업 프로세스를 쓰지 않고 직접 계산
                self.pool_off_until = now + 3.0
                self.state = "THINKING"
                self.think_until = now

        if self.state == "THINKING":
            if now >= self.think_until:
                if self.brain and self._submit_to_pool():
                    self.state = "WAITING"
                    ok = None
                else:
                    ok = self._plan_brain() if self.brain else False
                if ok is not None:                        # None: 이번 프레임 탐색 예산이 없음 -> 다음 프레임에 다시 시도
                    if not ok:
                        self.target_x, self.target_rot = self._find_best_move()
                        self.plan_hold, self.plan_path = False, None
                    self.state = "MOVING"
                    self._move_lock = self.engine.lock_events
                    self.last_action_time = now
                    self.plan_stuck = 0

        # 2. 조작 단계 (입력 1개씩: 홀드 -> 회전/이동 또는 미리 계산한 경로)
        elif self.state == "MOVING":
            if now - self.last_action_time >= self.action_interval:
                self.last_action_time = now
                e = self.engine
                if self.plan_hold:
                    self.plan_hold = False
                    if not e.hold():
                        self.state = "THINKING"           # 홀드가 안 되면 처음부터 다시 계획
                        self.think_until = now
                elif self.plan_path is not None:
                    if self.plan_path:
                        act = self.plan_path.pop(0)
                        if act == "L":
                            ok = e.move(-1, 0)
                        elif act == "R":
                            ok = e.move(1, 0)
                        elif act == "D":
                            ok = e.move(0, 1)
                            while ok and self.plan_path and self.plan_path[0] == "D":       # 이어지는 내리기는 한 번에 처리 (소프트 드롭은 빠름: 한 칸씩 기어 내려가 멈춘 것처럼 보이던 문제)
                                self.plan_path.pop(0)
                                ok = e.move(0, 1)
                        else:
                            ok = e.rotate(clockwise=(act == "cw"))
                        if not ok:                        # 경로가 어긋났으면(쓰레기가 올라오는 등) 다시 계획
                            self.plan_path = None
                            self.plan_stuck += 1
                            if self.plan_stuck >= 2:
                                # 경로가 반복 실패하면 경로 조작을 포기하고 단순 배치로 즉시 전환
                                self.target_x, self.target_rot = self._find_best_move()
                                self.plan_hold = False
                                self.state = "DROPPING" if (e.current_x == self.target_x and e.current_rot == self.target_rot) else "MOVING"
                            else:
                                self.state = "THINKING"
                                self.think_until = now
                    else:
                        self.state = "DROPPING"
                # 먼저 회전 맞추기 (3번 돌려야 하면 반대 방향으로 1번)
                elif e.current_rot != self.target_rot:
                    diff = (self.target_rot - e.current_rot) % 4
                    if not e.rotate(clockwise=(diff != 3)):
                        # 회전 불가(막힘) 시 현재 자세로 낙하 위치만 맞춤
                        self.target_rot = e.current_rot
                # 다음 X 위치 맞추기
                elif e.current_x < self.target_x:
                    if not e.move(1, 0):
                        self.state = "DROPPING"           # 막혔으면 그 자리에서 떨어뜨림
                elif e.current_x > self.target_x:
                    if not e.move(-1, 0):
                        self.state = "DROPPING"
                else:
                    # 위치와 회전이 다 맞으면 드롭 단계로 전환
                    self.state = "DROPPING"
                    
        # 3. 드롭 단계 (하드드롭 또는 소프트드롭 후 락다운)
        elif self.state == "DROPPING":
            if now - self.last_action_time >= (self.action_interval * 0.7):
                self.engine.hard_drop()
                attack_sent = self.engine.garbage_to_send
                self.engine.garbage_to_send = 0
                
                # 다음 피스를 위한 생각 상태로 전환
                self.state = "THINKING"
                self.think_until = now + random.uniform(*self.think_duration)
                self.last_action_time = now
                
        # 기본 엔진 틱 업데이트 (자연 낙하)
        # 워치독(free_fall)이면 빠르게 떨어뜨리고, 아니면 낙하 속도를 원래대로 두되(모든 난이도)
        # 조작 중인 브레인 봇은 계획한 입력이 끝까지 실행되도록 중력/락 타이머를 매 프레임 멈춰 둠
        if self.free_fall:
            self.engine.fall_speed = 0.15                # 강제 낙하: 빠르게 바닥으로 떨어뜨려 즉시 락다운
        else:
            self.engine.fall_speed = 0.8                 # 강제 낙하 때 바꾼 속도가 남아있지 않게 원상 복구 (쉬움 포함 모든 봇)
            if self.brain:
                self.engine.fall_timer = 0.0
                self.engine.lock_timer = 0.0
        self.engine.update(dt)
        if self.engine.garbage_to_send:                  # 중력 고정으로 생긴 공격도 놓치지 않고 수거
            attack_sent += self.engine.garbage_to_send
            self.engine.garbage_to_send = 0
        if self.engine.game_over:
            self.is_alive = False
            
        return attack_sent
