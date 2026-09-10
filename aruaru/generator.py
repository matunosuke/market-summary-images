"""Claude API で「エンジニアあるある」を生成する。"""

from __future__ import annotations

import json
import logging

import anthropic

from .tweet_text import MAX_WEIGHTED_LENGTH, TIMELINE_SOFT_LIMIT, Aruaru

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_ATTEMPTS = 4

# 日本語 1 文字 = 2 の重みなので、TIMELINE_SOFT_LIMIT は日本語 160 文字ぶん。
# 改行ぶんの余裕を見て、モデルには 150 文字を目安に指示する。
TARGET_JP_CHARS = 150

SYSTEM_PROMPT = f"""\
あなたは日本のソフトウェア開発現場を知り尽くした放送作家です。
X (旧 Twitter) に毎朝投稿する「エンジニアあるある」の会話ネタを 1 本つくります。

## 形式
- タイトルは、そのネタを一言で表す短いフレーズ (10 文字以内が目安)。
- 本文は 2 人 (まれに 3 人) の会話。4〜7 行。
- 各行は「話者」と「セリフ」に分ける。話者は 顧客 / SE / PM / 上司 / 新人 / 先輩 / 営業 / インフラ担当 / デザイナー など、場面に合う短い呼び名。
- 話が進むにつれて、一見ささいな要求の裏にある本当の重さが少しずつ見えてくる構成にする。
- 最後の 1 行が必ずオチになるようにする。技術的に「あー、それはそうなるよね」と現場の人間が頷く落とし方にすること。

## 制約
- タイトルと本文を合わせて、日本語 {TARGET_JP_CHARS} 文字以内に収めること。これを超えるとタイムライン上で折りたたまれ、オチが読まれなくなります。
- 絵文字、ハッシュタグ、URL、記号の装飾は一切使わない。
- セリフの中に鉤括弧「」を入れない (出力時に括弧で囲うため)。
- 実在の企業名、製品名、個人名は出さない。
- 誰かを見下したり、特定の職種を貶めたりしない。笑うのは状況であって人ではない。
- 技術的なディテールは正確に。それらしいだけの用語の羅列にしない。

## 出力例 (形式の参考。この内容そのものは使わないこと)
タイトル: ちょっとした修正
顧客「ちょっとだけ直したくて」
SE「どのあたりですか？」
顧客「ログイン画面、パスワードの入力欄をもう一つ増やすだけです」
SE「二段階認証ですか？」
顧客「そんな大したものじゃなくて、部署コードも入れるだけ」
SE「認証テーブルの設計から作り直しなんですよ、それ」
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "ネタのタイトル。鉤括弧は含めない。",
        },
        "lines": {
            "type": "array",
            "minItems": 4,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "description": "話者の呼び名"},
                    "text": {"type": "string", "description": "セリフ本文。鉤括弧は含めない。"},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "lines"],
    "additionalProperties": False,
}


def _build_user_message(recent_titles: list[str]) -> str:
    parts = ["今日ぶんの「エンジニアあるある」を 1 本つくってください。"]
    if recent_titles:
        listed = "\n".join(f"- {title}" for title in recent_titles)
        parts.append(
            "直近で投稿済みのタイトルです。同じ題材・同じオチの繰り返しは避けてください。\n" + listed
        )
    return "\n\n".join(parts)


class GenerationError(RuntimeError):
    """規定の回数を試しても投稿できるネタが得られなかった。"""


def generate(
    client: anthropic.Anthropic,
    recent_titles: list[str] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> Aruaru:
    """投稿できる長さに収まる「あるある」を 1 本返す。

    長さオーバーや不正な出力は、モデルにフィードバックして作り直させる。
    """
    messages: list[dict] = [
        {"role": "user", "content": _build_user_message(recent_titles or [])}
    ]
    last_error: str | None = None
    best_effort: Aruaru | None = None

    for attempt in range(1, max_attempts + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )

        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            raise GenerationError(f"モデルが生成を拒否しました: {detail}")

        raw = next((b.text for b in response.content if b.type == "text"), None)
        if raw is None:
            last_error = "テキストブロックが返りませんでした"
            logger.warning("試行 %d: %s", attempt, last_error)
            continue

        try:
            aruaru = Aruaru.from_payload(json.loads(raw))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            last_error = f"出力の形式が不正です: {exc}"
            logger.warning("試行 %d: %s", attempt, last_error)
        else:
            length = aruaru.weighted_length
            if length <= TIMELINE_SOFT_LIMIT:
                logger.info("試行 %d で生成成功 (重み付き %d)", attempt, length)
                return aruaru

            over = length - TIMELINE_SOFT_LIMIT
            last_error = (
                f"長すぎます (重み付き {length}、目安 {TIMELINE_SOFT_LIMIT})。"
                f"日本語で約 {(over + 1) // 2} 文字ぶん削ってください。"
            )
            logger.warning("試行 %d: %s", attempt, last_error)

            # 目安は超えたが投稿はできる。最後の試行なら、捨てずにこれを使う。
            if attempt == max_attempts and length <= MAX_WEIGHTED_LENGTH:
                logger.warning("目安は超えましたが、投稿可能なのでこれを採用します")
                return aruaru
            best_effort = aruaru

        if attempt < max_attempts:
            messages.append({"role": "assistant", "content": raw or "(空の応答)"})
            messages.append(
                {"role": "user", "content": f"{last_error}\nもう一度、作り直してください。"}
            )

    if best_effort is not None and best_effort.weighted_length <= MAX_WEIGHTED_LENGTH:
        logger.warning("目安に収まりませんでしたが、投稿可能なものを採用します")
        return best_effort

    raise GenerationError(f"{max_attempts} 回試しましたが生成できませんでした: {last_error}")
