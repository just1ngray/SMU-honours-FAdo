import unittest

from benchmark import sample


class TestFAdoize(unittest.TestCase):
    def test_charclass(self):
        f = sample.FAdoize
        self.assertEqual(f('\\d'), '[0-9]')
        self.assertEqual(f('\\D'), '[^0-9]')
        self.assertEqual(f('[\\d]'), '[0-9]')

        self.assertEqual(f('\\s'), ' ')
        self.assertEqual(f('\\S'), '[^ ]')
        self.assertEqual(f('[\\s]'), '[ ]')

        self.assertEqual(f('\\w'), '[0-9A-Za-z_]')
        self.assertEqual(f('\\W'), '[^0-9A-Za-z_]')
        self.assertEqual(f('[\\w]'), '[0-9A-Za-z_]')

    def test_almost_charclass(self):
        f = sample.FAdoize
        self.assertEqual(f('\\\\d'), '(\\\\ d)')
        self.assertEqual(f('\\\\D'), '(\\\\ D)')
        self.assertEqual(f('[\\\\d]'), '[\\\\d]')

        self.assertEqual(f('\\\\s'), '(\\\\ s)')
        self.assertEqual(f('\\\\S'), '(\\\\ S)')
        self.assertEqual(f('[\\\\s]'), '[\\\\s]')

        self.assertEqual(f('\\\\w'), '(\\\\ w)')
        self.assertEqual(f('\\\\W'), '(\\\\ W)')
        self.assertEqual(f('[\\\\w]'), '[\\\\w]')



if __name__ == "__main__":
    unittest.main()