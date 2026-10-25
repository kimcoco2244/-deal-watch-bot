# 가격 오류·초특가 감시봇

GitHub Actions가 약 5분 간격으로 공개 커뮤니티 게시물을 확인하고, 제목에서 **가격오류·가격실수·역대가·초특가** 등 키워드를 발견하면 텔레그램으로 알립니다.

## 현재 지원 출처
- 뽐뿌 RSS / 해외뽐뿌 RSS
- 아카라이브 핫딜 공개 페이지
- 루리웹 핫딜 공개 페이지

사이트 접속 제한이나 HTML 구조 변경 때문에 일부 출처가 실패할 수 있습니다. GitHub **Actions → Deal Watch Telegram → 실행 기록**에서 출처별 상태를 확인하세요. 로그인 전용 네이버 카페와 퀘이사존은 아직 포함하지 않았습니다.

## 설정 (휴대폰에서도 가능)
1. BotFather에서 만든 봇과 대화를 열고 **시작**을 누릅니다.
2. ChatGPT 채팅에 한 번 노출된 이전 봇 토큰은 반드시 BotFather의 `/revoke`로 폐기합니다.
3. 비공개로 새로 발급한 토큰을 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 `TELEGRAM_BOT_TOKEN` 이름으로 등록합니다.
4. 자신의 채팅 ID도 같은 위치에 `TELEGRAM_CHAT_ID`라는 이름으로 등록합니다. 자신의 Chat ID는 봇과 대화한 뒤 Telegram getUpdates API 또는 신뢰할 수 있는 ID 조회 방법으로 확인하세요. 토큰과 Chat ID를 소스나 공개 이슈에 적지 마세요.
5. 저장소 **Actions → Deal Watch Telegram → Run workflow**를 실행하여 초기 상태 파일을 만듭니다.
6. 같은 화면에서 **Send a Telegram test message only**를 선택해서 수신 테스트를 수행할 수 있습니다.

## 동작 방식과 한계
- 최초 실행은 기존 글을 기록만 하고 알림을 보내지 않습니다.
- 새 글 중 제목에 사전 정의된 단어가 있는 경우만 알립니다. 실제 가격과 배송 여부는 검증하지 않습니다.
- RSS에 게시 시각이 있으면 오래된 글은 제외하고, HTML 게시판은 발견 시각을 사용합니다.
- 이미 알린 URL은 저장소의 `.state/seen.json`에 기록하여 중복을 방지합니다.
- 예약 실행은 정확히 5분 간격을 보장하지 않습니다. 사이트별 제한과 GitHub Actions 지연으로 누락이 발생할 수 있습니다.
- 이 프로그램은 로그인 우회나 차단 회피를 시도하지 않습니다.
- 공개 저장소의 상태 파일에는 URL의 해시와 날짜만 저장합니다.
- 텔레그램 봇 토큰은 GitHub Secrets에만 보관하세요.

## 관리
`monitor.py`의 `SOURCES`와 키워드 배열을 수정해 출처와 감지 기준을 조정할 수 있습니다. 오류가 생기면 Actions 실행 로그를 확인하세요.
