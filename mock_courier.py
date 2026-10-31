"""Mock 택배사 — 실제 택배사 API 대신 쓰는 교체 가능한 어댑터.

실제 택배사로 바꿀 때는 이 클래스와 같은 메서드(book, label)를 가진 클래스만 만들면 된다.

주의: 택배사는 배송을 위해 실주소를 받는다. 받은 주소를 얼마나 보관할지는
택배사 정책이며 zip콕이 통제할 수 없다. (여기서는 self.bookings에 남는 것으로 표현)
"""

import secrets


class MockCourier:
    def __init__(self):
        self.bookings = []  # 택배사 쪽 기록 (zip콕 바깥)

    def book(self, sender: dict, receiver: dict) -> str:
        """방문 수거 예약. 상자에 적을 수거 코드(ZIP-XX)를 돌려준다.

        수거 코드는 SAFE 코드와 별개다. SAFE 코드는 화면 열쇠라 상자에 적으면 안 된다.
        """
        pickup_code = f"ZIP-{secrets.randbelow(100):02d}"
        self.bookings.append({"pickup_code": pickup_code, "sender": sender, "receiver": receiver})
        return pickup_code

    def label(self, pickup_code: str) -> dict:
        """상자에 붙는 송장. 양측 이름·연락처·주소를 표시하지 않는다."""
        return {
            "받는 분": "zip콕 안심배송",
            "보내는 분": "zip콕 안심배송",
            "수거 코드": pickup_code,
        }
