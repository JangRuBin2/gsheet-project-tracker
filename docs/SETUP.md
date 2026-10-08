# 처음 설정하기 (Google 인증)

이 도구는 **내 구글 계정 권한으로** 스프레드시트를 만들고 수정합니다.
그래서 처음 한 번은 Google Cloud에서 "이 프로그램이 내 시트를 다뤄도 된다"는 허가를 받아야 합니다.
아래 순서대로 하면 10분 정도 걸립니다.

> 아래 링크의 `gsheet-project-tracker`는 Google Cloud 프로젝트 ID입니다. 다른 ID를 쓰신다면 바꿔서 여세요.

---

## 0. 준비물

- Python 3.10 이상 (Windows: `winget install -e --id Python.Python.3.12`)
- 라이브러리 설치: `python -m pip install -r requirements.txt`

## 1. Google Cloud 프로젝트 만들기

1. https://console.cloud.google.com/projectcreate 에서 프로젝트를 만듭니다. (예: ID `gsheet-project-tracker`)
2. https://console.cloud.google.com/apis/library/sheets.googleapis.com 에서 **Google Sheets API → 사용**을 누릅니다.

## 2. OAuth 동의 화면 (처음 한 번만)

https://console.cloud.google.com/auth/overview?project=gsheet-project-tracker

1. **시작하기**를 누릅니다.
2. 아래 표대로 입력합니다.

| 항목 | 입력 |
|---|---|
| 앱 이름 | `gtrack` (아무거나) |
| 사용자 지원 이메일 | 본인 Gmail |
| 대상 | **외부** |
| 연락처 정보 | 본인 Gmail |

3. 동의에 체크하고 **만들기**를 누릅니다.

## 3. 테스트 사용자 추가 ⚠️ 빼먹기 쉬움

https://console.cloud.google.com/auth/audience?project=gsheet-project-tracker

1. **테스트 사용자 → + Add users**를 누릅니다.
2. **이 도구로 로그인할 Gmail 주소**를 입력하고 저장합니다.

- 앱이 '테스트' 상태라서 **여기 등록된 계정만 로그인할 수 있습니다.**
- 이 단계를 빼먹으면 로그인할 때 *"gtrack은(는) Google 인증 절차를 완료하지 않았습니다 (403 access_denied)"* 오류가 납니다.
- 다른 사람도 이 도구를 쓰게 하려면 그 사람의 Gmail도 추가합니다. 최대 100명까지 가능합니다.

## 4. OAuth 클라이언트 ID 만들기 → JSON 파일 받기

https://console.cloud.google.com/auth/clients/create?project=gsheet-project-tracker

1. **애플리케이션 유형: 데스크톱 앱**을 고릅니다. *웹 애플리케이션이 아닙니다.*
2. 이름은 아무거나 넣고 **만들기**를 누릅니다.
3. **JSON 다운로드**를 누릅니다. 창을 닫았다면 클라이언트 목록 오른쪽의 ⬇ 아이콘을 누르면 됩니다.
4. 받은 파일 `client_secret_XXXX.apps.googleusercontent.com.json`의 이름을 **`credentials.json`**으로 바꿉니다.
5. 프로젝트 폴더 맨 위(README.md가 있는 곳)에 둡니다.

> 🔒 이 파일에는 비밀값(client secret)이 들어 있습니다. 메신저나 메일로 보내거나 git에 올리지 마세요. ([SECURITY.md](SECURITY.md))

## 5. 첫 로그인 + 스프레드시트 만들기

```powershell
python -m gtrack init --title "2026 프로젝트 관리"
```

1. 브라우저가 열리면 **3단계에서 등록한 계정**을 선택합니다.
2. *"Google에서 확인하지 않은 앱"* 경고가 나오면 **고급 → gtrack(으)로 이동(안전하지 않음)**을 누릅니다. 본인이 만든 앱이라 괜찮습니다.
3. **계속**을 눌러 권한을 허용합니다.
4. 터미널에 스프레드시트 주소가 나오면 성공입니다.

