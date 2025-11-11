# YouTube動画検索・フィルタリングスクリプト（OAuth2認証版）

YouTube Data API v3を使用して、特定の条件に合う動画を検索・フィルタリングし、CSV形式で出力するPythonスクリプトです。

**⚠️ OAuth2認証対応版**: YouTube Data API v3のsearch.listエンドポイントがAPI Key認証をサポートしなくなったため、OAuth2認証に対応しました。

## 機能

- キーワードによる動画検索
- 投稿日フィルタ（半年以内の動画）
- チャンネル登録者数によるフィルタ（デフォルト: 5,000人以下）
- 動画再生回数によるフィルタ（デフォルト: 10,000回以上）
- CSV形式での結果出力（Excel対応のUTF-8 BOM付き）
- チャンネル情報のキャッシュによる効率的なAPI利用
- エラーハンドリング・リトライ処理
- **OAuth2認証**（初回実行後は自動認証）

## セットアップ

### 1. 必要なライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Consoleでの設定

#### 2-1. プロジェクトの作成とAPI有効化

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成（または既存のプロジェクトを選択）
3. 「APIとサービス」→「ライブラリ」から「YouTube Data API v3」を検索して有効化

#### 2-2. OAuth2クライアントIDの作成

1. 「APIとサービス」→「認証情報」を開く
2. 「認証情報を作成」→「OAuth クライアント ID」を選択
3. 同意画面の設定を求められた場合:
   - 「OAuth 同意画面」タブをクリック
   - ユーザータイプ: 「外部」を選択（個人利用の場合）
   - アプリ名、ユーザーサポートメール、デベロッパー連絡先を入力
   - スコープは設定不要（デフォルトのまま）
   - 「保存して次へ」で完了
4. 「認証情報」タブに戻り、再度「認証情報を作成」→「OAuth クライアント ID」を選択
5. アプリケーションの種類: **「デスクトップアプリ」**を選択
6. 名前を入力（例: YouTube Search Script）
7. 「作成」をクリック

#### 2-3. 認証情報のダウンロード

1. 作成したOAuth クライアントIDの右側にある「⬇ダウンロード」アイコンをクリック
2. JSONファイルがダウンロードされる
3. ダウンロードしたJSONファイルを `credentials.json` にリネーム
4. このスクリプトと同じディレクトリに配置

```bash
# ファイル構成例
youtube_search/
├── search_youtube.py
├── credentials.json  ← ここに配置
├── requirements.txt
└── README.md
```

**注意**: `credentials.json` は機密情報です。Gitにコミットしたり、他人と共有しないでください。

### 3. 初回実行（OAuth2認証）

初回実行時にブラウザが自動で開き、Googleアカウントでの認証が求められます。

```bash
python search_youtube.py --keyword "料理"
```

#### 認証フロー

1. スクリプトを実行すると、ブラウザが自動で開きます
2. Googleアカウントでログイン
3. 「このアプリは確認されていません」という警告が表示される場合:
   - 「詳細」をクリック
   - 「（アプリ名）に移動（安全ではないページ）」をクリック
   - これは個人利用のため問題ありません
4. 「YouTube Data API v3 YouTube アカウントの閲覧」の権限を許可
5. 「許可」をクリック
6. 認証完了後、`token.json` が自動生成されます

### 4. 2回目以降の実行

`token.json` が保存されているため、ブラウザを開かずに自動認証されます。

```bash
python search_youtube.py --keyword "料理"
```

トークンが期限切れの場合は自動更新されます。

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

### credentials.json が見つからないエラー

```
❌ エラー: credentials.json が見つかりません
```

→ Google Cloud ConsoleからOAuth2クライアントIDをダウンロードし、`credentials.json` にリネームしてスクリプトと同じディレクトリに配置してください。

### OAuth2認証失敗エラー

```
❌ OAuth2認証に失敗しました
```

→ ブラウザで「許可」をクリックしたか確認してください。認証をキャンセルすると失敗します。

### token.json の読み込みエラー

```
⚠️ token.jsonの読み込みに失敗しました
```

→ `token.json` が破損している可能性があります。削除して再度認証してください。

```bash
rm token.json
python search_youtube.py --keyword "料理"
```

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
- **OAuth2認証**:
  - `credentials.json` と `token.json` は機密情報です。Gitにコミットしたり、他人と共有しないでください
  - 「このアプリは確認されていません」という警告は、個人利用の場合は問題ありません
  - 本番環境や不特定多数に公開する場合は、Googleの審査が必要です

## ライセンス

MIT License

## 開発者向け情報

### ファイル構成

```
youtube_search/
├── search_youtube.py      # メインスクリプト（OAuth2認証版）
├── credentials.json       # OAuth2クライアントID（git管理外）
├── token.json            # アクセストークン（自動生成・git管理外）
├── requirements.txt       # 依存ライブラリ
├── .gitignore            # git除外ファイル設定
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
