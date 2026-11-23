import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from google.genai import errors, types
from PIL import Image

from main import read_brief,check_brand,demo_brand,main

class TestCli(unittest.TestCase):
    def test_brief(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.json';p.write_text(json.dumps({'industry':'x','target':'y','keywords':['a']}),encoding='utf-8')
            self.assertEqual(read_brief(p)['industry'],'x')
            p.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):read_brief(p)
    def test_brand(self):
        self.assertEqual(len(check_brand(demo_brand({}))['slogans']),3)
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
        brand = demo_brand({})
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
                logos = [response(text_part, image_part), failure, response(image_part)]
                client.models.generate_content.side_effect = [response(text_part), *logos] if text_supported else logos
                env = {'GEMINI_API_KEY': 'fake-secret', 'GEMINI_TEXT_MODEL': 'test-text', 'GEMINI_IMAGE_MODEL': 'test-image'}
                with patch.dict('os.environ', env), patch('dotenv.load_dotenv'), patch('main.create_client', return_value=client):
                    self.assertEqual(main(['--brief', str(brief), '--output', td]), 1)

                output = Path(td)
                report = (output / 'brand_result.json').read_text(encoding='utf-8')
                result = json.loads(report)
                self.assertNotIn('fake-secret', report)
                self.assertEqual(result['brand'], brand if text_supported else None)
                self.assertEqual((output / 'color_palette.png').exists(), text_supported)
                self.assertEqual(result['logos'], ['logo_01.png', 'logo_03.png'])
                self.assertTrue(any('HTTP 429' in error for error in result['errors']))
                with Image.open(output / 'logo_03.png') as png:
                    self.assertEqual(png.format, 'PNG')
                calls = client.models.generate_content.call_args_list
                if text_supported:
                    self.assertEqual(calls[0].kwargs['config']['response_mime_type'], 'application/json')
                else:
                    self.assertIn('without letters or words', calls[0].kwargs['contents'])
                self.assertEqual(calls[-1].kwargs['model'], 'test-image')
                self.assertEqual(calls[-1].kwargs['config']['response_modalities'], ['IMAGE'])
if __name__=='__main__':unittest.main()
