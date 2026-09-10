import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aruaru.tweet_text import Aruaru, Line, fits_in_tweet, weighted_length


def test_ascii_counts_one_each():
    assert weighted_length("hello") == 5


def test_japanese_counts_two_each():
    assert weighted_length("あいうえお") == 10


def test_newline_counts_one():
    assert weighted_length("あ\nい") == 5


def test_url_counts_as_23():
    assert weighted_length("https://example.com/a/very/long/path/indeed") == 23


def test_140_japanese_chars_is_the_limit():
    assert fits_in_tweet("あ" * 140)
    assert not fits_in_tweet("あ" * 141)


def test_render_matches_expected_format():
    aruaru = Aruaru(
        title="ちょっとした修正",
        lines=(
            Line("顧客", "ちょっとだけ直したくて"),
            Line("SE", "どのあたりですか？"),
        ),
    )
    assert aruaru.render() == (
        "エンジニアあるある「ちょっとした修正」\n"
        "\n"
        "顧客「ちょっとだけ直したくて」\n"
        "SE「どのあたりですか？」"
    )


def test_from_payload_rejects_too_few_lines():
    payload = {"title": "x", "lines": [{"speaker": "a", "text": "b"}]}
    try:
        Aruaru.from_payload(payload)
    except ValueError:
        return
    raise AssertionError("行数が少なすぎる入力は弾かれるべき")
