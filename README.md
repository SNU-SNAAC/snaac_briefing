SNAAC Briefing

SNAAC Briefing은 지난 하루 동안 공개된 스타트업 뉴스, 창업가·VC 인터뷰, 제품·성장 인사이트, 시장·정책 변화, 영상 콘텐츠를 자동 수집하고 OpenAI가 읽을 가치가 높은 4~5개를 선별·요약해 모바일 브리핑으로 배포하는 서비스입니다.

공개 페이지:

https://snu-snaac.github.io/snaac_briefing/

운영 흐름

매일 07:20 KST
GitHub Actions 예약 실행
→ 공개 RSS·Atom·YouTube 콘텐츠 수집
→ 최근 21일 소개 URL 중복 제거
→ OpenAI Responses API로 4~5개 선별·요약
→ 무료로 열람 가능한 원문·정상 링크 확인
→ 오늘 페이지와 날짜별 아카이브 생성
→ Python·JavaScript·핵심 UI 검사
→ GitHub Pages 배포

매일 09:00 KST
카카오 오픈채팅봇이 고정 안내문과 브리핑 링크 자동 발송

GitHub의 예약 실행은 서버 상황에 따라 지연될 수 있어 오전 9시 발송보다 충분히 앞선 오전 7시 20분에 시작합니다.

주요 기능

매일 스타트업 콘텐츠 4~5개 큐레이션

기사별 핵심 요약과 WHY IT MATTERS

유료 구독·로그인 장벽 및 오류 링크 필터

원본 컬러 썸네일과 YouTube 공식 썸네일

마지막 업데이트 시각 및 업데이트 지연 안내

이메일·비밀번호 회원가입과 로그인

로그인 세션 자동 복원

로그인 필수 기사 저장

선택형 스크랩 메모와 태그

저장 기사 내부 상세 카드

날짜별 지난 브리핑과 아카이브 검색

간단한 브리핑 만족도 피드백

원문 오류·페이월·요약 불일치 신고

최소한의 익명 이용 통계

최근 반응이 충분한 기사 기반 주간 인기 아티클

수동 preview와 실제 deploy 분리

자동화 실패·품질 보류 시 GitHub Issue 알림

기사 선별 원칙

단순 투자 유치 여부보다 아래 기준을 우선합니다.

새로운 관점이나 실행 가능한 교훈이 있는가

창업가·팀·제품·시장·VC를 이해하는 데 도움이 되는가

단순 발표가 아니라 배경과 변화의 의미를 설명하는가

신뢰할 수 있는 출처 또는 당사자 인터뷰인가

SNAAC 커뮤니티에서 읽고 이야기할 가치가 있는가

편집 규칙:

최종 4~5개

같은 출처 최대 2개

맥락 없는 투자 유치 단신 최대 1개

최근 21일 소개 URL 제외

유료 구독·로그인 원문 제외

단순 홍보·행사·협약성 콘텐츠 제외

잘못된 링크나 반복 리디렉션 제외

품질 기준을 통과한 기사가 4개 미만이면 기존 브리핑 유지

저장소 구조

.github/workflows/daily-briefing.yml  자동 실행·검사·Pages 배포
collect.py                           RSS·Atom·YouTube 후보 수집
select_news.py                       OpenAI 선별·요약·품질 검사
main.py                              전체 파이프라인 실행
page.py                              모바일 HTML·저장함·아카이브 생성
link_utils.py                        기사 URL 정리·중복 판별
repair_article_links.py              현재·과거 아카이브 URL 정리
smoke_check.py                       배포 전 생성 결과 검사
kakao.py                             선택형 운영자 개인 카카오 배포 확인 알림
get_kakao_token.py                   개인 카카오 알림용 최초 토큰 발급 도구
supabase_setup.sql                   로그인 저장함·통계·피드백·신고 DB 설정
docs/                                GitHub Pages 배포 결과

