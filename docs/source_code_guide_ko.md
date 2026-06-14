# 결재 RAG MVP 주요 소스코드 설명서

## 1. 시스템 개요

이 애플리케이션은 결재 관련 문서를 업로드하면 다음 처리를 수행한다.

1. PDF 문서의 텍스트와 기본 항목을 추출한다.
2. 업무 카테고리와 결재 종류에 맞는 기준 자료와 과거 결재를 검색한다.
3. 추출 결과와 검색 결과를 바탕으로 결재 폼, 요약, 체크리스트를 생성한다.
4. 필수서류와 주요 입력값의 누락을 표시한다.
5. 복수 문서의 금액, 거래처, 서비스명, 이용 기간 불일치를 비교한다.
6. 생성 결과, 직접 수정, 추가 채팅 이력을 자동 저장한다.

프론트엔드는 Streamlit, 백엔드는 FastAPI이다. 저장소와 AI 서비스는 설정에 따라 Local 구현 또는 Azure 구현으로 전환된다.

## 2. 프로젝트 구조

```text
workspace/
├─ frontend/
│  ├─ app.py
│  ├─ api_client.py
│  ├─ document_comparison.py
│  └─ components/
├─ backend/app/
│  ├─ main.py
│  ├─ core/config.py
│  ├─ schemas/models.py
│  ├─ routers/
│  └─ services/
│     ├─ document_fields.py
│     ├─ document_service.py
│     └─ rag_service.py
├─ scripts/
│  ├─ bootstrap_azure.py
│  ├─ seed_data.py
│  └─ generate_test_documents.py
├─ sample_data/
├─ tests/
└─ docs/
```

역할 분리:

- `frontend`: 화면 렌더링과 사용자 조작
- `routers`: HTTP API 입력 검증과 응답
- `services`: 문서 처리, 검색, AI 생성, 저장
- `schemas`: API와 저장 데이터 구조
- `scripts`: Azure 초기화와 샘플 데이터 준비
- `tests`: API, 문서 처리, UI 정책 회귀 테스트

## 3. 실행 구조

### 3.1 시작 명령

백엔드:

```powershell
lecture\Scripts\Activate.ps1
$env:APP_STORAGE_MODE="local"
uvicorn backend.app.main:app --reload --port 8000
```

프론트엔드:

```powershell
lecture\Scripts\Activate.ps1
$env:APP_STORAGE_MODE="local"
streamlit run frontend/app.py --server.port 8501
```

### 3.2 요청 흐름

```text
사용자
  -> Streamlit 화면
  -> frontend/api_client.py
  -> FastAPI router
  -> RagService
  -> Document/Search/AI/Storage service
  -> Local 파일 또는 Azure 리소스
  -> JSON 응답
  -> Streamlit 결과 화면
```

## 4. 프론트엔드 주요 코드

### 4.1 `frontend/app.py`

Streamlit 애플리케이션의 진입점이다.

주요 역할:

- 저장소 루트를 `sys.path`에 추가해 `streamlit run frontend/app.py` 직접 실행을 지원한다.
- 페이지 제목, wide layout, 공통 CSS를 설정한다.
- FastAPI `/health`를 먼저 호출한다.
- 백엔드가 정상이면 사이드바가 반환한 페이지 상태에 따라 화면을 전환한다.

화면 전환 값:

- `new`: 신규 작성
- `settings`: 초기 설정
- `result`: 방금 생성한 결과
- `history`: 과거 이력 상세

백엔드가 중지되어 있으면 사용자가 실행 방법을 알 수 있도록 오류와 Uvicorn 명령을 표시한다.

### 4.2 `frontend/api_client.py`

Streamlit과 FastAPI 사이의 HTTP 통신을 한곳에 모은다.

중요 포인트:

- 기본 주소는 `BACKEND_URL`, 미설정 시 `http://localhost:8000`이다.
- 모든 요청의 기본 timeout은 120초이다.
- HTTP 오류의 `detail`을 `ApiError`로 변환해 화면에서 동일한 방식으로 처리한다.
- 파일 업로드는 `multipart/form-data`로 전송한다.

주요 메서드:

