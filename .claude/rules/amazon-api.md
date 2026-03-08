# Amazon Advertising API 규칙

## 인증
- access_token 만료(1시간)는 `app/auth/amazon_oauth.py`에서 자동 갱신 처리
- 모든 API 클라이언트는 `AmazonAuthClient` 를 통해 토큰 획득
- refresh_token은 절대 로그에 출력하지 않음

## 필수 요청 헤더
모든 Amazon API 요청에 다음 헤더 포함:
```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Amazon-Advertising-API-ClientId": settings.AMAZON_CLIENT_ID,
    "Amazon-Advertising-API-Scope": settings.AMAZON_PROFILE_ID,
    "Content-Type": "application/json",
}
```

## 리포트 요청 패턴 (비동기 폴링)
Amazon 리포트는 즉시 반환되지 않음 — 요청 후 폴링 필수:
```
1. POST /reporting/reports  → reportId 획득
2. GET  /reporting/reports/{reportId}  → status 확인 (PENDING/PROCESSING/COMPLETED)
3. status == COMPLETED → downloadUrl로 실제 데이터 다운로드
4. 폴링 간격: 30초, 최대 대기: 10분
```

## 입찰가 변경 안전 제한 (비즈니스 로직 — 절대 변경 금지)
```python
MAX_BID_CHANGE_PCT = 0.30   # 1회 최대 ±30%
MIN_CLICKS_FOR_BID = 5      # 최소 클릭 수 미만이면 변경 금지
MIN_BID = 0.05              # 최소 입찰가 $0.05
TARGET_ROAS = 5.0           # 목표 ROAS (settings에서 override 가능)
```

## Rate Limit 대응
- 기본 제한: 초당 2~5 요청 (엔드포인트별 상이)
- 429 응답 시 exponential backoff 적용 (python.md 참고)
- 대량 입찰 변경은 배치(batch) 처리: 한 번에 최대 1,000건

## 데이터 신뢰도
- 리포트 데이터는 최대 24시간 지연 발생 가능
- 당일 데이터(today)는 불완전할 수 있으므로 전일(yesterday) 기준으로 분석
- 클릭 5회 미만 키워드는 입찰 변경 대상에서 제외 (통계적 신뢰도 부족)

## 엔드포인트별 메서드 매핑
| 작업 | 메서드 | 경로 |
|------|--------|------|
| 키워드 입찰 수정 | PUT | `/sp/keywords` |
| 네거티브 키워드 추가 | POST | `/sp/negativeKeywords` |
| 캠페인 예산 수정 | PUT | `/sp/campaigns` |
| 리포트 생성 요청 | POST | `/reporting/reports` |
| 리포트 상태 확인 | GET | `/reporting/reports/{id}` |
