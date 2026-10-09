"""
Block Royale 100 - 화상 키보드(OSK)의 글자판과 한글 조합기 (화면 없이 계산만: 테스트하기 쉽게 분리)
SteamOS(Proton)에서는 Steam 오버레이가 켜져 있으면 입력칸을 눌러도 Steam 키보드가 뜨지 않으므로, 게임이 직접 키보드를 그린다.
"""

# ---------------------------------------------------------------- 글자판
# 한 줄 = 키 목록. 키는 (보통 글자, Shift 글자) 또는 특수 키 이름("BACK", "SHIFT", "LANG", "SYM", "SPACE", "DONE", "CANCEL")
_DIGITS = [(c, c) for c in "1234567890"]
_EN = [[(c, c.upper()) for c in "qwertyuiop"], [(c, c.upper()) for c in "asdfghjkl"], [(c, c.upper()) for c in "zxcvbnm"]]
_KO = [[("ㅂ", "ㅃ"), ("ㅈ", "ㅉ"), ("ㄷ", "ㄸ"), ("ㄱ", "ㄲ"), ("ㅅ", "ㅆ"), ("ㅛ", "ㅛ"), ("ㅕ", "ㅕ"), ("ㅑ", "ㅑ"), ("ㅐ", "ㅒ"), ("ㅔ", "ㅖ")],
       [(c, c) for c in "ㅁㄴㅇㄹㅎㅗㅓㅏㅣ"],
       [(c, c) for c in "ㅋㅌㅊㅍㅠㅜㅡ"]]
_SYM = [[(c, c) for c in "!@#$%^&*()"], [(c, c) for c in "-_=+[]{};:"], [(c, c) for c in "'\",.<>/?~"]]


def layout(page):
    """page: 'en' | 'ko' | 'sym' -> 5줄의 키 목록 (맨 아래 줄은 기능 키)"""
    rows = _EN if page == "en" else (_KO if page == "ko" else _SYM)
    r0 = [k for k in _DIGITS] + ["BACK"]
    r1 = list(rows[0])
    r2 = list(rows[1])
    r3 = ["SHIFT"] + list(rows[2]) + ([(",", ","), (".", ".")] if page != "sym" else [])
    r4 = ["LANG", "SYM", "SPACE", "CANCEL", "DONE"]
    return [r0, r1, r2, r3, r4]


# ---------------------------------------------------------------- 한글 조합 (두벌식)
CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
VOWELS = set(JUNG)
_JUNG_COMBINE = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ", ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ", ("ㅡ", "ㅣ"): "ㅢ"}
_JONG_COMBINE = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
                 ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ"}
_JONG_SPLIT = {v: k for k, v in _JONG_COMBINE.items()}


def _syllable(cho, jung, jong):
    """초성/중성/종성 글자로 한 글자를 만듦 (없으면 낱자). 초성이 없는 종성은 쓰지 않음"""
    if cho and jung:
        return chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28 + JONG.index(jong or ""))
    return cho or jung or ""


class HangulComposer:
    """두벌식 자모를 하나씩 받아 글자를 조합. feed()는 (지울 글자 수, 넣을 글자)를 돌려줌:
    입력칸 끝의 조합 중이던 글자를 지우고 새로 만든 글자(들)를 넣으면 됨"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.cho = self.jung = self.jong = ""
        self._hist = []                                       # 지우기용: 직전 상태들

    def snapshot(self):
        return (self.cho, self.jung, self.jong, list(self._hist))

    def restore(self, snap):
        self.cho, self.jung, self.jong, hist = snap
        self._hist = list(hist)

    def composing(self):
        return bool(self.cho or self.jung)

    def render(self):
        return _syllable(self.cho, self.jung, self.jong)

    def _state(self):
        return (self.cho, self.jung, self.jong)

    def feed(self, j):
        old = self.render()
        self._hist.append(self._state())
        done = ""
        if j in VOWELS:
            if self.jong:
                if self.jong in _JONG_SPLIT:                  # 겹받침은 앞 자음만 남기고 뒤 자음이 다음 글자의 초성으로
                    keep, move = _JONG_SPLIT[self.jong]
                else:
                    keep, move = "", self.jong
                done = _syllable(self.cho, self.jung, keep)
                self.cho, self.jung, self.jong = move, j, ""
            elif self.jung and (self.jung, j) in _JUNG_COMBINE:
                self.jung = _JUNG_COMBINE[(self.jung, j)]
            elif self.jung:                                   # 모음 다음 또 모음(합칠 수 없음): 앞 글자를 끝내고 모음만 새로
                done = self.render()
                self.cho, self.jung, self.jong = "", j, ""
            else:
                self.jung = j                                 # 초성 뒤 모음 / 모음만
        else:
            if not self.cho and not self.jung:
                self.cho = j
            elif not self.jung:                               # 자음 다음 자음: 앞 자음은 낱자로 끝냄
                done = self.cho
                self.cho = j
            elif not self.jong:
                if self.cho and j in JONG and j not in "ㄸㅃㅉ":
                    self.jong = j
                else:
                    done = self.render()
                    self.cho, self.jung, self.jong = j, "", ""
            else:
                comb = _JONG_COMBINE.get((self.jong, j))
                if comb:
                    self.jong = comb
                else:
                    done = self.render()
                    self.cho, self.jung, self.jong = j, "", ""
        if done:                                              # 앞 글자는 확정됨: 지우기는 새로 시작한 글자 안에서만 되돌림
            self._hist = [(self.cho, "", "")] if (self.cho and self.jung) else [("", "", "")]
        return (1 if old else 0), done + self.render()

    def backspace(self):
        """조합 중인 글자의 마지막 자모를 하나 지움. (지울 글자 수, 다시 넣을 글자). 조합 중이 아니면 None"""
        if not self.composing():
            return None
        old = self.render()
        if self._hist:
            self.cho, self.jung, self.jong = self._hist.pop()
        else:
            self.reset()
        return (1 if old else 0), self.render()
