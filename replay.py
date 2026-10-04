"""
Block Royale 100 - 내 보드 리플레이 (v1.1.14)
경기 중 '내 보드'에서 일어난 사건만 가볍게 기록해 두었다가 다시 재생한다. 입력이나 난수를 되돌리는 방식이 아니라,
- 블록이 고정된 순간(L): 시각 / 블록 종류 / 칸 좌표 / 지워진 줄 / 그때의 점수
- 쓰레기 줄이 올라온 순간(G): 시각 / 줄 수 / 구멍 열
을 적고, 재생할 때는 빈 보드에 그 사건을 순서대로 적용해 보드를 다시 만든다. 그래서 프레임 시간이 달라도 결과가 어긋나지 않는다.
(블록이 떨어지는 중간 움직임은 기록하지 않고, 고정되는 순간마다 보드가 바뀌는 모습을 보여 준다. 100명 전체가 아니라 내 보드만.)
저장: replays.json (최근 MAX_REPLAYS판). 한 판은 보통 수십 KB 이하.
"""

import json
import os
import time

from app_paths import data_path

MAX_REPLAYS = 10
BOARD_W, BOARD_H = 10, 20


def replay_path():
    return data_path("replays.json")


class ReplayRecorder:
    """경기 중 엔진을 매 프레임 훑어 사건을 쌓음 (고정/쓰레기 횟수가 늘었을 때만 기록하므로 비용은 거의 없음)"""

    def __init__(self, meta=None):
        self.meta = dict(meta or {})
        self.events = []
        self._engine = None
        self.finished = False

    def update(self, engine, elapsed):
        if self.finished:
            return
        if engine is not self._engine:                         # 엔진이 바뀌면(재시작 등) 기준만 다시 잡음
            self._engine = engine
            engine.replay_log = []
            return
        log = engine.replay_log
        if not log:
            return
        t = round(float(elapsed), 2)
        for ev in log:                                         # 엔진이 쌓은 사건을 순서대로 옮김 (한 프레임에 여러 번 고정돼도 모두 기록)
            ev["t"] = t
            self.events.append(ev)
        last = log[-1]
        if last["k"] == "L":                                   # 지금 시점의 조작 중 블록 / 다음 3개 / 홀드 / 받을 쓰레기 (재생 화면 표시와 '여기서부터 연습'용)
            last["cp"] = engine.current_piece or ""
            last["nx"] = "".join(engine.next_queue[:3])
            last["hd"] = engine.hold_piece or ""
            last["ig"] = int(engine.incoming_garbage)
        engine.replay_log = []

    def finish(self, rank, total, kos, score, secs):
        """기록을 마무리해 저장용 dict로 돌려줌"""
        self.finished = True
        data = dict(self.meta)
        data.update({"date": time.strftime("%m-%d %H:%M"), "rank": int(rank), "total": int(total), "kos": int(kos),
                     "score": int(score), "secs": int(secs), "events": self.events})
        return data


def apply_events(events, upto_index=None):
    """사건 목록을 빈 보드에 순서대로 적용해 보드(행 목록, 값은 블록 종류 문자 또는 None)를 돌려줌 (재생과 검증에 공용)"""
    grid = [[None] * BOARD_W for _ in range(BOARD_H)]
    for ev in (events if upto_index is None else events[:upto_index]):
        apply_one(grid, ev)
    return grid


def apply_one(grid, ev):
    if ev["k"] == "L":
        for x, y in ev["c"]:
            if 0 <= y < BOARD_H and 0 <= x < BOARD_W:
                grid[y][x] = ev["p"]
        rows = sorted(set(ev["r"]))
        if rows:
            keep = [row for i, row in enumerate(grid) if i not in rows]
            grid[:] = [[None] * BOARD_W for _ in rows] + keep
    elif ev["k"] == "G":
        holes = ev["h"]
        for i in range(ev["n"]):
            hole = holes[i] if i < len(holes) else 0
            grid.pop(0)
            row = ["G"] * BOARD_W
            row[hole % BOARD_W] = None
            grid.append(row)


