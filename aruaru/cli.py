"""コマンドラインからの実行口。

  python -m aruaru --dry-run   # 生成だけして投稿しない
  python -m aruaru             # 生成して X に投稿する
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

from . import history, x_client
from .generator import GenerationError, generate
from .tweet_text import MAX_WEIGHTED_LENGTH, TIMELINE_SOFT_LIMIT, Aruaru

JST = timezone(timedelta(hours=9))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aruaru",
        description="「エンジニアあるある」を生成して X に投稿する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="生成した内容を表示するだけで、投稿も履歴の更新もしない",
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        default=history.DEFAULT_PATH,
        help=f"履歴ファイルのパス (既定: {history.DEFAULT_PATH})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="詳細なログを出す"
    )
    return parser.parse_args(argv)


def _report(aruaru: Aruaru, *, dry_run: bool) -> None:
    text = aruaru.render()
    label = "DRY RUN (投稿しません)" if dry_run else "投稿内容"
    print(f"===== {label} =====")
    print(text)
    print("=" * 32)
    length = aruaru.weighted_length
    note = "" if length <= TIMELINE_SOFT_LIMIT else "  ※タイムラインで折りたたまれます"
    print(
        f"X 文字数(重み付き): {length}  "
        f"[折りたたみの目安 {TIMELINE_SOFT_LIMIT} / 投稿上限 {MAX_WEIGHTED_LENGTH}]{note}"
    )
    print(f"実文字数: {len(text)}、{len(aruaru.lines)} 行")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # 投稿するつもりなら、生成にお金を使う前に認証情報を確かめる
    if not args.dry_run:
        missing = x_client.missing_credentials()
        if missing:
            print(
                "X の認証情報が足りません: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 2

    entries = history.load(args.history_file)

    try:
        client = anthropic.Anthropic()
        aruaru = generate(client, recent_titles=history.recent_titles(entries))
    except GenerationError as exc:
        print(f"生成に失敗しました: {exc}", file=sys.stderr)
        return 1
    except anthropic.AnthropicError as exc:
        print(f"Claude API の呼び出しに失敗しました: {exc}", file=sys.stderr)
        return 1
    except TypeError as exc:
        # SDK は認証情報が見つからないとき、リクエスト時に TypeError を投げる
        if "authentication method" not in str(exc):
            raise
        print(
            "Claude API の認証情報が見つかりません。"
            "環境変数 ANTHROPIC_API_KEY を設定してください。",
            file=sys.stderr,
        )
        return 2

    _report(aruaru, dry_run=args.dry_run)

    if args.dry_run:
        return 0

    try:
        tweet_id = x_client.post_tweet(aruaru.render())
    except (x_client.XCredentialsError, x_client.XPostError) as exc:
        print(f"投稿に失敗しました: {exc}", file=sys.stderr)
        return 1

    history.append(
        aruaru, tweet_id, datetime.now(JST).date(), path=args.history_file
    )
    print(f"投稿しました: https://x.com/i/web/status/{tweet_id}")
    return 0
