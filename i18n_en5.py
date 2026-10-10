"""
영어 번역표 5 (업적 이름·설명, 도전 과제 이름, 규칙 카드, 오늘의 도전/주간 변형 카드). i18n.py가 함께 읽음.
"""

EXACT = {
    "SteamOS(Proton)에서는 전체 화면이면 입력이 막혀 창 모드로 고정됩니다": "On SteamOS (Proton), full screen blocks input, so window mode is used",
    # ---------------------------------------------------------------- 업적 (이름 / 설명)
    "소규모 2~10인": "Small 2-10", "중규모 11~49인": "Medium 11-49", "대규모 50~100인": "Large 50-100",
    "첫 K.O.": "First K.O.", "한 판에서 상대를 1명 처치": "Eliminate 1 opponent in one match",
    "사냥꾼": "Hunter", "한 판에서 5명 처치": "Eliminate 5 in one match",
    "학살자": "Slayer", "한 판에서 10명 처치": "Eliminate 10 in one match",
    "전장의 지배자": "Ruler of the Field", "한 판에서 15명 처치": "Eliminate 15 in one match",
    "TOP 10 진입": "Top 10 Finish", "30인 이상 대전에서 10위 안": "Top 10 in a match of 30+ players",
    "10인 이상 대전에서 우승": "Win a match of 10+ players",
    "백인의 왕": "King of a Hundred", "100인 대전에서 우승": "Win a 100-player match",
    "마라토너": "Marathoner", "한 판에서 7분 이상 생존": "Survive 7+ minutes in one match",
    "철인": "Ironman", "한 판에서 9분 이상 생존": "Survive 9+ minutes in one match",
    "복수의 화신": "Avenger", "나를 자주 탈락시킨 라이벌 봇을 처치": "Defeat the rival bot that kept eliminating you",
    "신입 대원": "Rookie", "배틀로얄 10판 플레이": "Play 10 Battle Royale matches",
    "백전노장": "Veteran", "배틀로얄 100판 플레이": "Play 100 Battle Royale matches",
    "삼연의 왕관": "Triple Crown", "배틀로얄에서 우승 3번": "Win Battle Royale 3 times",
    "챔피언": "Champion", "배틀로얄에서 우승 10번": "Win Battle Royale 10 times",
    "상위권 단골": "Regular Contender", "5위 안에 10번 들기": "Finish in the top 5 ten times",
    "백 명 사냥": "Hundred Hunts", "누적 K.O. 100명": "100 K.O.s total",
    "천 줄의 길": "Road of 1,000", "누적 1,000줄 지우기": "Clear 1,000 lines total",
    "오천 줄의 길": "Road of 5,000", "누적 5,000줄 지우기": "Clear 5,000 lines total",
    "사다리 정복": "Ladder Conqueror", "난이도 사다리 4단계 모두 클리어": "Clear all 4 steps of the difficulty ladder",
    "시간 부자": "Time Rich", "배틀로얄 누적 플레이 10시간": "10 hours of Battle Royale play",
    "꾸준한 도전자": "Steady Challenger", "오늘의 도전을 3일 이상 플레이": "Play the Daily Challenge on 3+ days",
    "사흘 연속": "Three in a Row", "오늘의 도전 별을 3일 연속으로 받기": "Earn a Daily Challenge star 3 days in a row",
    "일주일 개근": "Perfect Week", "오늘의 도전 별을 7일 연속으로 받기": "Earn a Daily Challenge star 7 days in a row",
    "보름 개근": "Perfect Fortnight", "오늘의 도전 별을 14일 연속으로 받기": "Earn a Daily Challenge star 14 days in a row",
    "완벽한 하루": "Perfect Day", "하루에 오늘의 도전 별 3개를 모두 받기": "Earn all 3 Daily Challenge stars in one day",
    "별 수집가": "Star Collector", "오늘의 도전 별(★) 누적 30개": "30 Daily Challenge stars (★) total",
    "별의 지배자": "Star Sovereign", "오늘의 도전 + 주간 변형 별 누적 100개": "100 stars total from Daily + Weekly challenges",
    "변형 정복자": "Variant Conqueror", "주간 변형 규칙 네 가지 이상에서 별 1개 이상": "Earn a star in four or more weekly variants",
    "주간 단골": "Weekly Regular", "주간 변형 별 누적 10개": "10 Weekly Variant stars total",
    "완벽한 한 주": "Perfect Weekly", "한 주에 주간 변형 별 3개를 모두 받기": "Earn all 3 Weekly Variant stars in one week",
    "콤보 장인": "Combo Artisan", "한 판에서 8연속 콤보": "8-chain combo in one match",
    "콤보 전설": "Combo Legend", "한 판에서 12연속 콤보": "12-chain combo in one match",
    "수련생": "Trainee", "수련 완료": "Training complete",
    "T-스핀 마스터": "T-Spin Master", "연습에서 T-스핀 트리플 달성": "Land a T-Spin Triple in Practice",
    "퍼펙트 클리어": "Perfect Clear", "연습에서 퍼펙트 클리어 달성": "Land a Perfect Clear in Practice",
    "압박을 견딘 자": "Pressure Survivor", "압박 드릴에서 3분 버티기": "Last 3 minutes in the pressure drill",
    "스프린터": "Sprinter", "타임어택 쿼드 5번을 60초 안에": "Time Attack: 5 Quads within 60s",
    "타임어택 완주": "Time Attack Finisher",
    "속도광": "Speed Demon", "연습에서 60초 안에 블록 90개 놓기": "Place 90 pieces within 60s in Practice",
    "마스터 입문": "Master Initiate", "마스터 연습 과제 5개 완료": "Complete 5 Master practice tasks",
    "마스터 수료": "Master Graduate",
    "퍼펙트 두 번": "Perfect Twice", "연습에서 퍼펙트 클리어 2회": "2 Perfect Clears in Practice",
    "연속의 달인": "Chain Adept", "연습에서 10연속 콤보": "10-chain combo in Practice",
    "B2B 마스터": "B2B Master", "연습에서 B2B 7연속": "7 B2B in a row in Practice",
    "철벽": "Iron Wall", "압박 드릴에서 5분 버티기": "Last 5 minutes in the pressure drill",
    "질주": "Dash", "타임어택 40줄 스프린트를 90초 안에": "Time Attack: 40-line sprint within 90s",
    "트리플의 지배자": "Triple Overlord", "연습에서 T-스핀 트리플 3번": "3 T-Spin Triples in Practice",
    "수집가": "Collector", "업적 25개 달성": "Earn 25 achievements",
    "명예의 전당": "Hall of Fame", "업적 40개 달성": "Earn 40 achievements",
    "대전": "Battle", "누적": "Totals", "도전": "Challenge", "연습·기술": "Practice·Skill",
    "업적 3개 달성": "Earn 3 achievements", "로열 빅토리(우승) 1회": "1 Royale Victory (win)",
    "도전 과제 별(★) 누적 90개": "90 challenge stars (★) total", "레벨 5 달성": "Reach level 5", "레벨 10 달성": "Reach level 10",
    "참가": "Entry", "생존": "Survival", "명장면": "Highlights", "골든 타깃": "Golden target", "오늘 첫 판": "First game today",
    # ---------------------------------------------------------------- 도전 과제 (설명 / 짧은 이름)
    "기초": "Basic", "중급": "Intermediate", "고급": "Advanced",
    "G로 받은 줄 2줄 상쇄하기": "Cancel 2 received lines with G", "상쇄 2줄": "Cancel 2",
    "줄 10개 지우기": "Clear 10 lines", "10줄 삭제": "10 lines",
    "2줄 한 번에 지우기(더블) 3번": "Clear 2 lines at once (Double) 3 times", "더블 3번": "Double ×3",
    "3줄 한 번에 지우기(트리플)": "Clear 3 lines at once (Triple)", "트리플": "Triple",
    "4줄 한 번에 지우기(쿼드)": "Clear 4 lines at once (Quad)",
    "3연속 콤보 만들기": "Make a 3-chain combo", "콤보 3": "Combo 3",
    "T-스핀으로 줄 지우기": "Clear lines with a T-Spin",
    "줄 40개 지우기": "Clear 40 lines", "40줄 삭제": "40 lines", "쿼드 3번": "Quad ×3",
    "4연속 콤보 만들기": "Make a 4-chain combo", "콤보 4": "Combo 4",
    "Shift+G로 8줄을 받고 한 번에 4줄 이상 막기": "Receive 8 lines with Shift+G and block 4+ at once", "한번에 4막기": "Block 4 at once",
    "압박 드릴(V)에서 60초 버티기": "Last 60s in the pressure drill (V)",
    "B2B 쿼드 (쿼드를 연달아)": "B2B Quad (Quads in a row)", "B2B 쿼드": "B2B Quad",
    "5연속 콤보 만들기": "Make a 5-chain combo", "콤보 5": "Combo 5",
    "T-스핀 3번": "T-Spin ×3",
    "G로 받은 줄 누적 20줄 상쇄하기": "Cancel 20 received lines in total with G", "상쇄 20줄": "Cancel 20",
    "T-스핀 싱글 (1줄)": "T-Spin Single (1 line)", "T-스핀 싱글": "T-Spin Single",
    "미니 T-스핀 1회": "1 Mini T-Spin", "미니 T-스핀": "Mini T-Spin",
    "줄 100개 지우기": "Clear 100 lines", "100줄 삭제": "100 lines", "쿼드 8번": "Quad ×8",
    "T-스핀 더블 (2줄)": "T-Spin Double (2 lines)", "T-스핀 더블": "T-Spin Double",
    "B2B를 3번 이어가기": "Keep B2B going 3 times", "B2B 3연속": "B2B ×3",
    "7연속 콤보 만들기": "Make a 7-chain combo", "콤보 7": "Combo 7",
    "압박 드릴 Lv.5까지 버티기 (2분)": "Last until pressure drill Lv.5 (2 min)", "드릴 Lv.5": "Drill Lv.5",
    "압박 드릴 3분 버티기": "Last 3 minutes in the pressure drill", "드릴 3분": "Drill 3 min",
    "한 번에 8줄 이상 막기": "Block 8+ lines at once", "한번에 8막기": "Block 8 at once",
    "B2B를 5번 이어가기": "Keep B2B going 5 times", "B2B 5연속": "B2B ×5",
    "T-스핀 더블 3번": "T-Spin Double ×3", "T-더블 3번": "T-Dbl ×3",
    "T-스핀 트리플 (3줄)": "T-Spin Triple (3 lines)", "T-스핀 트리플": "T-Spin Triple",
    "퍼펙트 클리어 1회": "1 Perfect Clear",
    "블록 300개 놓기": "Place 300 pieces", "블록 300개": "300 pieces",
    "줄 200개 지우기": "Clear 200 lines", "200줄 삭제": "200 lines",
    "10연속 콤보 만들기": "Make a 10-chain combo", "콤보 10": "Combo 10",
    "G로 받은 줄 누적 50줄 상쇄하기": "Cancel 50 received lines in total with G", "상쇄 50줄": "Cancel 50",
    "T-스핀 더블 5번": "T-Spin Double ×5", "T-더블 5번": "T-Dbl ×5",
    "60초 안에 블록 90개 놓기 (초당 1.5개)": "Place 90 pieces in 60s (1.5/sec)", "블록 90/분": "90 pcs/min",
    "B2B를 7번 이어가기": "Keep B2B going 7 times", "B2B 7연속": "B2B ×7",
    "압박 드릴 5분 버티기": "Last 5 minutes in the pressure drill", "드릴 5분": "Drill 5 min",
    "T-스핀 트리플 3번": "T-Spin Triple ×3", "T-트리플 3번": "T-Tri ×3",
    "퍼펙트 클리어 2회": "2 Perfect Clears", "퍼펙트 2회": "Perfect ×2",
    "쿼드 5번": "Quad ×5", "번": "×",
    "40줄 스프린트": "40-line sprint", "더블 10번": "Double ×10",
    "T-스핀 더블 2번": "T-Spin Double ×2", "콤보 6 만들기": "Make a 6 combo",
    "1분 30초 생존": "Survive 1:30", "생존 1:30": "Survive 1:30",
    "줄 20개 지우기": "Clear 20 lines", "20줄 삭제": "20 lines",
    "받은 공격 2줄 막기": "Block 2 received lines", "K.O. 1명": "1 K.O.",
    "2연속 콤보": "2-chain combo", "콤보 2": "Combo 2", "쿼드 2회": "Quad ×2",
    "5분 생존": "Survive 5:00", "생존 5:00": "Survive 5:00", "K.O. 4명": "4 K.O.s",
    "받은 공격 8줄 막기": "Block 8 received lines", "상쇄 8줄": "Cancel 8",
    "30위 안에 들기": "Finish in the top 30", "30위 안": "Top 30",
    "보낸 줄 30줄": "Send 30 lines", "공격 30줄": "30 sent",
    "20위 안에 들기": "Finish in the top 20", "20위 안": "Top 20",
    "쿼드 4회": "Quad ×4", "K.O. 5명": "5 K.O.s",
    "한 번에 5줄 이상 막기": "Block 5+ lines at once", "한번에 5막기": "Block 5 at once",
    "위기 탈출 1회": "1 clutch escape", "위기 탈출": "Clutch escape",
    "1분 생존 (모두 어려움 봇)": "Survive 1:00 (all Hard bots)", "생존 1:00": "Survive 1:00",
    "어려움 봇 K.O. 1명": "1 K.O. of a Hard bot",
    "30인 중 15위 안 (절반 안)": "Top 15 of 30 (top half)", "15위 안": "Top 15",
    "받은 공격 5줄 막기 (폭격 대비)": "Block 5 received lines (prepare for barrage)", "상쇄 5줄": "Cancel 5",
    "한 번에 4줄 이상 막기": "Block 4+ lines at once",
    "퍼펙트 클리어 1회 (20줄!)": "1 Perfect Clear (20 lines!)",
    "NEXT 1개만 보고 줄 30개 지우기": "Clear 30 lines seeing only 1 NEXT", "30줄 삭제": "30 lines",
    "NEXT 1개만 보고 쿼드 2회": "2 Quads seeing only 1 NEXT",
    "7분 생존": "Survive 7:00", "생존 7:00": "Survive 7:00",
    "증폭 30초": "Boost 30s",
    "공격력 증폭(×1.2↑) 상태로 30초 생존": "Survive 30s with boosted attack (×1.2+)",
    "10위 안에 들기": "Finish in the top 10", "10위 안": "Top 10",
    # ---------------------------------------------------------------- 규칙 카드
    "싱글(1줄)": "Single (1 line)", "더블(2줄)": "Double (2 lines)", "트리플(3줄)": "Triple (3 lines)", "쿼드(4줄)": "Quad (4 lines)",
    "T-스핀 싱글/더블/트리플": "T-Spin Single/Double/Triple", "T-스핀 미니 싱글/더블": "T-Spin Mini Single/Double",
    "연속 콤보": "Chain combo", "6명 이상": "6 or more",
    "공격 줄 수": "Attack lines", "K.O. 열기 (공격력 증폭)": "K.O. Heat (attack boost)", "역습 보너스": "Counter bonus",
    "규칙 요약": "Rules Summary", "아무 키나 클릭으로 닫기  ·  F1": "Press any key or click to close  ·  F1",
    "여럿이 나를 노릴 때 내 공격에 더해집니다": "Added to my attacks when several players target me",
    "조준 모드  (TAB 순환 · 1~5 선택 · 상단 칩 클릭)": "Targeting modes  (TAB cycles · 1-5 select · click the top chips)",
    "아무 키나 눌러 시작   ·   ESC: 메뉴로": "Press any key to start   ·   ESC: Menu",
    "목표 3개를 달성해 별(★)을 모으세요. 여러 번 도전해도 달성한 별은 유지됩니다": "Complete the 3 goals to collect stars (★). Stars you earned are kept across attempts.",
    "오늘의 목표": "Today's Goals", "이번 주 목표": "This Week's Goals",
    " (이번 주 변형)": " (this week's variant)", "  ·  이번 주만의 규칙": "  ·  this week's special rule",
    "● 달성함": "● Done", "도전!": "Go!",
    "오늘 첫 도전입니다 — 기록이 남아 다음 도전에서 비교됩니다": "First try today — your record is saved and compared next time",
    "아직 기록 없음": "No record yet",
}

