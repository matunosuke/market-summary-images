"""X (旧 Twitter) API v2 への投稿。

OAuth 1.0a User Context で `POST /2/tweets` を叩く。
必要な認証情報は 4 つとも環境変数から読む。
"""

from __future__ import annotations

import logging
import os

from requests_oauthlib import OAuth1Session

logger = logging.getLogger(__name__)

TWEETS_ENDPOINT = "https://api.x.com/2/tweets"
REQUEST_TIMEOUT = 30

CREDENTIAL_ENV_VARS = (
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
)


class XCredentialsError(RuntimeError):
    """X の認証情報が揃っていない。"""


class XPostError(RuntimeError):
    """X への投稿が失敗した。"""


def missing_credentials() -> list[str]:
    """未設定の認証情報の環境変数名を返す。"""
    return [name for name in CREDENTIAL_ENV_VARS if not os.environ.get(name)]


def _session() -> OAuth1Session:
    missing = missing_credentials()
    if missing:
        raise XCredentialsError("環境変数が未設定です: " + ", ".join(missing))
    return OAuth1Session(
        client_key=os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_tweet(text: str) -> str:
    """ツイートを投稿し、投稿 ID を返す。"""
    response = _session().post(
        TWEETS_ENDPOINT, json={"text": text}, timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 201:
        raise XPostError(
            f"投稿に失敗しました (HTTP {response.status_code}): {response.text}"
        )
    tweet_id = response.json()["data"]["id"]
    logger.info("投稿しました: id=%s", tweet_id)
    return tweet_id
