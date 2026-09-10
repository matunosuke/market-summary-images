"""X (Twitter) の重み付き文字数カウントと、投稿テキストの組み立て。

X の文字数は「重み付き文字数」で数える (twitter-text config v3)。
ASCII などは 1 文字ぶん、日本語などは 2 文字ぶんとして扱われる。
つまり日本語だけなら、上限の数字の半分が実際に書ける文字数になる。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 投稿の上限 (重み付き)。X Premium の長文投稿ぶんを見込んで 25000。
# Premium でないアカウントに切り替える場合は 280 に戻すこと。
MAX_WEIGHTED_LENGTH = 25000

# タイムライン上でこれを超えると「もっと見る」で折りたたまれる。
# オチが隠れるとネタとして成立しないので、生成時はこの範囲を目安にする
# (日本語 160 文字ぶん)。上限ではなく目安なので、超えても投稿はできる。
TIMELINE_SOFT_LIMIT = 320

# twitter-text configuration v3
SCALE = 100
DEFAULT_WEIGHT = 200
TRANSFORMED_URL_LENGTH = 23

# この範囲のコードポイントだけ重み 100 (= 1 文字ぶん)。それ以外は 200 (= 2 文字ぶん)。
LIGHT_RANGES = (
    (0x0000, 0x10FF),
    (0x2000, 0x200D),
    (0x2010, 0x201F),
    (0x2032, 0x2037),
)

# t.co に短縮される URL は、実際の長さに関わらず 23 文字として数えられる
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _char_weight(ch: str) -> int:
    cp = ord(ch)
    for lo, hi in LIGHT_RANGES:
        if lo <= cp <= hi:
            return SCALE
    return DEFAULT_WEIGHT


def weighted_length(text: str) -> int:
    """X が数えるのと同じ重み付き文字数を返す (上限 280)。"""
    # URL は一律 23 文字として数えるので、先に取り除いて別勘定する
    urls = URL_RE.findall(text)
    rest = URL_RE.sub("", text)
    total = sum(_char_weight(ch) for ch in rest)
    return total // SCALE + len(urls) * TRANSFORMED_URL_LENGTH


def fits_in_tweet(text: str) -> bool:
    return 0 < weighted_length(text) <= MAX_WEIGHTED_LENGTH


@dataclass(frozen=True)
class Line:
    """会話の 1 行 (話者とセリフ)。"""

    speaker: str
    text: str

    def render(self) -> str:
        return f"{self.speaker}「{self.text}」"


@dataclass(frozen=True)
class Aruaru:
    """1 本ぶんの「エンジニアあるある」。"""

    title: str
    lines: tuple[Line, ...]

    def render(self) -> str:
        head = f"エンジニアあるある「{self.title}」"
        body = "\n".join(line.render() for line in self.lines)
        return f"{head}\n\n{body}"

    @property
    def weighted_length(self) -> int:
        return weighted_length(self.render())

    @classmethod
    def from_payload(cls, payload: dict) -> "Aruaru":
        """モデルが返した JSON を Aruaru に変換する。"""
        title = str(payload["title"]).strip()
        lines = tuple(
            Line(speaker=str(item["speaker"]).strip(), text=str(item["text"]).strip())
            for item in payload["lines"]
        )
        if not title:
            raise ValueError("title が空です")
        if len(lines) < 3:
            raise ValueError(f"会話が短すぎます (行数={len(lines)})")
        for line in lines:
            if not line.speaker or not line.text:
                raise ValueError(f"空の行があります: {line!r}")
        return cls(title=title, lines=lines)
