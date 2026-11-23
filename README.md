# PSA 카드 그립톡 브랜드 AI 생성 CLI

브랜드 브리프(JSON)를 바탕으로 브랜드명 3~5개와 각 이름의 의미, 슬로건 3개, 약 300자의 브랜드 스토리, HEX 컬러 팔레트와 로고 PNG 2~3개를 생성합니다. Google 공식 Python SDK `google-genai`로 Gemini Developer API를 호출합니다.

## 제품 콘셉트와 사용 기술

PSA 등급카드를 전용 프레임에 넣고 스마트폰 케이스에 연결해 휴대하거나 감상하는 그립 액세서리 콘셉트입니다. 프레임 뒤에는 접이식 원형 그립이 달립니다. 수집가가 좋아하는 카드를 일상에서 감상할 수 있도록 하는 것이 브랜드의 목표입니다. 접착력, 낙하 보호, 거치 안정성 등은 검증 전 설계 항목입니다.

- Python 3.10 이상과 표준 라이브러리 `argparse`, `json`, `unittest`
- Google 공식 SDK `google-genai`와 Gemini Developer API의 텍스트·이미지 모델
- `python-dotenv`로 환경변수 읽기, Matplotlib으로 팔레트 작성, Pillow로 로고 PNG 저장

## Windows에서 실행

1. Python 3.10 이상 설치
2. 이 폴더에서 PowerShell 열기
3. 다음 명령 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

4. `.env`에 Google AI Studio에서 발급한 `GEMINI_API_KEY`를 설정합니다. 실제 키는 로컬에만 보관합니다. Git에는 `.env.example`만 추가하세요.
5. 실행

```powershell
python main.py
```

`브랜드 브리프 JSON 경로`에 `brief.json`을 입력합니다. 브리프에는 문자열 `industry`, `target`, 비어 있지 않은 문자열 배열 `keywords`가 필요합니다. 출력 경로를 비우면 `./output`을 사용합니다.

macOS와 Linux에서는 다음과 같이 설치하고 실행합니다. 로컬 `.env`가 이미 있으면 그대로 사용합니다.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
python main.py
```

또는 바로 실행:

```powershell
python main.py --brief brief.json --output new_output --logos 2
```

## Gemini 모델 설정

텍스트와 팔레트만 생성하려면 `python main.py --brief brief.json --output new_output --skip-logos`를 실행합니다. 이 옵션은 이미지 모델 조회와 생성 요청을 건너뜁니다. 무료 실행이 필요하면 먼저 Google AI Studio에서 현재 키가 속한 프로젝트의 요금 등급이 Free인지 확인하세요.

| 환경 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 필수 | Gemini Developer API 인증 |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash-lite` | 브랜드 제안 JSON 생성 |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-lite-image` | 로고 이미지 생성 |

CLI는 시작 시 프로젝트 폴더의 `.env`를 읽습니다. 같은 이름의 셸 환경 변수가 있으면 그 값이 우선합니다. 각 단계에서 `models.get`으로 `generateContent` 지원을 확인합니다. 텍스트 모델에는 JSON 출력이, 이미지 모델에는 네이티브 이미지 출력이 필요하며, CLI는 실제 생성 요청과 반환 데이터에서 각각 확인합니다. 계정 권한, 결제 설정, 할당량은 API 호출 결과에 영향을 줄 수 있습니다. [텍스트 모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) · [이미지 모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image) · [공식 Python SDK](https://googleapis.github.io/python-genai/)

## API 없이 테스트

```powershell
python main.py --brief brief.json --output demo_output --demo
python -m unittest discover -s tests -v
```

**주의:** 데모 결과는 수동으로 작성된 예시이며 AI 생성 결과가 아닙니다. 이미지 API를 호출하지 않기 때문에 로고 PNG를 만들지 않습니다. 과제 제출의 실제 API 호출 검증은 정상 모드에서 수행하세요.

## 저장 파일
- `brand_result.json`: 브리프, 응답, 실행 모드, 생성 로고 파일명, 각 단계 오류
- `color_palette.png`: 메인 1개/서브 2~3개 색상 HEX 시각화
- `logo_01.png`~`logo_03.png`: 이미지 API가 성공한 항목만

## 제출 결과물

`submission/`에 검증한 결과물 4개를 담았습니다. 텍스트와 팔레트를 먼저 생성했고, 별도 실행에서 같은 브랜드 결과를 바탕으로 Gemini 이미지 API의 `gemini-3.1-flash-lite-image` 모델로 로고 2개를 생성했습니다. 제출 JSON의 `logos` 배열에 두 PNG 파일명을 기록했고, `logo_generation.separate_run`에 별도 실행임을 표시했습니다. `created_at`은 원본 텍스트 실행 기록의 생성 시각입니다.

| 파일 | 내용 |
| --- | --- |
| [brand_result.json](submission/brand_result.json) | 브랜드명과 의미 4개, 슬로건 3개, 276자 스토리, 메인 컬러 1개와 서브 컬러 2개 |
| [color_palette.png](submission/color_palette.png) | 스틸 차콜 `#2B2D31`, 클리어 실버 `#E0E2E5`, 아카이브 네이비 `#1E2530` |
| [logo_01.png](submission/logo_01.png) | 슬랩핏의 등급카드 프레임과 원형 그립을 결합한 세로형 시안, 1024×1024 |
| [logo_02.png](submission/logo_02.png) | 카드 모서리를 넣은 원형 배지와 슬랩핏 한글 워드마크를 배치한 가로형 시안, 1024×1024 |

