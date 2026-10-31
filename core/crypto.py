"""실주소 암호화·복호화 (AES-256-GCM).

- AES-256-GCM: 양방향 암호화. 택배 예약 때 실주소가 필요하므로 다시 풀 수 있어야 한다.
  ("단방향 암호화"가 아님에 주의)
- nonce: 암호화할 때마다 12바이트를 새로 만들어 암호문과 같이 저장한다.
  같은 키로 nonce를 재사용하면 GCM의 안전성이 깨진다.
- AAD(추가 인증 데이터) = 거래 ID.
  암호문을 다른 거래 행에 옮겨 붙이면 복호화가 실패한다(InvalidTag).
- 키는 코드에 넣지 않고 환경변수 ZIPKOK_KEY(base64)에서 읽는다.

⚠️ decrypt_address()는 service 계층의 택배 예약 함수에서만 호출한다 (복호화 단일 지점).
"""

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_ENV = "ZIPKOK_KEY"
NONCE_SIZE = 12  # GCM 권장 nonce 길이(바이트)


def generate_key() -> str:
    """새 256비트 키를 만들어 base64 문자열로 돌려준다. (.env에 넣을 값)"""
    return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()


def load_key() -> bytes:
    """환경변수에서 키를 읽는다. 없거나 길이가 틀리면 바로 멈춘다."""
    raw = os.environ.get(KEY_ENV)
    if not raw:
        raise RuntimeError(f"환경변수 {KEY_ENV}가 없습니다. .env.example을 참고하세요.")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise ValueError("키는 32바이트(256비트)여야 합니다.")
    return key


def encrypt_address(address: dict, trade_id: str, key: bytes) -> tuple[bytes, bytes]:
    """주소(dict)를 암호화해 (암호문, nonce)를 돌려준다.

    address 예: {"name": "...", "phone": "...", "road": "...", "detail": "..."}
    """
    nonce = os.urandom(NONCE_SIZE)  # 매번 새 nonce
    plaintext = json.dumps(address, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, trade_id.encode("utf-8"))
    return ciphertext, nonce


def decrypt_address(ciphertext: bytes, nonce: bytes, trade_id: str, key: bytes) -> dict:
    """암호문을 풀어 주소(dict)를 돌려준다.

    trade_id가 암호화할 때와 다르거나 암호문이 바뀌었으면
    cryptography.exceptions.InvalidTag 예외가 난다.
    """
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, trade_id.encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))
