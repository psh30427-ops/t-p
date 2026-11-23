import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from google.genai import errors, types
from httpx import ConnectError
from PIL import Image

from main import call_gemini, check_brand, demo_brand, generate_text, main, read_brief


def valid_draft():
    brand = demo_brand({})
    brand['story'] = '수집품을 일상에서 즐기는 방법을 제안합니다. ' * 12
    brand['story'] = brand['story'].strip()
    return brand

class TestCli(unittest.TestCase):
    def test_brief(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.json';p.write_text(json.dumps({'industry':'x','target':'y','keywords':['a']}),encoding='utf-8')
            self.assertEqual(read_brief(p)['industry'],'x')
            p.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):read_brief(p)
    def test_brand(self):
        self.assertEqual(len(check_brand(demo_brand({}))['slogans']),3)

    def test_interactive_recovers_missing_brief_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'brief.json'
            path.write_text('{}', encoding='utf-8')
            output = Path(td) / 'out'
            with patch('builtins.input', side_effect=[str(path), '카드', '수집가', '휴대, 전시']) as user_input:
                self.assertEqual(main(['--demo', '--output', str(output)]), 0)
            self.assertEqual(user_input.call_count, 4)
            report = json.loads((output / 'brand_result.json').read_text())
            self.assertEqual(report['source_brief']['keywords'], ['휴대', '전시'])
            with patch('builtins.input') as user_input:
                self.assertEqual(main(['--brief', str(path), '--demo']), 2)
            user_input.assert_not_called()

    def test_transient_errors_retry_with_bounded_backoff(self):
        failures = [errors.APIError(code, {}) for code in (429, 500, 502, 503, 504)]
        failures.append(ConnectError('network unavailable'))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__, code=getattr(failure, 'code', None)):
                operation = Mock(side_effect=[failure, failure, 'success'])
                with patch('main.random.uniform', return_value=0.25) as jitter, patch('main.time.sleep') as sleep:
                    self.assertEqual(call_gemini(operation, model='test'), 'success')
                self.assertEqual(operation.call_count, 3)
                self.assertEqual([call.args for call in sleep.call_args_list], [(1.25,), (2.25,)])
                self.assertEqual(jitter.call_count, 2)

    def test_permanent_errors_do_not_retry(self):
        for code in (400, 401, 403, 404):
            with self.subTest(code=code), patch('main.time.sleep') as sleep:
                operation = Mock(side_effect=errors.APIError(code, {}))
                with self.assertRaises(errors.APIError):
                    call_gemini(operation)
                operation.assert_called_once()
                sleep.assert_not_called()

    def test_revision_prompt_includes_specific_feedback_and_is_revalidated(self):
        brand = valid_draft()
        invalid = dict(brand, slogans=['하나'])
        client = Mock()
        generate = client.models.generate_content
        generate.side_effect = [Mock(text='{'), Mock(text=json.dumps(invalid)), Mock(text=json.dumps(brand))]
        self.assertEqual(generate_text(client, {}, 'test'), brand)
        self.assertEqual(generate.call_count, 3)
        self.assertIn('JSON 구문 오류', generate.call_args_list[1].kwargs['contents'])
        self.assertIn('슬로건은 문자열 3개', generate.call_args_list[2].kwargs['contents'])

    def test_revision_exhaustion_is_saved_as_failure(self):
        brief = Path(__file__).resolve().parents[1] / 'brief.json'
        brand = dict(valid_draft(), story='짧은 스토리')
        client = Mock()
        client.models.get.return_value = types.Model(supported_actions=['generateContent'])
        client.models.generate_content.return_value = Mock(text=json.dumps(brand))
        with tempfile.TemporaryDirectory() as td, patch.dict('os.environ', {'GEMINI_API_KEY': 'test'}), patch('dotenv.load_dotenv'), patch('main.create_client', return_value=client):
            self.assertEqual(main(['--brief', str(brief), '--output', td]), 1)
            result = json.loads((Path(td) / 'brand_result.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['brand'])
            self.assertEqual(result['logos'], [])
            self.assertIn('스토리', result['errors'][0])
        self.assertEqual(client.models.generate_content.call_count, 3)
        client.models.get.assert_called_once()
    def test_demo(self):
        with tempfile.TemporaryDirectory() as td, patch('dotenv.load_dotenv') as load_env:
            p=Path(td)/'b.json';p.write_text(json.dumps({'industry':'x','target':'y','keywords':['a']}),encoding='utf-8')
            output=Path(td)/'out'
            self.assertEqual(main(['--brief',str(p),'--output',str(output),'--demo']),0)
            self.assertTrue((output/'brand_result.json').exists())
            self.assertTrue((output/'color_palette.png').exists())
            self.assertFalse((output/'logo_01.png').exists())
            load_env.assert_not_called()

    def test_gemini_partial_failure(self):
        brief = Path(__file__).resolve().parents[1] / 'brief.json'
        brand = valid_draft()
        text_part = types.Part.from_text(text=json.dumps(brand))
        with BytesIO() as jpeg:
            Image.new('RGB', (3, 3)).save(jpeg, format='JPEG')
            image_part = types.Part.from_bytes(data=jpeg.getvalue(), mime_type='image/jpeg')

        def response(*parts):
            return types.GenerateContentResponse(candidates=[
                types.Candidate(content=types.Content(parts=list(parts))),
            ])

        for text_supported in (True, False):
            with self.subTest(text_supported=text_supported), tempfile.TemporaryDirectory() as td:
                client = Mock()
                supported = types.Model(supported_actions=['generateContent'])
                client.models.get.side_effect = [supported if text_supported else types.Model(), supported]
                failure = errors.ClientError(429, {'error': {'message': 'fake-secret'}})
                logos = [response(text_part, image_part), failure, failure, failure, response(image_part)]
                client.models.generate_content.side_effect = [response(text_part), *logos] if text_supported else logos
                env = {'GEMINI_API_KEY': 'fake-secret', 'GEMINI_TEXT_MODEL': 'test-text', 'GEMINI_IMAGE_MODEL': 'test-image'}
                with patch.dict('os.environ', env), patch('dotenv.load_dotenv'), patch('main.create_client', return_value=client), patch('main.time.sleep') as sleep:
                    self.assertEqual(main(['--brief', str(brief), '--output', td]), 1)

                output = Path(td)
                report = (output / 'brand_result.json').read_text(encoding='utf-8')
                result = json.loads(report)
                self.assertNotIn('fake-secret', report)
                self.assertEqual(result['brand'], brand if text_supported else None)
                self.assertEqual((output / 'color_palette.png').exists(), text_supported)
                self.assertEqual(result['status'], 'partial' if text_supported else 'failed')
                self.assertEqual(result['logos'], ['logo_01.png', 'logo_03.png'] if text_supported else [])
                calls = client.models.generate_content.call_args_list
                if text_supported:
                    self.assertEqual(calls[0].kwargs['config']['response_mime_type'], 'application/json')
                    self.assertTrue(any('HTTP 429' in error for error in result['errors']))
                    self.assertEqual(sleep.call_count, 2)
                    with Image.open(output / 'logo_03.png') as png:
                        self.assertEqual(png.format, 'PNG')
                    self.assertEqual(calls[-1].kwargs['model'], 'test-image')
                    self.assertEqual(calls[-1].kwargs['config']['response_modalities'], ['IMAGE'])
                else:
                    self.assertEqual(calls, [])
if __name__=='__main__':unittest.main()
