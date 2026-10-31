# zip콕 — 주소계의 PG

중고거래 택배 거래에서 **거래 상대도, 중고거래 플랫폼도 실주소를 갖지 않게 하는** 주소 토큰 중계 서비스 프로토타입입니다.
한신대학교 AI·SW캡스톤디자인 1·2 프로젝트이며, 결과물은 오픈소스로 공개합니다.

> 현재 단계: 캡스톤1 중간발표 — 핵심 로직(`core/`)과 보안 테스트까지 구현. 웹 화면(FastAPI + HTML 템플릿)은 이후 단계입니다.

## 왜 필요한가

택배가 가려면 누군가는 두 주소를 모두 알아야 합니다. 지금 개인 간 택배 거래에서는 그게 모르는 거래 상대이거나, 주소를 직접 수집하는 플랫폼입니다.
zip콕은 결제의 PG처럼 동작합니다. 카드번호 입력창이 PG의 것이고 가맹점은 토큰만 받듯이, **주소 입력창은 zip콕의 것이고 플랫폼은 `SAFE` 토큰만 받습니다.**

## 동작 방식

1. 플랫폼이 거래를 열면 zip콕이 판매자용·구매자용 `SAFE-XXXX-XXXX` 코드를 발급합니다.
2. 판매자와 구매자는 zip콕 페이지에서 실주소를 입력합니다. 주소는 AES-256-GCM으로 암호화해 저장합니다(거래 ID = AAD).
3. zip콕이 판매자 대신 택배를 예약합니다. **복호화는 이 예약 함수 한 곳에서만** 일어나고 기록이 남습니다.
4. 판매자는 상자에 수거 코드(`ZIP-XX`)만 적습니다. 송장에는 양측 이름·연락처·주소를 표시하지 않습니다.
5. 구매확정(직접 또는 배송 완료 48시간 후 자동)이 되면 암호문을 삭제하고 코드를 만료시킵니다. 분쟁 중이면 최대 30일(잠정)까지 보관합니다.

택배사는 실제 연동 없이 `mock_courier.py`(교체 가능한 어댑터)로 대신합니다.

## 운영 형태

| 운영 형태 | 얻는 것 |
|---|---|
| A. 독립 운영자(공공·제3자)가 운영 | 거래 상대 + 플랫폼 모두에게서 주소 숨김 |
| B. 플랫폼이 직접 설치 | 거래 상대에게서 숨김 + 최소 보관·파기. 플랫폼 비보관 효과는 없음 |

프로토타입은 A를 기준으로 만듭니다.

## 알려진 한계

- 키와 DB를 모두 가진 내부자가 DB를 직접 읽는 것은 막지 못합니다. 대신 보관 기간이 짧고, 정상 경로의 복호화는 한 곳에서만 일어나 기록됩니다.
- 택배사에 넘긴 주소는 택배사 정책대로 보관됩니다. 주소가 사라지는 곳은 zip콕과 플랫폼입니다.
- 송장번호로 배송조회를 하면 대리점 수준(동네)의 지역은 보일 수 있습니다.
- 현재 버전의 `platform.db` / `zipkok.db` 분리는 한 프로그램 안의 설계상 분리이며 보안 경계가 아닙니다. 서버 분리는 다음 단계입니다.

## 구조

```
zipkok/
├─ core/
│  ├─ safe_code.py    SAFE 코드 발급 (secrets, 혼동문자 제외 32종 8자리)
│  ├─ crypto.py       AES-256-GCM 암·복호화
│  ├─ zipkok_db.py    zip콕 DB: trades · tokens · addresses · access_log
│  ├─ platform_db.py  플랫폼 DB: 주소 컬럼 없음
│  └─ service.py      거래 생성 → 주소 등록 → 예약(유일한 복호화) → 확정·파기
├─ mock_courier.py    Mock 택배사 (수거 코드, 정보 미표시 송장)
├─ scripts/demo_db_compare.py   두 DB 내용 비교 출력
└─ tests/             pytest 보안 테스트
```

## 실행 방법

Python 3.12 이상이 필요합니다. (Windows는 `py`, macOS·Linux는 `python3`)

```
py -m pip install -r requirements.txt
py -m pytest -v                    # 테스트 실행
py scripts\demo_db_compare.py      # 샘플 거래로 두 DB 비교
```

실제로 키를 쓸 때는 `.env.example`을 `.env`로 복사하고 `ZIPKOK_KEY`를 채웁니다.

```
py -c "from core.crypto import generate_key; print(generate_key())"
```

`.env`와 `*.db` 파일은 `.gitignore`로 저장소에 올라가지 않습니다.

## 보안 테스트

| 테스트 | 확인하는 것 |
|---|---|
| `test_seller_view_has_no_buyer_address` 외 1 | 판매자·구매자 화면 데이터에 상대 주소 없음 |
| `test_label_shows_no_names_or_addresses` | 송장에 이름·연락처·주소 없음 |
| `test_decrypt_with_other_trade_id_fails` | 다른 거래 ID로는 복호화 실패 (AAD) |
| `test_confirmed_trade_reveals_no_address` | 파기 후 코드로 조회해도 주소 없음, 암호문 삭제 |
| `test_auto_confirm_after_48_hours` | 배송 완료 48시간 후 자동 파기 |
| `test_dispute_holds_then_destroys_at_limit` | 분쟁 중 보관, 상한 도달 시 파기 |
| `test_platform_db_has_no_address_column` | 플랫폼 DB에 주소 컬럼·주소 값 없음 |
| `test_platform_code_does_not_import_zipkok_db` | 플랫폼 코드가 zip콕 DB·암호 모듈을 쓰지 않음 |
| `test_decrypt_only_in_book_delivery` | 코드 전체에서 복호화 호출이 예약 함수 한 곳뿐 |

## 라이선스

[MIT License](LICENSE)
