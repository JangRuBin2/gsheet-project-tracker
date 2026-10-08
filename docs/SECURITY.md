# 보안 — 비밀 파일 관리

## 비밀 파일 목록

| 파일 | 들어 있는 것 | 유출되면 |
|---|---|---|
| `credentials.json` (= `client_secret_*.json`) | OAuth client ID + **client secret** | 남이 내 앱 이름으로 로그인 화면을 띄울 수 있습니다. 내 데이터에 바로 접근하지는 못합니다. |
| `token.json` | **access token / refresh token** | ⚠️ **내 구글 시트 전체를 읽고 쓸 수 있습니다.** 가장 위험합니다. |
| 서비스 계정 키 JSON | private key | 그 서비스 계정에 공유된 모든 시트에 접근할 수 있습니다. |
| `.gtrack.json` | 스프레드시트 ID | 비밀은 아닙니다. 공유 권한이 없으면 열 수 없습니다. 그래도 공개 저장소에는 올리지 않습니다. |

이 파일들은 모두 `.gitignore`에 들어 있어서 git에 올라가지 않습니다.

## 자동 검사

`python -m pytest`를 실행하면 `tests/test_secrets.py`가 아래 두 가지를 확인합니다.
- 위 파일들이 `.gitignore`에 걸리는지
- 커밋될 수 있는 파일에 client secret, refresh/access token, private key 형태의 문자열이 없는지

**커밋하기 전에 테스트를 돌리세요.**

## 도구가 지키는 것

- 인증 파일과 토큰의 **내용을 화면이나 로그에 출력하지 않습니다.** 오류 메시지에는 파일 경로만 나옵니다.
- `token.json`은 소유자만 읽을 수 있게 저장합니다. POSIX에서는 `0600`, Windows에서는 사용자 프로필 ACL을 따릅니다.
- 권한 범위는 `spreadsheets` 하나뿐입니다. Gmail이나 Drive 전체에는 접근하지 않습니다.
- 로그인 중에 터미널에 출력되는 인증 주소에는 client ID만 들어 있습니다. client ID는 공개돼도 되는 값입니다. secret이나 토큰은 들어 있지 않습니다.

## 유출이 의심될 때

1. **토큰 폐기**: https://myaccount.google.com/permissions 에서 `gtrack` 앱의 **액세스 권한을 삭제**합니다. 그 즉시 `token.json`이 무효가 됩니다.
2. **client secret 교체**: https://console.cloud.google.com/auth/clients?project=gsheet-project-tracker 에서 해당 클라이언트를 엽니다.
   - **보안 비밀 추가**로 새 secret을 만들고 기존 secret을 사용 중지·삭제합니다.
   - 또는 클라이언트를 지우고 새로 만듭니다.
   - 그다음 새 JSON을 받아 `credentials.json`을 교체합니다.
3. 로컬의 `token.json`을 지우고 다시 로그인합니다.
4. 이미 git에 커밋했다면 파일을 지우는 것만으로는 부족합니다. **기록에 남아 있으니 반드시 1~2번으로 폐기·교체하세요.**

## 하지 말 것

- `credentials.json`이나 `token.json`을 메신저, 메일, 이슈, 채팅(AI 포함)에 붙여넣기
- `git add -f`로 무시 목록을 우회하기
- 다른 사람과 `token.json` 공유하기. 각자 로그인해서 만들어야 합니다.