EXACT.update({
    # (관전 바 안내 문구는 길어지면 미니 보드를 덮으므로 i18n_en2에서 짧게 둠)
    # 대기실/입장 안내, 확인 창 버튼
    "방이 가득 찼습니다.": "The room is full.",
    "이미 경기가 진행 중입니다. 다음 경기를 기다려 주세요.": "A match is already in progress. Please wait for the next one.",
    "게임 버전이 호스트와 달라 입장할 수 없습니다. 같은 버전으로 맞춰 주세요.": "Your game version differs from the host's, so you can't join. Please use the same version.",
    "방 유지": "Keep Room", "방 닫기": "Close Room", "확인": "OK", "게임 진행 중": "Game in progress", "키보드": "Keyboard",
    # 커스텀 규칙 알림 조각
    "커스텀 규칙": "Custom rules", "(기록되지 않음)": "(not recorded)", "낙하 느리게": "Fall: slow", "낙하 기본": "Fall: normal", "낙하 빠르게": "Fall: fast",
    "열기 켬": "Heat on", "열기 끔": "Heat off",
    # 종료/나가기 확인 창
    "게임을 종료할까요?": "Quit the game?", "프로그램을 완전히 종료합니다.": "The program will close completely.",
    "게임에서 나갈까요?": "Leave the game?", "계속 플레이": "Keep Playing",
    "진행 중인 경기는 저장되지 않고 메인 메뉴로 돌아갑니다.": "The match in progress won't be saved and you'll return to the main menu.",
    "방장이 나가면 방이 닫히고 모든 참가자의 게임이 종료됩니다.": "If the host leaves, the room closes and the game ends for everyone.",
    "게임에서 나가면 탈락 처리되고 메인 메뉴로 돌아갑니다.": "If you leave, you're counted as eliminated and return to the main menu.",
    "이번 주 변형 규칙: 매주 규칙 하나가 바뀐 경기를 같은 블록 순서·같은 상대로 겨룹니다. (소수 정예 / 퍼펙트 폭격 / 안개 속 / 후반 가속 순환)": "Weekly variant: each week one rule changes, and everyone plays the same piece order against the same opponents. (rotates: Elite Few / Perfect Barrage / In the Fog / Late Rush)",
    "1줄": "1 line", "+1줄": "+1 line",
    "조준 모드": "Targeting", "경기 흐름": "Match Flow", "TAB 순환  ·  1~5 선택  ·  상단 칩 클릭": "TAB cycles  ·  1-5 select  ·  click the top chips",
    "사람 우선, 없으면 탈락 직전인 상대": "Humans first, else whoever is closest to elimination",
    "쌓인 블록 + 받을 공격이 가장 큰 상대": "Biggest stack + incoming garbage",
    "나를 노리는 상대에게 (여럿이면 동시에)": "Whoever targets you (all at once if several)",
    "K.O.를 가장 많이 쌓은 상대": "Player with the most K.O.s",
    "무작위 1명을 노리고 계속 유지": "One random survivor, kept while alive",
    "도전 시작": "Start Challenge",
    "건너뛰기": "Skip", "LAN 멀티: 상대도 같은 버전 필요": "LAN: others need the same version",
    "견습": "Apprentice", "숙련자": "Adept", "베테랑": "Veteran", "전략가": "Strategist", "명인": "Master", "전설": "Legend", "블록 로열": "Block Royale",
    "배틀로얄 · 커스텀": "Battle Royale · Custom", "서바이벌 · 커스텀": "Survival · Custom",
    "연결이 오래 끊겨 봇이 대신 플레이했습니다": "Disconnected too long; a bot played in your place",
    "15초 넘게 호스트와 연결이 끊겨 호스트가 내 자리를 봇에게 넘겼습니다.": "You were disconnected from the host for over 15 seconds, so the host handed your seat to a bot.",
    "고스트 레이스": "Ghost Race", "끝": "End",
    "켜면 혼자 하는 경기에서 저장된 내 리플레이 중 점수가 가장 높은 판의 보드가 왼쪽 상태 칸 아래에 작게 함께 달립니다. 같은 경기 시각의 그 판 점수와의 차이도 보여 줍니다. 리플레이가 없으면 아무것도 표시되지 않습니다.": "When on, in solo matches the board of your highest-scoring saved replay runs in a small panel under the left status box, with the score difference at the same match time. Nothing shows if you have no replays.",
    "내 최고 판이 경기 옆에 함께 달립니다 (아직 저장된 리플레이 없음)": "Your best run races alongside the match (no saved replays yet)",
    "경기 규칙": "Match rules", "팀전": "Team battle", "켜짐 · 같은 편은 공격 안 함": "On · allies don't attack", "꺼짐": "Off",
    "명단을 불러오는 중...": "Loading the roster...",
    "이 순간에서 연습": "Practice from here", "리플레이의 그 순간에서 연습을 시작합니다": "Starting practice from that moment of the replay",
    "주소를 입력하거나, LAN의 방을 찾는 중": "Type an address, or searching for LAN rooms",
    "방장이 게임을 시작하면 자동으로 시작됩니다": "The game starts automatically when the host starts it",
    "채팅": "Chat", "Tab / 클릭: 입력  ·  Enter: 전송": "Tab / click: type  ·  Enter: send", "내 이름": "My name",
    "아직 메시지가 없습니다. 인사를 건네 보세요!": "No messages yet. Say hello!", "메시지를 입력하세요": "Type a message", "여기를 클릭하거나 Tab": "Click here or press Tab",
    "대기실  ·  호스트": "Lobby  ·  Host", "대기실  ·  참가자": "Lobby  ·  Guest", "방 참가": "Join Room",
    "화면의 글이 모두 바뀝니다 (저장된 데이터 속 이름 등 일부는 그대로)": "The whole UI switches language (saved names stay as is)",
    "  잠긴 스킨: ": "  Locked skins: ",
    "업적 3개 달성": "Earn 3 achievements",
    "픽셀": "Pixel", "유리": "Glass", "별빛": "Starlight", "불씨": "Ember", "프리즘": "Prism",
    # 팀전 / 커스텀 규칙
    "팀 승리!": "Team Victory!", "팀 패배": "Team Defeat", "우리 팀이 끝까지 살아남았습니다": "Your team survived to the end",
    " · 상대 팀 승리": " · The other team won", "★ 내 팀 승리! ★": "★ My team wins! ★", "상대 팀 승리": "The other team wins",
    "★ 팀 승리! 우리 팀이 끝까지 살아남았습니다 ★": "★ Team victory! Your team survived to the end ★", "상대 팀이 승리했습니다": "The other team won",
    "팀전 (2팀)": "Team Battle", "같은 편은 공격하지 않고 상대 팀을 모두 탈락시키면 승리": "Allies don't attack each other; eliminate the other team to win",
    "팀전(2팀): 나와 같은 편 봇 절반은 서로 공격하지 않고, 상대 팀을 모두 탈락시키면 이깁니다. 같은 편은 초록 테두리로 표시됩니다. 혼자 하는 배틀로얄에서만 적용되고 기록되지 않습니다(4명 이상).": "Team Battle (2 teams): half the bots are on your side and never attack you or each other; eliminate the other team to win. Allies have a green border. Applies to solo Battle Royale only (4+ players) and isn't recorded.",
    "소수 정예": "Elite Few", "30인 · 모두 어려움 봇": "30 players · all Hard bots",
    "퍼펙트 폭격": "Perfect Barrage", "퍼펙트 클리어 공격 2배 (20줄)": "Perfect Clear attacks doubled (20 lines)",
    "안개 속": "In the Fog", "NEXT 블록이 1개만 보임": "Only 1 NEXT piece is visible",
    "후반 가속": "Late Rush", "공격력 증폭이 2분부터 시작": "Attack boost starts at 2:00",
    "이번 주 변형": "This week's variant",
    "1  대전": "1  Battle", "2  누적": "2  Totals", "3  도전": "3  Challenge", "4  연습·기술": "4  Practice·Skill", "5  마스터": "5  Master",
})