## 오류/주의
- 필수 필드 `industry`, `target`, `keywords` 검증. JSON 누락·형식 오류는 즉시 안내.
- 단계별 오류를 표준 오류와 `brand_result.json`에 기록합니다. 검증된 브랜드가 없으면 팔레트와 로고 생성을 건너뜁니다. 개별 로고 오류가 발생하면 다음 로고를 시도하며, HTTP 401 또는 403은 나머지 이미지 요청을 중단합니다. 단계 오류가 있으면 종료 코드는 `1`입니다.
- 응답 스키마 또는 HEX가 이상하면 오류로 보고 잘못된 데이터 저장을 피함.
- 생성 이미지에는 글자 오탈자가 있을 수 있으므로 결과 검수 필요.
- 일부 계정은 이미지 모델 사용 권한이나 결제 설정이 필요함. API 사용 비용 발생 가능.
- 상표 검색 및 법적 사용 가능성은 이 프로그램이 검증하지 않음.
- 제품 콘셉트는 초경량 V02 B안의 *설계 가정*을 참조; 실제 그립 안전성, 거치·보호 성능은 미검증.

## API 재시도와 단계별 정제

- **전송 재시도.** HTTP 429·500·502·503·504 및 일시적인 연결·타임아웃 오류는 요청당 최초 시도를 포함해 최대 3회 시도합니다. 대기 시간은 1초, 2초에 각각 0~0.5초의 무작위 지터를 더합니다. 401·403 등 목록 밖의 HTTP 오류는 즉시 반환합니다. SDK의 추가 재시도는 끕니다.
- **초안 → 검증 → 정제.** 브리프에서 브랜드 초안을 만들고 JSON 구문, 항목 수, HEX 형식, 스토리 길이(260~340자), 브랜드명 중복 및 대표 후보를 검증합니다. 실패하면 구체적인 문제와 직전 응답을 Gemini에 전달하고 전체 결과를 다시 검증합니다. 정제는 최대 2회입니다.
- **브리프 보완.** 대화형 실행에서는 누락되거나 잘못된 필수 항목을 하나씩 입력받습니다. `--brief` 자동 실행은 재질문 없이 입력 오류를 출력하고 종료 코드 `2`를 반환합니다.
- **결과 상태.** JSON 기존 필드를 유지하며 `status`를 추가합니다. `success`는 요청한 작업 완료, `partial`은 유효한 브랜드가 있지만 후속 단계에 오류 발생, `failed`는 유효한 브랜드 미생성을 뜻합니다. 실패 원인은 `errors`에 저장됩니다.
- **호출 상한.** 정상 실행의 생성 요청은 텍스트 1회와 로고당 1회입니다. 정제와 전송 재시도가 모두 소진되는 경우 텍스트 최대 9회, 로고당 최대 3회입니다. 모델 확인 요청은 별도입니다. 호출 실패 후 서버가 이미 처리했을 수 있으므로 재시도와 정제는 사용량을 늘릴 수 있습니다. 이미지 호출을 생략하려면 `--skip-logos`를, API 없이 검증하려면 `--demo`를 사용합니다.

## 출처
- 제품 기존 설계: https://github.com/psh30427-ops/pokemon
- 최신 README: https://github.com/psh30427-ops/pokemon/blob/main/deliverables/psa_grip_v02/ultralight_revision/README_ko.md
- 검증 보고서: https://github.com/psh30427-ops/pokemon/blob/main/deliverables/psa_grip_v02/ultralight_revision/validation_report_ko.md
- API 문서: https://ai.google.dev/gemini-api/docs

이 프로젝트는 **기존 CAD 파일을 수정하거나 GitHub 저장소를 변경하지 않습니다.**
