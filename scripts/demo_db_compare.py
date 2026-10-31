"""발표 캡처용: 샘플 거래 하나를 만들고 platform.db와 zipkok.db를 나란히 출력한다.

실행: py scripts/demo_db_compare.py
- 실제 키(.env)를 쓰지 않고 이번 실행에서만 쓸 임시 키를 만든다.
- demo_platform.db, demo_zipkok.db 파일이 생긴다 (.gitignore로 커밋 안 됨).
"""

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import platform_db, zipkok_db  # noqa: E402
from core.crypto import generate_key, load_key  # noqa: E402
from core.service import ZipkokService  # noqa: E402
from mock_courier import MockCourier  # noqa: E402

os.environ.setdefault("ZIPKOK_KEY", generate_key())

for name in ("demo_platform.db", "demo_zipkok.db"):
    (ROOT / name).unlink(missing_ok=True)

pdb = platform_db.connect(str(ROOT / "demo_platform.db"))
zdb = zipkok_db.connect(str(ROOT / "demo_zipkok.db"))
service = ZipkokService(zdb, load_key(), MockCourier())

seller_token, buyer_token = service.open_trade("T-0001")
platform_db.create_trade(pdb, "T-0001", "[상품명]", seller_token, buyer_token)
service.register_address(seller_token, {"name": "김판매", "phone": "010-1111-2222", "road": "서울특별시 종로구 세종대로 1", "detail": "101호"})
service.register_address(buyer_token, {"name": "이구매", "phone": "010-3333-4444", "road": "경기도 오산시 한신대길 137", "detail": "202호"})
pickup_code = service.book_delivery("T-0001")

print("=" * 70)
print("[platform.db] trades  ← 플랫폼(도토리마켓)이 가진 것: 주소 컬럼 없음")
print("=" * 70)
for row in pdb.execute("SELECT * FROM trades"):
    print(dict(row))

print()
print("=" * 70)
print("[zipkok.db] addresses  ← zip콕만 가진 것: 암호문 (앞 24바이트만 표시)")
print("=" * 70)
for row in zdb.execute("SELECT token, ciphertext, nonce FROM addresses"):
    print(f"{row['token']}  ciphertext={row['ciphertext'][:24].hex()}...  nonce={row['nonce'].hex()}")

print()
print("[zipkok.db] access_log")
for row in zdb.execute("SELECT action, at FROM access_log"):
    print(f"  {row['action']:<22} {row['at']}")

print()
print(f"판매자 화면: {service.view_for_token(seller_token)}")
print(f"구매자 화면: {service.view_for_token(buyer_token)}")
