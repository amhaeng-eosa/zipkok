"""테스트 공용 준비물: 빈 DB 두 개, 키, Mock 택배사, 서비스."""

import pytest

from core import platform_db, zipkok_db
from core.crypto import generate_key, load_key
from core.service import ZipkokService
from mock_courier import MockCourier

SELLER_ADDRESS = {"name": "김판매", "phone": "010-1111-2222", "road": "서울특별시 종로구 세종대로 1", "detail": "판매동 101호"}
BUYER_ADDRESS = {"name": "이구매", "phone": "010-3333-4444", "road": "경기도 오산시 한신대길 137", "detail": "구매동 202호"}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("ZIPKOK_KEY", generate_key())
    return load_key()


@pytest.fixture
def courier():
    return MockCourier()


@pytest.fixture
def zdb():
    return zipkok_db.connect()


@pytest.fixture
def pdb():
    return platform_db.connect()


@pytest.fixture
def service(zdb, key, courier):
    return ZipkokService(zdb, key, courier)


@pytest.fixture
def booked_trade(service, pdb):
    """플랫폼이 거래를 만들고, 양쪽이 주소를 등록하고, 예약까지 마친 상태."""
    seller_token, buyer_token = service.open_trade("T-0001")
    platform_db.create_trade(pdb, "T-0001", "캠핑 의자", seller_token, buyer_token)
    service.register_address(seller_token, SELLER_ADDRESS)
    service.register_address(buyer_token, BUYER_ADDRESS)
    pickup_code = service.book_delivery("T-0001")
    return {"trade_id": "T-0001", "seller": seller_token, "buyer": buyer_token, "pickup_code": pickup_code}
