"""인증: OAuth 데스크톱 클라이언트(credentials.json) 또는 서비스 계정 키 둘 다 지원.

credentials.json / token.json 에는 비밀값이 들어 있으므로 내용을 출력하거나 로그로 남기지 않는다.
설정 방법은 docs/SETUP.md 참고.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SETUP_DOC = "docs/SETUP.md"


def build_service(credentials_path: str | None = None, token_path: str = "token.json"):
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=load_credentials(credentials_path, token_path), cache_discovery=False)


def load_credentials(credentials_path: str | None, token_path: str):
    key_file = Path(credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "credentials.json")
    if not key_file.exists():
        raise FileNotFoundError(
            f"인증 파일이 없습니다: {key_file}\n"
            f"Google Cloud Console 에서 OAuth 클라이언트(데스크톱 앱) JSON 을 받아 credentials.json 으로 "
            f"저장하세요. 자세한 방법은 {SETUP_DOC} 참고."
        )
    try:
        info = json.loads(key_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(f"{key_file} 이 올바른 JSON 이 아닙니다. 다시 내려받으세요. ({SETUP_DOC})") from None

    if info.get("type") == "service_account":
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if "installed" not in info:
        raise ValueError(
            f"{key_file} 은 '데스크톱 앱' 유형 OAuth 클라이언트가 아닙니다. "
            f"애플리케이션 유형을 '데스크톱 앱'으로 다시 만드세요. ({SETUP_DOC})"
        )

    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = Path(token_path)
    creds = None
    if token.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token), SCOPES)
        except (ValueError, json.JSONDecodeError):
            creds = None  # 손상된 토큰 → 다시 로그인
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(token, creds)
            return creds
        except RefreshError:
            # 테스트 모드 앱은 refresh token 이 7일 후 만료된다 → 다시 로그인
            print("로그인이 만료되어 다시 인증합니다. 브라우저에서 로그인해 주세요.")

    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = InstalledAppFlow.from_client_secrets_file(str(key_file), SCOPES).run_local_server(
        port=0, open_browser=True,
        authorization_prompt_message="브라우저가 열리지 않으면 이 주소를 직접 여세요:\n{url}",
        success_message="인증이 완료되었습니다. 이 창을 닫아도 됩니다.",
    )
    _save_token(token, creds)
    return creds


def _save_token(path: Path, creds) -> None:
    """토큰을 소유자만 읽을 수 있게 저장한다 (POSIX 0600; Windows 는 사용자 프로필 ACL 을 따른다)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