| 메서드 | API | 용도 |
|---|---|---|
| `requirements` | `GET /requirements` | 카테고리별 준비사항 조회 |
| `create_case` | `POST /cases` | 신규 case와 파일 생성 |
| `generate` | `POST /cases/{id}/generate` | 결재안 생성 |
| `patch_case` | `PATCH /cases/{id}` | 폼 자동 저장 |
| `chat` | `POST /cases/{id}/chat` | 추가 지시와 새 버전 생성 |
| `clone` | `POST /cases/{id}/clone` | 과거 이력 복사 |

### 4.3 `frontend/components/sidebar.py`

사이드바 메뉴와 작성 이력을 담당한다.

- 작성 이력은 `updated_at` 기준 최신순 API 결과를 사용한다.
- 생성 버전이 한 번 이상 존재하는 건만 이력에 표시한다.
- 이력 버튼을 누르면 `history` 페이지와 `case_id`를 세션에 저장한다.
- Backend와 AI Search 상태는 일반 사용자 사이드바에 표시하지 않는다.

### 4.4 `frontend/components/settings_page.py`

UI-00 초기 설정 화면이다.

세 탭:

1. `入力・書類基準`: 필수 필드, 필수서류, 조건부서류 저장
2. `基準資料`: 규정, 표준 양식, 필요서류 기준, 샘플 과거 결재 업로드
3. `接続確認`: 관리자용 Azure 의존성 확인

필수 입력 항목 형식:

```text
purpose|目的|textarea
vendor|取引先|text
amount|金額|number
```

조건부서류 형식:

```text
見積書|新規契約または10万円以上の場合
```

`検索インデックスを更新`은 저장된 기준 자료와 과거 결재를 검색 서비스에 전달한다.
자료는 제목과 종류가 각각 다르므로 한 번에 한 건씩 등록하며, 등록 후 폼을 초기화한다.
자료 제목이 비어 있으면 업로드 파일명을 제목으로 사용한다.
Local mode에서는 로컬 저장소를 직접 검색하므로 Azure AI Search로 전송하지 않는다.

### 4.5 `frontend/components/new_case_page.py`

UI-01 신규 결재 작성 화면이다.

입력 항목:

- 업무 카테고리
- 결재 종류
- 제목과 목적
- 결재 과목번호, 예정 금액, 결재번호
- PDF, JPG, PNG 첨부

버튼 정책:

- 주요 실행 버튼은 `AI決裁案を作成` 하나이다.
- 목적이 없거나 기타 카테고리명이 없으면 비활성화된다.
- 별도 임시저장, 저장, 편집, 완료 버튼은 없다.

생성 과정:

1. 신규 case 생성과 파일 업로드
2. `/generate` 호출
3. 결과 case ID를 세션에 저장
4. 결과 화면으로 전환

과거 이력 복사 상태에서는 기존 복사 case를 `PATCH`하고 추가 파일을 등록한 뒤 다시 생성한다.

### 4.6 `frontend/components/result_page.py`

UI-02 결과와 UI-03 이력 상세를 함께 처리한다.

화면 왼쪽:

- 원본 파일 선택
- pypdfium2로 PDF 페이지를 이미지 렌더링하거나 이미지 원본 표시
- 원본 PDF를 별도 탭에서 여는 링크 제공

화면 오른쪽:

- 편집 가능한 결재 폼
- 필드 변경 시 `_save_form`이 `PATCH /cases/{id}` 호출
- 별도 저장 버튼 없이 자동 저장
- 폼 전체 내용을 클립보드로 복사하는 버튼

폼 아래의 `要約` 연속 영역:

- 생성 요약
- 문서별 거래처, 서비스명, 금액, 이용 기간 비교표
- 부족·주의
- 체크리스트
- 필요서류

`詳細情報` 확장 영역:

- 유사 결재
- 수정 이력

추가 채팅은 `st.chat_input`으로 입력하며, API가 새 버전을 만든 뒤 화면을 다시 로드한다.

## 5. 백엔드 주요 코드

### 5.1 `backend/app/main.py`

FastAPI 앱을 생성하고 서비스 컨테이너와 라우터를 등록한다.

애플리케이션 시작 시:

1. 환경 설정을 읽는다.
2. Local 또는 Azure 서비스 구현을 선택한다.
3. 생성된 서비스를 `app.state.services`에 보관한다.
4. 각 router가 동일한 서비스 인스턴스를 사용한다.

