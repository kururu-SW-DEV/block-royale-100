"""
Block Royale 100 - Core Block Game Engine
7-Bag, Hold, Next Queue, Ghost Piece, Wall Kick, Garbage Offset/Pushing 지원
"""

import math
import random
from config import (
    BOARD_WIDTH, BOARD_HEIGHT, TETROMINOES,
    GARBAGE_ATTACK_TABLE, COMBO_BONUS, TSPIN_ATTACK_TABLE, TSPIN_MINI_ATTACK_TABLE,
    MAX_GARBAGE_PER_LOCK, PERFECT_CLEAR_ATTACK, MAX_INCOMING_GARBAGE
)

# SRS 기본 오프셋 킥 데이터 (JLSTZ용)
JLSTZ_KICKS = {
    (0, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 2): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (0, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)]
}

# I 피스 전용 오프셋 킥 데이터
I_KICKS = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)]
}

class BlockEngine:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        # 쓰레기 구멍 위치 전용 RNG (피스 시퀀스 RNG와 분리하여 시드 재현성 유지)
        self.garbage_rng = random.Random()
        self.width = BOARD_WIDTH
        self.height = BOARD_HEIGHT

        # 보드: height x width (None이면 빈칸, 아니면 피스 타입 'I', 'J', 'G' 등)
        self.grid = [[None for _ in range(self.width)] for _ in range(self.height)]

        self.bag = []
        self.next_queue = []
        self._refill_next_queue()

        # 현재 피스 정보
        self.current_piece = None
        self.current_rot = 0
        self.current_x = 3
        self.current_y = 0

        # 홀드 기능
        self.hold_piece = None
        self.can_hold = True

        # 게임 상태
        self.game_over = False
        self.lines_cleared_total = 0
        self.score = 0
        self.combo = -1
        self.max_combo = 0
        self.b2b = False                # Back-to-Back 연속 난이도 클리어 플래그
        self.b2b_chain = 0              # B2B 보너스를 연속으로 받은 횟수 (표시용: B2B x2, x3 ...)
        self.last_move_was_rotation = False  # T-스핀 판정용 회전 플래그
        self.last_kick_index = 0        # 마지막 회전에서 사용된 킥 인덱스 (T-스핀 Mini 판정용)
        self.badge_rate = 0.0           # 배지 공격력 증폭률 (상쇄 이전에 적용)
        self.last_clear_info = None     # 직전 클리어 상세 (T-Spin, B2B, 행 인덱스 등)
        self.cleared_row_indices = []   # 라인 클리어 시각 이펙트용 행 목록
        self.lock_events = 0            # 피스가 고정될 때마다 증가 (UI 이펙트/효과음 트리거용)
        self.perfect_clears = 0         # 퍼펙트 클리어 달성 횟수 (UI/중계 트리거용)
        self.garbage_pushed_total = 0   # 지금까지 보드에 올라온 쓰레기 줄 수 (효과음 트리거용)
        self.last_lock_cells = []       # 마지막으로 고정된 피스의 칸 좌표 (UI 이펙트용)
        self.last_locked_piece = None   # 마지막으로 고정된 피스 종류 (효과음 음높이용)

        # 쓰레기 라인(Garbage) 시스템
        self.incoming_garbage = 0       # 공격 대기 중인 줄 수
        self.garbage_to_send = 0        # 방금 라인 클리어로 발생한 공격력
        self.attack_generated_total = 0  # 들어오는 쓰레기 상쇄 여부와 무관하게 누적된 총 생성 공격력 (APM 집계용)

        # 낙하 타이머 및 락 딜레이 (표준 낙하/락 딜레이)
        self.fall_speed = 0.8  # 초 단위 (생존자 수에 따라 배틀로얄에서 가속됨)
        self.fall_timer = 0.0
        self.lock_delay = 0.5  # 바닥 닿았을 때 락 딜레이 (초)
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.max_lock_resets = 15

        # 첫 번째 피스 스폰
        self.spawn_piece()

    def _generate_bag(self):
        bag = list(TETROMINOES.keys())
        self.rng.shuffle(bag)
        return bag

    def _refill_next_queue(self):
        while len(self.next_queue) < 7:
            if not self.bag:
                self.bag = self._generate_bag()
            self.next_queue.append(self.bag.pop())

    def spawn_piece(self):
        self._refill_next_queue()
        self.current_piece = self.next_queue.pop(0)
        self.current_rot = 0
        self.current_x = 3 if self.current_piece != 'O' else 4
        self.current_y = 0
        self.can_hold = True
        self._reset_piece_timers()

        # 스폰되자마자 충돌하면 게임 오버
        if self._check_collision(self.current_x, self.current_y, self.current_rot):
            self.game_over = True

    def _reset_piece_timers(self):
        """새 피스가 등장(스폰/홀드)할 때 낙하/락 타이머와 회전 플래그를 초기화"""
        self.fall_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.last_move_was_rotation = False
        self.last_kick_index = 0

    def _get_blocks(self, piece_type, rot, px, py):
        shape = TETROMINOES[piece_type][rot % 4]
        return [(px + x, py + y) for (x, y) in shape]

    def _check_collision(self, px, py, rot, piece_type=None):
        if piece_type is None:
            piece_type = self.current_piece
        blocks = self._get_blocks(piece_type, rot, px, py)
        for x, y in blocks:
            if x < 0 or x >= self.width or y >= self.height:
                return True
            if y >= 0 and self.grid[y][x] is not None:
                return True
        return False

    def _on_piece_manipulated(self):
        """블록 조작 시 락 딜레이 리셋 (최대 15회)"""
        if self._is_touching_ground():
            if self.lock_resets < self.max_lock_resets:
                self.lock_timer = 0.0
                self.lock_resets += 1
        else:
            self.lock_timer = 0.0

    def move(self, dx, dy, soft=False, auto=False):
        """좌우 및 아래 이동. 성공 여부 반환.
        soft: 소프트 드롭 입력(점수 +1), auto: 중력에 의한 자동 낙하(락 리셋 횟수를 소모하지 않음)."""
        if self.game_over:
            return False
        if not self._check_collision(self.current_x + dx, self.current_y + dy, self.current_rot):
            self.current_x += dx
            self.current_y += dy
            if dy > 0 and soft:
                self.score += 1
                self.fall_timer = 0.0
            self.last_move_was_rotation = False
            if auto:
                self.lock_timer = 0.0
            else:
                self._on_piece_manipulated()
            return True
        return False

    def rotate(self, clockwise=True):
        """SRS 킥 테이블을 적용한 회전"""
        if self.game_over or self.current_piece == 'O':
            return False

        old_rot = self.current_rot
        new_rot = (old_rot + 1) % 4 if clockwise else (old_rot - 1) % 4

        # 킥 데이터 조회
        kick_table = I_KICKS if self.current_piece == 'I' else JLSTZ_KICKS
        kicks = kick_table.get((old_rot, new_rot), [(0, 0)])

        for kick_idx, (kx, ky) in enumerate(kicks):
            test_x = self.current_x + kx
            test_y = self.current_y - ky
            if not self._check_collision(test_x, test_y, new_rot):
                self.current_x = test_x
                self.current_y = test_y
                self.current_rot = new_rot
                self.last_move_was_rotation = True
                self.last_kick_index = kick_idx
                self._on_piece_manipulated()
                return True
        return False

    def _detect_tspin(self):
        """T-스핀 판정. 반환: None(아님) / 'mini' / 'full'
        3-코너 규칙 + 뾰족한 방향 앞쪽 코너 2개가 모두 막혀야 정식 T-스핀,
        아니면 Mini (단, 5번째 킥을 사용한 경우는 정식 T-스핀)."""
        if self.current_piece != 'T' or not self.last_move_was_rotation:
            return None

        cx = self.current_x + 1
        cy = self.current_y + 1

        def occupied(x, y):
            if x < 0 or x >= self.width or y >= self.height or y < 0:
                return True
            return self.grid[y][x] is not None

        tl = occupied(cx - 1, cy - 1)
        tr = occupied(cx + 1, cy - 1)
        bl = occupied(cx - 1, cy + 1)
        br = occupied(cx + 1, cy + 1)
        if tl + tr + bl + br < 3:
            return None

        front = {0: (tl, tr), 1: (tr, br), 2: (bl, br), 3: (tl, bl)}[self.current_rot % 4]
        if all(front) or self.last_kick_index == 4:
            return 'full'
        return 'mini'

    def hold(self):
        """홀드 기능 (1피스당 1회)"""
        if self.game_over or not self.can_hold:
            return False

        prev_current = self.current_piece
        if self.hold_piece is None:
            self.hold_piece = prev_current
            self.spawn_piece()
        else:
            self.current_piece = self.hold_piece
            self.hold_piece = prev_current
            self.current_rot = 0
            self.current_x = 3 if self.current_piece != 'O' else 4
            self.current_y = 0
            self._reset_piece_timers()
            if self._check_collision(self.current_x, self.current_y, self.current_rot):
                self.game_over = True
        self.can_hold = False  # 이번 턴 추가 홀드 금지
        return True

    def get_ghost_y(self):
        """현재 피스가 하드 드롭될 Y 위치 반환"""
        if self.game_over or self.current_piece is None:
            return self.current_y
        ghost_y = self.current_y
        while not self._check_collision(self.current_x, ghost_y + 1, self.current_rot):
            ghost_y += 1
        return ghost_y

    def hard_drop(self):
        """하드 드롭: 즉시 낙하 후 락다운"""
        if self.game_over:
            return 0
        drop_dist = 0
        while not self._check_collision(self.current_x, self.current_y + 1, self.current_rot):
            self.current_y += 1
            drop_dist += 1
        self.score += drop_dist * 2
        return self.lock_down()

    def _is_touching_ground(self):
        return self._check_collision(self.current_x, self.current_y + 1, self.current_rot)

    def lock_down(self):
        """피스를 보드에 고정하고 라인 클리어 및 T-스핀, B2B, 쓰레기 라인 처리"""
        if self.game_over:
            return 0

        # 락다운 전 T-스핀 판정 검사
        tspin_kind = self._detect_tspin()
        is_tspin = tspin_kind is not None
        is_mini = (tspin_kind == 'mini')

        blocks = self._get_blocks(self.current_piece, self.current_rot, self.current_x, self.current_y)
        for x, y in blocks:
            if 0 <= y < self.height and 0 <= x < self.width:
                self.grid[y][x] = self.current_piece
            else:
                self.game_over = True
        self.last_lock_cells = [(x, y) for x, y in blocks if 0 <= y < self.height]
        self.last_locked_piece = self.current_piece
        self.lock_events += 1

        # 라인 클리어 검사
        cleared_lines = self._clear_lines()

        # 공격력 계산 및 T-Spin / Back-to-Back (B2B) 판정
        attack_lines = 0
        is_b2b = False
        is_pc = False

        if cleared_lines > 0:
            self.combo += 1
            if self.combo > self.max_combo:
                self.max_combo = self.combo
            is_difficult = (cleared_lines == 4 or is_tspin)

            if is_difficult:
                is_b2b = self.b2b
                self.b2b = True
                self.b2b_chain = self.b2b_chain + 1 if is_b2b else 0
            else:
                self.b2b = False
                self.b2b_chain = 0

            # 기본 공격력 산정
            if is_mini:
                base_attack = TSPIN_MINI_ATTACK_TABLE.get(cleared_lines, 0)
            elif is_tspin:
                base_attack = TSPIN_ATTACK_TABLE.get(cleared_lines, 2)
            else:
                base_attack = GARBAGE_ATTACK_TABLE.get(cleared_lines, 0)

            # B2B 보너스 (+1줄 공격력)
            if is_b2b and is_difficult:
                base_attack += 1

            # 퍼펙트 클리어: 줄을 지운 뒤 보드에 블록이 하나도 없으면 큰 보너스 공격
            is_pc = all(cell is None for row in self.grid for cell in row)
            if is_pc:
                base_attack += PERFECT_CLEAR_ATTACK
                self.perfect_clears += 1
                self.score += 3000

            # 콤보 보너스 (combo 0 = 첫 클리어 = 보너스 없음)
            combo_att = COMBO_BONUS[min(self.combo, len(COMBO_BONUS) - 1)]
            attack_lines = base_attack + combo_att

            # 배지 증폭은 상쇄 이전에 적용 (증폭된 공격력으로 들어오는 쓰레기를 상쇄)
            if self.badge_rate > 0:
                attack_lines += int(math.ceil(attack_lines * self.badge_rate))

            self.attack_generated_total += attack_lines    # 상쇄로 사라지는 몫도 APM에는 그대로 반영 (수비만 하느라 APM이 0에 묶이지 않게)

            # 들어오는 쓰레기 줄 상쇄
            if self.incoming_garbage > 0:
                canceled = min(self.incoming_garbage, attack_lines)
                self.incoming_garbage -= canceled
                attack_lines -= canceled
        else:
            self.combo = -1
            if is_tspin:
                self.score += 100

        self.garbage_to_send += attack_lines         # 같은 프레임에 두 번 고정돼도 앞선 공격이 사라지지 않게 누적
        self.last_clear_info = {
            'cleared': cleared_lines,
            'is_tspin': is_tspin,
            'is_mini': is_mini,
            'is_b2b': is_b2b,
            'b2b_chain': self.b2b_chain,
            'is_pc': is_pc,
            'attack': attack_lines,
            'combo': self.combo,
            'cleared_rows': list(self.cleared_row_indices)
        }

        # 라인을 지우지 못했고 대기 중인 쓰레기 줄이 있다면 보드 아래로 밀어올림
        # (한 번에 올라오는 줄 수는 제한하고, 초과분은 다음 락다운까지 대기열에 유지)
        if cleared_lines == 0 and self.incoming_garbage > 0 and not self.game_over:
            push = min(self.incoming_garbage, MAX_GARBAGE_PER_LOCK)
            self.incoming_garbage -= push
            self._push_garbage(push)

        # 다음 피스 스폰
        self.spawn_piece()
        return cleared_lines

    def _clear_lines(self):
        cleared_rows = []
        new_grid = []
        for y, row in enumerate(self.grid):
            if any(cell is None for cell in row):
                new_grid.append(row)
            else:
                cleared_rows.append(y)

        cleared = len(cleared_rows)
        self.cleared_row_indices = cleared_rows

        if cleared > 0:
            for _ in range(cleared):
                new_grid.insert(0, [None for _ in range(self.width)])
            self.grid = new_grid
            self.lines_cleared_total += cleared
            self.score += (100 * cleared * cleared)
        return cleared

    def _push_garbage(self, count):
        """보드 하단에 구멍 1개가 뚫린 쓰레기 줄을 밀어 올림"""
        hole_x = self.garbage_rng.randint(0, self.width - 1)
        self.garbage_pushed_total += count
        for _ in range(count):
            # 맨 위 줄이 비어있지 않으면 밀려 올라가면서 게임오버
            if any(self.grid[0]):
                self.game_over = True
                break
            self.grid.pop(0)
            new_row = ['G'] * self.width
            new_row[hole_x] = None
            self.grid.append(new_row)

        # 쓰레기 줄이 올라왔을 때 현재 조작 중인 피스가 겹치지 않도록 위로 보정
        if self.current_piece and not self.game_over:
            while self._check_collision(self.current_x, self.current_y, self.current_rot) and self.current_y > -2:
                self.current_y -= 1
            if self._check_collision(self.current_x, self.current_y, self.current_rot):
                self.game_over = True

    def queue_garbage(self, count):
        """상대방에게 공격받아 쓰레기 라인 대기열에 추가됨 (대기열 상한 MAX_INCOMING_GARBAGE: 넘치는 분량은 버림)"""
        self.incoming_garbage = min(MAX_INCOMING_GARBAGE, self.incoming_garbage + count)

    def update(self, dt):
        """프레임 틱 업데이트 (dt 기반 자연 낙하 및 락 딜레이)"""
        if self.game_over:
            return 0

        # 바닥에 닿았는지 체크
        if self._is_touching_ground():
            self.lock_timer += dt
            if self.lock_timer >= self.lock_delay:
                self.lock_timer = 0.0
                return self.lock_down()
        else:
            self.lock_timer = 0.0
            self.fall_timer += dt
            # 프레임이 튀어도 낙하가 밀리지 않도록 누적 시간만큼 여러 칸 낙하
            steps = 0
            while self.fall_timer >= self.fall_speed and steps < self.height:
                self.fall_timer -= self.fall_speed
                steps += 1
                if not self.move(0, 1, auto=True):
                    self.fall_timer = 0.0
                    break

        return 0

    def get_lock_progress(self):
        """바닥에 닿아 락되기까지 진행률 (0.0 ~ 1.0). UI 락 딜레이 표시용."""
        if self.game_over or not self._is_touching_ground():
            return 0.0
        return min(1.0, self.lock_timer / self.lock_delay)

    # ---------------------------------------------------------------- 관전용 스냅샷 (네트워크 전송)
    def snapshot(self):
        """관전자에게 보낼 전체 보드 상태: 블록 색(종류), 조작 중인 피스, 홀드, 다음 블록, 대기 공격 등"""
        return {
            "g": ["".join(c if c else "." for c in row) for row in self.grid],
            "p": [self.current_piece, self.current_rot, self.current_x, self.current_y] if self.current_piece else None,
            "h": self.hold_piece,
            "n": list(self.next_queue[:3]),
            "ig": self.incoming_garbage,
            "c": self.combo,
            "b": int(self.b2b),
            "bc": self.b2b_chain,
            "go": int(self.game_over),
            "lp": round(self.get_lock_progress(), 2),
        }

    def load_snapshot(self, snap):
        """snapshot()이 만든 상태를 이 엔진에 그대로 반영 (관전 화면에서 실제 플레이처럼 그리기 위함)"""
        self.grid = [[(ch if ch != "." else None) for ch in row] for row in snap["g"]]
        p = snap.get("p")
        if p:
            self.current_piece, self.current_rot, self.current_x, self.current_y = p[0], int(p[1]), int(p[2]), int(p[3])
        else:
            self.current_piece = None
        self.hold_piece = snap.get("h")
        self.next_queue = list(snap.get("n") or [])
        self.incoming_garbage = int(snap.get("ig", 0))
        self.combo = int(snap.get("c", -1))
        self.b2b = bool(snap.get("b", 0))
        self.b2b_chain = int(snap.get("bc", 0)) if self.b2b else 0
        self.game_over = bool(snap.get("go", 0))
        self.lock_timer = float(snap.get("lp", 0.0)) * self.lock_delay
        self.can_hold = True

    def get_compact_grid(self):
        """
        네트워크 전송 및 미니 렌더링 최적화를 위한 20x10 압축 표현
        각 행을 10비트 정수로 표현 (1: 블록 존재)
        """
        compact = []
        for row in self.grid:
            row_val = 0
            for cell in row:
                row_val = (row_val << 1) | (1 if cell is not None else 0)
            compact.append(row_val)
        return compact

    def get_highest_block_row(self):
        """현재 보드에서 가장 높이 쌓인 줄의 행 인덱스(0이 맨 위, 20이면 빈 보드)"""
        for y, row in enumerate(self.grid):
            if any(cell is not None for cell in row):
                return y
        return self.height
