"""資料の取り込み・予約配信・未対応の検知などを行うバックグラウンド処理"""

import logging
import time

from app import create_app
from app.extensions import db
from app.ingestion.pipeline import ingest_next

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 5


def run_once() -> None:
    """待っている処理をすべて行う。"""
    # 取り込み待ちの資料がなくなるまで続ける（まとめてアップロードされたときに待たせないため）
    while ingest_next():
        pass


def main() -> None:
    """worker を起動し、POLL_INTERVAL_SEC ごとに待っている処理を行う。"""
    app = create_app()
    log.info("started")
    with app.app_context():
        while True:
            try:
                run_once()
            except Exception:
                # DB に一時的につながらないときなどに worker ごと止まらないよう、
                # 記録して次回やり直す
                log.exception("処理に失敗しました")
                db.session.rollback()
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