### 5.2 `backend/app/core/config.py`

Pydantic Settings로 `.env`와 환경변수를 읽는다.

중요 설정:

| 환경변수 | 설명 |
|---|---|
| `APP_STORAGE_MODE` | `local` 또는 `azure` |
| `APP_DATA_DIR` | Local 데이터 경로 |
| `BACKEND_URL` | Streamlit에서 호출할 FastAPI 주소 |
| `AZURE_OPENAI_*` | Chat/Embedding 연결 |
| `AZURE_SEARCH_*` | AI Search 연결과 인덱스 |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob Storage 연결 |
| `AZURE_COSMOS_ENABLED` | `false`이면 Cosmos 대신 로컬 이력 저장 |
| `AZURE_COSMOS_*` | Cosmos DB 연결 |

Azure mode에서 필수 설정이 누락되면 `missing_azure_settings()`가 누락 변수명을 반환한다.
`AZURE_COSMOS_ENABLED=false`이면 OpenAI, AI Search, Blob Storage는 Azure를 사용하고
결재 설정과 이력은 `data/database.json`에 자동 저장한다.

### 5.3 `backend/app/schemas/models.py`

Pydantic 모델로 API 입력, AI 출력, 저장 데이터를 검증한다.

핵심 모델:

- `RequirementConfig`: 카테고리별 필수 입력과 서류 기준
- `CaseRecord`: 결재 건 전체 상태
- `ApprovalForm`: 화면 오른쪽에 표시할 생성 폼
- `FileRecord`: 파일 경로, 페이지별 추출 텍스트
- `ValidationResult`: 오류, 경고, 정상 판정
- `SourceRef`: 생성 필드와 원본 근거의 연결
- `GenerationPayload`: AI가 반환해야 하는 구조화 JSON

`CaseRecord.current_version`과 `versions`는 AI 생성 및 채팅 재생성 이력을 관리한다.

### 5.4 `backend/app/routers/cases.py`

결재 case API를 제공한다.

신규 생성:

1. `POST /cases`가 case ID를 만든다.
2. 파일을 Blob 구현에 저장한다.
3. `DocumentService`가 PDF 페이지 텍스트를 추출한다.
4. case를 데이터 저장소에 저장한다.

결재안 생성:

1. status를 `processing`으로 변경한다.
2. `RagService.generate()`를 호출한다.
3. 성공 시 `generated`, 실패 시 `failed`로 저장한다.

자동 저장:

- `PATCH /cases/{id}`는 전달받은 필드만 변경한다.
- 변경 후 누락 검증을 다시 수행하고 저장한다.

복사:

- 새 case ID를 생성한다.
- 원본 파일을 새 경로로 복사한다.
- 기존 버전과 채팅 로그는 초기화한다.
- 복사된 파일에는 재확인이 필요하다는 표시를 저장한다.

### 5.5 `backend/app/routers/settings.py`

초기 설정과 기준 자료 API를 제공한다.

- 기준 설정은 동일한 카테고리와 결재 종류 조합을 갱신한다.
- 자료 파일은 `config-materials` 영역에 저장한다.
- PDF는 페이지별 텍스트, MD/TXT는 UTF-8 텍스트를 읽는다.
- 재색인 시 기준 자료와 과거 결재를 공통 검색 문서 구조로 변환한다.

### 5.6 `backend/app/routers/health.py`

두 종류의 상태 확인을 제공한다.

- `/health`: FastAPI 프로세스가 응답하는지 확인
- `/health/dependencies`: Blob, AI Search, Azure OpenAI, Cosmos 연결 확인

`/health`는 Streamlit 시작, 로드밸런서, 운영 모니터링에서 백엔드 생존 여부를 빠르게 판단하기 위해 필요하다.
`/health/dependencies`는 초기 설정 화면에서만 사용하며, 키를 노출하지 않고 다음 안전한 정보도 표시한다.

- 실제 Storage Account 이름과 사용하는 Blob 컨테이너
- AI Search 인덱스명
- Search 등록 방식이 SDK 직접 업로드 방식이라는 점
- Cosmos를 끈 경우 로컬 저장 파일 `data/database.json`

## 6. 서비스 계층

### 6.1 `backend/app/services/container.py`

