"""資料の取り込み・予約配信・未対応の検知などを行うバックグラウンド処理"""

import logging
import time

from app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 5


def run_once() -> None:
    # TODO: 取り込み待ちの資料を処理する（テキスト抽出→チャンク分割→ベクトル化）
    pass


def main() -> None:
    app = create_app()
    log.info("started")
    with app.app_context():
        while True:
            run_once()
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
