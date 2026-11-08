"""Regresní příklady pro import průmyslových objektů z OSM."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

sys.modules.setdefault('geo', types.ModuleType('geo'))
spec = importlib.util.spec_from_file_location('kominy', Path(__file__).resolve().parents[1] / 'nastroje/kominy.py')
kominy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kominy)

class KominyTest(unittest.TestCase):
    def node(self, kind, lat=50.0):
        return {'lat': lat, 'lon': 15.0, 'tags': {'man_made': kind}}

    def test_blizke_rozne_druhy_zustavaji(self):
        got = kominy.vyber([self.node('chimney'), self.node('storage_tank')])
        self.assertEqual({x['k'] for x in got}, {'komin', 'nadrz'})

    def test_dva_blizke_body_stejneho_druhu_zustavaji(self):
        self.assertEqual(len(kominy.vyber([self.node('chimney'), self.node('chimney', 50.00002)])), 2)

    def test_bod_a_plocha_stejne_stavby_se_slouci(self):
        area = {'bounds': {'minlat': 49.99999, 'maxlat': 50.00001, 'minlon': 14.99999, 'maxlon': 15.00001}, 'tags': {'man_made': 'chimney'}}
        node = self.node('chimney'); node['tags']['height'] = '31'
        got = kominy.vyber([node, area])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['h'], 31)
        self.assertIsNotNone(got[0]['r'])

    def test_plocha_nepohlti_vic_nez_jeden_bod(self):
        area = {'bounds': {'minlat': 49.99999, 'maxlat': 50.00001, 'minlon': 14.99999, 'maxlon': 15.00001}, 'tags': {'man_made': 'chimney'}}
        got = kominy.vyber([area, self.node('chimney'), self.node('chimney', 50.00002)])
        self.assertEqual(len(got), 2)

    def test_podzemni_potrubi(self):
        geom = [{'lat': 50, 'lon': 15}, {'lat': 50.001, 'lon': 15}]
        elements = [{'geometry': geom, 'tags': t} for t in [
            {'location':'underground'}, {'location':'underwater'}, {'tunnel':'yes'}, {'tunnel':'culvert'}, {'layer':'-1'},
            {'location':'overground'}, {'tunnel':'no'}, {'layer':'1'}, {},
        ]]
        self.assertEqual(len(kominy.potrubi(elements)), 4)

if __name__ == '__main__': unittest.main()
