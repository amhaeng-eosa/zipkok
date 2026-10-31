"""platform.db — 중고거래 플랫폼(예시: 도토리마켓) 쪽 저장소.

핵심: 주소 컬럼이 아예 없다. 플랫폼은 SAFE 토큰만 갖는다. (주소계의 PG)
이 모듈은 zipkok_db를 import하지 않는다 → 플랫폼 코드는 zip콕 데이터에 접근하지 않음
(캡스톤1은 한 프로그램 안의 설계상 분리. 테스트로 확인한다.)
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id     TEXT PRIMARY KEY,
    item_name    TEXT NOT NULL,
    seller_token TEXT NOT NULL,
    buyer_token  TEXT NOT NULL,
    status       TEXT NOT NULL
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def create_trade(conn, trade_id: str, item_name: str, seller_token: str, buyer_token: str) -> None:
    conn.execute(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?)",
        (trade_id, item_name, seller_token, buyer_token, "IN_PROGRESS"),
    )
    conn.commit()


def set_status(conn, trade_id: str, status: str) -> None:
    conn.execute("UPDATE trades SET status = ? WHERE trade_id = ?", (status, trade_id))
    conn.commit()


def get_trade(conn, trade_id: str) -> dict:
    row = conn.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
    return dict(row) if row else {}