`APP_STORAGE_MODE`에 따라 구현체를 선택하는 조립 지점이다.

Local mode:

- `LocalDataStore`
- `LocalBlobStore`
- `LocalSearchService`
- `LocalAIService`

Azure mode:

- `AzureDataStore`
- `AzureBlobStore`
- `AzureSearchService`
- `AzureAIService`

화면과 router는 구현체 차이를 알 필요가 없다. 따라서 Local mode에서 기능을 먼저 검증한 뒤 환경변수로 Azure mode로 전환할 수 있다.

### 6.2 `backend/app/services/storage.py`

Local 저장:

- 메타데이터: `data/database.json`
- 파일: `data/files/{container}/{path}`
- JSON 저장 시 임시 파일 작성 후 교체해 중간 손상을 줄인다.

Azure 저장:

- Blob Storage: 원본과 기준 자료
- Cosmos DB `decision-data`: case, 설정, 기준 자료 메타데이터
- Cosmos DB `past-decisions`: 과거 결재 샘플

Cosmos DB가 애플리케이션 데이터베이스이며 별도의 일반 DB는 사용하지 않는다.
`AZURE_COSMOS_ENABLED=false`인 Azure mode에서는 Blob, AI Search, Azure OpenAI는 Azure를 사용하고,
case, 작성 이력, 설정, 기준 자료 메타데이터만 `data/database.json`에 저장한다.

Blob 저장 경로:

- 초기 설정 자료: `config-materials/settings/{category}/{approval_type}/{material_id}/{file_name}`
- 신규 작성 첨부: `uploaded-documents/cases/{case_id}/original/{file_id}_{file_name}`
- Local mode의 같은 논리 경로: `data/files/{container}/{path}`

### 6.3 `backend/app/services/document_service.py`

문서 처리 담당이다.

현재 지원:

- 텍스트가 포함된 PDF의 페이지별 추출
- JPG/PNG 저장과 미리보기
- 파일명과 본문에서 청구서, 견적서, 계약서 등 문서 종류 판정
- 금액, 거래처, 서비스명, 문서일자, 이용 시작일·종료일 정규식 추출
- 복수 문서의 금액, 거래처, 서비스명, 이용 기간 일치 여부 판정

현재 미지원:

- 스캔 PDF와 이미지 OCR
- 표 구조 복원

공통 추출 규칙은 `backend/app/services/document_fields.py`에 둔다.
백엔드 검증과 프론트엔드 비교표가 같은 정규식과 날짜·금액 정규화 규칙을 사용하므로
한쪽 화면만 다른 값을 표시하는 문제를 줄인다.

`frontend/document_comparison.py`는 공통 추출 결과를 다음 열로 변환한다.

- 확인 항목
- AI 결재 폼 값
- 문서 종류
- 문서 기재값
- 대조 결과

### 6.4 `backend/app/services/search_service.py`

Local 검색:

- 검색어와 문서의 토큰 겹침으로 점수를 계산한다.
- 업무 카테고리와 결재 종류를 필터링한다.
- 규정, 필요서류 기준, 표준 양식에 우선 점수를 더한다.
- 재색인 버튼은 검색 대상 건수만 확인하며 자료를 다시 저장하지 않는다.

Azure 검색:

- 키워드 검색과 임베딩 벡터 검색을 함께 수행한다.
- 업무 카테고리와 결재 종류 필터를 적용한다.
- 결과를 RAG 생성 근거로 반환한다.

RAG 전체가 AI Search 안에서 실행되는 것은 아니다. AI Search는 관련 근거를 검색하고, FastAPI의 `RagService`가 검색 결과를 Azure OpenAI 입력과 결합하며, Azure OpenAI가 최종 답변을 생성한다.

### 6.5 `backend/app/services/ai_service.py`

Local AI:

- 규칙 기반으로 데모 결재 폼을 생성한다.
- 실제 생성형 AI 호출 없이 화면과 API 동작을 확인한다.
- `3文` 지시는 결재 본문을 최대 세 문장으로 단순 축약한다.

Azure AI:

- Azure OpenAI Chat Completions에 구조화 JSON을 요청한다.
- `GenerationPayload` 스키마로 응답을 검증한다.
- 검증 실패 시 한 번 수정 요청을 보낸다.
- Embedding API는 AI Search 벡터 생성과 검색 질의에 사용한다.

