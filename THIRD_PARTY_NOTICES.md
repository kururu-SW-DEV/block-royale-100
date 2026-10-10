# 서드파티 라이선스 고지 (Third-Party Notices)

BLOCK ROYALE 100은 아래 오픈소스 소프트웨어를 사용합니다. 각 소프트웨어의 저작권과 라이선스는 해당 프로젝트에 있습니다.
(정확한 최신 조건은 각 프로젝트의 공식 라이선스 문서를 확인하세요.)

| 구성요소 | 용도 | 라이선스 |
|---|---|---|
| [pygame-ce](https://pyga.me/) | 그래픽, 입력, 오디오 | GNU LGPL v2.1 |
| [SDL2](https://libsdl.org/) (pygame-ce에 포함) | 저수준 미디어 계층 | zlib License |
| [NumPy](https://numpy.org/) | 사운드 합성 | BSD 3-Clause |
| [Python](https://www.python.org/) | 실행 환경 | PSF License |

## LGPL(pygame-ce) 관련 안내
- 이 프로젝트는 pygame-ce를 수정하지 않고 `import`하여 사용합니다.
- 실행 파일(exe 등)로 묶어 배포할 경우: pygame-ce의 LGPL 전문과 저작권 고지를 함께 제공하고, 사용자가 pygame-ce를 다른 버전으로 교체해 실행할 수 있어야 합니다
  (예: PyInstaller의 폴더(one-dir) 방식 사용, 라이브러리 원본 소스 제공 위치 안내).

## 포함되지 않은 자산
- **글꼴**: 게임은 OS에 설치된 글꼴(Windows의 "맑은 고딕" 등)을 불러 쓰며 글꼴 파일을 포함하지 않습니다. 글꼴 파일을 함께 배포하려면 해당 글꼴의 라이선스를 확인하세요.
- **사운드/음악**: 외부 음원 파일 없이 `sound_fx.py`가 코드로 합성합니다.
- **아이콘**(`icon.png`, `icon.ico`): `make_icon.py`가 코드로 직접 그린 자체 제작물입니다(외부 이미지 미사용). 다시 만들려면 `python make_icon.py`를 실행하세요.

## Nanum Gothic (나눔고딕) — 선택 동봉 글꼴
- SteamOS/Proton처럼 OS에 한글 글꼴이 없을 때만 대체 글꼴로 쓰입니다 (`assets/fonts/`, 파일이 있을 때). OS 글꼴이 있으면 쓰이지 않습니다.
- 저작권: NHN Corporation / NAVER (정확한 저작권 표시와 예약 글꼴 이름은 글꼴과 함께 받은 `OFL.txt`의 내용을 그대로 따릅니다)
- 라이선스: SIL Open Font License, Version 1.1 — https://scripts.sil.org/OFL (전문은 `assets/fonts/OFL.txt`)
- 수정 없이 그대로 동봉하며, 글꼴 파일만 따로 판매하지 않습니다.

## Black Han Sans (블랙한산스) — 제목/배너용 동봉 글꼴
- 제목, 액션 배너, 메인 메뉴 카드 제목에 쓰입니다 (`assets/fonts/BlackHanSans-Regular.ttf`). 파일이 없으면 기본 글꼴로 대체됩니다.
- 저작권: 2015 The Black Han Sans Project Authors (https://github.com/zesstype/Black-Han-Sans)
- 라이선스: SIL Open Font License, Version 1.1 (전문은 `assets/fonts/OFL-BlackHanSans.txt`). 수정 없이 그대로 동봉하며 글꼴 파일만 따로 판매하지 않습니다.

## Rajdhani — HUD 숫자용 동봉 글꼴
- 시간/점수/APM 등 숫자와 영문 HUD에 쓰입니다 (`assets/fonts/Rajdhani-Bold.ttf`). 한글이 섞인 문구는 기본 글꼴로 그려집니다.
- 저작권: Copyright (c) 2014, Indian Type Foundry (info@indiantypefoundry.com)
- 라이선스: SIL Open Font License, Version 1.1 (전문은 `assets/fonts/OFL-Rajdhani.txt`). 수정 없이 그대로 동봉하며 글꼴 파일만 따로 판매하지 않습니다.