TEMPLATES = {
    "쓰레기 {}": "Garbage {}",
    "{#}초 이상 호스트에게서 응답이 없습니다.": "No response from the host for over {} seconds.",
    "나머지 {#}명": "{} more",
    "{} 님이 입장했습니다": "{} joined", "{} 님이 나갔습니다": "{} left",
    "{} 님이 이름을 {}(으)로 바꿨습니다": "{} changed their name to {}",
    "{} 님의 연결이 끊겨 봇이 대신 플레이합니다": "{}'s connection dropped; a bot is playing in their place",
    "방 제목   {}": "Room name   {}",
    "드릴 종료: {#}초 버팀  ·  막은 줄 {#}  ★ 최고 기록!": "Drill over: survived {}s  ·  blocked {} lines  ★ Best record!",
    "드릴 종료: {#}초 버팀  ·  막은 줄 {#}  (최고 {#}초)": "Drill over: survived {}s  ·  blocked {} lines  (best {}s)",
    "{#}/{#}번": "{}/{} times",
    "소수 정예 ★{#}/{#}": "Elite Few ★{}/{}", "퍼펙트 폭격 ★{#}/{#}": "Perfect Barrage ★{}/{}", "안개 속 ★{#}/{#}": "In the Fog ★{}/{}", "후반 가속 ★{#}/{#}": "Late Rush ★{}/{}",
    "{}   ·   최종 {#}위 / {#}명   ·   K.O. {#}": "{}   ·   Final #{} / {} players   ·   K.O. {}",
    "받은 공격은 {}초 차징 뒤에 올라옵니다. 그 사이에 줄을 지우면 먼저 깎입니다. (한 번에 최대 {}줄)": "Received attacks rise after a {}s charge. Clearing lines in between cancels them first. (max {} lines at once)",
    "경기 시작 {}분부터 매분 공격력 +{}% (최대 ×{}). 생존자가 절반이 되면 PHASE 2, 더 줄면 FINAL.": "From minute {} of the match, attack +{}% every minute (max ×{}). PHASE 2 at half the field, FINAL below that.",
    "처음이라면  {} 1) 연습 기초 과제 3개 ({#}/3)   {} 2) 첫 경기 끝까지 해 보기": "New here?  {} 1) 3 basic practice tasks ({}/3)   {} 2) play your first match to the end",
    " 칭호 '{}'": " title '{}'",
    "내 최고 판({}점)이 경기 옆에 함께 달립니다 (혼자 하는 경기)": "Your best run ({} pts) races alongside the match (solo matches)",
    "{#}인": "{} players",
    "♥ 아군 위기!  {}": "♥ Ally in danger!  {}",
    "받을 공격 {#}줄": "Incoming {} lines",
    "{}의 방": "{}'s room",
    "팀전 · 내 팀 {#}명 vs 상대 팀 {#}명 (같은 편은 공격하지 않아요)": "Team battle · my team {} vs other team {} (allies don't attack each other)",
    " · 우리 팀 {#}명 / 상대 팀 {#}명 생존 (끝까지 지켜보세요)": " · Your team {} / other team {} alive (watch it through)",
    "주간 변형  ·  {}": "Weekly Variant  ·  {}", "{}  ·  이번 주만의 규칙": "{}  ·  this week's special rule",
    "바뀐 규칙:  {}": "Changed rule:  {}",
    "{#}월 {#}일  ·  100인 혼합 난이도  ·  모두에게 같은 블록 순서": "{}/{}  ·  100 players, mixed difficulty  ·  same piece order for everyone",
    "이번 주 최고 순위: #{#}위   ·   별 {#}/3": "This week's best rank: #{}   ·   Stars {}/3",
    "이번 주 최고 순위: 아직 기록 없음   ·   별 {#}/3": "This week's best rank: none yet   ·   Stars {}/3",
    "지난 최고: {#}위 · {} 생존   ·   {#}번째 도전": "Past best: #{} · survived {}   ·   try #{}",
    "연속 출석 {#}일 (최고 {#}일)   ·   별 하나만 따도 출석으로 인정": "Streak {} days (best {})   ·   one star counts as attendance",
    "이번 주 변형({}) 최고 #{#}위": "This week's variant ({}) best #{}",
    "진행 {#} / {#}분": "Progress {} / {} min",
    "연습 과제 {#}개 완료": "Complete {} practice tasks", "연습 과제 {#}개를 모두 완료": "Complete all {} practice tasks",
    "타임어택 {#}종 모두 기록 남기기": "Set a record in all {} Time Attack types",
    "마스터 연습 과제 {#}개를 모두 완료": "Complete all {} Master practice tasks",
    "마스터 연습 과제 {#}개 완료": "Complete {} Master practice tasks",
    "{#}줄": "{} lines", "+{#}줄": "+{} lines", "+{#}~{#}줄": "+{}-{} lines",
    "{#} / {#}줄": "{} / {} lines", "{#} / {#} / {#}줄": "{} / {} / {} lines",
    "K.O. {#}개": "{} K.O.s", "공격력 +{#}%": "Attack +{}%",
    "{#}명이 나를 노림": "{} target me",
    "• 받은 공격은 {}초 차징 뒤에 올라옵니다. 그 사이에 줄을 지우면 먼저 깎입니다. (한 번에 최대 {}줄)": "• Received attacks rise after a {}s charge. Clearing lines in between cancels them first. (max {} lines at once)",
    "• 경기 시작 {}분부터 매분 공격력 +{}% (최대 ×{}). 생존자가 절반이 되면 PHASE 2, 더 줄면 FINAL.": "• From minute {} of the match, attack +{}% every minute (max ×{}). PHASE 2 at half the field, FINAL below that.",
}