시스템 프롬프트는 규정과 필요서류 기준을 우선하고, 과거 사례는 표현 참고로만 사용하도록 지정한다.

### 6.6 `backend/app/services/rag_service.py`

RAG 처리의 중심 오케스트레이터이다.

`generate()` 순서:

1. 카테고리별 requirement 조회
2. 업로드 문서 텍스트 결합
3. 금액, 날짜, 거래처, 서비스명 추출
4. 검색 질의 생성
5. 기준 자료와 과거 결재 검색
6. AI에 생성 요청
7. 필수서류, 조건부 서류, 주요 필드 누락 검증
8. 복수 문서의 금액·거래처·서비스명·기간 불일치 검증
9. 경고 항목을 체크리스트에 `要確認`으로 반영
10. 유사 결재와 필드별 출처 구성
11. 버전 증가와 자동 저장

`revise()`는 추가 채팅 지시를 반영하고 새 버전과 채팅 로그를 저장한다.

`required_documents`와 `conditional_documents`를 모두 판정한다. 현재 조건식은 `10万円以上`,
`年間契約`, `新規契約`, `新規取引`, `継続契約` 등의 키워드와 폼 값을 이용한다.

문서 간 불일치 검증은 Azure OpenAI 응답과 별도로 실행한다. 따라서 AI가 잘못된 체크리스트를 반환해도
서버가 실제 추출값을 비교하여 `DOCUMENT_AMOUNT_MISMATCH`,
`DOCUMENT_VENDOR_MISMATCH`, `DOCUMENT_SERVICE_NAME_MISMATCH`,
`DOCUMENT_SERVICE_PERIOD_MISMATCH` 경고를 생성한다.

## 7. RAG 데이터 흐름

### 7.1 기준 자료 준비

```text
초기 설정 화면
  -> 기준 자료 업로드
  -> Blob Storage 저장
  -> Cosmos DB 또는 data/database.json에 메타데이터 저장
  -> FastAPI가 PDF/MD/TXT 텍스트 추출
  -> Azure OpenAI Embedding 생성
  -> 검색 인덱스 갱신
  -> Azure AI Search SDK upload_documents로 직접 색인
```

본 구현은 Azure AI Search의 Pull Indexer 방식이 아니다. 따라서 본 애플리케이션 전용
Data source, Indexer, Skillset은 생성하지 않는다. 인덱스만 생성하고 FastAPI가 문서와 벡터를 직접 등록한다.

### 7.2 신규 결재 생성

```text
결재 입력 + 첨부파일
  -> FastAPI
  -> Blob Storage 원본 저장
  -> PDF 텍스트 추출
  -> AI Search 하이브리드 검색
  -> Azure OpenAI 구조화 생성
  -> 필수서류·문서 간 값 불일치 검증과 출처 연결
  -> Cosmos DB 또는 data/database.json 자동 저장
  -> Streamlit 결과 표시
```

현재 업로드 문서는 즉시 AI Search 인덱스에 넣지 않는다. 해당 요청의 추출과 생성 근거로 사용하고, 생성 결과는 case 이력으로 저장한다.

## 8. 저장 데이터와 버전

case 한 건에는 다음 정보가 함께 저장된다.

- 사용자 입력
- 첨부파일 메타데이터와 추출 페이지
- AI 추출 필드
- 결재 폼
- 요약과 체크리스트
- 부족·주의 결과
- 유사 결재
- 필드별 출처
- 채팅 로그와 생성 버전

버전 증가 시점:

- 최초 `AI決裁案を作成`
- 추가 채팅에 의한 재생성

폼을 직접 수정한 `PATCH`는 현재 값은 저장하지만 별도 버전을 만들지는 않는다.

## 9. Azure 초기화 스크립트

`scripts/bootstrap_azure.py`는 기존 Azure 계정 수준 리소스를 새로 만들지 않는다.

생성 또는 확인 대상:

- Blob 컨테이너 4개
- `AZURE_COSMOS_ENABLED=true`일 때만 Cosmos DB `decision-rag`와 컨테이너
- `.env`의 `AZURE_SEARCH_INDEX_NAME`으로 지정한 AI Search 인덱스

