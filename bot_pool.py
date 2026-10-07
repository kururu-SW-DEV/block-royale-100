"""
Block Royale 100 - 봇 계산 작업 프로세스 풀
봇의 배치 탐색(bot_brain.plan_rows)을 별도 프로세스 여러 개에 나눠 맡겨 CPU 코어를 함께 씀.
 - 요청/응답은 아주 작음(보드 20줄 + 블록 정보). 결과가 한두 프레임 늦어도 봇은 '생각 중' 상태로 기다림.
 - 코어가 적거나 작업 프로세스가 죽으면 자동으로 꺼지고, 봇은 메인 프로세스에서 직접 계산(예전 방식)함.
 - 시작은 비동기: 작업 프로세스가 준비되기 전까지는 직접 계산으로 진행.
"""

import multiprocessing
import os
import pickle
import queue
import time

MAX_WORKERS = 6
MAX_INFLIGHT_PER_WORKER = 3            # 작업자 한 명당 동시에 맡길 수 있는 요청 수
STALL_AFTER = 5.0                      # 맡긴 요청이 있는데 이 시간(초) 동안 어떤 결과도 오지 않으면 작업 프로세스가 멈춘 것으로 보고 끔 (죽지는 않았지만 응답이 없는 경우)
STALE_AFTER = 8.0                      # 이 시간(초) 넘게 아무도 가져가지 않은 요청/결과는 정리 (탈락한 봇이 남긴 것)

_state = {"procs": [], "req": None, "res": None, "next": 1, "ready": {}, "pending": set(), "hello": 0,
          "broken": False, "started": False, "workers": 0, "last_res": 0.0,
          "born": {}, "params": None, "params_blob": None, "params_ver": 0}


