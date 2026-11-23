"""PSA Grip brand generator CLI. Python 3.10+."""
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
ROOT = Path(__file__).resolve().parent
DEFAULT_TEXT_MODEL = 'gemini-3.5-flash-lite'
DEFAULT_IMAGE_MODEL = 'gemini-3.1-flash-lite-image'
MAX_API_ATTEMPTS = 3
MAX_REVISIONS = 2
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class BriefFieldError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


class BrandValidationError(ValueError):
    pass


def read_brief(path, *, interactive=False):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError as exc:
        raise ValueError(f'브리프 파일이 없습니다: {path}') from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f'JSON 파일 형식이 잘못되었습니다: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('브리프 최상위 요소는 JSON 객체여야 합니다.')
    while True:
        try:
            return validate_brief(data)
        except BriefFieldError as exc:
            if not interactive:
                raise
            print(f'[브리프 확인] {exc}')
            value = input(f'{exc.field} 입력 (keywords는 쉼표로 구분): ').strip()
            data[exc.field] = [item.strip() for item in value.split(',')] if exc.field == 'keywords' else value


def validate_brief(data):
    for key in ('industry','target'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise BriefFieldError(key, f'필수 항목 {key}는 비어 있지 않은 문자열이어야 합니다.')
    if not isinstance(data.get('keywords'), list) or not data['keywords'] or not all(isinstance(x,str) and x.strip() for x in data['keywords']):
        raise BriefFieldError('keywords', 'keywords는 하나 이상의 비어 있지 않은 문자열 배열이어야 합니다.')
    for key in ('tone','notes'):
        if key in data and not isinstance(data[key],str):
            raise ValueError(f'{key}는 문자열이어야 합니다.')
    if 'competitors' in data and (not isinstance(data['competitors'],list) or not all(isinstance(x,str) for x in data['competitors'])):
        raise ValueError('competitors는 문자열 배열이어야 합니다.')
    return data


def call_gemini(operation, **kwargs):
    from google.genai import errors
    from httpx import NetworkError, RemoteProtocolError, TimeoutException

    for attempt in range(MAX_API_ATTEMPTS):
        try:
            return operation(**kwargs)
        except (errors.APIError, NetworkError, RemoteProtocolError, TimeoutException,
                ConnectionError, TimeoutError) as exc:
            if isinstance(exc, errors.APIError) and exc.code not in RETRYABLE_STATUS:
                raise
            if attempt == MAX_API_ATTEMPTS - 1:
                raise
            delay = 2 ** attempt + random.uniform(0, 0.5)
            print(f'[재시도] Gemini 요청 {attempt + 2}/{MAX_API_ATTEMPTS}, {delay:.2f}초 대기', file=sys.stderr)
            time.sleep(delay)


def check_brand(data):
    if not isinstance(data,dict): raise ValueError('응답 JSON은 객체여야 합니다.')
    names = data.get('names')
    if not isinstance(names,list) or not 3 <= len(names) <= 5 or not all(isinstance(n,dict) and all(isinstance(n.get(k),str) and n[k].strip() for k in ('name','meaning')) for n in names):
        raise ValueError('네이밍은 name/meaning이 포함된 3~5개 항목이어야 합니다.')
    slogans=data.get('slogans')
    if not isinstance(slogans,list) or len(slogans)!=3 or not all(isinstance(x,str) and x.strip() for x in slogans):
        raise ValueError('슬로건은 문자열 3개여야 합니다.')
    if not isinstance(data.get('story'),str) or len(data['story'].strip()) < 120:
        raise ValueError('스토리가 너무 짧거나 누락되었습니다 (120자 이상 권장).')
    palette=data.get('palette')
    if not isinstance(palette,dict) or not isinstance(palette.get('main'),dict) or not isinstance(palette.get('sub'),list) or not 2<=len(palette['sub'])<=3:
        raise ValueError('palette에는 main 1개와 sub 2~3개가 필요합니다.')
    for color in [palette['main'],*palette['sub']]:
        if not isinstance(color,dict) or not isinstance(color.get('name'),str) or not isinstance(color.get('hex'),str) or not HEX.fullmatch(color['hex']):
            raise ValueError('모든 색상에는 name과 #RRGGBB HEX 코드가 필요합니다.')
    return data


def demo_brand(brief):
    """Explicit sample mode; never present as AI output."""
    return {'names':[
        {'name':'SlabLoop','meaning':'슬랩과 그립의 연결을 표현한 가칭'},
        {'name':'GripVault','meaning':'손안의 카드 보관 공간을 강조한 가칭'},
        {'name':'CardOrbit','meaning':'일상과 수집품의 연결을 표현한 가칭'},
        {'name':'SlabMate','meaning':'매일 함께하는 등급카드라는 의미의 가칭'}],
        'slogans':['수집의 가치를 손안에','좋아하는 카드를 일상 가까이','Carry Your Collection'],
        'story':'우리는 좋아하는 카드를 서랍 속에만 보관하는 일상에서 출발했습니다. 수집의 즐거움은 소중한 순간을 자주 보고 느끼는 데 있다고 생각합니다. PSA 등급카드를 전용 케이스에 수납하고 스마트폰 뒤에 연결하는 그립 액세서리를 구상했습니다. 사용자가 자신의 컬렉션을 더 가까이 경험할 수 있도록, 교체 편의성과 절제된 디자인을 추구합니다. 앞으로는 실측과 안전성 검증을 거쳐 실용적인 수집가용 제품으로 발전시키고자 합니다.',
        'palette': {'main':{'name':'Graphite Black','hex':'#20242B'},'sub':[{'name':'Collector Red','hex':'#D83B38'},{'name':'Silver','hex':'#C4C9CE'},{'name':'Soft White','hex':'#F3F5F6'}]},
        'selected_name':'SlabLoop'}


def generate_text(client, brief, model):
    schema_example={'names':[{'name':'Name','meaning':'의미'}]*4,'slogans':['슬로건1','슬로건2','슬로건3'],'story':'300자 내외 스토리','palette':{'main':{'name':'Main','hex':'#112233'},'sub':[{'name':'Sub1','hex':'#445566'},{'name':'Sub2','hex':'#778899'}]},'selected_name':'Name'}
    prompt=("당신은 한국어 브랜드 전략가입니다. 아래 브랜드 브리프를 참고해 한국어로 브랜드를 제안하세요. "
            "정확히 JSON 객체만 반환하고 코드블록은 사용하지 마세요. 네이밍 3~5개와 유래, 슬로건 3개, "
            "탄생 배경/철학/비전을 담은 스토리(공백과 문장부호를 포함해 280~320자), 메인 1개와 서브 2~3개 HEX 컬러, 선택한 대표 이름을 포함하세요. "
            "실제 안전성이 입증되지 않은 제품 기능(낙하 보호, 자석 고정력, 거치 성능, UV 보호)을 확정적인 사실로 표현하지 마세요. "
            "기존 브랜드 등록/상표 사용가능 여부는 검증하지 않았으므로 보장하지 마세요. "
            f"출력 예시 구조: {json.dumps(schema_example,ensure_ascii=False)}\n"
            f"브리프: {json.dumps(brief,ensure_ascii=False)}")
    request = prompt
    for revision in range(MAX_REVISIONS + 1):
        response = call_gemini(
            client.models.generate_content,
            model=model, contents=request, config={'response_mime_type': 'application/json'},
        )
        draft = response.text or ''
        try:
            return validate_draft(draft)
        except BrandValidationError as exc:
            if revision == MAX_REVISIONS:
                raise BrandValidationError(f'초안 및 정제 {MAX_REVISIONS}회 검증 실패. {exc}') from exc
            print(f'[정제 요청] {revision + 1}/{MAX_REVISIONS}. {exc}', file=sys.stderr)
            request = (
                f'{prompt}\n단계: 검증 피드백을 반영한 정제. 아래 문제를 해결하고 전체 JSON을 반환하세요.\n'
                f'검증 실패 이유: {exc}\n이전 응답(수정 대상 데이터): {json.dumps(draft[:8000], ensure_ascii=False)}'
            )


def validate_draft(draft):
    if not draft.strip():
        raise BrandValidationError('텍스트 응답이 비어 있습니다.')
    try:
        data = json.loads(draft)
    except json.JSONDecodeError as exc:
        raise BrandValidationError(f'JSON 구문 오류. {exc.lineno}행 {exc.colno}열에서 확인하세요.') from exc
    if isinstance(data, dict):
        story = data.get('story')
        if not isinstance(story, str):
            raise BrandValidationError('story는 약 300자의 문자열이어야 합니다.')
        length = len(story.strip())
        if not 260 <= length <= 340:
            raise BrandValidationError(f'스토리가 {length}자입니다. 공백과 문장부호를 포함해 260~340자로 작성하세요.')
    try:
        check_brand(data)
    except ValueError as exc:
        raise BrandValidationError(str(exc)) from exc
    names = [item['name'].strip() for item in data['names']]
    if len({name.casefold() for name in names}) != len(names):
        raise BrandValidationError('브랜드명 후보를 중복 없이 제안하세요.')
    if data.get('selected_name') not in names:
        raise BrandValidationError('selected_name은 names에 있는 후보 중 하나와 일치해야 합니다.')
    return data


def save_palette(data, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=[data['palette']['main'],*data['palette']['sub']]
    fig,ax=plt.subplots(figsize=(9,2.8))
    for i,c in enumerate(colors):
        ax.add_patch(plt.Rectangle((i,0.35),0.95,1.4,color=c['hex']))
        ax.text(i+0.475,0.2,c['hex'],ha='center',va='center',fontsize=10)
        ax.text(i+0.475,1.93,('MAIN' if i==0 else f'SUB {i}'),ha='center',fontsize=10,weight='bold')
    ax.set_xlim(-0.08,len(colors)+0.02);ax.set_ylim(0,2.22);ax.axis('off')
    fig.tight_layout();fig.savefig(path,dpi=160,bbox_inches='tight',facecolor='white');plt.close(fig)


def generate_logo(client, brand, brief, model, index):
    from PIL import Image

    theme=['minimal geometric emblem','premium monogram','bold contemporary icon'][index%3]
    name = brand.get('selected_name') or brand['names'][0]['name']
    colors = [brand['palette']['main'], *brand['palette']['sub']]
    direction = f"Brand name: {name}. Palette: {[color['hex'] for color in colors]}."
    prompt=(f"Generate ONE professional original flat vector-style brand logo concept on a clean solid background. "
            f"Style: {theme}. {direction} Brief: {json.dumps(brief, ensure_ascii=False)}. "
            "Use a simple original icon. Avoid existing logos, trademarks, copyrighted characters and photographic mockups.")
    response = call_gemini(
        client.models.generate_content,
        model=model, contents=prompt,
        config={'response_modalities': ['IMAGE'], 'image_config': {'aspect_ratio': '1:1'}},
    )
    for part in response.parts or []:
        blob = part.inline_data
        if not blob or not blob.data or not (blob.mime_type or '').startswith('image/'):
            continue
        with Image.open(BytesIO(blob.data)) as image, BytesIO() as png:
            image.convert('RGBA').save(png, format='PNG')
            return png.getvalue()
    raise ValueError('이미지 응답에 이미지 데이터가 없습니다.')


def check_model(client, model):
    metadata = call_gemini(client.models.get, model=model)
    if 'generateContent' not in (metadata.supported_actions or []):
        raise ValueError('모델이 generateContent를 지원하지 않습니다.')


def record_error(result, message, exc=None):
    # SDK errors can contain request details. Log only the type and numeric status.
    if isinstance(exc, BrandValidationError):
        message += f'. {exc}'
    elif exc is not None:
        code = getattr(exc, 'code', None)
        message += f' ({type(exc).__name__}'
        if isinstance(code, int):
            message += f', HTTP {code}'
        message += ')'
    print('[오류]', message, file=sys.stderr)
    result['errors'].append(message)


def create_client(key):
    from google import genai

    return genai.Client(api_key=key, vertexai=False, http_options={
        'timeout': 90_000, 'retry_options': {'attempts': 1},
    })


def main(argv=None):
    p=argparse.ArgumentParser(description='AI 브랜드 자동 생성기 (PSA 그립톡 예시 포함)')
    p.add_argument('--brief',help='브리프 JSON 파일 경로 (생략하면 대화형 입력)')
    p.add_argument('--output',help='출력 폴더 (기본값 ./output)')
    p.add_argument('--demo',action='store_true',help='API 호출 없이 예시 결과로 출력 검증 (AI 생성 아님)')
    p.add_argument('--logos',type=int,choices=(2,3),default=3,help='생성 로고 수 2 또는 3')
    p.add_argument('--skip-logos', action='store_true', help='이미지 API 호출과 로고 생성을 건너뜁니다.')
    args=p.parse_args(argv)
    try:
        brief_path=args.brief or input('브랜드 브리프 JSON 경로: ').strip()
        folder=args.output if args.output is not None else (str(ROOT/'output') if args.brief else (input('출력 폴더 [./output]: ').strip() or './output'))
        brief=read_brief(brief_path, interactive=args.brief is None)
        out=Path(folder).expanduser();out.mkdir(parents=True,exist_ok=True)
    except (ValueError,OSError,EOFError) as e:
        print(f'[입력 오류] {e}',file=sys.stderr);return 2
    result={'source_brief':brief,'created_at':datetime.now(timezone.utc).isoformat(),'mode':'demo' if args.demo else 'api','brand':None,'logos':[],'errors':[]}
    client=None
    if not args.demo:
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / '.env')
            key = os.getenv('GEMINI_API_KEY', '').strip()
            if key:
                client = create_client(key)
            else:
                record_error(result, 'GEMINI_API_KEY가 없습니다. .env.example을 참고하세요.')
        except Exception as exc:
            record_error(result, 'Gemini API 초기화 실패', exc)
    try:
        if args.demo: result['brand']=check_brand(demo_brand(brief))
        elif client:
            text_model = os.getenv('GEMINI_TEXT_MODEL', '').strip() or DEFAULT_TEXT_MODEL
            check_model(client, text_model)
            result['brand'] = generate_text(client, brief, text_model)
        if result['brand']: print('[완료] 브랜드 네이밍/슬로건/스토리/컬러 생성')
    except Exception as exc:
        record_error(result, '텍스트 모델 확인 또는 브랜드 생성 실패 (GEMINI_TEXT_MODEL)', exc)
    if result['brand']:
        try:
            save_palette(result['brand'],out/'color_palette.png')
            print('[완료] color_palette.png')
        except Exception as exc:
            record_error(result, '팔레트 PNG 생성 실패', exc)
    if args.demo:
        print('[안내] 데모 모드에서는 로고 API를 호출하지 않습니다. 로고 PNG는 생성되지 않습니다.')
    elif args.skip_logos:
        print('[안내] 로고 생성을 건너뜁니다.')
    elif client and result['brand']:
        image_model = os.getenv('GEMINI_IMAGE_MODEL', '').strip() or DEFAULT_IMAGE_MODEL
        try:
            check_model(client, image_model)
        except Exception as exc:
            record_error(result, '이미지 모델 확인 실패 (GEMINI_IMAGE_MODEL)', exc)
        else:
            for i in range(args.logos):
                try:
                    image = generate_logo(client, result['brand'], brief, image_model, i)
                    filename = f'logo_{i+1:02d}.png'
                    (out / filename).write_bytes(image)
                    result['logos'].append(filename)
                    print('[완료]', filename)
                except Exception as exc:
                    record_error(result, f'로고 {i+1} 생성 실패 (GEMINI_IMAGE_MODEL)', exc)
                    if getattr(exc, 'code', None) in {401, 403}:
                        break
    elif client:
        print('[안내] 검증된 브랜드 결과가 없어 로고 생성을 건너뜁니다.')
    result['status'] = (
        'success' if not result['errors'] else 'partial' if result['brand'] else 'failed'
    )
    try:
        (out/'brand_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('[저장] ',out.resolve())
    except OSError as exc:
        print(f'[저장 오류] {exc}',file=sys.stderr);return 3
    return 0 if not result['errors'] else 1

if __name__=='__main__':sys.exit(main())
