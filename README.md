# 毎朝のエンジニアあるある自動投稿

毎朝 8:00 (JST) に「エンジニアあるある」を Claude に 1 本考えさせて、X に投稿します。

```
エンジニアあるある「すぐ終わる調査」

上司「見るだけだから今日中でいいよね」
SE「本番のログですよね」
上司「エラーが出た時間帯だけでいいよ」
SE「そこ、ちょうどローテーションが走ってます」
上司「じゃあ残ってないの」
SE「復元するので、まず権限申請からです」
```

## 使い方

```bash
pip install -r requirements.txt

python -m aruaru --dry-run   # 生成して表示するだけ (投稿しない)
python -m aruaru             # 生成して X に投稿する
```

`--dry-run` は X の認証情報なしで動きます (Claude の API キーは必要)。

## 必要な環境変数

GitHub Actions で動かす場合は、リポジトリの Settings → Secrets and variables → Actions に
同名の Secret として登録してください。

| 環境変数 | 用途 |
| --- | --- |
| `ANTHROPIC_API_KEY` | ネタの生成 (Claude API) |
| `X_API_KEY` | X アプリの API Key (Consumer Key) |
| `X_API_SECRET` | X アプリの API Key Secret |
| `X_ACCESS_TOKEN` | 投稿するアカウントの Access Token |
| `X_ACCESS_TOKEN_SECRET` | 投稿するアカウントの Access Token Secret |

X 側は、Developer Portal でアプリの権限を **Read and write** にしたうえで
Access Token を発行し直す必要があります (権限変更前に発行したトークンでは投稿できません)。

## 自動実行

`.github/workflows/daily-aruaru.yml` が `0 23 * * *` (UTC) = 毎朝 8:00 (JST) に動きます。

- GitHub Actions の cron は混雑状況によって数分〜十数分遅れて起動することがあります。
- スケジュール実行はデフォルトブランチのワークフローだけが対象です。
- Actions タブから手動実行もできます。`dry_run` を on にすると投稿せず生成結果だけ確認できます。

## 文字数について

X の文字数は「重み付き文字数」で数えられ、日本語は 1 文字 = 2 として扱われます。
このリポジトリは **X Premium (長文投稿が使えるアカウント)** を前提に、
`aruaru/tweet_text.py` の `MAX_WEIGHTED_LENGTH` を 25000 にしています。
Premium でないアカウントで運用する場合は、ここを **280** に戻してください。

ただし上限とは別に、タイムライン上で「もっと見る」に折りたたまれない長さの目安として
`TIMELINE_SOFT_LIMIT` (320 = 日本語 160 文字ぶん) を置いています。オチが折りたたみの
向こうに隠れるとネタとして成立しないためです。

生成時はこの目安を超えると、「何文字ぶん削ってほしいか」をモデルに返して作り直させます
(最大 4 回)。それでも収まらなかった場合は、投稿上限に収まってさえいれば捨てずに投稿します。
このやり取りは `--verbose` を付けるとログに出ます。

## 重複回避

投稿したネタは `data/history.json` に追記され、次回以降は直近 30 件のタイトルを
プロンプトに渡して「同じ題材・同じオチ」を避けさせます。
ワークフローは投稿後にこのファイルをコミットして戻します。

## 構成

| ファイル | 役割 |
| --- | --- |
| `aruaru/generator.py` | Claude API でネタを生成 (構造化出力 + 長さ超過時の再生成) |
| `aruaru/tweet_text.py` | X の重み付き文字数カウントと投稿テキストの組み立て |
| `aruaru/x_client.py` | X API v2 への投稿 (OAuth 1.0a) |
| `aruaru/history.py` | 投稿履歴の読み書き |
| `aruaru/cli.py` | コマンドラインの入口 |

## テスト

```bash
python -m pytest tests/ -q
```
