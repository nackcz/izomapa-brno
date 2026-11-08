import unittest
from nastroje.gtfs_casy import dopln_mezicasy

class MezicasyTest(unittest.TestCase):
    def test_doplni_cas_a_zachova_mezizastavku(self):
        data = [(3, 720, 720, 200, 'C'), (1, 600, 610, 0, 'A'), (2, None, None, 0, 'B')]
        out = dopln_mezicasy(data)
        self.assertEqual([x[4] for x in out], ['A', 'B', 'C'])
        self.assertEqual(out[1][1:4], (665, 665, 100))
    def test_vice_mezizastavek(self):
        data = [(1,0,0,0,'A'), (2,None,None,0,'B'), (3,None,None,0,'C'), (4,90,90,0,'D')]
        self.assertEqual([x[1] for x in dopln_mezicasy(data)], [0,30,60,90])
    def test_bez_extrapolace(self):
        data = [(1,None,None,0,'A'), (2,60,60,0,'B'), (3,None,None,0,'C')]
        self.assertEqual([x[4] for x in dopln_mezicasy(data)], ['B'])

if __name__ == '__main__': unittest.main()
