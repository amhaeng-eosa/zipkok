"""보안 테스트 — 발표에서 "통제가 실제로 동작한다"는 근거.

1. 판매자 화면 데이터에 구매자 실주소 없음 (반대도)
2. 다른 거래 ID로 복호화 실패 (AAD) → test_crypto.py
3. 파기된 거래의 코드로 조회 시 실주소 안 나옴
4. platform.db에 주소 컬럼 없음 + 플랫폼 코드가 zip콕 DB에 접근하지 않음
+ 복호화 단일 지점: decrypt_address()는 book_delivery 안에서만 호출
"""

import ast
import pathlib
from datetime import datetime, timedelta, timezone

from core import platform_db
from tests.conftest import BUYER_ADDRESS, SELLER_ADDRESS

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _contains_any(data: dict, address: dict) -> bool:
    text = str(data)
    return any(value in text for value in address.values())


# ---------- 1 ----------

def test_seller_view_has_no_buyer_address(service, booked_trade):
    view = service.view_for_token(booked_trade["seller"])
    assert not _contains_any(view, BUYER_ADDRESS)
    assert view["pickup_code"].startswith("ZIP-")  # 수거 코드는 보임


def test_buyer_view_has_no_seller_address(service, booked_trade):
    view = service.view_for_token(booked_trade["buyer"])
    assert not _contains_any(view, SELLER_ADDRESS)
    assert "pickup_code" not in view


def test_label_shows_no_names_or_addresses(courier, booked_trade):
    label = courier.label(booked_trade["pickup_code"])
    assert not _contains_any(label, SELLER_ADDRESS)
    assert not _contains_any(label, BUYER_ADDRESS)


# ---------- 3 ----------

def test_confirmed_trade_reveals_no_address(service, zdb, booked_trade):
    service.mark_delivered("T-0001")
    service.confirm_trade("T-0001")

    assert service.view_for_token(booked_trade["seller"]) == {"state": "EXPIRED"}
    assert service.view_for_token(booked_trade["buyer"]) == {"state": "EXPIRED"}
    left = zdb.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    assert left == 0  # 암호문까지 삭제됨


def test_auto_confirm_after_48_hours(service, zdb, booked_trade):
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    service.mark_delivered("T-0001", now=t0)

    assert service.sweep(now=t0 + timedelta(hours=47)) == []          # 아직 보관
    assert service.sweep(now=t0 + timedelta(hours=48)) == ["T-0001"]  # 자동 확정 → 파기
    assert zdb.execute("SELECT COUNT(*) FROM addresses").fetchone()[0] == 0


def test_dispute_holds_then_destroys_at_limit(service, zdb, booked_trade):
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    service.mark_delivered("T-0001", now=t0)
    service.open_dispute("T-0001", now=t0 + timedelta(hours=10))

    assert service.sweep(now=t0 + timedelta(days=3)) == []   # 분쟁 중이라 48시간이 지나도 보관
    assert zdb.execute("SELECT COUNT(*) FROM addresses").fetchone()[0] == 2
    assert service.sweep(now=t0 + timedelta(hours=10, days=30)) == ["T-0001"]  # 상한 도달
    assert zdb.execute("SELECT COUNT(*) FROM addresses").fetchone()[0] == 0


# ---------- 4 ----------

def test_platform_db_has_no_address_column(pdb, booked_trade):
    columns = [row["name"] for row in pdb.execute("PRAGMA table_info(trades)")]
    for word in ("address", "addr", "road", "phone", "name"):
        assert not any(word in c and c != "item_name" for c in columns)

    stored = platform_db.get_trade(pdb, "T-0001")
    assert not _contains_any(stored, SELLER_ADDRESS)
    assert not _contains_any(stored, BUYER_ADDRESS)
    assert stored["seller_token"].startswith("SAFE-")


def test_platform_code_does_not_import_zipkok_db():
    source = (ROOT / "core" / "platform_db.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported += [a.name for a in node.names]
    assert not any("zipkok_db" in name or "crypto" in name for name in imported)


# ---------- 복호화 단일 지점 ----------

def test_decrypt_only_in_book_delivery():
    """프로젝트 전체에서 decrypt_address() 호출이 book_delivery 안에만 있는지 검사한다."""
    callers = []
    for path in ROOT.rglob("*.py"):
        skip = {"tests", ".venv", "venv", "site-packages", "__pycache__"}
        if skip & set(path.parts) or path.name == "crypto.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in ast.walk(tree):
            if isinstance(func, ast.FunctionDef):
                for node in ast.walk(func):
                    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "decrypt_address":
                        callers.append(f"{path.name}:{func.name}")
    assert set(callers) == {"service.py:book_delivery"}


def test_decrypt_is_logged_once(service, zdb, booked_trade):
    actions = [r["action"] for r in zdb.execute("SELECT action FROM access_log WHERE trade_id = 'T-0001'")]
    assert actions.count("DECRYPT_FOR_BOOKING") == 1
