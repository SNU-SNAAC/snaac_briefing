# SNAAC v6 Light 검사 결과

검사 완료 항목:

- Python 문법: `page.py`, `select_news.py`, `main.py`, `smoke_check.py`, `collect.py`
- 생성 HTML: 메인·날짜별 아카이브·아카이브 인덱스
- 기사 수: 4개 샘플로 생성 및 smoke check 통과
- JavaScript: Node.js `--check` 통과
- 삭제 확인: `무료 원문만`, `오늘의 관점`, 관심 분야 UI, 인증 메일 재발송, OpenAI 토큰 안내
- 아카이브 검색: 로그인 폼과 분리, `autocomplete=off`, `aria-autocomplete=none`, 초기 readonly 및 자동 입력 제거 코드 확인
- 선택 로직: 72점 이상 후보 우선, 부족 시 60점 이상 보완 후보로 최소 4개 구성 테스트
- GitHub Actions YAML 구문 파싱

실제 Supabase 프로젝트와 OpenAI API 키를 사용한 계정 가입 및 실 API 호출은 이 환경에서 수행하지 않았습니다. 배포 전 preview와 테스트 계정 1개로 최종 확인해야 합니다.
