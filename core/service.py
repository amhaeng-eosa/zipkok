"""zip콕 서비스 — 거래 생성 → 주소 등록 → 택배 예약 → 구매확정·파기.

플랫폼은 이 함수들만 호출하고, 돌려받는 것은 SAFE 토큰과 상태뿐이다. 주소는 절대 돌려주지 않는다.

상태 머신
    OPEN(주소 등록 중) → BOOKED(예약) → DELIVERED(배송 완료) → DESTROYED(파기)
                                         DELIVERED → DISPUTED(분쟁 보류) → DESTROYED

파기 규칙 (2026-10-31 결정, 상한은 잠정)
- 구매확정 시 즉시 파기
- 배송 완료 후 48시간이 지나면 자동 구매확정 → 파기 (당근 바로구매와 같은 기준)
- 분쟁 중이면 확정·취소까지 보관, 단 최대 30일이 지나면 자동 파기
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from core.crypto import decrypt_address, encrypt_address
from core.safe_code import generate_safe_code

AUTO_CONFIRM = timedelta(hours=48)
DISPUTE_HOLD_LIMIT = timedelta(days=30)  # 잠정 값


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


class ZipkokService:
    def __init__(self, conn: sqlite3.Connection, key: bytes, courier):
        self.conn = conn
        self.key = key
        self.courier = courier

    # ---------- 내부 도구 ----------

    def _log(self, trade_id: str, action: str, now: datetime) -> None:
        self.conn.execute(
            "INSERT INTO access_log (trade_id, action, at) VALUES (?, ?, ?)",
            (trade_id, action, now.isoformat()),
        )

    def _state(self, trade_id: str) -> str:
        row = self.conn.execute("SELECT state FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if row is None:
            raise ValueError("없는 거래입니다.")
        return row["state"]

    def _require(self, trade_id: str, *allowed: str) -> None:
        state = self._state(trade_id)
        if state not in allowed:
            raise ValueError(f"현재 상태({state})에서는 할 수 없는 작업입니다.")

    def _issue_token(self, trade_id: str, role: str) -> str:
        """SAFE 코드를 발급한다. 이미 있는 코드와 겹치면(UNIQUE 위반) 다시 뽑는다."""
        for _ in range(5):
            token = generate_safe_code()
            try:
                self.conn.execute(
                    "INSERT INTO tokens (token, trade_id, role) VALUES (?, ?, ?)",
                    (token, trade_id, role),
                )
                return token
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("SAFE 코드 발급에 계속 실패했습니다.")

    # ---------- 1. 거래 생성 ----------

    def open_trade(self, trade_id: str, now: datetime | None = None) -> tuple[str, str]:
        """거래를 열고 판매자용·구매자용 SAFE 코드를 돌려준다."""
        now = _now(now)
        self.conn.execute("INSERT INTO trades (trade_id, state) VALUES (?, 'OPEN')", (trade_id,))
        seller_token = self._issue_token(trade_id, "seller")
        buyer_token = self._issue_token(trade_id, "buyer")
        self._log(trade_id, "OPEN", now)
        self.conn.commit()
        return seller_token, buyer_token

    # ---------- 2. 주소 등록 (zip콕 입력 페이지에서 호출) ----------

    def register_address(self, token: str, address: dict, now: datetime | None = None) -> None:
        """실주소를 암호화해 저장한다. 평문 주소는 어디에도 저장하지 않는다."""
        now = _now(now)
        row = self.conn.execute(
            "SELECT trade_id, role FROM tokens WHERE token = ? AND active = 1", (token,)
        ).fetchone()
        if row is None:
            raise ValueError("유효하지 않은 SAFE 코드입니다.")
        self._require(row["trade_id"], "OPEN")

        ciphertext, nonce = encrypt_address(address, row["trade_id"], self.key)
        self.conn.execute(
            "INSERT OR REPLACE INTO addresses (token, ciphertext, nonce) VALUES (?, ?, ?)",
            (token, ciphertext, nonce),
        )
        self._log(row["trade_id"], f"REGISTER_{row['role'].upper()}", now)
        self.conn.commit()

    # ---------- 3. 택배 예약: 유일한 복호화 지점 ----------

    def book_delivery(self, trade_id: str, now: datetime | None = None) -> str:
        """판매자 대신 택배를 예약하고 수거 코드를 돌려준다.

        ★ 복호화 단일 지점: decrypt_address()는 이 함수에서만 호출한다.
          (테스트 test_decrypt_only_in_book_delivery가 코드 전체를 검사해 확인)
        복호화한 주소는 택배사에 넘기는 데만 쓰고, 저장하거나 돌려주지 않는다.
        """
        now = _now(now)
        self._require(trade_id, "OPEN")

        rows = self.conn.execute(
            """SELECT t.role, a.ciphertext, a.nonce
               FROM tokens t JOIN addresses a ON a.token = t.token
               WHERE t.trade_id = ?""",
            (trade_id,),
        ).fetchall()
        encrypted = {r["role"]: r for r in rows}
        if set(encrypted) != {"seller", "buyer"}:
            raise ValueError("판매자와 구매자 주소가 모두 등록돼야 예약할 수 있습니다.")

        seller = decrypt_address(encrypted["seller"]["ciphertext"], encrypted["seller"]["nonce"], trade_id, self.key)
        buyer = decrypt_address(encrypted["buyer"]["ciphertext"], encrypted["buyer"]["nonce"], trade_id, self.key)
        self._log(trade_id, "DECRYPT_FOR_BOOKING", now)

        pickup_code = self.courier.book(sender=seller, receiver=buyer)

        self.conn.execute(
            "UPDATE trades SET state = 'BOOKED', pickup_code = ? WHERE trade_id = ?",
            (pickup_code, trade_id),
        )
        self.conn.commit()
        return pickup_code

    # ---------- 4. 배송 완료 (Mock 택배사가 알려준다고 가정) ----------

    def mark_delivered(self, trade_id: str, now: datetime | None = None) -> None:
        now = _now(now)
        self._require(trade_id, "BOOKED")
        self.conn.execute(
            "UPDATE trades SET state = 'DELIVERED', delivered_at = ? WHERE trade_id = ?",
            (now.isoformat(), trade_id),
        )
        self._log(trade_id, "DELIVERED", now)
        self.conn.commit()

    # ---------- 5. 구매확정 · 분쟁 · 파기 ----------

    def confirm_trade(self, trade_id: str, now: datetime | None = None) -> None:
        """플랫폼이 보내는 구매확정 신호. 받는 즉시 주소를 파기한다."""
        self._require(trade_id, "DELIVERED", "DISPUTED")
        self._destroy(trade_id, "CONFIRMED", _now(now))

    def open_dispute(self, trade_id: str, now: datetime | None = None) -> None:
        """구매자가 문제를 신고하면 자동 확정을 멈추고 보관을 연장한다(상한 있음)."""
        now = _now(now)
        self._require(trade_id, "DELIVERED")
        self.conn.execute(
            "UPDATE trades SET state = 'DISPUTED', disputed_at = ? WHERE trade_id = ?",
            (now.isoformat(), trade_id),
        )
        self._log(trade_id, "DISPUTE", now)
        self.conn.commit()

    def sweep(self, now: datetime | None = None) -> list[str]:
        """기한이 지난 거래를 찾아 파기한다. (서버에서 주기적으로 실행)

        - DELIVERED이고 배송 완료 후 48시간 경과 → 자동 구매확정 → 파기
        - DISPUTED이고 분쟁 시작 후 30일 경과 → 상한 도달 → 파기
        """
        now = _now(now)
        destroyed = []
        rows = self.conn.execute(
            "SELECT trade_id, state, delivered_at, disputed_at FROM trades WHERE state IN ('DELIVERED', 'DISPUTED')"
        ).fetchall()
        for r in rows:
            if r["state"] == "DELIVERED" and now - datetime.fromisoformat(r["delivered_at"]) >= AUTO_CONFIRM:
                self._destroy(r["trade_id"], "AUTO_CONFIRMED", now)
                destroyed.append(r["trade_id"])
            elif r["state"] == "DISPUTED" and now - datetime.fromisoformat(r["disputed_at"]) >= DISPUTE_HOLD_LIMIT:
                self._destroy(r["trade_id"], "HOLD_LIMIT", now)
                destroyed.append(r["trade_id"])
        return destroyed

    def _destroy(self, trade_id: str, reason: str, now: datetime) -> None:
        """주소 암호문을 삭제하고 SAFE 코드를 만료시킨다. 되돌릴 수 없다."""
        self.conn.execute(
            "DELETE FROM addresses WHERE token IN (SELECT token FROM tokens WHERE trade_id = ?)",
            (trade_id,),
        )
        self.conn.execute("UPDATE tokens SET active = 0 WHERE trade_id = ?", (trade_id,))
        self.conn.execute(
            "UPDATE trades SET state = 'DESTROYED', destroyed_at = ?, destroy_reason = ? WHERE trade_id = ?",
            (now.isoformat(), reason, trade_id),
        )
        self._log(trade_id, f"DESTROY_{reason}", now)
        self.conn.commit()

    # ---------- 6. 화면용 조회 (주소는 절대 포함하지 않음) ----------

    def view_for_token(self, token: str) -> dict:
        """판매자·구매자 화면에 보여줄 정보. 상대방 주소는 물론 본인 주소도 돌려주지 않는다."""
        row = self.conn.execute(
            """SELECT t.role, t.active, tr.state, tr.pickup_code
               FROM tokens t JOIN trades tr ON tr.trade_id = t.trade_id
               WHERE t.token = ?""",
            (token,),
        ).fetchone()
        if row is None or not row["active"]:
            return {"state": "EXPIRED"}
        view = {"role": row["role"], "state": row["state"], "counterparty": "비공개"}
        if row["role"] == "seller" and row["pickup_code"]:
            view["pickup_code"] = row["pickup_code"]  # 판매자는 상자에 적을 수거 코드만 본다
        return view