로그인에 성공하면 다음 두 파일이 생깁니다.
- `token.json`: 로그인 토큰입니다. 다음부터는 로그인 없이 실행됩니다.
- `.gtrack.json`: 사용할 스프레드시트 ID입니다.

이미 있는 스프레드시트를 쓰려면 아래처럼 연결합니다. 스프레드시트 ID는 URL의 `/d/`와 `/edit` 사이 문자열입니다.
```powershell
python -m gtrack init --existing 1AbC...xyz
```

---

## 자주 나는 문제

| 증상 | 원인 / 해결 |
|---|---|
| `403 access_denied`, "인증 절차를 완료하지 않았습니다" | 로그인한 계정이 **테스트 사용자**에 없습니다. 3단계에서 정확한 주소를 추가하고, 1~2분 뒤 다시 시도하세요. 크롬에 계정이 여러 개 로그인돼 있으면 다른 계정이 선택됐는지도 확인하세요. |
| "Google에서 확인하지 않은 앱" | 정상입니다. **고급 → 이동**을 누르세요. |
| `인증 파일이 없습니다: credentials.json` | 4단계 파일이 없거나 이름이 다릅니다. 확장자가 `.json.json`으로 두 번 붙지 않았는지도 확인하세요. 탐색기에서 "파일 확장명 표시"를 켜면 보입니다. |
| "'데스크톱 앱' 유형 OAuth 클라이언트가 아닙니다" | 웹 애플리케이션 유형으로 만들어졌습니다. 4단계를 **데스크톱 앱**으로 다시 하세요. |
| **7일쯤 지나서** 다시 로그인 창이 뜸 | 테스트 상태 앱은 로그인 토큰이 7일 뒤 만료됩니다. 도구가 자동으로 다시 로그인을 요청하니 로그인만 하면 됩니다. 매번 귀찮다면 동의 화면의 **앱 게시(프로덕션으로 전환)**를 하면 됩니다. 개인 사용은 Google 검토 없이 "확인되지 않은 앱" 경고만 뜹니다. |
| 브라우저가 안 열림 | 터미널에 출력된 주소를 복사해 직접 여세요. 로그인은 **도구를 실행한 그 PC**의 브라우저에서 해야 합니다. 로그인 결과를 localhost로 받기 때문입니다. |
| 다른 계정으로 바꾸고 싶음 | `token.json`을 지우고 아무 명령이나 다시 실행하세요. |
| `Google API 오류: 403 ... does not have permission` | 로그인한 계정이 그 스프레드시트의 편집 권한을 갖고 있지 않습니다. 시트 소유자에게 공유를 요청하세요. |

## 다른 사람과 함께 쓰기

- **시트만 같이 보거나 수정하려는 경우**: 구글 시트의 **공유** 버튼으로 초대하면 됩니다. 그 사람은 이 도구를 설치하지 않아도 됩니다.
- **그 사람도 이 도구(명령어)를 쓰려는 경우**:
  1. 3단계에서 그 사람의 Gmail을 테스트 사용자로 추가합니다.
  2. 시트를 그 사람에게 편집자로 공유합니다.
  3. `credentials.json`은 보안 채널로 전달하거나, 그 사람이 자기 Google Cloud 프로젝트에서 직접 만들게 합니다.
  4. 그 사람 PC에서 `init --existing <스프레드시트ID>`를 실행합니다.
  - `token.json`은 **절대 공유하지 마세요.** 계정마다 각자 로그인해서 만들어야 합니다.

## (선택) 서비스 계정으로 자동화

브라우저 로그인 없이 서버나 스케줄러에서 돌리려면 서비스 계정을 씁니다.

1. https://console.cloud.google.com/iam-admin/serviceaccounts 에서 서비스 계정을 만들고 **키 추가 → JSON**을 받습니다.
2. 받은 파일을 `credentials.json`으로 두거나 `--credentials 경로`로 지정합니다.
3. 서비스 계정이 만든 파일은 내 드라이브에 보이지 않습니다. 그래서 **내가 만든 스프레드시트를 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)에 편집자로 공유**한 뒤 `init --existing <ID>`로 연결합니다.