settings.py는 현재 실행 코드에서 사용하지 않습니다. 과거 경제 브리핑 프로젝트의 잔여 파일이므로 SNAAC 저장소에서는 삭제하는 것이 맞습니다.

GitHub Actions 설정

필수 Secrets

OPENAI_API_KEY
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY

권장 Variables

SITE_URL=https://snu-snaac.github.io/snaac_briefing/
SUPABASE_REDIRECT_URL=https://snu-snaac.github.io/snaac_briefing/
PRIVACY_CONTACT_EMAIL=운영 문의 이메일

선택 Variables

OPENAI_MODEL                 기본값 gpt-5.4-mini
MIN_QUALITY_SCORE            기본값 72
MIN_SUPPLEMENT_QUALITY_SCORE 기본값 60
DELETE_ACCOUNT_FUNCTION      기본값 delete-account

선택 Secrets

아래 값은 운영자 개인 카카오톡으로 배포 확인 알림을 보낼 때만 사용합니다. 오픈채팅방 오전 9시 자동 발송은 카카오 오픈채팅봇의 알림 기능이 담당합니다.

KAKAO_REST_API_KEY
KAKAO_REFRESH_TOKEN
GH_PAT

Supabase 설정

Supabase SQL Editor에서 저장소의 supabase_setup.sql 전체를 실행합니다.

현재 웹페이지가 사용하는 핵심 객체:

테이블

saved_articles
briefing_events
briefing_feedback
article_reports
account_deletion_requests

뷰

weekly_article_highlights
daily_briefing_metrics
article_engagement_metrics
briefing_feedback_metrics

user_preferences는 관심 분야·오늘의 관점 기능을 제거한 현재 라이트 버전에서는 사용하지 않습니다.

Supabase 브라우저 코드에는 Publishable Key만 사용합니다. service_role, Secret Key, Database Password를 GitHub나 정적 HTML에 넣지 마세요.

이메일 인증 없이 가입 직후 로그인하려면:

Supabase Dashboard
→ Authentication
→ Sign In / Providers
→ Email
→ Allow new users to sign up: ON
→ Confirm email: OFF

수동 실행

Actions
→ SNAAC 모닝 브리핑
→ Run workflow

preview

실제 사이트와 아카이브를 변경하지 않음

_preview 결과를 Artifact로 다운로드 가능

UI나 코드 수정 후 먼저 사용

deploy

실제 docs/ 생성

저장소에 아카이브 기록

GitHub Pages 공개 배포

예약 실행은 자동으로 deploy 모드입니다.

정상 로그

[수집 완료]
[선별 완료]
[페이지 생성 완료]
[기사 링크 정리 완료]
[생성 결과 검사 완료]
GitHub Pages 실제 배포

운영 데이터 확인

API 비용·토큰: OpenAI Usage

가입 계정: Supabase Authentication → Users

저장 기사: saved_articles

방문·클릭·저장 이벤트: briefing_events

만족도: briefing_feedback

기사 신고: article_reports

자동화 상태: GitHub Actions와 Issues

일별 집계 예시:

select *
from public.daily_briefing_metrics
order by briefing_date desc;

기사별 반응 예시:

select *
from public.article_engagement_metrics
order by briefing_date desc, clicks desc;

카카오 오픈채팅 자동 발송

방장이 모바일 카카오톡에서 다음 경로로 한 번 설정합니다.

오픈채팅방
→ 우측 상단 메뉴(≡)
→ 챗봇 beta
→ 오픈채팅봇
→ 편집
→ 알림
→ 매일 오전 9시

오픈채팅봇은 고정 문구와 고정 링크를 보내고, 링크가 가리키는 GitHub Pages 콘텐츠만 매일 갱신됩니다.

비용 구조

OpenAI API 비용은 GitHub Actions가 기사 후보를 선별·요약할 때만 발생합니다. 사용자가 브리핑 페이지, 저장함, 지난 회차, 원문 링크를 열 때는 OpenAI API가 호출되지 않습니다.