# 연습 과제 목록 줄: "· 이름"(다음 과제) / "이름 -"(타임어택 기록 없음) 형태로 붙는 짧은 이름들
for _k, _v in list(EXACT.items()):
    if len(_k) <= 16 and not _k.startswith(("· ", "1  ", "2  ", "3  ", "4  ", "5  ")):
        EXACT.setdefault("· " + _k, "· " + _v)
        EXACT.setdefault(_k + " -", _v + " -")
EXACT["쓰레기 · 초기화 · 압박 드릴"] = "Garbage · Reset · Pressure drill"
TEMPLATES.update({
    "기초 {#}/{#}": "Basic {}/{}", "중급 {#}/{#}": "Mid {}/{}", "고급 {#}/{#}": "Adv {}/{}", "마스터 {#}/{#}": "Master {}/{}",
})

# BUG_REPORT.md(2026-10-07)에서 확인된 영어 미번역: 반응 프리셋, 스테이지 음악 세트 0, 클리어 문구, 연결 끊김 알림, 보상 줄, 시스템 채팅 이름, 키 교체 안내
EXACT.update({
    "느긋": "Relaxed", "빠름": "Fast", "프로": "Pro",
    "Cyber Rush (오리지널)": "Cyber Rush (Original)",
    "오리지널 3부작: Cyber Rush → Hyperdrive Override → Apex Protocol": "Original trilogy: Cyber Rush → Hyperdrive Override → Apex Protocol",
    "모든 난이도 클리어": "All difficulties cleared",
    "(사람)": "(human)", "시스템": "System",
})
TEMPLATES.update({
    "드릴 {#}초": "Drill {}s",
    "{} 클리어! 모든 난이도 클리어": "{} cleared! All difficulties cleared",
    "★ B2B x{#} 쿼드! ★": "★ B2B x{} Quad! ★",
    "{} 연결 끊김 · 봇이 대신 플레이": "{} disconnected · a bot takes over",
    "★ 새 스킨 해금!  {}": "★ New skin unlocked!  {}",
    "★ 레벨 업! 칭호 '{}'": "★ Level up! Title '{}'",
    "레벨 업! 칭호 '{}'": "Level up! Title '{}'",
    "업적 달성!  {} 외 {#}개": "Achievement unlocked!  {} +{} more",
    "★ 업적 달성!  {} 외 {#}개": "★ Achievement unlocked!  {} +{} more",
})

