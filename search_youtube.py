#!/usr/bin/env python3
"""
YouTube動画検索・フィルタリングスクリプト

YouTube Data API v3を使用して、特定条件に合う動画を検索し、
CSV形式で出力します。
"""

import os
import sys
import csv
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubeSearcher:
    """YouTube動画検索・フィルタリングクラス"""

    def __init__(self, api_key: str):
        """
        初期化

        Args:
            api_key: YouTube Data API v3のAPIキー
        """
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.channel_cache = {}  # チャンネル情報のキャッシュ

    def search_videos(
        self,
        keyword: str,
        max_results: int = 50,
        published_after_months: int = 6
    ) -> List[Dict]:
        """
        キーワードで動画を検索

        Args:
            keyword: 検索キーワード
            max_results: 取得する最大件数
            published_after_months: 何ヶ月前からの動画を取得するか

        Returns:
            検索結果のリスト（video_id, title, channel_id, channel_title を含む）
        """
        print(f"🔍 検索中: キーワード='{keyword}', 最大{max_results}件")

        # 投稿日の下限を計算（N ヶ月前）
        published_after = datetime.utcnow() - timedelta(days=30 * published_after_months)
        published_after_str = published_after.strftime('%Y-%m-%dT%H:%M:%SZ')

        results = []
        next_page_token = None

        try:
            while len(results) < max_results:
                # search.list APIを呼び出し
                request = self.youtube.search().list(
                    part='snippet',
                    q=keyword,
                    type='video',
                    publishedAfter=published_after_str,
                    maxResults=min(50, max_results - len(results)),  # 最大50件/回
                    pageToken=next_page_token,
                    order='relevance'
                )

                response = self._execute_with_retry(request)

                # 結果を整形
                for item in response.get('items', []):
                    results.append({
                        'video_id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'channel_id': item['snippet']['channelId'],
                        'channel_title': item['snippet']['channelTitle']
                    })

                # 次のページがあるかチェック
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

        except HttpError as e:
            if e.resp.status == 403:
                print("❌ エラー: API クオータを超過しました")
                sys.exit(1)
            else:
                raise

        print(f"✅ 検索完了: {len(results)}件の動画を取得")
        return results

    def get_video_statistics(self, video_ids: List[str]) -> Dict[str, int]:
        """
        動画の統計情報（再生回数など）を取得

        Args:
            video_ids: 動画IDのリスト

        Returns:
            video_id -> 再生回数 の辞書
        """
        print(f"📊 動画統計情報を取得中: {len(video_ids)}件")

        statistics = {}

        # 50件ずつバッチ処理
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]

            request = self.youtube.videos().list(
                part='statistics',
                id=','.join(batch)
            )

            response = self._execute_with_retry(request)

            for item in response.get('items', []):
                video_id = item['id']
                view_count = int(item['statistics'].get('viewCount', 0))
                statistics[video_id] = view_count

        print(f"✅ 動画統計情報の取得完了")
        return statistics

    def get_channel_subscribers(self, channel_ids: List[str]) -> Dict[str, Optional[int]]:
        """
        チャンネルの登録者数を取得（キャッシュあり）

        Args:
            channel_ids: チャンネルIDのリスト

        Returns:
            channel_id -> 登録者数 の辞書（取得できない場合はNone）
        """
        # キャッシュにない channel_id だけを取得
        uncached_ids = [cid for cid in channel_ids if cid not in self.channel_cache]

        if uncached_ids:
            print(f"👥 チャンネル登録者数を取得中: {len(uncached_ids)}件（キャッシュ: {len(channel_ids) - len(uncached_ids)}件）")

            # 50件ずつバッチ処理
            for i in range(0, len(uncached_ids), 50):
                batch = uncached_ids[i:i+50]

                request = self.youtube.channels().list(
                    part='statistics',
                    id=','.join(batch)
                )

                response = self._execute_with_retry(request)

                for item in response.get('items', []):
                    channel_id = item['id']
                    # hiddenSubscriberCount の場合は登録者数が取得できない
                    if item['statistics'].get('hiddenSubscriberCount', False):
                        self.channel_cache[channel_id] = None
                    else:
                        subscriber_count = int(item['statistics'].get('subscriberCount', 0))
                        self.channel_cache[channel_id] = subscriber_count

            print(f"✅ チャンネル登録者数の取得完了")

        # キャッシュから返す
        return {cid: self.channel_cache.get(cid) for cid in channel_ids}

    def filter_videos(
        self,
        videos: List[Dict],
        min_views: int,
        max_subscribers: int
    ) -> List[Dict]:
        """
        動画をフィルタリング

        Args:
            videos: 動画情報のリスト
            min_views: 最小再生回数
            max_subscribers: 最大登録者数

        Returns:
            条件に合致する動画のリスト
        """
        print(f"🔍 フィルタリング中: 再生回数>={min_views}, 登録者数<={max_subscribers}")

        # 動画IDとチャンネルIDを抽出
        video_ids = [v['video_id'] for v in videos]
        channel_ids = list(set([v['channel_id'] for v in videos]))

        # 統計情報を取得
        video_stats = self.get_video_statistics(video_ids)
        channel_subscribers = self.get_channel_subscribers(channel_ids)

        # フィルタリング
        filtered = []
        for video in videos:
            video_id = video['video_id']
            channel_id = video['channel_id']

            view_count = video_stats.get(video_id, 0)
            subscriber_count = channel_subscribers.get(channel_id)

            # 登録者数が取得できない場合は除外
            if subscriber_count is None:
                continue

            # 条件チェック
            if view_count >= min_views and subscriber_count <= max_subscribers:
                video['view_count'] = view_count
                video['subscriber_count'] = subscriber_count
                filtered.append(video)

        print(f"✅ フィルタリング完了: {len(filtered)}件が条件に合致")
        return filtered

    def export_to_csv(self, videos: List[Dict], keyword: str) -> str:
        """
        動画リストをCSVファイルに出力

        Args:
            videos: 動画情報のリスト
            keyword: 検索キーワード（ファイル名に使用）

        Returns:
            出力したファイル名
        """
        # ファイル名を生成（タイムスタンプ付き）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # ファイル名に使えない文字を置換
        safe_keyword = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in keyword)
        filename = f"youtube_results_{safe_keyword}_{timestamp}.csv"

        print(f"💾 CSV出力中: {filename}")

        # UTF-8 BOM付きで出力（Excel対応）
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)

            # ヘッダー
            writer.writerow(['動画タイトル', 'url', 'チャンネル名', '再生回数', '登録者数'])

            # データ
            for video in videos:
                url = f"https://www.youtube.com/watch?v={video['video_id']}"
                writer.writerow([
                    video['title'],
                    url,
                    video['channel_title'],
                    video['view_count'],
                    video['subscriber_count']
                ])

        print(f"✅ CSV出力完了: {filename}")
        return filename

    def _execute_with_retry(self, request, max_retries: int = 3):
        """
        APIリクエストをリトライ付きで実行

        Args:
            request: APIリクエスト
            max_retries: 最大リトライ回数

        Returns:
            APIレスポンス
        """
        for attempt in range(max_retries):
            try:
                return request.execute()
            except HttpError as e:
                if e.resp.status in [500, 503]:  # サーバーエラー
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数バックオフ
                        print(f"⚠️  サーバーエラー発生。{wait_time}秒後にリトライします...")
                        time.sleep(wait_time)
                    else:
                        raise
                else:
                    raise

        return None


