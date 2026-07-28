"""카카오 리프레시 토큰 최초 발급 스크립트 (한 번만 실행하면 됩니다).

사전 준비 (README의 '카카오 설정' 참고):
1. developers.kakao.com에서 앱 생성 → REST API 키 확보
2. [내 애플리케이션 > 제품 설정 > 카카오 로그인] 활성화
   - Redirect URI에 https://localhost 등록
3. [동의항목]에서 '카카오톡 메시지 전송(talk_message)' 설정

사용법:
    python get_kakao_token.py
"""

import requests

REDIRECT_URI = "https://localhost"

rest_api_key = input("REST API 키 입력: ").strip()

auth_url = (
    f"https://kauth.kakao.com/oauth/authorize"
    f"?client_id={rest_api_key}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=talk_message"
)
print("\n1) 아래 URL을 브라우저에서 열고 카카오 로그인 후 동의하세요:")
print(auth_url)
print("\n2) 이동된 주소창의 https://localhost/?code=XXXX 에서 code 값을 복사하세요.")
print("   (페이지가 '연결할 수 없음'으로 떠도 정상입니다. 주소창만 보면 됩니다.)\n")

code = input("code 값 입력: ").strip()

resp = requests.post(
    "https://kauth.kakao.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    },
    timeout=30,
)
resp.raise_for_status()
data = resp.json()

print("\n===== 발급 완료 =====")
print(f"refresh_token (GitHub Secret에 저장): \n{data['refresh_token']}")
print("\n이 값을 GitHub 저장소 Settings > Secrets > KAKAO_REFRESH_TOKEN 에 넣으세요.")