# 지형 윤곽선 설정
EXACT.update({
    "지형 윤곽선": "Stack outline",
    "쌓인 블록 윗면을 따라 밝은 선을 그림 (메인 보드)": "Bright line along the top of the stack (main board)",
    "켜면 메인 보드에 쌓인 블록의 윗면을 따라 밝은 선이 이어져 지형의 높낮이와 구멍 위치가 한눈에 보입니다. 기본은 꺼짐이며, 줄이 내려앉는 순간에는 잠시 숨습니다.":
        "Draws a bright line along the top of your stack on the main board so heights and holes read at a glance. Off by default; it hides briefly while rows are settling.",
})

EXACT.update({"입력한 주소를 찾을 수 없습니다. 주소를 다시 확인해 주세요.": "Could not find that address. Please check it and try again."})

# v1.4.27: 메인 메뉴 작은 카드, 다음 난이도 도전, K.O. 열기 흡수
EXACT.update({"다음 난이도 도전": "Next difficulty", "오늘 아직 안 함": "Not played today", "이번 주 아직 안 함": "Not played this week"})
TEMPLATES.update({
    "완료한 과제 {#}개": "{} tasks done",
    "★{#}/3 · 최고 {#}위": "★{}/3 · best #{}",
    "이번 주 최고 {#}위": "Best this week: #{}",
    "[K.O. 처치!] +{#} 열기 획득 >> {}": "[K.O.!] +{} heat >> {}",
    "[K.O. 처치!] +{#} 열기 획득 >> {}  (상대 열기 {#} 흡수)": "[K.O.!] +{} heat >> {}  (absorbed {} from the victim)",
})

