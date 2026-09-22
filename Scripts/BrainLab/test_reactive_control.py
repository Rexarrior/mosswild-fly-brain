"""Contract checks for the sensory-only comparison motor, before embodied runs."""
import math
import random
import unittest
from reactive_control import motor

class ControlContract(unittest.TestCase):
    def test_zero_and_mirror(self):
        self.assertEqual(motor([0.]*8)['drive'],0)
        rng=random.Random(8801)
        for _ in range(1000):
            c=[rng.random() for _ in range(8)]
            mirror=[c[1],c[0],c[3],c[2],c[5],c[4],c[6],c[7]]
            a,b=motor(c),motor(mirror)
            self.assertAlmostEqual(a['turn'],-b['turn'])
            self.assertAlmostEqual(a['drive'],b['drive'])
            self.assertTrue(-1<=a['turn']<=1 and 0<=a['drive']<=1)
            self.assertEqual(a['forward_hz'],0)
    def test_modalities_have_equal_weight(self):
        for i in (0,2,4):
            c=[0.]*8;c[i]=.1;c[6]=.4
            self.assertAlmostEqual(motor(c)['turn'],.4)
    def test_invalid_channels_rejected(self):
        for c in ([0]*7,[0]*9,[math.nan]*8,[-.1]*8,[1.1]*8):
            with self.assertRaises(ValueError):motor(c)

if __name__=='__main__':unittest.main()
