# git 커밋 → 시트 자동 반영

연결한 저장소에서 **커밋하거나 푸시하면** git hook이 백그라운드에서 `gtrack git sync`를 실행합니다.
커밋은 **커밋 로그** 시트에 기록되고, 연결된 작업의 상태가 갱신됩니다.
누가 커밋하든 똑같이 동작합니다. 사람이든 Claude Code나 다른 AI 에이전트든 상관없습니다.

## 연결 / 해제

```powershell
python -m gtrack git link --repo D:/work/my-app --project "웹사이트 개편" [--since 2026-10-08]
python -m gtrack git list                                     # 연결된 저장소 목록
python -m gtrack git sync --repo D:/work/my-app --dry-run   # 시트를 바꾸지 않고 결과만 보기
python -m gtrack git sync                                     # 연결된 모든 저장소를 지금 반영
python -m gtrack git unlink --repo D:/work/my-app           # hook 제거 + 연결 해제
```

- `link`는 대상 저장소의 `.git/hooks/post-commit`과 `pre-push`를 설치합니다.
  - `.git` 안에 있는 파일이라 **저장소 코드나 커밋에는 영향을 주지 않습니다.**
  - 같은 이름의 다른 hook이 이미 있으면 덮어쓰지 않고 오류를 냅니다. 이때는 직접 합쳐야 합니다.
- hook은 백그라운드로 실행됩니다. 그래서 커밋이나 푸시가 느려지거나 실패하지 않습니다. 결과는 `<저장소>/.git/gtrack-sync.log`에 남습니다.
- `--since` 이전 커밋은 반영하지 않습니다. 기본값은 연결한 날입니다.
- 같은 커밋은 한 번만 반영됩니다. 커밋 로그 시트의 커밋 해시로 중복을 막습니다.
- 커밋 직후와 푸시 직전 hook이 동시에 돌 수 있어서 잠금 파일(`.git/gtrack-sync.lock`)로 순서를 지킵니다.

## 커밋이 작업에 연결되는 방법

| 방법 | 예 | 작업 상태 반영 |
|---|---|---|
| 메시지에 작업 ID 직접 쓰기 | `feat: 검색 필터 T-018` | ✅ 항상 |
| 완료 표시 | `T-018 완료`, `closes T-018`, `[T-018 done]` | ✅ 그 작업을 **완료** 처리 |
| scope 규칙 | `fix: 카드 정렬 (search)`, `fix(search): …` | `feat`·`fix`·`perf` 커밋만 |
| 경로 규칙 | `components/search/**` 파일 변경 | `feat`·`fix`·`perf` 커밋만 |

- scope나 경로로 찾은 작업이 **3개를 넘으면** 여러 화면을 한꺼번에 고친 정리 커밋으로 보고, 로그에만 남깁니다.
- `refactor`, `style`, `docs`, `chore`, `test`, `build` 커밋도 로그에만 남깁니다. 연결 작업은 `관련작업` 칸에 표시됩니다.

**상태 반영 규칙**
- `대기` 작업은 → `진행중`이 됩니다.
- 시작일이 비어 있으면 → 첫 커밋 날짜로 채웁니다.
- 완료 표시가 있으면 → `완료`가 되고, 진척률 100%와 완료일이 기록됩니다.
- `완료`, `보류`, `차단` 작업의 상태는 완료 표시가 없으면 바꾸지 않습니다.
- **진척률은 자동으로 바꾸지 않습니다.** 커밋만으로는 얼마나 진행됐는지 알 수 없기 때문입니다. 진척률은 사람이 갱신하거나 Claude에게 요청하세요.

## 규칙 편집 (`.gtrack.json`)

규칙은 이 폴더의 `.gtrack.json`에 저장됩니다. 로컬 경로가 들어 있어서 git에는 올리지 않습니다.

```json
{
  "spreadsheet_id": "...",
  "git_sync": {
    "d:/work/my-app": {
      "path": "D:/work/my-app",
      "project": "웹사이트 개편",
      "since": "2026-10-01",
      "paths":  { "app/*/*/search/*": "T-018", "components/search/*": "T-018" },
      "scopes": { "search": "T-018", "e2e": "T-006" }
    }
  }
}
```
- `paths`: 저장소 루트 기준 경로에 대한 glob 패턴입니다.
  - `*`는 `/`를 포함한 모든 문자와 맞습니다.
  - `[`는 패턴 문자이므로 `app/[domain]` 대신 `app/*`로 씁니다.
- `scopes`: 커밋 제목의 `(scope)` 값입니다. `(search, shop)`처럼 여러 개면 각각 확인합니다.
- 새 작업을 추가하면 그 작업의 경로나 scope 규칙도 함께 추가하세요. Claude에게 "T-019 카테고리 경로 규칙 추가해줘"라고 요청해도 됩니다.

## 주의

- hook은 **브라우저 로그인 없이** 동작합니다. 로그인 토큰이 만료되면(테스트 모드는 7일) 로그에 "구글 로그인이 필요합니다"가 남고 반영되지 않습니다.
  - 그때 `python -m gtrack project list`를 한 번 실행해 다시 로그인한 뒤 `python -m gtrack git sync`를 실행하면, 밀린 커밋이 한꺼번에 반영됩니다.
- hook은 현재 체크아웃된 브랜치(HEAD)의 커밋만 읽습니다. 다른 브랜치 커밋은 그 브랜치에서 다음에 커밋하거나 푸시할 때 반영됩니다.
- hook은 이 폴더(gsheet-project-tracker)의 Python 경로를 그대로 사용합니다. 폴더를 옮기거나 Python을 다시 설치했다면 `git link`를 다시 실행하세요.