# v1.4.27 메인 화면 단순화 (목록 + 설명 패널)
EXACT.update({"바로 실행": "Run now", "프로필": "Profile"})
TEMPLATES.update({"★ 다음 도전: {} 봇 {#}인↑에서 {#}위 안": "★ Next goal: top {2} vs {0} bots in {1}+ players"})

# v1.4.27 메인 화면 카테고리 (함께하기 / 혼자하기) + 한 줄 설명
EXACT.update({
    "함께하기": "Multiplayer", "혼자하기": "Solo",
    "봇과 바로 대전합니다": "Jump into a match against bots",
    "방을 열고 친구를 초대합니다. 빈 자리는 봇이 채웁니다": "Open a room and invite friends. Bots fill empty seats",
    "LAN에서 방을 찾거나 IP로 직접 접속합니다": "Find a room on your LAN or connect by IP",
    "혼자 자유롭게 연습합니다. 전적에는 남지 않아요": "Practice freely on your own. Not saved to your records",
    "하루 한 번, 모두 같은 블록 순서로 순위를 겨룹니다": "Once a day, everyone gets the same pieces. Compete for rank",
    "매주 규칙 하나가 바뀐 경기로 겨룹니다": "Compete with one rule changed each week",
    "이름 · 인원 · 봇 난이도 설정": "Name · players · bot difficulty",
})
EXACT.update({"전적에 남지 않음": "Not recorded"})

