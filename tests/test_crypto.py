"""1단계 테스트: SAFE 코드 발급 + AES-256-GCM 암호화."""

import re

import pytest
from cryptography.exceptions import InvalidTag

from core.crypto import decrypt_address, encrypt_address, generate_key, load_key
from core.safe_code import ALPHABET, generate_safe_code

ADDRESS = {
    "name": "홍길동",
    "phone": "010-1234-5678",
    "road": "경기도 오산시 한신대길 137",
    "detail": "101동 1001호",
}


@pytest.fixture
def key(monkeypatch):
    """테스트마다 새 키를 환경변수에 넣고 읽어온다."""
    monkeypatch.setenv("ZIPKOK_KEY", generate_key())
    return load_key()


# ---------- SAFE 코드 ----------

def test_safe_code_format():
    code = generate_safe_code()
    assert re.fullmatch(r"SAFE-[A-Z0-9]{4}-[A-Z0-9]{4}", code)


def test_safe_code_has_no_confusing_chars():
    assert len(ALPHABET) == 32
    for ch in "0O1I":
        assert ch not in ALPHABET


def test_safe_code_is_random():
    codes = {generate_safe_code() for _ in range(1000)}
    assert len(codes) == 1000  # 1000번 뽑아도 겹치지 않음 (경우의 수 약 1.1조)


# ---------- 암호화 ----------

def test_encrypt_then_decrypt_returns_same_address(key):
    ciphertext, nonce = encrypt_address(ADDRESS, "T-0001", key)
    assert decrypt_address(ciphertext, nonce, "T-0001", key) == ADDRESS


def test_ciphertext_does_not_contain_plain_address(key):
    ciphertext, _ = encrypt_address(ADDRESS, "T-0001", key)
    assert "한신대길".encode() not in ciphertext


def test_nonce_is_new_every_time(key):
    _, nonce1 = encrypt_address(ADDRESS, "T-0001", key)
    _, nonce2 = encrypt_address(ADDRESS, "T-0001", key)
    assert nonce1 != nonce2


def test_decrypt_with_other_trade_id_fails(key):
    """보안 테스트 2번: 다른 거래 ID로는 복호화 실패 (AAD)."""
    ciphertext, nonce = encrypt_address(ADDRESS, "T-0001", key)
    with pytest.raises(InvalidTag):
        decrypt_address(ciphertext, nonce, "T-0002", key)


def test_decrypt_with_other_key_fails(key):
    ciphertext, nonce = encrypt_address(ADDRESS, "T-0001", key)
    other_key = bytes(32)
    with pytest.raises(InvalidTag):
        decrypt_address(ciphertext, nonce, "T-0001", other_key)


def test_missing_key_stops(monkeypatch):
    monkeypatch.delenv("ZIPKOK_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_key()
