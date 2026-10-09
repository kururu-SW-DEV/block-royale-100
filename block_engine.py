"""
Block Royale 100 - Core Block Game Engine
7-Bag, Hold, Next Queue, Ghost Piece, Wall Kick, Garbage Offset/Pushing 지원
"""

import math
import random
from config import (
    BOARD_WIDTH, BOARD_HEIGHT, SPAWN_Y, TETROMINOES,
    GARBAGE_ATTACK_TABLE, COMBO_BONUS, TSPIN_ATTACK_TABLE, TSPIN_MINI_ATTACK_TABLE,
    MAX_GARBAGE_PER_LOCK, PERFECT_CLEAR_ATTACK, MAX_INCOMING_GARBAGE, GARBAGE_CHARGE_DELAY
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

PIECE_TYPES = frozenset(TETROMINOES)


class BlockEngine:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        # 쓰레기 구멍 위치 전용 RNG (피스 시퀀스 RNG와 분리하여 시드 재현성 유지)
        self.garbage_rng = random.Random()
        self._take_holes = []                    # 마지막으로 꺼낸 쓰레기 묶음들의 구멍 열 (_take_garbage가 채움)
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
        self.current_y = SPAWN_Y

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
        self.perfect_clear_attack = PERFECT_CLEAR_ATTACK   # 주간 변형 규칙으로 바뀔 수 있음
        self.lock_events = 0            # 피스가 고정될 때마다 증가 (UI 이펙트/효과음 트리거용)
        self.perfect_clears = 0         # 퍼펙트 클리어 달성 횟수 (UI/중계 트리거용)
        self.garbage_pushed_total = 0   # 지금까지 보드에 올라온 쓰레기 줄 수 (효과음 트리거용)
        self.last_lock_cells = []       # 마지막으로 고정된 피스의 칸 좌표 (UI 이펙트용)
        self.cleared_row_cells = []     # 방금 지운 줄의 (행, 칸 값 목록) (UI 파쇄 연출용, 렌더러가 소비)
        self.settle_offsets = []        # 줄 제거 뒤 새 행마다 내려온 칸 수 (UI 내려앉기 연출용)
        self.replay_log = None          # 리플레이 기록기가 켜 두면 고정/쓰레기 사건을 하나도 빠짐없이 쌓음 (한 프레임에 여러 번 고정돼도 손실 없음). None이면 기록 안 함
        self.push_holes = []            # 방금 올라온 쓰레기 줄의 구멍 열 (UI 상승 연출용, 렌더러가 소비)
        self.hard_drop_events = 0       # 하드 드롭 횟수 (UI 궤적 트리거)
        self.last_hard_drop = None      # {"cells": 떨어지기 전 칸, "dist": 낙하 거리}
        self.last_locked_piece = None   # 마지막으로 고정된 피스 종류 (효과음 음높이용)

        # 쓰레기 라인(Garbage) 시스템
        self._ig_total = 0              # incoming_garbage 합계 캐시 (묶음이 바뀔 때 갱신: 프레임마다 100개 엔진이 다시 합산하지 않게)
        self._garbage = []              # 대기 중인 쓰레기 묶음 [[줄 수, 도착(준비) 시각, 보낸 사람], ...] (오래된 것부터). incoming_garbage는 그 합계
        self._clock = 0.0               # 엔진 시계(초): update(dt)로 흐르며 쓰레기 묶음의 차징 시간을 잼
        self.garbage_delay = GARBAGE_CHARGE_DELAY
        self.garbage_to_send = 0        # 방금 라인 클리어로 발생한 공격력
        self.attack_generated_total = 0  # 들어오는 쓰레기 상쇄 여부와 무관하게 누적된 총 생성 공격력 (APM 집계용)
        self.garbage_canceled_total = 0  # 줄을 지워 상쇄한(막은) 받을 공격 누적 줄 수 (왼쪽 통계 칸 "막은 줄")

        # 낙하 타이머 및 락 딜레이 (표준 낙하/락 딜레이)
        self.fall_speed = 0.8  # 초 단위 (생존자 수에 따라 배틀로얄에서 가속됨)
        self.fall_timer = 0.0
        self.lock_delay = 0.5  # 바닥 닿았을 때 락 딜레이 (초)
        self.lock_timer = 0.0
        self.lock_resets = 0      # 바닥에서 한 조작 횟수 (최대+1까지 셈: 15번까지는 락 타이머를 되돌리고, 그다음 조작/착지는 바로 고정)
        self.max_lock_resets = 15
        self.lowest_y = 0         # 이 블록이 지금까지 내려간 가장 낮은 줄 (더 낮은 줄에 내려가면 조작 횟수를 다시 15번 줌: 가이드라인 Move Reset)

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
        self.current_y = SPAWN_Y
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
        self.lowest_y = self.current_y
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

    def _track_lowest(self):
        """블록이 이전보다 낮은 줄에 내려갔으면 조작 횟수를 새로 15번 준다 (같은 높이에서 뜨고 내려앉기를 반복해도 횟수는 늘지 않음)"""
        if self.current_y > self.lowest_y:
            self.lowest_y = self.current_y
            self.lock_resets = 0

    def _on_piece_manipulated(self, was_touching=False):
        """블록 조작 시 락 딜레이 리셋 (줄마다 최대 15회). 조작 전이나 후에 바닥에 닿아 있으면 한 번으로 셈 (회전으로 떴다 내려앉아도 공짜가 아님).
        15번을 넘긴 조작은 타이머를 되돌리지 못하고, 바닥에 닿아 있는 한 다음 업데이트에서 바로 고정됨"""
        if was_touching or self._is_touching_ground():
            if self.lock_resets < self.max_lock_resets:
                self.lock_timer = 0.0
            if self.lock_resets <= self.max_lock_resets:
                self.lock_resets += 1
        else:
            self.lock_timer = 0.0

    def move(self, dx, dy, soft=False, auto=False):
        """좌우 및 아래 이동. 성공 여부 반환.
        soft: 소프트 드롭 입력(점수 +1), auto: 중력에 의한 자동 낙하(락 리셋 횟수를 소모하지 않음)."""
        if self.game_over:
            return False
        if not self._check_collision(self.current_x + dx, self.current_y + dy, self.current_rot):
            was_touching = self._is_touching_ground()
            self.current_x += dx
            self.current_y += dy
            self._track_lowest()
            if dy > 0 and soft:
                self.score += 1
                self.fall_timer = 0.0
            self.last_move_was_rotation = False
            if auto:
                self.lock_timer = 0.0
            else:
                self._on_piece_manipulated(was_touching)
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
                was_touching = self._is_touching_ground()
                self.current_x = test_x
                self.current_y = test_y
                self.current_rot = new_rot
                self._track_lowest()
                self.last_move_was_rotation = True
                self.last_kick_index = kick_idx
                self._on_piece_manipulated(was_touching)
                return True
        return False

    # 180도 회전 킥 후보 (dx, 위쪽이 +): 제자리 -> 위 -> 좌우 -> 좌우 위
    ROT180_KICKS = [(0, 0), (0, 1), (1, 0), (-1, 0), (1, 1), (-1, 1)]
    ROT180_KICKS_I = ROT180_KICKS + [(2, 0), (-2, 0), (0, 2)]       # 4칸짜리 I는 벽/구멍 근처에서 더 넓게 시도 (180도 회전이 쉽게 막히지 않게)

    def rotate180(self):
        """180도 회전(선택 키). SRS에는 없는 동작이라 간단한 킥 목록만 쓰며, T-스핀 판정은 기존 3-코너 규칙을 그대로 따름(킥 번호로 인한 정식 판정은 없음)"""
        if self.game_over or self.current_piece == 'O':
            return False
        new_rot = (self.current_rot + 2) % 4
        for kick_idx, (kx, ky) in enumerate(self.ROT180_KICKS_I if self.current_piece == 'I' else self.ROT180_KICKS):
            test_x = self.current_x + kx
            test_y = self.current_y - ky
            if not self._check_collision(test_x, test_y, new_rot):
                was_touching = self._is_touching_ground()
                self.current_x = test_x
                self.current_y = test_y
                self.current_rot = new_rot
                self._track_lowest()
                self.last_move_was_rotation = True
                self.last_kick_index = min(kick_idx, 3)
                self._on_piece_manipulated(was_touching)
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
            if x < 0 or x >= self.width or y >= self.height:
                return True                                      # 벽/바닥은 막힌 칸
            if y < 0:
                return False                                     # 위쪽 숨김 구역은 비어 있음 (충돌 판정과 같은 규칙: 천장 근처에서 가짜 T-스핀이 나오지 않게)
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
            self.current_y = SPAWN_Y
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
        start_cells = [(x, y) for x, y in self._get_blocks(self.current_piece, self.current_rot, self.current_x, self.current_y)]
        while not self._check_collision(self.current_x, self.current_y + 1, self.current_rot):
            self.current_y += 1
            drop_dist += 1
        self.score += drop_dist * 2
        if drop_dist > 0:
            self.last_move_was_rotation = False                # 떨어진 뒤에는 회전 직후가 아님 (중력 낙하와 같게): 공중 회전 후 하드 드롭이 T-스핀이 되지 않음
        self.hard_drop_events += 1
        self.last_hard_drop = {"cells": start_cells, "dist": drop_dist}
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
        if all(y < 0 for _x, y in blocks):                       # 락 아웃: 블록이 전부 보이는 칸 위(숨김 구역)에서 고정되면 탈락. 일부만 걸쳐 있으면 숨은 칸은 버리고 계속
            self.game_over = True
        for x, y in blocks:
            if 0 <= y < self.height and 0 <= x < self.width:
                self.grid[y][x] = self.current_piece
            elif y >= 0:                                         # 옆/아래로 보드 밖은 있을 수 없는 위치
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
        canceled = 0                                   # 이번 클리어로 상쇄(막은)한 받을 공격 줄 수 (도전 과제 판정용)

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

            # B2B 보너스: 연쇄가 이어질수록 커짐 (연쇄 1~3: +1줄, 4~7: +2줄, 8 이상: +3줄) -> 어려운 클리어를 끊지 않고 모았다 터뜨리는 보람
            if is_b2b and is_difficult:
                base_attack += 1 + (self.b2b_chain >= 4) + (self.b2b_chain >= 8)

            # 퍼펙트 클리어: 줄을 지운 뒤 보드에 블록이 하나도 없으면 큰 보너스 공격
            is_pc = all(cell is None for row in self.grid for cell in row)
            if is_pc:
                base_attack += self.perfect_clear_attack
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
                self.garbage_canceled_total += canceled
                attack_lines -= canceled
        else:
            self.combo = -1
            if is_tspin:
                self.score += 100

        if self.replay_log is not None:
            self.replay_log.append({"k": "L", "p": self.current_piece, "c": [[int(x), int(y)] for x, y in self.last_lock_cells],
                                    "r": [int(r) for r in self.cleared_row_indices] if cleared_lines else [], "s": int(self.score)})
        self.garbage_to_send += attack_lines         # 같은 프레임에 두 번 고정돼도 앞선 공격이 사라지지 않게 누적
        self.last_clear_info = {
            'cleared': cleared_lines,
            'is_tspin': is_tspin,
            'is_mini': is_mini,
            'is_b2b': is_b2b,
            'b2b_chain': self.b2b_chain,
            'is_pc': is_pc,
            'attack': attack_lines,
            'canceled': canceled,
            'combo': self.combo,
            'cleared_rows': list(self.cleared_row_indices)
        }

        # 라인을 지우지 못했고 대기 중인 쓰레기 줄이 있다면 보드 아래로 밀어올림
        # (한 번에 올라오는 줄 수는 제한하고, 초과분은 다음 락다운까지 대기열에 유지)
        # (차징이 끝난 묶음만 올라옴. 묶음마다 구멍 위치가 따로 정해짐)
        if cleared_lines == 0 and self._garbage and not self.game_over:
            self.current_piece = None                            # 방금 고정한 블록은 이미 보드에 있음: 남겨 두면 _push_garbage가 그 자리를 '조작 중 블록'으로 보고 충돌 보정을 해 억울하게 탈락시킴
            groups = self._take_garbage(MAX_GARBAGE_PER_LOCK, ready_only=True)
            for group, hole in zip(groups, self._take_holes):
                self._push_garbage(group, hole)
                if self.game_over:
                    break

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
            self.cleared_row_cells = [(y, list(self.grid[y])) for y in cleared_rows]
            keep = [y for y in range(len(self.grid)) if y not in cleared_rows]
            offs = [0] * len(self.grid)
            for i, oy in enumerate(keep):
                offs[cleared + i] = (cleared + i) - oy
            self.settle_offsets = offs
            for _ in range(cleared):
                new_grid.insert(0, [None for _ in range(self.width)])
            self.grid = new_grid
            self.lines_cleared_total += cleared
            self.score += (100 * cleared * cleared)
        return cleared

    def _push_garbage(self, count, hole_x=None):
        """보드 하단에 구멍 1개가 뚫린 쓰레기 줄을 밀어 올림. 한 번에 올라오는 줄은 모두 같은 열에 구멍이 있음 (hole_x가 없으면 무작위)"""
        if hole_x is None:
            hole_x = self.garbage_rng.randint(0, self.width - 1)
        rec = None
        if self.replay_log is not None:
            rec = {"k": "G", "n": 0, "h": []}
            self.replay_log.append(rec)
        for i in range(count):
            # 맨 위 줄에 블록이 있어도 바로 탈락시키지 않음: 천장 밖으로 밀려난 칸은 사라지고, 새 블록이 나올 자리(또는 지금 조작 중인 블록)가 막힐 때만 탈락
            # (가이드라인 게임의 숨김 구역처럼, 스폰 구역 밖의 모서리에 블록이 닿았다고 억울하게 죽지 않게. 실제로 올라온 줄만 기록/집계)
            self.push_holes.append(hole_x)
            del self.push_holes[:-12]
            self.garbage_pushed_total += 1
            if rec is not None:
                rec["h"].append(int(hole_x))
                rec["n"] = len(rec["h"])
            self.grid.pop(0)
            new_row = ['G'] * self.width
            new_row[hole_x] = None
            self.grid.append(new_row)
        if rec is not None and not rec["h"]:
            self.replay_log.remove(rec)                 # 한 줄도 올라오지 못했으면 기록하지 않음

        # 쓰레기 줄이 올라왔을 때 현재 조작 중인 피스가 겹치지 않도록 위로 보정
        if self.current_piece and not self.game_over:
            while self._check_collision(self.current_x, self.current_y, self.current_rot) and self.current_y > -2:
                self.current_y -= 1
            if self._check_collision(self.current_x, self.current_y, self.current_rot):
                self.game_over = True

    @property
    def incoming_garbage(self):
        """공격 대기 중인 총 줄 수 (차징 중인 것 포함). AI/UI/네트워크는 이 값을 그대로 씀"""
        return self._ig_total

    @incoming_garbage.setter
    def incoming_garbage(self, value):
        """총 대기 줄 수를 직접 바꿈: 줄이면 오래된 묶음부터 차감 (상쇄/강제 밀어올림), 늘리면 바로 올라올 수 있는 묶음으로 추가 (스냅샷 복원 등)"""
        value = max(0, int(value))
        cur = self.incoming_garbage
        if value < cur:
            self._take_garbage(cur - value, ready_only=False)
        elif value > cur:
            self._garbage.append([value - cur, self._clock, None])
            self._ig_total = sum(b[0] for b in self._garbage)

    @property
    def ready_garbage(self):
        """차징이 끝나 다음 락다운(줄을 못 지웠을 때)에 올라올 수 있는 줄 수"""
        return sum(b[0] for b in self._garbage if b[1] <= self._clock)

    def garbage_segments(self):
        """경고 게이지용: [(줄 수, 올라올 준비 완료 여부, 보낸 사람), ...] (오래된 것부터 = 아래쪽부터)"""
        return [(b[0], b[1] <= self._clock, b[2]) for b in self._garbage]

    def _take_garbage(self, limit, ready_only):
        """대기 쓰레기를 오래된 묶음부터 최대 limit줄 꺼냄. 반환: 묶음별 줄 수 목록 (같은 묶음은 같은 구멍을 씀).
        ready_only일 때는 묶음마다 구멍 열을 하나 정해 두고(self._take_holes에 같은 순서로) 한 번에 다 못 올라와 나뉘어도 같은 열을 씀:
        한 번의 공격(쿼드 4줄 등)은 일직선 구멍으로 올라와 I 블록 하나로 되받아칠 수 있음. 다른 공격 묶음끼리는 구멍이 무작위"""
        taken, groups = 0, []
        self._take_holes = []
        for b in list(self._garbage):
            if ready_only and b[1] > self._clock:
                continue                      # 아직 충전 중인 묶음은 건너뛰고, 뒤에 들어온 즉시(instant) 묶음은 꺼냄
            n = min(b[0], limit - taken)
            if n <= 0:
                break
            b[0] -= n
            taken += n
            groups.append(n)
            if ready_only:
                if len(b) < 4:
                    b.append(self.garbage_rng.randint(0, self.width - 1))
                self._take_holes.append(b[3])
            if b[0] <= 0:
                self._garbage.remove(b)
        self._ig_total = sum(b[0] for b in self._garbage)
        return groups

    def queue_garbage(self, count, source=None, instant=False):
        """상대방에게 공격받아 쓰레기 라인 대기열에 추가됨 (대기열 상한 MAX_INCOMING_GARBAGE: 넘치는 분량은 버림).
        보통은 garbage_delay초 동안 차징한 뒤에야 올라올 수 있음. instant=True(시간 압박 등 공격이 아닌 것)는 바로 올라올 수 있음"""
        count = min(int(count), MAX_INCOMING_GARBAGE - self.incoming_garbage)
        if count > 0:
            delay = 0.0 if instant else self.garbage_delay
            self._garbage.append([count, self._clock + delay, source])
            self._ig_total += count

    def update(self, dt):
        """프레임 틱 업데이트 (dt 기반 자연 낙하 및 락 딜레이)"""
        if self.game_over:
            return 0
        self._clock += dt

        # 바닥에 닿았는지 체크
        if self._is_touching_ground():
            self.lock_timer += dt
            if self.lock_timer >= self.lock_delay or self.lock_resets > self.max_lock_resets:
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
            if self.lock_resets > self.max_lock_resets and self._is_touching_ground():
                return self.lock_down()         # 조작 횟수를 다 쓴 블록이 내려앉은 그 틱에 고정 (다음 입력이 끼어들어 다시 뜨는 것을 막음)

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
        """snapshot()이 만든 상태를 이 엔진에 그대로 반영 (관전 화면에서 실제 플레이처럼 그리기 위함).
        네트워크로 받은 값이라 먼저 모양/블록 종류를 검사하고, 맞지 않으면 아무것도 바꾸지 않고 ValueError"""
        g, p0 = snap["g"], snap.get("p")
        if not (isinstance(g, list) and len(g) == self.height and all(isinstance(r, str) and len(r) == self.width and set(r) <= set(".IJLOSTZG") for r in g)):
            raise ValueError("snapshot grid")
        if p0 and not (isinstance(p0, (list, tuple)) and len(p0) == 4 and p0[0] in PIECE_TYPES):
            raise ValueError("snapshot piece")
        for key in ("h", "n"):
            v = snap.get(key)
            if v and not all(c in PIECE_TYPES for c in v):
                raise ValueError("snapshot " + key)
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
        self.lowest_y = self.current_y                 # 새로 받은 블록 위치 기준으로 조작 횟수 제한을 다시 셈
        self.lock_resets = 0
        self._refill_next_queue()                      # 스냅샷은 다음 블록을 3개만 담으므로 탐색에 필요한 만큼 채움

    SPAWN_COLS = (3, 4, 5, 6)         # 새 블록이 나오는 열 (스폰 자리가 막히면 탈락)

    def spawn_column_top(self):
        """스폰 열(3~6)에서 가장 위에 있는 블록의 줄 번호 (없으면 보드 높이). 0 이하로 올라가면 새 블록이 나올 자리가 막힘"""
        for y in range(self.height):
            if any(self.grid[y][x] is not None for x in self.SPAWN_COLS):
                return y
        return self.height

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