def main():
    """メイン処理"""
    # 環境変数を読み込み
    load_dotenv()

    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(
        description='YouTube動画検索・フィルタリングスクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python search_youtube.py --keyword "料理"
  python search_youtube.py --keyword "プログラミング" --max-results 100
  python search_youtube.py --keyword "Python" --min-views 5000 --max-subscribers 10000
        """
    )

    parser.add_argument(
        '--keyword',
        required=True,
        help='検索キーワード（必須）'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=50,
        help='検索結果の最大取得数（デフォルト: 50）'
    )
    parser.add_argument(
        '--min-views',
        type=int,
        default=10000,
        help='最小再生回数（デフォルト: 10000）'
    )
    parser.add_argument(
        '--max-subscribers',
        type=int,
        default=5000,
        help='最大登録者数（デフォルト: 5000）'
    )

    args = parser.parse_args()

    # API Keyの確認
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("❌ エラー: YOUTUBE_API_KEY が設定されていません")
        print("   .envファイルに YOUTUBE_API_KEY=your_api_key を設定してください")
        sys.exit(1)

    print("=" * 60)
    print("YouTube動画検索・フィルタリングスクリプト")
    print("=" * 60)
    print(f"検索キーワード: {args.keyword}")
    print(f"最大取得数: {args.max_results}")
    print(f"最小再生回数: {args.min_views:,}")
    print(f"最大登録者数: {args.max_subscribers:,}")
    print(f"投稿期間: 半年以内（6ヶ月前〜現在）")
    print("=" * 60)
    print()

    try:
        # YouTubeSearcherインスタンスを作成
        searcher = YouTubeSearcher(api_key)

        # 動画を検索
        videos = searcher.search_videos(
            keyword=args.keyword,
            max_results=args.max_results,
            published_after_months=6
        )

        if not videos:
            print("⚠️  検索結果が0件です")
            return

        # フィルタリング
        filtered_videos = searcher.filter_videos(
            videos=videos,
            min_views=args.min_views,
            max_subscribers=args.max_subscribers
        )

        if not filtered_videos:
            print("⚠️  条件に合致する動画が見つかりませんでした")
            return

        # CSV出力
        filename = searcher.export_to_csv(filtered_videos, args.keyword)

        print()
        print("=" * 60)
        print(f"🎉 完了!")
        print(f"   抽出件数: {len(filtered_videos)}件")
        print(f"   出力ファイル: {filename}")
        print("=" * 60)

    except HttpError as e:
        print(f"❌ YouTube API エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
