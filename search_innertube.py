#!/usr/bin/env python3
"""
YouTube InnerTube APIバズ動画発見ツール

InnerTube API（非公式）を使用して、キーワードなしで大量の動画を取得し、
以下の条件でフィルタリングしてバズ動画を発見します：
- 投稿日: 半年以内（2025年5月12日以降）
- チャンネル登録者数: 10,000人未満
- 再生回数: チャンネル登録者数の3倍以上
"""

import os
import sys
import csv
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
from tqdm import tqdm

try:
    import innertube
except ImportError:
    print("❌ エラー: innertubeライブラリがインストールされていません")
    print("   以下のコマンドでインストールしてください:")
    print("   pip install innertube")
    sys.exit(1)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InnerTubeSearcher:
    """InnerTube APIを使用した動画検索クラス"""

    def __init__(self):
        """初期化"""
        print("\n" + "="*60)
        print("🔧 InnerTube APIクライアントを初期化中...")
        print("="*60 + "\n")

        try:
            self.client = innertube.InnerTube("WEB")
            print("✅ InnerTube クライアント初期化完了")
        except Exception as e:
            print(f"❌ InnerTube クライアントの初期化に失敗: {e}")
            raise

        self.video_ids: Set[str] = set()  # 重複排除用
        self.channel_cache: Dict[str, Optional[int]] = {}  # チャンネル情報キャッシュ

    def fetch_trending_videos(self) -> List[str]:
        """
        Trending動画のIDを取得

        Returns:
            動画IDのリスト
        """
        print("📊 Trending動画を取得中...")

        try:
            # Trendingページを取得
            # paramsを削除してシンプルにbrowse_idだけで試す
            data = self.client.browse("FEtrending")

            # デバッグ用: レスポンスを保存
            self._save_debug_response(data, 'trending_response.json')

            # 動画IDを抽出
            video_ids = self.parse_video_ids(data)

            print(f"✅ Trending動画を {len(video_ids)} 件取得しました")
            return video_ids

        except Exception as e:
            print(f"⚠️  Trending動画の取得に失敗: {e}")
            logger.error(f"Trending動画取得エラー: {e}", exc_info=True)
            return []

    def fetch_home_feed_videos(self) -> List[str]:
        """
        ホームフィード（おすすめ）動画のIDを取得

        Returns:
            動画IDのリスト
        """
        print("🏠 ホームフィード動画を取得中...")

        try:
            # ホームフィード（おすすめ）を取得
            data = self.client.browse("FEwhat_to_watch")

            # デバッグ用: レスポンスを保存
            self._save_debug_response(data, 'home_feed_response.json')

            # 動画IDを抽出
            video_ids = self.parse_video_ids(data)

            print(f"✅ ホームフィード動画を {len(video_ids)} 件取得しました")
            return video_ids

        except Exception as e:
            print(f"⚠️  ホームフィード動画の取得に失敗: {e}")
            logger.error(f"ホームフィード取得エラー: {e}", exc_info=True)
            return []

    def parse_video_ids(self, response: dict) -> List[str]:
        """
        レスポンスから動画IDを再帰的に抽出

        Args:
            response: InnerTube APIのレスポンス

        Returns:
            動画IDのリスト
        """
        video_ids = []

        try:
            video_ids = self._recursive_find_video_ids(response)
            video_ids = list(set(video_ids))  # 重複削除
        except Exception as e:
            print(f"⚠️  動画IDのパースに失敗: {e}")
            logger.error(f"パースエラー: {e}", exc_info=True)

        return video_ids

    def _recursive_find_video_ids(self, obj, video_ids=None) -> List[str]:
        """
        再帰的に動画IDを探索

        Args:
            obj: 探索対象のオブジェクト（dict, list, その他）
            video_ids: 動画IDを蓄積するリスト

        Returns:
            動画IDのリスト
        """
        if video_ids is None:
            video_ids = []

        if isinstance(obj, dict):
            # videoIdキーが見つかったら追加
            if 'videoId' in obj:
                video_id = obj['videoId']
                if isinstance(video_id, str) and len(video_id) == 11:  # YouTube動画IDは11文字
                    video_ids.append(video_id)

            # 全てのキーを再帰的に探索
            for key, value in obj.items():
                self._recursive_find_video_ids(value, video_ids)

        elif isinstance(obj, list):
            # リストの各要素を再帰的に探索
            for item in obj:
                self._recursive_find_video_ids(item, video_ids)

        return video_ids

    def get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        動画の詳細情報を取得

        InnerTube APIのplayerエンドポイントを使用して、
        動画タイトル、チャンネル名、再生回数、投稿日などを取得します。

        Args:
            video_ids: 動画IDのリスト

        Returns:
            動画情報の辞書のリスト
        """
        print(f"\n📝 動画詳細を取得中: {len(video_ids)} 件")

        videos = []

        for video_id in tqdm(video_ids, desc="動画詳細取得"):
            try:
                # レート制限対策
                time.sleep(0.3)

                # playerエンドポイントで詳細取得
                player_data = self.client.player(video_id=video_id)

                # videoDetailsから情報を抽出
                video_details = player_data.get('videoDetails', {})

                if not video_details:
                    logger.warning(f"動画 {video_id} の詳細が取得できませんでした")
                    continue

                # 基本情報を抽出
                title = video_details.get('title', '')
                channel_id = video_details.get('channelId', '')
                channel_name = video_details.get('author', '')
                view_count = int(video_details.get('viewCount', 0))
                length_seconds = int(video_details.get('lengthSeconds', 0))

                # 投稿日はmicroformatから取得
                microformat = player_data.get('microformat', {}).get('playerMicroformatRenderer', {})
                publish_date_str = microformat.get('publishDate', '')

                # 投稿日をdatetimeに変換
                if publish_date_str:
                    try:
                        publish_date = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))
                    except ValueError:
                        publish_date = None
                else:
                    publish_date = None

                videos.append({
                    'video_id': video_id,
                    'title': title,
                    'channel_id': channel_id,
                    'channel_name': channel_name,
                    'view_count': view_count,
                    'length_seconds': length_seconds,
                    'publish_date': publish_date
                })

            except Exception as e:
                logger.warning(f"動画 {video_id} の詳細取得に失敗: {e}")
                continue

        print(f"✅ 動画詳細取得完了: {len(videos)} 件")
        return videos

    def get_channel_subscribers(self, channel_ids: List[str]) -> Dict[str, Optional[int]]:
        """
        チャンネルの登録者数を取得（キャッシュあり）

        Args:
            channel_ids: チャンネルIDのリスト

        Returns:
            channel_id -> 登録者数 の辞書（取得できない場合はNone）
        """
        # キャッシュにないchannel_idだけを取得
        uncached_ids = [cid for cid in channel_ids if cid not in self.channel_cache]

        if uncached_ids:
            print(f"\n👥 チャンネル登録者数を取得中: {len(uncached_ids)} 件（キャッシュ: {len(channel_ids) - len(uncached_ids)} 件）")

            for channel_id in tqdm(uncached_ids, desc="チャンネル情報取得"):
                try:
                    # レート制限対策
                    time.sleep(0.3)

                    # browseエンドポイントでチャンネル情報を取得
                    channel_data = self.client.browse(browse_id=channel_id)

                    # ヘッダーから登録者数を抽出
                    header = channel_data.get('header', {})

                    # c4TabbedHeaderRendererまたはpageHeaderRendererから登録者数を取得
                    subscriber_count = None

                    if 'c4TabbedHeaderRenderer' in header:
                        subscriber_text = header['c4TabbedHeaderRenderer'].get('subscriberCountText', {})
                        if 'simpleText' in subscriber_text:
                            subscriber_count = self._parse_subscriber_count(subscriber_text['simpleText'])

                    elif 'pageHeaderRenderer' in header:
                        content = header['pageHeaderRenderer'].get('content', {})
                        if 'pageHeaderViewModel' in content:
                            metadata = content['pageHeaderViewModel'].get('metadata', {})
                            if 'contentMetadataViewModel' in metadata:
                                metadata_rows = metadata['contentMetadataViewModel'].get('metadataRows', [])
                                for row in metadata_rows:
                                    if 'metadataParts' in row:
                                        for part in row['metadataParts']:
                                            if 'text' in part and 'text' in part['text']:
                                                text = part['text']['text']
                                                if '登録者' in text or 'subscriber' in text.lower():
                                                    subscriber_count = self._parse_subscriber_count(text)
                                                    break

                    self.channel_cache[channel_id] = subscriber_count

                except Exception as e:
                    logger.warning(f"チャンネル {channel_id} の登録者数取得に失敗: {e}")
                    self.channel_cache[channel_id] = None
                    continue

            print(f"✅ チャンネル登録者数取得完了")

        # キャッシュから返す
        return {cid: self.channel_cache.get(cid) for cid in channel_ids}

    def _parse_subscriber_count(self, text: str) -> Optional[int]:
        """
        登録者数のテキストを数値に変換

        例: "1.5万人の登録者" -> 15000
            "1.2K subscribers" -> 1200

        Args:
            text: 登録者数のテキスト

        Returns:
            登録者数（取得できない場合はNone）
        """
        import re

        # 数値部分を抽出
        match = re.search(r'([\d.,]+)\s*([万千KkMm])?', text)
        if not match:
            return None

        number_str = match.group(1).replace(',', '').replace('.', '')
        multiplier_str = match.group(2)

        try:
            number = float(match.group(1).replace(',', ''))
        except ValueError:
            return None

        # 単位に応じて乗算
        if multiplier_str:
            if multiplier_str in ['万', 'K', 'k']:
                number *= 10000 if multiplier_str == '万' else 1000
            elif multiplier_str in ['千']:
                number *= 1000
            elif multiplier_str in ['M', 'm']:
                number *= 1000000

        return int(number)

    def filter_videos(self, videos: List[Dict]) -> List[Dict]:
        """
        条件に合う動画をフィルタリング

        条件:
        - 投稿日: 半年以内
        - チャンネル登録者数: 10,000人未満
        - 再生回数: 登録者数 × 3 以上

        Args:
            videos: 動画情報のリスト

        Returns:
            条件に合致する動画のリスト
        """
        print("\n🔎 条件に合う動画をフィルタリング中...")

        # 半年前の日付
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)

        # チャンネルIDを抽出
        channel_ids = list(set([v['channel_id'] for v in videos if v.get('channel_id')]))

        # 登録者数を取得
        channel_subscribers = self.get_channel_subscribers(channel_ids)

        # フィルタリング
        filtered = []
        stats = {
            'total': len(videos),
            'recent': 0,
            'small_channel': 0,
            'buzz': 0
        }

        for video in videos:
            channel_id = video.get('channel_id')
            publish_date = video.get('publish_date')
            view_count = video.get('view_count', 0)

            # 登録者数を取得
            subscriber_count = channel_subscribers.get(channel_id)

            # 登録者数が取得できない場合はスキップ
            if subscriber_count is None:
                continue

            # 投稿日が取得できない、または半年以内でない場合はスキップ
            if not publish_date or publish_date < six_months_ago:
                continue

            stats['recent'] += 1

            # 登録者数が10,000人以上の場合はスキップ
            if subscriber_count >= 10000:
                continue

            stats['small_channel'] += 1

            # 再生回数が登録者数の3倍未満の場合はスキップ
            if view_count < subscriber_count * 3:
                continue

            stats['buzz'] += 1

            # 条件に合致した動画を追加
            video['subscriber_count'] = subscriber_count
            filtered.append(video)

        print(f"\n📊 フィルタリング結果:")
        print(f"  - 総動画数: {stats['total']} 件")
        print(f"  - 半年以内: {stats['recent']} 件")
        print(f"  - 登録者1万人未満: {stats['small_channel']} 件")
        print(f"  - 再生回数3倍以上（バズ動画）: {stats['buzz']} 件")

        return filtered

    def export_to_csv(self, videos: List[Dict], filename: str):
        """
        動画リストをCSVファイルに出力

        Args:
            videos: 動画情報のリスト
            filename: 出力ファイル名
        """
        print(f"\n💾 CSV出力中: {filename}")

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
                    video['channel_name'],
                    video['view_count'],
                    video['subscriber_count']
                ])

        print(f"✅ CSV出力完了: {filename}")

    def _save_debug_response(self, data: dict, filename: str):
        """
        デバッグ用: APIレスポンスをJSONファイルに保存

        Args:
            data: APIレスポンス
            filename: 出力ファイル名
        """
        try:
            debug_dir = os.path.join(os.path.dirname(__file__), 'debug')
            os.makedirs(debug_dir, exist_ok=True)

            filepath = os.path.join(debug_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"デバッグレスポンスを保存: {filepath}")
        except Exception as e:
            logger.warning(f"デバッグレスポンスの保存に失敗: {e}")


def main():
    """メイン処理"""
    print("="*60)
    print("🚀 YouTube InnerTube API バズ動画発見ツール")
    print("="*60)
    print()
    print("【検索条件】")
    print("  - 投稿日: 半年以内（2025年5月12日以降）")
    print("  - チャンネル登録者数: 10,000人未満")
    print("  - 再生回数: チャンネル登録者数の3倍以上")
    print()
    print("【データソース】")
    print("  - YouTube Trending動画")
    print("  - YouTube ホームフィード（おすすめ）")
    print()
    print("="*60)
    print()

    try:
        # InnerTubeSearcherインスタンスを作成
        searcher = InnerTubeSearcher()

        # ステップ1: 動画ID収集
        print("\n" + "="*60)
        print("📡 ステップ1: 動画ID収集")
        print("="*60)

        # Trending動画を取得
        trending_ids = searcher.fetch_trending_videos()

        # ホームフィード動画を取得
        home_ids = searcher.fetch_home_feed_videos()

        # 重複削除
        all_video_ids = list(set(trending_ids + home_ids))
        print(f"\n✅ 合計 {len(all_video_ids)} 件の動画IDを収集（重複除去後）")

        if not all_video_ids:
            print("⚠️  動画IDが1件も取得できませんでした")
            return

        # ステップ2: 詳細情報取得
        print("\n" + "="*60)
        print("📝 ステップ2: 動画詳細情報取得")
        print("="*60)

        videos = searcher.get_video_details(all_video_ids)

        if not videos:
            print("⚠️  動画詳細が1件も取得できませんでした")
            return

        # ステップ3: フィルタリング
        print("\n" + "="*60)
        print("🔎 ステップ3: フィルタリング")
        print("="*60)

        filtered_videos = searcher.filter_videos(videos)

        if not filtered_videos:
            print("\n⚠️  条件に合致する動画が見つかりませんでした")
            return

        # ステップ4: CSV出力
        print("\n" + "="*60)
        print("💾 ステップ4: CSV出力")
        print("="*60)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"youtube_innertube_results_{timestamp}.csv"

        searcher.export_to_csv(filtered_videos, filename)

        # 完了メッセージ
        print("\n" + "="*60)
        print("🎉 完了!")
        print("="*60)
        print(f"   抽出件数: {len(filtered_videos)} 件")
        print(f"   出力ファイル: {filename}")
        print("="*60)
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        logger.error("予期しないエラー", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
