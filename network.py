"""
Block Royale 100 - Serverless UDP Network Engine
호스트 모드 및 클라이언트 모드를 모두 지원하는 P2P UDP 네트워크 엔진
"""

import socket
import threading
import json
import time
import zlib
import math
from config import DEFAULT_UDP_PORT, DISCOVERY_BROADCAST_PORT, NAME_COLOR_COUNT, APP_VERSION

PROTOCOL_VERSION = 1         # 호환되지 않는 패킷 변경 때 올림. JOIN_REQ의 proto와 다르면 호스트가 거절

MAX_CHAT_LEN = 120            # 채팅 한 줄 최대 글자 수
MAX_ATTACK_LINES = 20        # 패킷 1개당 허용되는 최대 공격 줄 수 (위조/오류 방어)
MAX_CLIENT_PACKET = 8192     # 호스트가 클라이언트에게서 받는 패킷 최대 크기
ATTACK_BUCKET_MAX = 120      # 클라이언트 한 명이 한꺼번에 보낼 수 있는 공격 줄 수 (토큰 버킷 용량)
ATTACK_REFILL_PER_SEC = 10   # 초당 회복되는 공격 줄 수 (정상 플레이 상한보다 넉넉하게)
MAX_INCOMING_ATTACKS = 300   # 처리 대기 중인 공격 큐 상한
WORLD_SYNC_CHUNK = 8         # WORLD_SYNC 패킷 하나에 담는 플레이어 수 (압축 후 MTU 1.5KB 이내)


class MsgType:
    """UDP 메시지의 "type" 값. 송신/수신이 같은 상수를 쓰도록 한 곳에 모음 (오타 방지, 프로토콜 목록 확인용)"""
    # 참가자 -> 호스트
    JOIN_REQ = "JOIN_REQ"; CLIENT_STATE = "CLIENT_STATE"; ATTACK = "ATTACK"; PING = "PING"
    LEAVE = "LEAVE"; PROFILE = "PROFILE"; CHAT = "CHAT"; PROBE = "PROBE"
    # 호스트 -> 참가자
    JOIN_ACK = "JOIN_ACK"; JOIN_NACK = "JOIN_NACK"; ROSTER = "ROSTER"; GAME_START = "GAME_START"
    WORLD_SYNC = "WORLD_SYNC"; LOBBY_RETURN = "LOBBY_RETURN"; HOST_LEFT = "HOST_LEFT"; PROFILE_ACK = "PROFILE_ACK"
    PROBE_ACK = "PROBE_ACK"
    # LAN 방 알림
    BEACON = "BEACON"; BEACON_CLOSED = "BEACON_CLOSED"

    ALL = frozenset({"JOIN_REQ", "CLIENT_STATE", "ATTACK", "PING", "LEAVE", "PROFILE", "CHAT", "PROBE", "JOIN_ACK",
                     "JOIN_NACK", "ROSTER", "GAME_START", "WORLD_SYNC", "LOBBY_RETURN", "HOST_LEFT", "PROFILE_ACK",
                     "PROBE_ACK", "BEACON", "BEACON_CLOSED"})


def _disable_udp_connreset(sock):
    """Windows: 상대 포트가 닫혀 있으면 다음 recvfrom이 ConnectionResetError(10054)를 내는 동작을 끔."""
    ioctl = getattr(sock, "ioctl", None)
    code = getattr(socket, "SIO_UDP_CONNRESET", None)
    if ioctl is None or code is None:
        return
    try:
        ioctl(code, False)
    except (OSError, ValueError):
        pass


def _recv_should_stop(sock, running, err):
    """수신 중 오류가 났을 때 루프를 끝낼지 판단. 상대가 죽어서 생기는 CONNRESET은 무시하고 계속 받음."""
    if not running:
        return True
    if isinstance(err, ConnectionResetError):
        return False
    try:
        if sock.fileno() == -1:
            return True
    except OSError:
        return True
    time.sleep(0.01)             # 다른 일시 오류: 바쁜 대기 방지
    return False


def _sanitize_name(name, fallback):
    if not isinstance(name, str):
        return fallback
    name = "".join(ch for ch in name if ch.isprintable()).strip()[:16]
    return name or fallback


_SNAP_CHARS = set("IJLOSTZG.")
_PIECES = set("IJLOSTZ")


def _sanitize_snapshot(snap):
    """관전용 스냅샷 검증. 잘못된 값이면 None (가로 10 x 세로 20, 허용된 문자만)."""
    if not isinstance(snap, dict):
        return None
    g = snap.get("g")
    if not isinstance(g, list) or len(g) != 20:
        return None
    for row in g:
        if not isinstance(row, str) or len(row) != 10 or not set(row) <= _SNAP_CHARS:
            return None
    p = snap.get("p")
    if p is not None:
        if not (isinstance(p, list) and len(p) == 4 and p[0] in _PIECES and all(isinstance(v, int) and not isinstance(v, bool) for v in p[1:])):
            return None
        if not (0 <= p[1] < 4 and -4 <= p[2] <= 14 and -4 <= p[3] <= 24):
            return None
    h = snap.get("h")
    if h is not None and h not in _PIECES:
        return None
    n = snap.get("n")
    if not isinstance(n, list) or len(n) > 3 or not all(x in _PIECES for x in n):
        return None
    def _int(v, lo, hi, default):
        return max(lo, min(hi, v)) if isinstance(v, int) and not isinstance(v, bool) else default
    lp = snap.get("lp", 0.0)
    return {"g": list(g), "p": p, "h": h, "n": list(n),
            "ig": _int(snap.get("ig"), 0, 400, 0), "c": _int(snap.get("c"), -1, 99, -1),
            "b": 1 if snap.get("b") else 0, "bc": _int(snap.get("bc"), 0, 999, 0), "go": 1 if snap.get("go") else 0,
            "lp": float(lp) if isinstance(lp, (int, float)) and 0 <= lp <= 1 else 0.0}