def default_workers():
    """코어 수에 맞춘 작업 프로세스 수 (BR_BOT_WORKERS 환경 변수로 지정 가능, 0이면 끔)"""
    env = os.environ.get("BR_BOT_WORKERS")
    if env is not None:
        try:
            return max(0, min(MAX_WORKERS, int(env)))
        except ValueError:
            return 0
    cpus = os.cpu_count() or 1
    return max(0, min(MAX_WORKERS, cpus // 2 - 1))


def _worker_main(req_q, res_q):
    import bot_brain
    defaults = dict(bot_brain.PARAMS)                  # 일부 값만 덮어쓴 파라미터가 다음 요청에 남지 않게 기본값을 기억해 둠
    res_q.put((0, "hello"))
    last_ver = None
    while True:
        item = req_q.get()
        if item is None:
            break
        rid, rows, cur, hold, qu, can_hold, combo, b2b, inc, depth, beam, atk, ts, (ver, blob) = item
        if ver != last_ver:                            # 파라미터는 바뀐 버전일 때만 풀어서 적용
            bot_brain.PARAMS.clear()
            bot_brain.PARAMS.update(defaults)
            bot_brain.PARAMS.update(pickle.loads(blob))
            last_ver = ver
        try:
            res = bot_brain.plan_rows(rows, cur, hold, qu, can_hold, combo, b2b, inc, depth, beam, atk, ts)[:6]
        except Exception:
            res = []
        res_q.put((rid, res))


def start(workers=None):
    """작업 프로세스를 띄움(이미 떠 있으면 무시). 준비는 비동기로 진행됨"""
    st = _state
    if st["started"] or st["broken"]:
        return
    n = default_workers() if workers is None else max(0, min(MAX_WORKERS, workers))
    st["started"] = True
    st["workers"] = n
    if n <= 0:
        return
    try:
        ctx = multiprocessing.get_context("spawn")
        st["req"], st["res"] = ctx.Queue(), ctx.Queue()
        for _ in range(n):
            p = ctx.Process(target=_worker_main, args=(st["req"], st["res"]), daemon=True)
            p.start()
            st["procs"].append(p)
    except Exception:
        _mark_broken()


def _mark_broken():
    _state["broken"] = True
    stop()


def stop():
    st = _state
    for _ in st["procs"]:
        try:
            st["req"].put_nowait(None)
        except Exception:
            pass
    for p in st["procs"]:
        try:
            p.join(timeout=0.3)
            if p.is_alive():
                p.terminate()
        except Exception:
            pass
    st["procs"] = []
    st["ready"].clear()
    st["pending"].clear()
    st["born"].clear()
    st["params"] = st["params_blob"] = None
    st["hello"] = 0
    st["last_res"] = 0.0
    st["req"] = st["res"] = None
    st["started"] = False                              # 다시 start()하면 작업 프로세스가 새로 떠야 함


def pump():
    """도착한 결과를 모으고 작업 프로세스가 죽었는지 확인 (프레임마다 한 번 호출)"""
    st = _state
    if not st["procs"]:
        return
    now = time.time()
    gap = now - st.get("last_pump", now)
    st["last_pump"] = now
    if gap > 1.0:                                      # 일시정지 등으로 pump가 오래 멈췄다면 그 시간은 '멈춘 작업자/오래된 요청' 판정에서 뺌
        for rid in st["born"]:
            st["born"][rid] += gap
        if st["last_res"]:
            st["last_res"] += gap
    try:
        while True:
            rid, res = st["res"].get_nowait()
            st["last_res"] = time.time()
            if rid == 0:
                st["hello"] += 1
            elif rid in st["pending"]:
                st["pending"].discard(rid)
                st["ready"][rid] = res
    except queue.Empty:
        pass
    except Exception:
        _mark_broken()
        return
    if st["born"]:                                     # 주인(탈락한 봇 등)이 가져가지 않은 오래된 요청/결과 정리
        cutoff = time.time() - STALE_AFTER
        for rid in [r for r, t in st["born"].items() if t < cutoff]:
            st["born"].pop(rid, None)
            st["pending"].discard(rid)
            st["ready"].pop(rid, None)
    if any(not p.is_alive() for p in st["procs"]):
        _mark_broken()
    elif st["pending"] and st["hello"] > 0 and time.time() - st["last_res"] > STALL_AFTER:
        _mark_broken()                                 # 멈춘 작업자: 봇은 메인 프로세스에서 직접 계산하는 방식으로 이어감


def enabled():
    """준비를 마친 작업 프로세스가 있고 여유가 있는가"""
    st = _state
    return st["hello"] > 0 and not st["broken"] and len(st["pending"]) < st["hello"] * MAX_INFLIGHT_PER_WORKER


def ready_workers():
    return _state["hello"]


def submit(rows, cur, hold, qu, can_hold, combo, b2b, inc, depth, beam, atk, ts, params):
    """탐색 요청을 맡김. 요청 번호를 돌려줌(맡길 수 없으면 None)"""
    st = _state
    if not enabled():
        return None
    rid = st["next"]
    st["next"] += 1
    if params != st["params"]:                         # 요청마다 dict를 pickle하지 않고, 바뀔 때만 한 번 묶어 둠
        st["params"] = dict(params)
        st["params_blob"] = pickle.dumps(st["params"])
        st["params_ver"] += 1
    try:
        st["req"].put((rid, rows, cur, hold, qu, can_hold, combo, b2b, inc, depth, beam, atk, ts,
                       (st["params_ver"], st["params_blob"])))
    except Exception:
        _mark_broken()
        return None
    if not st["pending"]:
        st["last_res"] = time.time()                   # 한가하다가 처음 맡기는 순간부터 응답 시간을 잼
    st["pending"].add(rid)
    st["born"][rid] = time.time()
    return rid


def take(rid):
    """결과가 왔으면 꺼내서 돌려주고(없으면 None), 요청을 정리함"""
    res = _state["ready"].pop(rid, None)
    if res is not None:
        _state["born"].pop(rid, None)
    return res


def cancel(rid):
    _state["pending"].discard(rid)
    _state["ready"].pop(rid, None)
    _state["born"].pop(rid, None)


def wait_ready(timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        pump()
        if _state["hello"] >= max(1, _state["workers"]):
            return True
        time.sleep(0.02)
    return _state["hello"] > 0
