# YouTube動画検索・フィルタリングスクリプト

YouTube Data API v3を使用して、特定の条件に合う動画を検索・フィルタリングし、CSV形式で出力するPythonスクリプトです。

## 機能

- キーワードによる動画検索
- 投稿日フィルタ（半年以内の動画）
- チャンネル登録者数によるフィルタ（デフォルト: 5,000人以下）
- 動画再生回数によるフィルタ（デフォルト: 10,000回以上）
- CSV形式での結果出力（Excel対応のUTF-8 BOM付き）
- チャンネル情報のキャッシュによる効率的なAPI利用
- エラーハンドリング・リトライ処理

## セットアップ

### 1. 必要なライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. YouTube Data API v3のAPIキー取得

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成（または既存のプロジェクトを選択）
3. 「APIとサービス」→「ライブラリ」から「YouTube Data API v3」を検索して有効化
4. 「APIとサービス」→「認証情報」から「認証情報を作成」→「APIキー」を選択
5. 作成されたAPIキーをコピー

詳細な手順は[公式ドキュメント](https://developers.google.com/youtube/v3/getting-started)を参照してください。

### 3. 環境変数の設定

`.env.example` をコピーして `.env` ファイルを作成し、取得したAPIキーを設定します。

```bash
cp .env.example .env
```

`.env` ファイルを編集:

```
YOUTUBE_API_KEY=ここに取得したAPIキーを貼り付け
```

**注意**: `.env` ファイルは `.gitignore` に追加し、リポジトリにコミットしないでください。

## 使い方

### 基本的な使い方

```bash
python search_youtube.py --keyword "料理"
```

### オプション指定

```bash
# 最大100件取得
python search_youtube.py --keyword "プログラミング" --max-results 100

# 再生回数と登録者数の条件を変更
python search_youtube.py --keyword "Python" --min-views 5000 --max-subscribers 10000
```

### コマンドライン引数

| 引数 | 説明 | デフォルト値 | 必須 |
|------|------|--------------|------|
| `--keyword` | 検索キーワード | - | ✅ |
| `--max-results` | 検索結果の最大取得数 | 50 | ❌ |
| `--min-views` | 最小再生回数 | 10000 | ❌ |
| `--max-subscribers` | 最大登録者数 | 5000 | ❌ |

### ヘルプ表示

```bash
python search_youtube.py --help
```

## 出力結果

### ファイル名

`youtube_results_{検索キーワード}_{実行日時}.csv`

例: `youtube_results_料理_20231115_143025.csv`

### CSV形式

| 列名 | 説明 |
|------|------|
| 動画タイトル | YouTubeの動画タイトル |
| url | 動画のURL（https://www.youtube.com/watch?v=...） |
| チャンネル名 | チャンネルの名前 |
| 再生回数 | 動画の再生回数 |
| 登録者数 | チャンネルの登録者数 |

### サンプル出力

```csv
動画タイトル,url,チャンネル名,再生回数,登録者数
初心者でも簡単！パスタの作り方,https://www.youtube.com/watch?v=abc123,料理チャンネル,15000,3000
時短レシピ！10分でできるカレー,https://www.youtube.com/watch?v=def456,クッキングTV,25000,4500
```

## API クオータ制限について

YouTube Data API v3には1日あたりのクオータ制限（デフォルト: 10,000ユニット/日）があります。

### 各API呼び出しのコスト

| API | コスト |
|-----|--------|
| `search.list` | 100ユニット |
| `videos.list` | 1ユニット |
| `channels.list` | 1ユニット |

### クオータの計算例

検索で50件の動画を取得し、フィルタリングする場合:

- `search.list`: 100ユニット × 1回 = 100ユニット
- `videos.list`: 1ユニット × 1回（50件バッチ） = 1ユニット
- `channels.list`: 1ユニット × 1回（チャンネル数による） = 約1ユニット

**合計**: 約102ユニット

1日に約98回（約4,900件）の動画を検索できる計算になります。

### クオータ節約の工夫

このスクリプトでは以下の工夫をしています:

1. **チャンネル情報のキャッシュ**: 同じチャンネルの情報は再取得しない
2. **バッチ処理**: 複数の動画・チャンネル情報を1回のAPIコールで取得（最大50件）

### クオータ超過時

クオータを超過すると、以下のエラーが表示されます:

```
❌ エラー: API クオータを超過しました
```

翌日（太平洋標準時の午前0時）にクオータがリセットされます。

クオータの使用状況は [Google Cloud Console](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas) で確認できます。

## トラブルシューティング

### API Keyが設定されていないエラー

```
❌ エラー: YOUTUBE_API_KEY が設定されていません
```

→ `.env` ファイルに正しくAPIキーが設定されているか確認してください。

### クオータ超過エラー

```
❌ エラー: API クオータを超過しました
```

→ 翌日まで待つか、Google Cloud Consoleでクオータの増量をリクエストしてください。

### 検索結果が0件

```
⚠️  検索結果が0件です
```

→ キーワードを変更するか、投稿期間を広げてみてください。

### 条件に合致する動画が0件

```
⚠️  条件に合致する動画が見つかりませんでした
```

→ `--min-views` や `--max-subscribers` の条件を緩和してみてください。

## 注意事項

- **登録者数非公開のチャンネル**: 登録者数を非公開にしているチャンネルの動画は除外されます
- **API利用規約**: YouTube APIの[利用規約](https://developers.google.com/youtube/terms/api-services-terms-of-service)を遵守してください
- **商用利用**: 商用利用する場合は、YouTubeの利用規約を確認してください
- **スクレイピング禁止**: このスクリプトは公式APIを使用していますが、過度な使用は控えてください

## ライセンス

MIT License

## 開発者向け情報

### ファイル構成

```
youtube_search/
├── search_youtube.py      # メインスクリプト
├── .env.example           # API Key設定例
├── .env                   # API Key（git管理外）
├── requirements.txt       # 依存ライブラリ
└── README.md             # このファイル
```

### 主要クラス・メソッド

- `YouTubeSearcher`: メインクラス
  - `search_videos()`: キーワードで動画を検索
  - `get_video_statistics()`: 動画の再生回数を取得
  - `get_channel_subscribers()`: チャンネルの登録者数を取得（キャッシュあり）
  - `filter_videos()`: 条件に合う動画をフィルタリング
  - `export_to_csv()`: CSV形式で出力

## サポート

問題が発生した場合は、GitHubのIssuesで報告してください。