# v1.4.27 규칙 카드: B2B 보너스 단계와 열기 흡수
EXACT.update({"B2B (연쇄 1~3/4~7/8~)": "B2B (chain 1-3 / 4-7 / 8+)", "+1 / +2 / +3줄": "+1 / +2 / +3 lines",
              "처치 시 상대 열기 흡수": "Take victim's heat", })
TEMPLATES.update({"K.O.의 절반 (최대 {#})": "Half their KOs (max {})"})

# v1.4.31 골든 타깃 순환
EXACT.update({"★ 골든 타깃이 바뀌었어요! 금빛 $ 카드를 노리세요 ★": "★ The golden target changed! Go for the gold $ card ★"})

EXACT.update({"← → 인원  ·  D 난이도  ·  클릭/휠도 가능": "← → players  ·  D difficulty  ·  click/wheel also work", "← → 인원": "← → players"})

TEMPLATES.update({"평소 대비 생존 ▲ {#}초": "Survived ▲ {}s vs. your usual", "평소 대비 생존 ▼ {#}초": "Survived ▼ {}s vs. your usual"})

TEMPLATES.update({"스크린샷 저장: {}": "Screenshot saved: {}"})
EXACT.update({"스크린샷을 저장하지 못했어요": "Could not save the screenshot"})

EXACT.update({"화면 번쩍임": "Screen flash", "큰 순간에 보드가 하얗게 번쩍임 (화면 흔들림과 따로 끌 수 있음)": "White flash on big moments (separate from shake)",
              "큰 순간(쿼드, 퍼펙트 클리어, K.O. 등)에 보드가 하얗게 번쩍이는 효과입니다. 화면 흔들림 설정과 따로 끌 수 있어서, 흔들림은 켜 두고 번쩍임만 끌 수도 있습니다.": "A white flash on the board during big moments (quad, perfect clear, K.O., etc.). It can be turned off separately from screen shake, so you can keep the shake and disable only the flash."})

EXACT.update({"▲ 받을 공격": "▲ Incoming"})

# v1.4.31 입문 미션
EXACT.update({"첫 경기를 끝까지 해 보기": "Play your first match to the end", "첫 K.O. 처치하기": "Score your first K.O.",
              "Tab이나 1~5 키로 조준 모드 바꿔 보기": "Switch the aim mode with Tab or 1-5",
              "연습 모드에서 G 키로 쓰레기를 받아 막아 보기": "In Practice, press G to take garbage and block it",
              "50인 이상 경기에서 10위 안에 들기": "Finish in the top 10 of a 50+ player match"})
TEMPLATES.update({"입문 미션 {#}/{#} · {}": "Starter mission {}/{} · {}", "★ 입문 미션 완료 · {}": "★ Starter mission complete · {}",
                  "★ 입문 미션 완료! {} (+{#} XP)": "★ Starter mission complete! {} (+{} XP)"})

EXACT.update({"V  마지막 8초 보기": "V  Watch last 8s", "LB  마지막 8초 보기": "LB  Watch last 8s", "마지막 8초": "Last 8 seconds", "V 닫기": "V close", "LB 닫기": "LB close"})

EXACT.update({"우승 예측": "Winner pick"})
TEMPLATES.update({"우승 예측: {}": "Winner pick: {}"})

TEMPLATES.update({"우승 예측 적중!  {}  +{#} XP": "Winner pick hit!  {}  +{} XP"})

# v1.4.31 짧아진 전투 토스트
TEMPLATES.update({"◀ +{#}  {}": "◀ +{}  {}", "◀ +{#}  ({#}명)": "◀ +{}  ({} players)",
                  "▶ +{#}  {}": "▶ +{}  {}", "▶▶ +{#}  {}": "▶▶ +{}  {}",
                  "열기{#}": "Heat {}", "역습+{#}": "Counter +{}"})

TEMPLATES.update({"★ 새 효과 해금!  {}": "★ New effect unlocked!  {}"})
EXACT.update({"K.O. 구슬이 하늘색으로 바뀝니다": "K.O. orbs turn sky blue", "K.O. 구슬이 분홍색으로 바뀝니다": "K.O. orbs turn pink", "K.O. 구슬이 무지개색으로 바뀝니다": "K.O. orbs turn rainbow"})

# v1.4.31 주간 변형 3종 추가 (무거운 전장 / 빠른 낙하 / 홀드 금지)
EXACT.update({"무거운 전장": "Heavy Front", "쓰레기 줄이 1.5배": "Garbage lines ×1.5", "빠른 낙하": "Fast Fall", "블록이 더 빨리 떨어짐": "Pieces fall faster",
              "홀드 금지": "No Hold", "홀드를 쓸 수 없음": "Hold is disabled",
              "받은 공격 8줄 막기 (무거운 전장)": "Block 8 incoming lines (Heavy Front)", "상쇄 8줄": "Block 8", "K.O. 3명": "Score 3 K.O.s", "K.O. 3": "K.O. 3",
              "빠른 낙하 속에서 줄 40개 지우기": "Clear 40 lines while pieces fall fast", "40줄 삭제": "40 lines", "5분 생존": "Survive 5 minutes", "생존 5:00": "Survive 5:00",
              "홀드 없이 줄 30개 지우기": "Clear 30 lines without hold", "홀드 없이 쿼드 1회": "One quad without hold", "쿼드 1회": "1 quad", "15위 안에 들기": "Finish in the top 15"})

TEMPLATES.update({"{#}점": "{} pts"})