def _sanitize_color(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < NAME_COLOR_COUNT:
        return value
    return 0


def _sanitize_chat_text(text):
    if not isinstance(text, str):
        return ""
    return "".join(ch for ch in text if ch.isprintable()).strip()[:MAX_CHAT_LEN]


def _sanitize_state(state):
    """클라이언트가 보낸 보드 상태를 검증/정규화. 잘못된 값이면 None."""
    if not isinstance(state, dict):
        return None
    grid = state.get("compact_grid")
    if not isinstance(grid, list) or len(grid) != 20:
        return None
    clean_grid = []
    for row in grid:
        if not isinstance(row, int) or isinstance(row, bool) or not (0 <= row < 1024):
            return None
        clean_grid.append(row)
    highest = state.get("highest_y", 20)
    if not isinstance(highest, int) or isinstance(highest, bool):
        highest = 20
    score = state.get("score", 0)
    if not isinstance(score, int) or isinstance(score, bool):
        score = 0
    spec = state.get("spec")
    out = {
        "is_alive": bool(state.get("is_alive", True)),
        "compact_grid": clean_grid,
        "highest_y": max(0, min(20, highest)),
        "score": max(0, score),
        "lines": max(0, min(99999, state.get("lines"))) if isinstance(state.get("lines"), int) and not isinstance(state.get("lines"), bool) else 0,
        "spec": spec[:32] if isinstance(spec, str) else None,     # 이 클라이언트가 관전 중인 대상 ID
    }
    snap = _sanitize_snapshot(state.get("snap"))
    if snap is not None:
        out["snap"] = snap
    return out


def _sanitize_world_state(st):
    """(클라이언트) 호스트가 보낸 플레이어 상태 검증: 숫자/문자열 필드의 타입과 범위를 강제 (잘못된 값이 게임 로직에 들어가 크래시하는 것을 방지)"""
    def _num(v, lo, hi, default):
        return max(lo, min(hi, v)) if isinstance(v, int) and not isinstance(v, bool) else default
    out = {"id": str(st["id"])[:32], "name": _sanitize_name(st.get("name"), "?"), "is_alive": bool(st.get("is_alive", True))}
    grid = st.get("compact_grid")
    if isinstance(grid, list) and len(grid) == 20 and all(isinstance(r, int) and not isinstance(r, bool) and 0 <= r < 1024 for r in grid):
        out["compact_grid"] = list(grid)
    out["highest_y"] = _num(st.get("highest_y"), 0, 20, 20)
    for key, hi in (("ko_count", 99), ("rank", 100), ("score", 10**9), ("lines", 99999), ("atk", 10**6)):
        if isinstance(st.get(key), int) and not isinstance(st.get(key), bool):
            out[key] = _num(st.get(key), 0, hi, 0)
    sv = st.get("surv")
    if isinstance(sv, (int, float)) and not isinstance(sv, bool) and math.isfinite(sv):
        out["surv"] = float(max(0.0, min(1e6, sv)))
    if isinstance(st.get("ig"), int) and not isinstance(st.get("ig"), bool):
        out["ig"] = _num(st.get("ig"), 0, 400, 0)                 # 받을 공격(쓰레기) 줄 수
    cg = st.get("cg")
    if isinstance(cg, str) and len(cg) == 200 and set(cg) <= _SNAP_CHARS:
        out["cg"] = cg
    cp = st.get("cp")
    if isinstance(cp, list) and len(cp) == 4 and cp[0] in _PIECES and all(isinstance(v, int) and not isinstance(v, bool) for v in cp[1:]):
        out["cp"] = [cp[0], cp[1] % 4, max(-4, min(14, cp[2])), max(-4, min(24, cp[3]))]
    else:
        out["cp"] = None
    nx = st.get("nx")
    if isinstance(nx, str) and len(nx) <= 3 and set(nx) <= _PIECES:
        out["nx"] = nx
    hd = st.get("hd")
    if isinstance(hd, str) and len(hd) <= 1 and set(hd) <= _PIECES:
        out["hd"] = hd
    snap = _sanitize_snapshot(st.get("snap"))
    if snap is not None:
        out["snap"] = snap
    return out


def _sanitize_attack(msg):
    """공격 패킷 검증. 유효하면 (from_id, to_id, lines), 아니면 None."""
    from_id = msg.get("from_id")
    to_id = msg.get("to_id")
    lines = msg.get("lines")
    if not isinstance(from_id, str) or not isinstance(to_id, str):
        return None
    if not isinstance(lines, int) or isinstance(lines, bool) or lines <= 0:
        return None
    return from_id, to_id, min(lines, MAX_ATTACK_LINES)


class NetworkManager:
    def __init__(self):
        self.mode = "NONE"  # "NONE", "HOST", "CLIENT"
        self.sock = None
        self.running = False
        self.listen_thread = None
        self.beacon_thread = None

        # 호스트 관련 데이터
        self.host_port = DEFAULT_UDP_PORT
        self.clients = {}  # {addr_tuple: {"id": str, "name": str, "last_seen": float, "state": dict, "seq": int}}
        self.client_next_id = 1

        # 클라이언트 관련 데이터
        self.server_addr = None
        self.my_player_id = None
        self.connected = False
        self.state_seq = 0             # 클라이언트 상태 패킷 시퀀스 (송신용)
        self._world_ts = {}            # 마지막으로 처리한 WORLD_SYNC 타임스탬프 (조각 번호별)

        # 수신 큐 / 최근 수신 데이터
        self.incoming_attacks = []     # [(from_id, to_id, lines)]
        self.remote_players_state = {} # {player_id: state_dict}
        self.game_started = False
        self.room_settings = {}
        self.initial_players = []
        self.join_rejected = None      # (클라이언트) 호스트가 입장을 거절한 이유 ("full" / "started" / "version")
        self.host_view_of_me = None    # (클라이언트) 호스트가 보낸 '나'의 상태 (순위 등 호스트 기준 값)
        self.match_attacks = True      # (클라이언트) 호스트가 정한 게임 모드 (False = 서바이벌: 공격 없음)
        self.lobby_return = False      # (클라이언트) 호스트가 경기를 마치고 대기실로 돌아왔다는 통보를 받음
        self.roster = []               # (클라이언트) 호스트가 알려준 참가자 명단 [{id, name, color, host}]
        self.roster_target = 0         # (클라이언트) 호스트가 정한 대전 인원
        self.my_color = 0              # 내 이름 색상 번호 (JOIN 요청 / 호스트 채팅에 사용)
        self.profile_ack = None        # (클라이언트) 호스트가 확정해 준 내 이름/색 {name, color}
        self.chat_log = []             # 채팅 기록 [{seq, id, name, text, sys, rx}] (최대 100개)
        self.chat_seq = 0              # (호스트) 채팅 순번
        self._chat_lock = threading.Lock()
        self._chat_seen = set()        # (클라이언트) 이미 받은 채팅 순번 (중복 수신 방지)
        self.host_left = False         # (클라이언트) 호스트가 방을 닫았다는 통보를 받음
        self.last_server_packet = 0.0  # (클라이언트) 호스트에게서 마지막으로 패킷을 받은 시각
        self.left_events = []          # (호스트) 나간 참가자 이름 목록 (화면 알림용)
        self.probe_results = {}        # 직접 조회한 주소의 방 정보 {(host, port): {ok, ts, room_name, players, max_players, open}}
        self._probing = set()
        self.remote_details = {}       # (클라이언트) 호스트가 보내준 관전 대상의 상세 스냅샷 {player_id: snapshot}

        # 방 검색(Discovery) 결과
        self.discovered_rooms = {}  # {host_ip: {"name": str, "players": int, "max": int, "timestamp": float}}

    # ----------------------------------------------------
    # 호스트(Host) 모드 시작
    # ----------------------------------------------------
    def start_host(self, port=DEFAULT_UDP_PORT, room_name="Royale Room", max_players=100):
        self.mode = "HOST"
        self.host_port = port
        self.my_player_id = "HOST_P1"
        self.clients = {}
        self.client_next_id = 1
        self.incoming_attacks.clear()
        self.remote_players_state.clear()
        self.chat_log.clear()
        self.chat_seq = 0
        self.left_events.clear()
        self.game_started = False
        self.room_settings = {
            "room_name": room_name,
            "max_players": max_players,
            "port": port
        }

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)   # Windows: 이미 쓰는 포트면 바인딩 실패로 알림
            else:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(("", port))
            _disable_udp_connreset(self.sock)
            self.running = True

            # 수신 스레드
            self.listen_thread = threading.Thread(target=self._host_receive_loop, daemon=True)
            self.listen_thread.start()

            # LAN 방 알림 비콘 스레드
            self.beacon_thread = threading.Thread(target=self._host_beacon_loop, daemon=True)
            self.beacon_thread.start()
            print(f"[Network] Host serverless UDP started on port {port}")
            return True
        except Exception as e:
            print(f"[Network] Failed to start Host: {e}")
            self.stop()
            return False

    def _host_beacon_loop(self):
        """LAN 내 클라이언트들이 방을 찾을 수 있도록 브로드캐스트 비콘 전송"""
        b_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running and not self.game_started:
            try:
                msg = {
                    "type": MsgType.BEACON,
                    "room_name": self.room_settings.get("room_name", "Block Room"),
                    "port": self.host_port,
                    "players": len(self.clients) + 1,
                    "max_players": self.room_settings.get("max_players", 100)
                }
                data = json.dumps(msg).encode('utf-8')
                b_sock.sendto(data, ("<broadcast>", DISCOVERY_BROADCAST_PORT))
            except Exception:
                pass
            if self.clients:
                self.host_broadcast_roster()
            time.sleep(1.0)

        try:
            b_sock.close()
        except Exception:
            pass

    def _host_receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.error as e:
                if _recv_should_stop(self.sock, self.running, e):
                    break
                continue
            except Exception:
                continue
            try:
                if len(data) > MAX_CLIENT_PACKET:
                    continue
                msg = json.loads(data.decode('utf-8'))
                if not isinstance(msg, dict):
                    continue
                mtype = msg.get("type")
                if addr in self.clients:
                    self.clients[addr]["last_seen"] = time.time()      # 종류와 상관없이 등록된 참가자가 보낸 패킷은 생존 신호

                if mtype == MsgType.JOIN_REQ:
                    self._host_handle_join(msg, addr)

                elif mtype == MsgType.CLIENT_STATE:
                    # 등록된 클라이언트의 상태만 수용 (시퀀스가 오래된 패킷은 무시)
                    cinfo = self.clients.get(addr)
                    if cinfo is None:
                        continue
                    seq = msg.get("seq")
                    if isinstance(seq, int) and seq <= cinfo.get("seq", -1):
                        continue
                    clean = _sanitize_state(msg.get("state"))
                    if clean is None:
                        continue
                    if isinstance(seq, int):
                        cinfo["seq"] = seq
                    cinfo["last_seen"] = time.time()
                    clean["id"] = cinfo["id"]
                    clean["name"] = cinfo["name"]
                    cinfo["state"] = clean
                    self.remote_players_state[cinfo["id"]] = clean

                elif mtype == MsgType.ATTACK:
                    # 등록된 클라이언트만 자기 ID로 공격 가능 (타인 ID 위조 차단)
                    cinfo = self.clients.get(addr)
                    parsed = _sanitize_attack(msg)
                    if cinfo is None or parsed is None:
                        continue
                    from_id, to_id, lines = parsed
                    if from_id != cinfo["id"]:
                        continue
                    if self.remote_players_state.get(from_id, {}).get("is_alive", True) is False:
                        continue                                       # 이미 탈락한 참가자의 공격은 무시
                    now_a = time.time()
                    tokens = min(ATTACK_BUCKET_MAX, cinfo.get("atk_tokens", ATTACK_BUCKET_MAX) + (now_a - cinfo.get("atk_t", now_a)) * ATTACK_REFILL_PER_SEC)
                    cinfo["atk_t"] = now_a
                    if tokens < lines or len(self.incoming_attacks) >= MAX_INCOMING_ATTACKS:
                        cinfo["atk_tokens"] = tokens
                        continue                                       # 속도 제한 초과(도배/조작) 공격은 버림
                    cinfo["atk_tokens"] = tokens - lines
                    self.incoming_attacks.append((from_id, to_id, lines))
                    # 다른 클라이언트들에게도 공격 이벤트 즉시 중계
                    self._host_broadcast(
                        {"type": MsgType.ATTACK, "from_id": from_id, "to_id": to_id, "lines": lines},
                        exclude_addr=addr
                    )

                elif mtype == MsgType.CHAT:
                    cinfo = self.clients.get(addr)
                    text = _sanitize_chat_text(msg.get("text"))
                    now = time.time()
                    if cinfo and text and now - cinfo.get("chat_t", 0.0) >= 0.4:      # 도배 방지 (0.4초에 1개)
                        cinfo["chat_t"] = now
                        self._host_publish_chat(cinfo["id"], cinfo["name"], text, color=cinfo.get("color", 0))

                elif mtype == MsgType.PROFILE:
                    self._host_handle_profile(addr, msg)

                elif mtype == MsgType.LEAVE:
                    self._host_drop_client(addr)

                elif mtype == MsgType.PROBE:
                    # 방 정보 조회: 참가하지 않고 방 이름/인원만 알려줌 (참가 화면에서 입력한 주소의 방을 목록에 띄우기 위함)
                    reply = {
                        "type": MsgType.PROBE_ACK,
                        "room_name": self.room_settings.get("room_name", "Block Room"),
                        "players": len(self.clients) + 1,
                        "max_players": self.room_settings.get("max_players", 100),
                        "open": not self.game_started,
                    }
                    try:
                        self.sock.sendto(json.dumps(reply).encode('utf-8'), addr)
                    except Exception:
                        pass

                elif mtype == MsgType.PING:
                    if addr in self.clients:
                        self.clients[addr]["last_seen"] = time.time()
            except Exception:
                # 패킷 깨짐 등 무시
                pass

    def _host_handle_join(self, msg, addr):
        """참가 요청 처리. 같은 주소의 중복 요청에는 기존 ID로 ACK만 다시 보냄."""
        info = self.clients.get(addr)
        if info is None and msg.get("proto") != PROTOCOL_VERSION:       # 다른 버전은 규칙/패킷이 어긋나므로 입장 거절
            try:
                self.sock.sendto(json.dumps({"type": MsgType.JOIN_NACK, "reason": "version", "host_app": APP_VERSION}).encode('utf-8'), addr)
            except Exception:
                pass
            return
        if info is None:
            if self.game_started or len(self.clients) + 1 >= self.room_settings.get("max_players", 100):
                reason = "started" if self.game_started else "full"
                try:                                            # 조용히 무시하지 않고 거절 이유를 알려 줌
                    self.sock.sendto(json.dumps({"type": MsgType.JOIN_NACK, "reason": reason}).encode('utf-8'), addr)
                except Exception:
                    pass
                return
            new_id = f"NET_P{self.client_next_id}"
            self.client_next_id += 1
            base_name = _sanitize_name(msg.get("name"), f"Player_{new_id}")
            taken = {c["name"] for c in list(self.clients.values())} | {self.room_settings.get("host_name", "")}
            name, n = base_name, 2
            while name in taken:                               # 같은 이름이 있으면 구분되도록 번호를 붙임
                name = f"{base_name[:13]}#{n}"
                n += 1
            info = {
                "id": new_id,
                "name": name,
                "color": _sanitize_color(msg.get("color")),
                "last_seen": time.time(),
                "state": {},
                "seq": -1
            }
            self.clients[addr] = info
            print(f"[Network] Client {new_id} ({addr}) joined.")
            self._host_publish_chat("SYS", "시스템", f"{name} 님이 입장했습니다", system=True)
            self.host_broadcast_roster()
        ack = {
            "type": MsgType.JOIN_ACK,
            "assigned_id": info["id"],
            "room_settings": self.room_settings
        }
        try:
            self.sock.sendto(json.dumps(ack).encode('utf-8'), addr)
        except Exception:
            pass

    def _host_broadcast(self, msg_dict, exclude_addr=None, compress=False):
        data = json.dumps(msg_dict).encode('utf-8')
        if compress:
            data = b"Z" + zlib.compress(data, 1)        # 큰 패킷(전체 플레이어 상태)은 압축해서 전송
        for addr in list(self.clients.keys()):
            if addr != exclude_addr:
                try:
                    self.sock.sendto(data, addr)
                except Exception:
                    pass

    def host_send_start_game(self, players_summary_list, attacks_enabled=True):
        """호스트가 게임 시작 패킷을 모든 클라이언트에게 신뢰성 있게 반복 전송"""
        self.game_started = True
        now0 = time.time()
        for info in list(self.clients.values()):
            info["last_seen"] = now0                     # 대기실에서 오래 기다렸어도 시작 직후 곧바로 제거되지 않게
        msg = {
            "type": MsgType.GAME_START,
            "players_list": players_summary_list,
            "attacks": bool(attacks_enabled),
            "start_time": time.time()
        }
        # UDP 유실 방지 3회 버스트 전송
        for _ in range(3):
            self._host_broadcast(msg)
            time.sleep(0.03)

    def _append_chat(self, entry):
        entry["rx"] = time.time()
        self.chat_log.append(entry)
        if len(self.chat_log) > 100:
            del self.chat_log[:len(self.chat_log) - 100]

    def _host_publish_chat(self, pid, name, text, system=False, color=0):
        """(호스트) 채팅/시스템 메시지를 기록하고 모든 참가자에게 전송 (유실 대비 2회 전송, 순번으로 중복 제거)"""
        with self._chat_lock:
            self.chat_seq += 1
            seq_now = self.chat_seq
        entry = {"seq": seq_now, "id": pid, "name": name, "text": text, "sys": bool(system), "color": _sanitize_color(color)}
        self._append_chat(dict(entry))
        msg = {"type": MsgType.CHAT, **entry}
        for _ in range(2):
            self._host_broadcast(msg)

    def send_chat(self, text, my_name="Host"):
        """채팅 전송. 호스트는 직접 방송하고, 클라이언트는 호스트에게 보냄(호스트가 다시 방송해 모두에게 표시됨)."""
        text = _sanitize_chat_text(text)
        if not text or not self.running:
            return False
        if self.mode == "HOST":
            self._host_publish_chat(self.my_player_id or "HOST_P1", _sanitize_name(my_name, "Host"), text, color=self.my_color)
            return True
        if self.mode == "CLIENT" and self.connected:
            try:
                self.sock.sendto(json.dumps({"type": MsgType.CHAT, "text": text}).encode('utf-8'), self.server_addr)
                return True
            except Exception:
                return False
        return False

    def host_reopen_room(self):
        """(호스트) 경기가 끝난 뒤 같은 방을 대기실 상태로 되돌림: 참가자는 유지하고 모두에게 대기실 복귀를 알림"""
        if self.mode != "HOST" or not self.running:
            return
        self.game_started = False
        self.remote_players_state.clear()       # 지난 경기의 탈락 상태가 다음 경기에 남지 않도록
        self.incoming_attacks.clear()
        now = time.time()
        for info in list(self.clients.values()):
            info["state"] = {}
            info["last_seen"] = now
        for _ in range(3):
            self._host_broadcast({"type": MsgType.LOBBY_RETURN})
            time.sleep(0.02)
        if not (self.beacon_thread and self.beacon_thread.is_alive()):     # 방 알림(비콘)/명단 전송 재개
            self.beacon_thread = threading.Thread(target=self._host_beacon_loop, daemon=True)
            self.beacon_thread.start()
        self.host_broadcast_roster()

    def roster_list(self):
        """(호스트) 현재 참가자 명단: 방장 + 접속한 클라이언트"""
        out = [{"id": self.my_player_id or "HOST_P1", "name": self.room_settings.get("host_name", "Host"),
                "color": self.my_color, "host": True}]
        for c in list(self.clients.values()):
            out.append({"id": c["id"], "name": c["name"], "color": c.get("color", 0), "host": False})
        return out

    def host_broadcast_roster(self):
        """(호스트) 참가자 전원에게 전체 명단과 대전 인원을 전송 (대기실에서 모두가 같은 명단을 보도록)"""
        if not self.running or self.mode != "HOST" or not self.clients:
            return
        self._host_broadcast({"type": MsgType.ROSTER, "players": self.roster_list(), "target": self.room_settings.get("target", 0)})

    def unique_name(self, base, exclude_addr=None, exclude_host=False):
        """(호스트) 다른 참가자/호스트와 겹치지 않는 이름 (겹치면 #번호를 붙임). exclude_*: 이름을 바꾸는 본인은 제외"""
        taken = {c["name"] for a, c in list(self.clients.items()) if a != exclude_addr}
        if not exclude_host:
            taken.add(self.room_settings.get("host_name", ""))
        name, n = base, 2
        while name in taken:
            name = f"{base[:13]}#{n}"
            n += 1
        return name

    def _host_handle_profile(self, addr, msg):
        """(호스트) 참가자가 이름/색을 바꿈: 이름 중복 정리 후 반영하고, 본인에게 확정값을 알리며 모두에게 시스템 메시지 전송"""
        info = self.clients.get(addr)
        if not info:
            return
        old = info["name"]
        new = self.unique_name(_sanitize_name(msg.get("name"), old), exclude_addr=addr)
        info["name"] = new
        info["color"] = _sanitize_color(msg.get("color"))
        try:
            self.sock.sendto(json.dumps({"type": MsgType.PROFILE_ACK, "name": new, "color": info["color"]}).encode('utf-8'), addr)
        except Exception:
            pass
        if new != old:
            self._host_publish_chat("SYS", "시스템", f"{old} 님이 이름을 {new}(으)로 바꿨습니다", system=True)
        self.host_broadcast_roster()

    def host_set_profile(self, name, color):
        """(호스트) 내 이름/색 변경 반영. 다른 참가자와 겹치면 번호를 붙인 최종 이름을 반환."""
        old = self.room_settings.get("host_name", "")
        final = self.unique_name(_sanitize_name(name, "Host"), exclude_host=True)
        self.room_settings["host_name"] = final
        self.my_color = _sanitize_color(color)
        if old and final != old and self.running:
            self._host_publish_chat("SYS", "시스템", f"{old} 님이 이름을 {final}(으)로 바꿨습니다", system=True)
        self.host_broadcast_roster()
        return final

    def send_profile(self, name, color):
        """(클라이언트) 내 이름/색 변경을 호스트에 알림 (호스트가 확정값을 PROFILE_ACK로 돌려줌)"""
        self.my_color = _sanitize_color(color)
        if self.mode == "CLIENT" and self.connected and self.sock:
            try:
                self.sock.sendto(json.dumps({"type": MsgType.PROFILE, "name": name, "color": self.my_color}).encode('utf-8'), self.server_addr)
            except Exception:
                pass

    def _host_drop_client(self, addr):
        """(호스트) 참가자가 나갔거나 연결이 끊김: 목록에서 제거하고, 게임 중이면 탈락 처리되도록 상태를 표시"""
        info = self.clients.pop(addr, None)
        if not info:
            return
        st = dict(self.remote_players_state.get(info["id"], {}))
        st["is_alive"] = False
        self.remote_players_state[info["id"]] = st
        self.left_events.append(info.get("name", info["id"]))
        self._host_publish_chat("SYS", "시스템", f"{info.get('name', info['id'])} 님이 나갔습니다", system=True)
        self.host_broadcast_roster()
        print(f"[Network] Client {info['id']} left.")

    def reap_clients(self, timeout=6.0):
        """(호스트) 게임 중 일정 시간 아무 신호가 없는 참가자를 연결 끊김으로 처리"""
        if not self.game_started:
            return
        now = time.time()
        for addr, info in list(self.clients.items()):
            if now - info.get("last_seen", now) > timeout:
                self._host_drop_client(addr)

    def seconds_since_host_packet(self):
        """(클라이언트) 호스트에게서 마지막 패킷을 받은 지 몇 초인지 (접속 전이면 0)"""
        if self.mode != "CLIENT" or not self.connected or not self.last_server_packet:
            return 0.0
        return time.time() - self.last_server_packet

    def get_spectated_ids(self):
        """(호스트) 현재 클라이언트들이 관전 중인 플레이어 ID 집합 (최근 2초 안에 보고한 것만)"""
        now = time.time()
        ids = set()
        for info in list(self.clients.values()):
            spec = info.get("state", {}).get("spec")
            if spec and now - info.get("last_seen", 0) < 2.0:
                ids.add(spec)
        return ids

    def host_sync_world(self, all_states, details=None):
        """호스트가 수집한 모든 플레이어 상태(+ 관전 대상의 상세 스냅샷)를 클라이언트들에게 전송"""
        if not self.running or self.mode != "HOST":
            return
        # 100명 전체를 한 패킷(압축 후 약 9KB)으로 보내면 IP 조각화로 조각 하나만 유실돼도 전체가 버려짐
        # -> 플레이어 WORLD_SYNC_CHUNK 명씩 독립 패킷(약 1.2KB 이하)으로 나눠 보냄. 각 패킷은 자기 몫만 갱신하므로 유실 영향이 작음
        ts = time.time()
        chunk = WORLD_SYNC_CHUNK
        parts = [all_states[i:i + chunk] for i in range(0, len(all_states), chunk)] or [[]]
        for idx, part in enumerate(parts):
            self._host_broadcast({"type": MsgType.WORLD_SYNC, "timestamp": ts, "part": idx, "states": part}, compress=True)
        if details:
            self._host_broadcast({"type": MsgType.WORLD_SYNC, "timestamp": ts, "part": "d", "states": [], "details": details}, compress=True)

    # ----------------------------------------------------
    # 클라이언트(Client) 모드 시작
    # ----------------------------------------------------
    def start_client(self, host_ip, host_port=DEFAULT_UDP_PORT, player_name="Player"):
        try:
            host_ip = socket.gethostbyname(host_ip)      # 호스트 이름으로 입력해도 접속되도록 IP로 바꿔 저장 (수신 패킷의 IP와 비교하기 때문)
        except Exception:
            print(f"[Network] Cannot resolve host: {host_ip}")
            return False
        self.mode = "CLIENT"
        self.server_addr = (host_ip, host_port)
        self.connected = False
        self.incoming_attacks.clear()
        self.remote_players_state.clear()
        self.game_started = False
        self.initial_players = []
        self.state_seq = 0
        self._world_ts = {}
        self._join_name = player_name
        self.join_rejected = None
        self.host_view_of_me = None
        self.lobby_return = False
        self.roster = []
        self.roster_target = 0
        self.chat_log.clear()
        self._chat_seen.clear()
        self.host_left = False
        self.last_server_packet = 0.0

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("", 0)) # 임의 로컬 포트 바인딩
            _disable_udp_connreset(self.sock)
            self.running = True

            # 수신 스레드
            self.listen_thread = threading.Thread(target=self._client_receive_loop, daemon=True)
            self.listen_thread.start()

            # 참가 요청 패킷 전송 (최대 5회 시도)
            join_msg = {
                "type": MsgType.JOIN_REQ,
                "name": player_name,
                "color": self.my_color,
                "proto": PROTOCOL_VERSION,
                "app": APP_VERSION
            }
            data = json.dumps(join_msg).encode('utf-8')
            for _ in range(5):
                self.sock.sendto(data, self.server_addr)
                time.sleep(0.1)
                if self.connected:
                    break

            print(f"[Network] Client connected to {host_ip}:{host_port} with ID: {self.my_player_id}")
            return True
        except Exception as e:
            print(f"[Network] Failed to start Client: {e}")
            self.stop()
            return False

    def client_keepalive(self, interval=1.0):
        """(클라이언트) 접속 중에는 어떤 화면(대기실/결과 화면 포함)에서도 1초마다 PING을 보내 호스트가 연결 끊김으로 오인하지 않게 함"""
        if self.mode != "CLIENT" or not self.running or not self.connected or not self.sock:
            return
        now = time.time()
        if now - getattr(self, "_last_ping", 0.0) < interval:
            return
        self._last_ping = now
        try:
            self.sock.sendto(json.dumps({"type": MsgType.PING}).encode('utf-8'), self.server_addr)
        except Exception:
            pass

    def client_retry_join(self):
        """아직 호스트의 응답(JOIN_ACK)을 못 받았다면 참가 요청을 다시 전송 (대기실에서 주기적으로 호출)"""
        if self.mode != "CLIENT" or not self.running or self.connected or not self.sock or self.join_rejected:
            return
        try:
            data = json.dumps({"type": MsgType.JOIN_REQ, "name": getattr(self, "_join_name", "Player"), "color": self.my_color, "proto": PROTOCOL_VERSION, "app": APP_VERSION}).encode('utf-8')
            self.sock.sendto(data, self.server_addr)
        except Exception:
            pass

    def _client_receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.error as e:
                if _recv_should_stop(self.sock, self.running, e):
                    break
                continue
            except Exception:
                continue
            try:
                # 호스트가 아닌 주소에서 온 패킷은 무시
                if addr[0] != self.server_addr[0] or addr[1] != self.server_addr[1]:
                    continue
                if data[:1] == b"Z":                         # 압축된 패킷 (압축 해제 크기 제한으로 폭탄 방지)
                    dec = zlib.decompressobj()
                    data = dec.decompress(data[1:], 2_000_000)
                    if dec.unconsumed_tail:
                        continue
                msg = json.loads(data.decode('utf-8'))
                if not isinstance(msg, dict):
                    continue
                self.last_server_packet = time.time()
                mtype = msg.get("type")

                if mtype == MsgType.HOST_LEFT:
                    self.host_left = True

                elif mtype == MsgType.LOBBY_RETURN:
                    # 호스트가 다시 대기실로 돌아옴: 지난 경기 상태를 비우고 다음 시작 신호를 기다림
                    self.lobby_return = True
                    self.host_view_of_me = None
                    self.game_started = False
                    self.initial_players = []
                    self.remote_players_state.clear()
                    self.remote_details.clear()
                    self.incoming_attacks.clear()
                    self._world_ts = {}

                elif mtype == MsgType.ROSTER:
                    players = msg.get("players")
                    if isinstance(players, list):
                        clean = []
                        for e in players[:100]:
                            if isinstance(e, dict) and isinstance(e.get("id"), str):
                                clean.append({"id": e["id"][:32], "name": _sanitize_name(e.get("name"), "?"),
                                              "color": _sanitize_color(e.get("color")), "host": bool(e.get("host"))})
                        self.roster = clean
                    tg = msg.get("target")
                    if isinstance(tg, int) and not isinstance(tg, bool):
                        self.roster_target = max(0, min(100, tg))

                elif mtype == MsgType.PROFILE_ACK:
                    self.profile_ack = {"name": _sanitize_name(msg.get("name"), "Player"), "color": _sanitize_color(msg.get("color"))}

                elif mtype == MsgType.CHAT:
                    seq = msg.get("seq")
                    text = _sanitize_chat_text(msg.get("text"))
                    if isinstance(seq, int) and not isinstance(seq, bool) and seq not in self._chat_seen and text:
                        self._chat_seen.add(seq)
                        self._append_chat({
                            "seq": seq, "id": str(msg.get("id", ""))[:32],
                            "name": _sanitize_name(msg.get("name"), "?"), "text": text, "sys": bool(msg.get("sys", False)),
                            "color": _sanitize_color(msg.get("color")),
                        })

                elif mtype == MsgType.JOIN_ACK:
                    aid = msg.get("assigned_id")
                    if not isinstance(aid, str) or not aid:
                        continue
                    rs = msg.get("room_settings", {})
                    self.connected = True
                    self.my_player_id = aid[:32]
                    self.room_settings = rs if isinstance(rs, dict) else {}
                    print(f"[Network] Joined successfully! Assigned ID: {self.my_player_id}")

                elif mtype == MsgType.JOIN_NACK:
                    reason = msg.get("reason")
                    if reason in ("full", "started", "version") and not self.connected:
                        self.join_rejected = reason

                elif mtype == MsgType.GAME_START:
                    plist = msg.get("players_list")
                    valid = (isinstance(plist, list) and 2 <= len(plist) <= 100 and self.connected and self.my_player_id and
                             all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in plist) and
                             any(e["id"] == self.my_player_id for e in plist))
                    if valid and not self.game_started:               # 접속 확인 전이거나 내 ID가 없는 시작 신호는 무시
                        self.initial_players = [
                            {"id": e["id"][:32], "name": _sanitize_name(e.get("name"), "?"), "is_ai": bool(e.get("is_ai"))} for e in plist]
                        self.match_attacks = bool(msg.get("attacks", True))
                        self.game_started = True
                        print(f"[Network] Game start received from host! Total players: {len(self.initial_players)}")

                elif mtype == MsgType.WORLD_SYNC:
                    # 전체 플레이어들의 최신 상태 수신 (순서가 뒤바뀐 오래된 패킷은 무시)
                    ts = msg.get("timestamp")
                    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
                        if not math.isfinite(ts):
                            continue                                     # inf/nan 타임스탬프로 이후 동기화가 막히는 것 방지
                        part = msg.get("part", 0)
                        part = part if (part == "d" or (isinstance(part, int) and not isinstance(part, bool) and 0 <= part < 64)) else 0
                        last = self._world_ts.get(part, 0.0)             # 조각마다 따로 최신 여부를 판단 (다른 조각의 패킷이 먼저 와도 버리지 않음)
                        if ts <= last and last - ts < 30.0:
                            continue                                     # 순서가 뒤바뀐 오래된 패킷 (호스트 시계가 크게 되돌려지면 새로 시작)
                        self._world_ts[part] = ts
                    details = msg.get("details")
                    if isinstance(details, dict):
                        for did, dsnap in details.items():
                            clean = _sanitize_snapshot(dsnap)
                            if isinstance(did, str) and clean is not None:
                                self.remote_details[did] = clean
                    states = msg.get("states", [])
                    if not isinstance(states, list):
                        continue
                    for st in states:
                        if not isinstance(st, dict):
                            continue
                        pid = st.get("id")
                        if isinstance(pid, str) and pid:
                            clean = _sanitize_world_state(st)
                            if clean is None:
                                continue
                            if pid == self.my_player_id:
                                self.host_view_of_me = clean            # 호스트가 판정한 내 순위/생존 (내 보드는 로컬에서 그대로)
                            else:
                                self.remote_players_state[pid[:32]] = clean

                elif mtype == MsgType.ATTACK:
                    parsed = _sanitize_attack(msg)
                    if parsed is not None:
                        self.incoming_attacks.append(parsed)
            except Exception:
                pass

    def client_send_state(self, state_dict):
        """클라이언트가 자신의 보드 상태를 호스트에 전송"""
        if not self.running or self.mode != "CLIENT" or not self.connected:
            return
        self.state_seq += 1
        msg = {
            "type": MsgType.CLIENT_STATE,
            "seq": self.state_seq,
            "state": state_dict
        }
        try:
            self.sock.sendto(json.dumps(msg).encode('utf-8'), self.server_addr)
        except Exception:
            pass

    def send_attack(self, from_id, to_id, lines):
        """공격 패킷 발송"""
        msg = {
            "type": MsgType.ATTACK,
            "from_id": from_id,
            "to_id": to_id,
            "lines": lines
        }
        if self.mode == "HOST":
            self._host_broadcast(msg)
        elif self.mode == "CLIENT" and self.connected:
            try:
                self.sock.sendto(json.dumps(msg).encode('utf-8'), self.server_addr)
            except Exception:
                pass

    # ----------------------------------------------------
    # LAN 방 자동 검색 (Discovery)
    # ----------------------------------------------------
    def probe_async(self, host, port, min_interval=1.2):
        """host:port 의 방이 열려 있는지 백그라운드로 조회 (결과는 probe_results). 같은 주소는 min_interval 초에 한 번만."""
        key = (host, port)
        res = self.probe_results.get(key)
        if key in self._probing or (res and time.time() - res["ts"] < min_interval):
            return
        self._probing.add(key)
        threading.Thread(target=self._probe_worker, args=key, daemon=True).start()

    def _probe_worker(self, host, port):
        info = {"ok": False}
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.6)
            s.sendto(json.dumps({"type": MsgType.PROBE}).encode('utf-8'), (host, port))
            deadline = time.time() + 0.8
            while time.time() < deadline:
                data, addr = s.recvfrom(2048)
                msg = json.loads(data.decode('utf-8'))
                if isinstance(msg, dict) and msg.get("type") == MsgType.PROBE_ACK:
                    mp = msg.get("max_players")
                    pl = msg.get("players")
                    info = {
                        "ok": True,
                        "room_name": _sanitize_name(msg.get("room_name"), "Room"),
                        "players": pl if isinstance(pl, int) and not isinstance(pl, bool) else 1,
                        "max_players": mp if isinstance(mp, int) and not isinstance(mp, bool) else 100,
                        "open": bool(msg.get("open", True)),
                    }
                    break
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        info["ts"] = time.time()
        self.probe_results[(host, port)] = info
        self._probing.discard((host, port))

    def start_discovery_listener(self):
        """로컬 LAN에 열려있는 호스트 방들을 찾는 리스너 시작"""
        disc_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        disc_thread.start()

    def _handle_discovery_message(self, host_ip, msg):
        """LAN 방 알림 수신 처리: BEACON은 방 목록에 등록/갱신, BEACON_CLOSED는 그 방을 바로 삭제 (포트가 같을 때만)"""
        if not isinstance(msg, dict):
            return
        kind = msg.get("type")
        if kind == MsgType.BEACON_CLOSED:
            info = self.discovered_rooms.get(host_ip)
            if info is not None and info.get("port") == msg.get("port"):
                self.discovered_rooms.pop(host_ip, None)          # 방이 닫혔음: 4초 만료를 기다리지 않고 바로 삭제
        elif kind == MsgType.BEACON:
            self.discovered_rooms[host_ip] = {
                "ip": host_ip,
                "port": msg.get("port", DEFAULT_UDP_PORT),
                "room_name": _sanitize_name(msg.get("room_name"), "Room"),
                "players": msg.get("players", 1),
                "max_players": msg.get("max_players", 100),
                "last_seen": time.time()
            }

    def _discovery_loop(self):
        d_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            d_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            d_sock.bind(("", DISCOVERY_BROADCAST_PORT))
            d_sock.settimeout(2.0)

            while True:
                try:
                    data, addr = d_sock.recvfrom(2048)
                    msg = json.loads(data.decode('utf-8'))
                    self._handle_discovery_message(addr[0], msg)
                except socket.timeout:
                    pass
                except Exception:
                    pass
                # 오래된 방 목록 정리 (패킷 수신 여부와 무관하게 주기적으로)
                now = time.time()
                self.discovered_rooms = {
                    ip: info for ip, info in self.discovered_rooms.items()
                    if now - info["last_seen"] < 4.0
                }
        except Exception as e:
            print(f"[Discovery] Failed to bind discovery socket: {e}")
        finally:
            try:
                d_sock.close()
            except Exception:
                pass

    def stop(self):
        was_host_running = self.running and self.mode == "HOST"
        host_port = self.host_port
        # 나가기 통보: 호스트는 참가자 전원에게 방이 닫혔음을, 클라이언트는 호스트에게 나갔음을 알림
        if self.running and self.sock:
            try:
                if self.mode == "HOST" and self.clients:
                    for _ in range(3):
                        self._host_broadcast({"type": MsgType.HOST_LEFT})
                        time.sleep(0.02)
                elif self.mode == "CLIENT" and self.connected and self.server_addr:
                    for _ in range(2):
                        self.sock.sendto(json.dumps({"type": MsgType.LEAVE}).encode('utf-8'), self.server_addr)
                        time.sleep(0.01)
            except Exception:
                pass
        self.running = False
        if was_host_running:
            self._broadcast_room_closed(host_port)             # 방 목록(방 참가 화면)에서 바로 지워지도록 닫힘을 알림 (안 보내면 비콘이 끊긴 뒤 몇 초간 남음)
        self.probe_results.clear()                             # 이 PC에서 조회해 둔 방 정보도 비움 (닫은 방이 조회 캐시 때문에 남지 않게)
        self.discovered_rooms = {}
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.connected = False
        self.mode = "NONE"
        print("[Network] Stopped.")

    @staticmethod
    def _broadcast_room_closed(port):
        """방 닫힘(BEACON_CLOSED)을 LAN에 몇 번 브로드캐스트. 비콘 스레드가 마지막 비콘을 늦게 보내는 경우까지 덮도록 간격을 두고 여러 번"""
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            data = json.dumps({"type": MsgType.BEACON_CLOSED, "port": port}).encode('utf-8')
            for _ in range(3):
                s.sendto(data, ("<broadcast>", DISCOVERY_BROADCAST_PORT))
                time.sleep(0.05)
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
