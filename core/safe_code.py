"""SAFE 코드(주소 토큰) 발급.

SAFE 코드는 실주소 대신 거래 상대와 플랫폼에 주는 1회용 랜덤 값이다.
- 주소나 지역 정보를 전혀 담지 않는다 (암호문도 아님).
- 형식: SAFE-XXXX-XXXX (영숫자 8자리)
- 문자 32종: 숫자 2~9 + 영문 대문자(I, O 제외) → 0/O, 1/I 혼동 방지
- 경우의 수: 32^8 ≈ 1.1조
- 중복 확인(DB UNIQUE + 재발급)은 DB를 다루는 service 계층에서 한다.
"""

import secrets

# 혼동문자(0, O, 1, I)를 뺀 32종 문자
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_safe_code() -> str:
    """SAFE-XXXX-XXXX 형식의 랜덤 코드를 만든다.

    random 모듈이 아니라 secrets 모듈을 쓴다.
    secrets는 암호학적으로 안전한 난수라 다음 값을 예측할 수 없다.
    """
    chars = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"SAFE-{chars[:4]}-{chars[4:]}"
