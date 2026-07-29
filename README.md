# 개인 경제 모닝 브리핑

국내외 경제·주식·금리·환율·산업 흐름을 자동 수집하고, 무료로 끝까지 읽을 수 있는 원문 가운데 중요한 소식을 모바일 브리핑으로 발행하는 개인용 프로젝트입니다.

## 기본 편집 원칙

- 하루 **8개 목표**: 국내 4개 + 글로벌 4개
- 공개 후보가 부족할 때만 국내·글로벌 각 최소 3개, 총 6개까지 허용
- 주식·시장 또는 환율·원자재 관련 항목 최소 2개
- 시장, 거시경제, 금리·통화, 환율·원자재, 산업·기업, 정책·규제 중 최소 3개 분야
- 같은 매체 최대 2개, 같은 사건의 중복 보도는 1개
- 단순 종목 추천·급등주·매수 유도 콘텐츠 제외
- 로그인·구독·결제 없이 확인 가능한 원문만 최종 후보로 사용
- 최근 14일에 소개한 URL 중복 방지

사이트에는 모바일 카드, 날짜별 지난 회차, 이메일 회원가입·로그인, 로그인 필수 저장, 선택형 스크랩 메모, 저장 기사 내부 상세 카드가 포함됩니다.

무료 원문 판별은 알려진 유료 도메인 차단과 실제 페이지 응답·페이월 문구 확인을 함께 사용합니다. 매체가 정책이나 HTML 구조를 바꾸면 완벽하지 않을 수 있으므로, 반복적으로 섞이는 사이트는 `settings.py`의 `PAYWALL_BLOCKED_DOMAINS`에 도메인을 추가하세요.

OpenAI API가 429·크레딧 부족·일시 장애로 실패하면 **공개 RSS 후보만으로 폴백 브리핑을 생성**합니다. Action 전체가 실패해 사이트가 멈추는 대신 페이지를 계속 갱신하지만, 폴백 요약은 피드 문장을 사용하므로 AI 요약보다 거칠거나 영어일 수 있습니다.

## 권장 저장소 이름

```text
economy-briefing
```

코드에는 GitHub 사용자 이름을 하드코딩하지 않았습니다. 다른 저장소 이름을 사용해도 작동합니다.

## 1. 개인 GitHub 저장소 만들기

```text
Repository name: economy-briefing
Visibility: Public
```

다운로드한 ZIP 자체를 GitHub에 올리지 않습니다. ZIP을 압축 해제한 뒤 **폴더 안의 파일과 폴더 전체**를 새 저장소 최상단에 올립니다.

```text
.github/workflows/daily-briefing.yml
docs/
collect.py
main.py
page.py
select_news.py
settings.py
requirements.txt
supabase_setup.sql
README.md
```

## 2. GitHub Pages 켜기

이 프로젝트는 브리핑 생성과 Pages 배포를 같은 Action에서 끝냅니다.

```text
Settings
→ Pages
→ Build and deployment
→ Source: GitHub Actions
```

별도의 Pages 템플릿 파일을 만들 필요는 없습니다. 공개 주소는 보통 다음 형식입니다.

```text
https://내깃허브아이디.github.io/economy-briefing/
```

## 3. OpenAI API 연결

```text
Settings
→ Secrets and variables
→ Actions
→ Secrets
→ New repository secret
```

등록할 Secret:

```text
OPENAI_API_KEY
```

ChatGPT 구독과 OpenAI API 크레딧은 별도입니다. 기본 모델은 `gpt-5.6-luna`이며, 다음 Actions Variable을 만들면 모델을 바꿀 수 있습니다.

```text
OPENAI_MODEL
```

OpenAI 웹 보완 탐색을 끄고 RSS 후보만 AI에 전달하려면 `.github/workflows/daily-briefing.yml`에서 다음 값을 `0`으로 바꿉니다.

```yaml
ENABLE_WEB_DISCOVERY: "0"
```

## 4. 로그인과 저장함 연결

경제·정치 브리핑은 **Supabase 프로젝트 하나를 공유**할 수 있습니다. 로그인 계정은 공유되고 저장함은 서로 다른 테이블로 분리됩니다.

두 서비스를 함께 운영할 때는 전체 묶음의 `supabase_setup_both.sql`을 한 번 실행합니다. 경제 서비스만 운영할 때는 이 폴더의 `supabase_setup.sql`을 실행합니다.

```text
Supabase Dashboard
→ SQL Editor
→ New query
→ SQL 전체 붙여넣기
→ Run
```

이메일 로그인 설정:

```text
Authentication
→ Providers
→ Email
→ Allow new users to sign up: ON
```

처음 테스트할 때 `Confirm email`을 끄면 가입 직후 바로 로그인됩니다. 개인 계정 하나만 사용할 계획이라면 본인 계정을 만든 뒤 `Allow new users to sign up`을 다시 끄면 기존 계정만 로그인할 수 있습니다.

이메일 인증을 켜는 경우 URL Configuration에 실제 Pages 주소를 등록합니다.

```text
https://내깃허브아이디.github.io/economy-briefing/**
```

Supabase의 `Project URL` 또는 `API URL`과 `Publishable key`를 복사해 GitHub Actions Secret으로 등록합니다.

```text
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
```

브라우저용 설정에는 `service_role`, Secret key, Database password를 절대 넣지 않습니다.

## 5. 첫 실행

```text
Actions
→ 경제 모닝 브리핑
→ Run workflow
→ Branch: main
→ Run workflow
```

정상 로그에는 다음 문구가 나타납니다.

```text
[수집 완료]
[선별 완료] 또는 [RSS 폴백 완료]
[페이지 생성 완료]
[완료]
GitHub Pages 배포
```

Action이 초록색으로 끝난 뒤에도 브라우저 캐시 때문에 이전 화면이 보이면 주소 끝에 `?v=1`을 붙이고, 다음 확인 때 숫자를 바꿉니다.

## 자동 실행 시각

```text
매일 한국시간 오전 07:40
```

정치 브리핑 08:05와 OpenAI 호출이 겹치지 않도록 시간을 분리했습니다. GitHub Actions 예약 실행은 서버 부하에 따라 몇 분 늦어질 수 있습니다.

`Run workflow`는 예약 시간을 기다리지 않고 즉시 실행하며, **실행 당시 한국 날짜**로 회차를 생성합니다.

## 소개 카드 링크 변경

기본 `ABOUT THIS BRIEFING` 카드는 현재 GitHub 저장소로 연결됩니다. 다른 홈페이지로 연결하려면 다음 Actions Variable을 추가합니다.

```text
ABOUT_URL
```

## 가장 자주 수정할 파일

- `settings.py`: 기사 수, 국내·글로벌 비율, RSS, 차단 도메인, 카테고리, 프롬프트, 사이트 문구
- `page.py`: 모바일 화면, 로그인, 저장함, 날짜별 아카이브 UI
- `.github/workflows/daily-briefing.yml`: 자동 실행 시각과 Pages 배포
