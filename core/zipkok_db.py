"""zipkok.db — zip콕 쪽 저장소. 실주소 암호문은 여기에만 있다.

테이블
- trades:     거래 상태 (상태 머신)
- tokens:     SAFE 코드 ↔ 거래 매핑 (판매자용·구매자용 각 1개)
- addresses:  주소 암호문 + nonce. 파기할 때 행을 통째로 삭제한다.
- access_log: 등록·복호화·파기 기록
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id       TEXT PRIMARY KEY,
    state          TEXT NOT NULL
                   CHECK (state IN ('OPEN', 'BOOKED', 'DELIVERED', 'DISPUTED', 'DESTROYED')),
    pickup_code    TEXT,
    delivered_at   TEXT,
    disputed_at    TEXT,
    destroyed_at   TEXT,
    destroy_reason TEXT
);

CREATE TABLE IF NOT EXISTS tokens (
    token    TEXT PRIMARY KEY,                -- PRIMARY KEY = UNIQUE (중복 발급 방지)
    trade_id TEXT NOT NULL REFERENCES trades(trade_id),
    role     TEXT NOT NULL CHECK (role IN ('seller', 'buyer')),
    active   INTEGER NOT NULL DEFAULT 1,
    UNIQUE (trade_id, role)
);

CREATE TABLE IF NOT EXISTS addresses (
    token      TEXT PRIMARY KEY REFERENCES tokens(token),
    ciphertext BLOB NOT NULL,                 -- AES-256-GCM 암호문
    nonce      BLOB NOT NULL                  -- 암호화마다 새로 만든 12바이트
);

CREATE TABLE IF NOT EXISTS access_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    action   TEXT NOT NULL,
    at       TEXT NOT NULL
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """zipkok.db에 연결하고 테이블이 없으면 만든다."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
