import json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ObceTest(unittest.TestCase):
    def test_adresy_sdileni_a_kompatibilita_bez_obci(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d/'web').mkdir(); (d/'site').mkdir(); (d/'assets').mkdir()
            (d/'web/app.html').write_text((ROOT/'web/app.html').read_text())
            m = json.loads((ROOT/'priklady/mesto.json').read_text())
            m['url'] = 'https://example.cz/mapa'
            (d/'mesto.json').write_text(json.dumps(m))
            env = {**os.environ, 'PYTHONPATH':str(ROOT)}
            def build(): subprocess.run([sys.executable, str(ROOT/'build_html.py')], cwd=d, env=env, check=True, capture_output=True)
            build()
            main = (d/'site/index.html').read_text()
            self.assertIn('<link rel="canonical" href="https://example.cz/mapa/">', main)
            (d/'obce').mkdir()
            (d/'obce/lhota.json').write_text(json.dumps({'nazev':'Lhota'}))
            (d/'obce/jina.json').write_text(json.dumps({'nazev':'Jiná', 'url':'https://example.cz/vlastni.html'}))
            build()
            a = (d/'site/index_lhota.html').read_text()
            b = (d/'site/index_jina.html').read_text()
            self.assertIn('<link rel="canonical" href="https://example.cz/mapa/index_lhota.html">', a)
            self.assertIn('<meta property="og:url" content="https://example.cz/vlastni.html">', b)
            self.assertIn('<meta property="og:image" content="https://example.cz/mapa/obce/jina/og.jpg">', b)
            self.assertNotIn('vlastni.html/obce/', b)

if __name__ == '__main__': unittest.main()