# v1.4.33 게임 효과 개선 (패드 진동 설정, 미니 T-스핀, B2B 끊김, 공격 누적)
EXACT.update({"패드 진동": "Controller rumble",
              "쿼드/피격/K.O./하드 드롭 진동 (화면 흔들림과 따로 조절)": "Quad/hit/K.O./hard-drop rumble (separate from screen shake)",
              "쿼드/피격/K.O. 때 화면이 흔들림 (패드 진동은 따로)": "Screen shakes on quads/hits/K.O.s (rumble is separate)",
              "패드를 쓸 때 쿼드·피격·K.O.·하드 드롭에서 패드가 울리는 세기입니다. 화면 흔들림 설정과 따로 정할 수 있습니다.": "How strongly the controller rumbles on quads, hits, K.O.s and hard drops. Set separately from screen shake.",
              "T-스핀 미니": "T-Spin Mini", "T-스핀 미니 싱글": "T-Spin Mini Single", "T-스핀 미니 더블": "T-Spin Mini Double"})
TEMPLATES.update({"B2B ×{#} 끝": "B2B ×{} ended", "▶ {#}줄": "▶ {} lines"})

# v1.4.34 화상 키보드 (SteamOS/Proton)
EXACT.update({"지우기": "Delete", "공백": "Space", "취소": "Cancel", "완료": "Done", "한글": "KR", "채팅": "Chat", "플레이어 이름": "Player name", "이니셜": "Initials", "호스트 주소": "Host address", "화상 키보드": "On-screen keyboard",
              "화상 키보드 (Y)": "On-screen keyboard (Y)",
              "십자키 이동  ·  A 입력  ·  X 지우기  ·  Y 대문자  ·  LB 한/영  ·  RB 기호  ·  Back 완료  ·  B 취소": "D-pad move  ·  A type  ·  X delete  ·  Y shift  ·  LB language  ·  RB symbols  ·  Back done  ·  B cancel",
              "터치/클릭으로 입력  ·  다 쓰면 '완료'를 누르세요  ·  물리 키보드로 치면 이 키보드는 닫힙니다": "Tap or click to type  ·  press Done when finished  ·  typing on a physical keyboard closes this one"})

# v1.4.34 메인 화면 Start 버튼 = 설정
EXACT.update({"설정 (Start)": "Settings (Start)"})

# v1.4.36 패드 분리
EXACT.update({"패드 연결이 끊겨 일시정지했습니다": "Controller disconnected - paused"})

# v1.4.37 빛 연출
EXACT.update({"빛 연출": "Light effects", "최소": "Minimal", "화려하게": "Fancy",
              "줄 삭제·하드 드롭의 빛 번짐, 배경과 우승 연출 (최소 = 예전 화면)": "Glow on line clears and hard drops, backgrounds and victory scenes (Minimal = old look)",
              "줄 삭제·하드 드롭의 빛 번짐, 단계별 배경, 우승 연출의 화려함입니다. 화면이 느려지면 '최소'로 두세요 (최소 = 예전과 같은 화면). 화면 흔들림/번쩍임 설정도 따릅니다.": "How flashy the glow on line clears and hard drops, the stage backgrounds and the victory scene are. Choose Minimal if the game runs slowly (Minimal = the old look). Screen shake and flash settings are respected."})

# v1.4.38 빛 연출 설명 갱신
EXACT.update({"빛 번짐·불씨·우승 연출, 화려하게는 음악에 맞춘 배경 맥동까지": "Glow, embers and victory scenes; Fancy adds background pulsing to the music",
              "빛 연출의 정도입니다. 최소 = 빛 번짐·불씨·박자 연출 없이 정지된 배경 장식만, 보통 = 빛 번짐과 불씨(배경은 번쩍이지 않음), 화려하게 = 음악에 맞춘 배경 맥동까지. 화면이 느려지면 '최소'로 두세요. 화면 흔들림/번쩍임 설정도 따릅니다.": "How strong the light effects are. Minimal = no glow, embers or beat effects, only still background decoration; Normal = glow and embers (the background does not flash); Fancy = also pulses the background to the music. Choose Minimal if the game runs slowly. Screen shake and flash settings are respected."})

# v1.4.38 빛 연출 설명이 영어에서 오른쪽 버튼과 겹치지 않게 짧게
EXACT.update({"빛 번짐·불씨·우승 연출 (화려하게: 음악 맥동)": "Glow, embers, victory scenes (Fancy: beat pulse)"})

# v1.4.40 진단 정보 복사 / 빛 연출 상태 안내
EXACT.update({"진단 정보 복사": "Copy diagnostics", "복사했습니다": "Copied", "error.log 폴더": "error.log folder",
              "움직임 멈춤: 화면 흔들림이 꺼져 있음": "Motion paused: screen shake is off", "밝기 낮춤: 화면 번쩍임이 꺼져 있음": "Dimmed: screen flash is off"})

# v1.4.42 레벨 보상: 보드 테두리 장식 / 조준 모드 이름
EXACT.update({"내 보드에 은빛 테두리 장식이 붙습니다": "Your board gets a silver border trim",
              "내 보드 테두리 장식이 청록빛으로 바뀝니다": "Your board border trim turns teal",
              "내 보드 테두리 장식이 자수정빛 이중 테두리로 바뀝니다": "Your board border trim becomes a double amethyst frame",
              "내 보드 테두리 장식이 황금 이중 테두리로 바뀝니다": "Your board border trim becomes a double gold frame"})

# v1.4.42 주시 대상 칸
EXACT.update({"주시 대상": "Watch list", "위협": "Threat", "표적": "Target"})

# 경기 중 팁 문구("TIP  " + 안내문)가 영어에서 한글로 남던 것
TEMPLATES.update({"TIP  {}": "TIP  {}"})

# v1.4.49 왕관석 스킨
EXACT.update({"왕관석": "Crownstone", "모서리를 깎은 돌에 왕관 문양을 새긴 고유 블록": "Chamfered stone blocks engraved with a crown"})