Embedding API의 실제 벡터 길이를 확인한 뒤 AI Search 필드 차원을 설정한다.
AI Search Data source, Indexer, Skillset은 생성하지 않는다. 애플리케이션이
`SearchClient.upload_documents()`로 기준 자료와 과거 결재를 직접 등록하기 때문이다.

## 10. 테스트 자료 생성

`scripts/generate_test_documents.py`는 `sample_data/test_documents/upload/`의 Markdown을 일본어 텍스트 추출이 가능한 PDF로 변환한다.

```powershell
python -m scripts.generate_test_documents
```

출력 위치:

```text
sample_data/test_documents/pdf/
```

이 PDF는 문서 추출, 필수서류 판정, 원본 미리보기 수동 테스트에 사용한다.

## 11. 테스트 코드

주요 테스트:

- `tests/test_api.py`: 설정, 생성, 수정, 채팅, 복사 API
- `tests/test_document_service.py`: PDF 텍스트와 기본 필드 추출
- `tests/test_ui_policy.py`: 버튼 정책과 화면 문구
- `tests/test_test_documents.py`: 제공 테스트 PDF의 생성과 추출 가능 여부

실행:

```powershell
pytest -q
```

## 12. 주요 제한사항

- 로그인과 사용자별 권한은 구현하지 않았으며 `demo-user`를 사용한다.
- 이미지와 스캔 PDF의 OCR은 구현하지 않았다.
- 조건부서류의 조건식은 화면 안내만 하며 자동 판정하지 않는다.
- 여러 첨부문서 사이 금액, 날짜, 계약기간 불일치는 자동 판정하지 않는다.
- Local 검색은 단순 토큰 검색이므로 Azure AI Search와 검색 품질이 다르다.
- Local AI 결과는 규칙 기반이며 실제 생성형 AI 품질을 평가할 수 없다.
- 기존 코드나 Git 이력에 키가 노출된 적이 있다면 Azure 통합 전에 반드시 키를 재발급해야 한다.

## 13. 기능 확장 시 수정 위치

새 추출 필드 추가:

1. `ApprovalForm`과 필요하면 `CaseRecord` 스키마 수정
2. `DocumentService.extract_basic_fields()` 또는 Azure AI 출력 스키마 수정
3. `RagService` 검증과 출처 연결 수정
4. `result_page.py` 입력 위젯 추가
5. API 및 UI 회귀 테스트 추가

새 카테고리 추가:

1. Streamlit `CATEGORIES` 수정
2. 샘플 requirement 추가
3. 기준 자료 등록
4. AI Search 재색인
5. 해당 카테고리 테스트 케이스 추가

새 검증 규칙 추가:

1. 요구사항과 오류 코드 정의
2. `RagService._validate()` 또는 별도 검증 서비스 구현
3. `ValidationResult`로 화면에 전달
4. 정상계와 오류계 테스트 추가

## 14. 장애 확인 순서

화면이 열리지 않을 때:

1. 가상환경이 활성화되었는지 확인한다.
2. FastAPI `http://localhost:8000/health`를 확인한다.
3. Streamlit 실행 위치가 저장소 루트인지 확인한다.
4. `BACKEND_URL`이 실제 FastAPI 주소와 같은지 확인한다.

생성이 실패할 때:

1. FastAPI 터미널 오류를 확인한다.
2. Azure mode라면 `/health/dependencies`를 확인한다.
3. Chat/Embedding 배포명과 API key를 확인한다.
4. AI Search 인덱스명과 벡터 차원을 확인한다.
5. 업로드 PDF에 실제 텍스트 레이어가 있는지 확인한다.

저장이 보이지 않을 때:

1. `AZURE_COSMOS_ENABLED=false`이면 `data/database.json`을 확인한다.
2. Blob 원본은 Storage Account의 `uploaded-documents` 컨테이너를 확인한다.
3. 페이지별 추출 결과는 `extracted-texts`, 생성 버전은 `generated-outputs`를 확인한다.
4. 기준 자료는 `config-materials`를 확인한다.
5. AI Search는 `.env`의 인덱스명을 확인하며 Data source, Indexer, Skillset은 찾지 않는다.
6. 직접 수정은 버전이 아니라 현재 폼 값만 변경한다는 점을 확인한다.
