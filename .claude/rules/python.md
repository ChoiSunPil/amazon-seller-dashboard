# Python 코딩 규칙

## 기본 원칙
- Python 3.13+ 문법 사용
- 모든 함수/메서드에 type hints 필수
- PEP 8 준수 (라인 길이 최대 100자)
- docstring은 핵심 함수에만 간결하게 작성

## 비동기 패턴
- Amazon API 호출은 반드시 `async/await` 사용
- I/O 바운드 작업은 모두 async로 처리
- `asyncio.gather()`로 병렬 요청 처리

```python
# ✅ 올바른 패턴
async def fetch_report(report_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/reports/{report_id}", headers=headers)
        response.raise_for_status()
        return response.json()

# ❌ 금지
def fetch_report(report_id):
    return requests.get(...)  # 동기 호출 금지
```

## 환경변수
- 하드코딩 절대 금지 — 반드시 `app/config.py`의 Settings 클래스에서 로드
- API 키, 토큰, 시크릿은 코드에 직접 작성 금지

```python
# ✅ 올바른 패턴
from app.config import settings
client_id = settings.AMAZON_CLIENT_ID

# ❌ 금지
client_id = "amzn1.application-oa2-client.xxxxx"
```

## 에러 핸들링
- Amazon API 429 (rate limit) 반드시 처리 — exponential backoff 적용
- 모든 외부 API 호출에 timeout 설정
- 예외는 로깅 후 재발생 또는 적절한 HTTP 예외로 변환

```python
# ✅ Rate limit 처리 패턴
import asyncio

async def api_call_with_retry(func, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited. Waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")
```

## 로깅
- `logging` 모듈 사용 (`print()` 금지)
- API 요청/응답은 DEBUG 레벨로 기록
- 에러와 액션 결정은 INFO 레벨 이상으로 기록

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Bid update applied: keyword_id={kw_id}, new_bid={new_bid}")
logger.debug(f"API response: {response.json()}")
```

## 패키지 관리
- 패키지 추가 시 반드시 `uv add <package>` 사용 (pip 직접 설치 금지)
- 개발 전용 패키지는 `uv add --dev <package>`
