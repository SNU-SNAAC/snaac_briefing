# 🌅 SNAAC 모닝 브리핑 봇 (100% 자동화)

매일 아침, 사람 손 없이 스타트업 뉴스 브리핑이 오픈채팅방에 도착하는 구조입니다.

```
[매일 08:30 KST] GitHub Actions (자동)
  ├─ 1. collect.py     : 6개 스타트업 매체 RSS에서 24시간 내 기사 수집
  ├─ 2. select_news.py : OpenAI API(GPT)가 5개 선별 + 1~2줄 요약
  ├─ 3. page.py        : 브리핑 웹페이지 생성 → GitHub Pages 자동 배포
  └─ 4. (선택) 팀장 카톡으로 "오늘자 배포 완료" 확인 알림

[매일 09:00 KST] 카카오 공식 오픈채팅봇 반복알림 (최초 1회만 설정)
  └─ "🌅 오늘의 SNAAC 모닝 브리핑 👉 [고정 링크]" → 400명에게 자동 발송
```

모두 카카오 공식 기능만 사용하므로 계정 정지 리스크가 없고, 페이지는 기사 원문
링크만 제공하므로(썸네일은 핫링크) 저작권 리스크도 최소화됩니다.

## 셋업 (최초 1회, 약 15분)

### 1. GitHub 저장소 + Pages
1. 이 폴더를 GitHub **Public** 저장소로 업로드 (Pages 무료 사용 조건)
2. 저장소 → Settings → Pages → Source: `Deploy from a branch`,
   Branch: `main` / 폴더: `/docs` → Save
3. 몇 분 뒤 `https://<계정명>.github.io/<저장소명>/` 접속 확인
   (처음엔 페이지가 없으니, 아래 4번까지 마치고 Actions 수동 실행 후 확인)

### 2. OpenAI API 키
[platform.openai.com](https://platform.openai.com) 가입 → 결제 수단 등록/충전 →
좌측 메뉴 **API keys** → **Create new secret key**로 발급 (`sk-...`).
하루 1회 호출이라 비용은 월 1달러 미만 수준입니다.
최신 요금: https://openai.com/api/pricing
기본 모델은 `gpt-5.4-mini`이며 `select_news.py`의 `MODEL`에서 변경 가능합니다.

### 3. GitHub Secrets 등록
저장소 → Settings → Secrets and variables → Actions:

| Secret | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `KAKAO_REST_API_KEY` | 선택 | 팀장 카톡 확인 알림용 (README 하단 참고) |
| `KAKAO_REFRESH_TOKEN` | 선택 | 〃 |
| `GH_PAT` | 선택 | 카카오 토큰 자동 갱신용 |

### 4. 테스트
Actions 탭 → "SNAAC 모닝 브리핑" → **Run workflow** → 완료 후
Pages 주소에서 오늘 브리핑이 뜨는지 확인.

### 5. 오픈채팅봇 반복알림 설정 (핵심!)
오픈채팅방 방장 계정으로:
1. 채팅방 우측 상단 ≡ → **오픈채팅봇** → 활성화
2. **알림메시지** → 반복알림 추가
   - 시간: 매일 오전 9:00
   - 내용 예시:
     ```
     🌅 오늘의 SNAAC 모닝 브리핑이 도착했어요!
     어제 스타트업 생태계 주요 소식 5가지 👇
     https://<계정명>.github.io/<저장소명>/
     ```
3. 저장하면 끝. 이후 매일 9시에 자동 발송됩니다.

> ⚠️ 오픈채팅봇 메뉴 구성은 카카오 업데이트에 따라 조금씩 바뀔 수 있습니다.

## 운영 팁

- **주말 오프**: 주말 발송을 끄려면 워크플로 cron을 `30 23 * * 0-4`(월~금 아침)로,
  오픈채팅봇 반복알림도 평일로 설정
- **기사가 없는 날**: 페이지를 갱신하지 않고 전날 브리핑을 유지합니다
- **매체 추가**: `collect.py`의 `FEEDS` / **선별 기준**: `select_news.py`의 `SYSTEM_PROMPT`
- **썸네일 끄기**: `page.py`의 `SHOW_THUMBNAILS = False` (매체 이니셜 카드로 대체)
- **디자인 수정**: `page.py`의 HTML/CSS 템플릿

## (선택) 팀장 카톡 확인 알림

매일 아침 "배포 완료 + 오늘의 5개 제목"을 팀장 카톡(나와의 채팅)으로 받고 싶다면:
1. [developers.kakao.com](https://developers.kakao.com) 앱 생성 → REST API 키 확보
2. 카카오 로그인 활성화, Redirect URI `https://localhost` 등록,
   동의항목에서 `talk_message` 설정
3. 로컬에서 `python get_kakao_token.py` 실행 → refresh_token 발급
4. Secrets에 `KAKAO_REST_API_KEY`, `KAKAO_REFRESH_TOKEN` 등록

리프레시 토큰은 약 2개월 유효하며, `GH_PAT`(repo 권한 PAT)를 등록해두면
봇이 자동 갱신합니다. 미등록 시 약 2개월마다 3번 과정을 반복하면 됩니다.

## 주의사항

- GitHub Actions cron은 몇 분 지연될 수 있어 8:30에 여유 있게 실행합니다
- RSS 피드 주소가 매체 사정으로 바뀌면 `FEEDS`를 점검하세요
- 카카오 링크 미리보기는 캐시되므로 채팅방 썸네일이 매일 바뀌지 않을 수 있습니다
  (페이지 내부 썸네일은 매일 갱신됨)