class ReplayPlayer:
    """저장된 리플레이 한 판을 시각 t에 맞는 보드로 보여 줌. 앞으로 재생은 사건을 이어서 적용, 되감기는 처음부터 다시 적용"""

    def __init__(self, data):
        self.data = data
        self.events = data["events"]
        self.duration = max([e["t"] for e in self.events] + [float(data.get("secs", 0))] + [1.0])
        self.t = 0.0
        self.speed = 1.0
        self.paused = False
        self.reset()

    def reset(self):
        self.grid = [[None] * BOARD_W for _ in range(BOARD_H)]
        self.idx = 0
        self.score = 0
        self.cur, self.next, self.hold, self.ig = "", "", "", 0      # 가장 최근 고정 시점의 조작 중 블록 / 다음 블록 / 홀드 / 받을 쓰레기
        self.last = None            # 가장 최근에 적용한 사건 (고정된 칸 강조용)
        self.last_t = -9.0

    def seek(self, t):
        t = max(0.0, min(self.duration, t))
        if t < self.t:
            self.reset()
        self.t = t
        self._advance()

    def _advance(self):
        while self.idx < len(self.events) and self.events[self.idx]["t"] <= self.t:
            ev = self.events[self.idx]
            apply_one(self.grid, ev)
            if ev["k"] == "L":
                self.score = ev.get("s", self.score)
                if "nx" in ev:
                    self.cur, self.next, self.hold, self.ig = ev.get("cp", ""), ev["nx"], ev.get("hd", ""), ev.get("ig", 0)
            self.last, self.last_t = ev, ev["t"]
            self.idx += 1

    def update(self, dt):
        if not self.paused and self.t < self.duration:
            self.t = min(self.duration, self.t + dt * self.speed)
            self._advance()

    @property
    def finished(self):
        return self.t >= self.duration


def _valid_event(ev):
    if not isinstance(ev, dict) or ev.get("k") not in ("L", "G") or not isinstance(ev.get("t"), (int, float)):
        return False
    if ev["k"] == "L":
        return (isinstance(ev.get("p"), str) and len(ev["p"]) == 1 and isinstance(ev.get("c"), list) and len(ev["c"]) <= 8
                and all(isinstance(c, list) and len(c) == 2 and all(isinstance(v, int) for v in c) for c in ev["c"])
                and isinstance(ev.get("r"), list) and all(isinstance(r, int) and 0 <= r < BOARD_H for r in ev["r"])
                and all(isinstance(ev.get(k, ""), str) and len(ev.get(k, "")) <= n and set(ev.get(k, "")) <= set("IJLOSTZ") for k, n in (("cp", 1), ("nx", 3), ("hd", 1)))
                and isinstance(ev.get("ig", 0), int) and not isinstance(ev.get("ig", 0), bool) and 0 <= ev.get("ig", 0) <= 400)
    return isinstance(ev.get("n"), int) and 0 < ev["n"] <= 24 and isinstance(ev.get("h"), list) and all(isinstance(h, int) for h in ev["h"])


def _clean(entry):
    """저장 파일에서 읽은 한 판이 형식에 맞으면 정리해서 돌려주고, 아니면 None"""
    if not isinstance(entry, dict) or not isinstance(entry.get("events"), list):
        return None
    evs = [e for e in entry["events"] if _valid_event(e)]
    if len(evs) != len(entry["events"]) or len(evs) > 6000:
        return None
    out = {"events": evs}
    for k in ("rank", "total", "kos", "score", "secs"):
        v = entry.get(k, 0)
        out[k] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else 0
    out["date"] = entry.get("date", "")[:16] if isinstance(entry.get("date"), str) else ""
    return out


def best_replay(replays):
    """고스트로 쓸 '내 최고 판': 점수가 가장 높은 판 (같으면 더 오래 버틴 판). 사건이 있는 판만. 없으면 None"""
    ok = [r for r in replays if r.get("events")]
    return max(ok, key=lambda r: (r.get("score", 0), r.get("secs", 0))) if ok else None


def load_replays(path=None):
    path = path or replay_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []
    items = raw.get("replays") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    out = [c for c in (_clean(e) for e in items) if c]
    return out[-MAX_REPLAYS:]


def save_replay(entry, path=None):
    """새 판을 맨 뒤에 붙이고 최근 MAX_REPLAYS판만 남김 (임시 파일에 쓴 뒤 교체). 실패해도 게임에는 영향 없음"""
    path = path or replay_path()
    try:
        if not entry or len(entry.get("events", [])) < 3:       # 거의 아무 일도 없던 판은 저장하지 않음
            return False
        items = load_replays(path) + [entry]
        items = items[-MAX_REPLAYS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"replays": items}, f, separators=(",", ":"))
        os.replace(tmp, path)
        return True
    except Exception:
        return False
