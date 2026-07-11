import os
import time
from datetime import datetime


def get_file_modified_time_difference(file_path: str) -> int | None:
    """
    ファイルの最終更新時刻と現在時刻の差を秒単位で計算する。

    Args:
        file_path (str): ファイルのパス

    Returns:
        int: 最終更新時刻と現在時刻の差（秒）。
            ファイルが存在しない、またはアクセスできない場合はNoneを返す。
    """
    try:
        # ファイルの最終更新時刻をタイムスタンプ（秒）で取得
        file_modified_timestamp = os.path.getmtime(file_path)

        # ファイルの最終更新時刻をdatetimeオブジェクトに変換
        file_modified_datetime = datetime.fromtimestamp(file_modified_timestamp)

        # 現在時刻を取得
        current_datetime = datetime.now()

        # 時刻の差を計算（秒単位）
        time_difference = (current_datetime - file_modified_datetime).total_seconds()

        return int(time_difference)  # 秒単位の差を整数で返す

    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {file_path}")
        return None
    except PermissionError:
        print(f"エラー: ファイルへのアクセス権がありません: {file_path}")
        return None
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None


if __name__ == "__main__":
    file_path = "/var/www/nginx/gekiyasutokka.com/wp-content/cache/all/index.htmla"
    time_dif = get_file_modified_time_difference(file_path)
    if time_dif is None or time_dif > 60 * 5:
        print("古いのでファイルを更新する")
    else:
        print("新しいのでファイルを更新しない")
