import unittest
import copy

from benchmark.util import RangeList

class TestRangeList(unittest.TestCase):
    def setUp(self):
        inc = lambda x: x+1
        dec = lambda x: x-1
        self.getRange = lambda: RangeList([(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)], inc=inc, dec=dec)
        return super(TestRangeList, self).setUp()

    def test_add_base(self):
        l = self.getRange()
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_add_noChange(self):
        l = self.getRange()
        l.add(15)
        l.add(90, 91)
        l.add(100)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_add_outsideHigh(self):
        l = self.getRange()
        l.add(200)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100), (200, 200)]")
        l.add(200, 201)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100), (200, 201)]")

    def test_add_outsideLow(self):
        l = self.getRange()
        l.add(-200)
        self.assertEqual(str(l), "[(-200, -200), (10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")
        l.add(-201, -200)
        self.assertEqual(str(l), "[(-201, -200), (10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_add_insideNoOverlap(self):
        l = self.getRange()
        l.add(25)
        l.add(61, 69)
        self.assertEqual(str(l), "[(10, 20), (25, 25), (30, 40), (50, 60), (61, 69), (70, 80), (90, 100)]")

    def test_add_overlapLow(self):
        l = self.getRange()
        l.add(35, 45)
        self.assertEqual(str(l), "[(10, 20), (30, 45), (50, 60), (70, 80), (90, 100)]")

    def test_add_overlapHigh(self):
        l = self.getRange()
        l.add(85, 95)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (85, 100)]")

    def test_add_mergeInternal(self):
        l = self.getRange()
        l.add(20, 61)
        self.assertEqual(str(l), "[(10, 61), (70, 80), (90, 100)]")

    def test_add_mergeUpper(self):
        l = self.getRange()
        l.add(0, 110)
        self.assertEqual(str(l), "[(0, 110)]")

    def test_add_mergeLower(self):
        l = self.getRange()
        l.add(-10, 100)
        self.assertEqual(str(l), "[(-10, 100)]")

    def test_add_mergeAllExact(self):
        l = self.getRange()
        l.add(0, 100)
        self.assertEqual(str(l), "[(0, 100)]")

    def test_add_mergeAllOver(self):
        l = self.getRange()
        l.add(-10, 110)
        self.assertEqual(str(l), "[(-10, 110)]")


    def test_remove_none(self):
        l = self.getRange()
        l.remove(0, 5)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")
        l.remove(110, 200)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")
        l.remove(21, 22)
        self.assertEqual(str(l), "[(10, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_remove_splitOne(self):
        l = self.getRange()
        l.remove(11, 19)
        self.assertEqual(str(l), "[(10, 10), (20, 20), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_remove_one(self):
        l = self.getRange()
        l.remove(10, 20)
        self.assertEqual(str(l), "[(30, 40), (50, 60), (70, 80), (90, 100)]")
        l.remove(90, 100)
        self.assertEqual(str(l), "[(30, 40), (50, 60), (70, 80)]")
        l.remove(50, 60)
        self.assertEqual(str(l), "[(30, 40), (70, 80)]")

    def test_remove_upper(self):
        l = self.getRange()
        l.remove(15, 25)
        self.assertEqual(str(l), "[(10, 14), (30, 40), (50, 60), (70, 80), (90, 100)]")

    def test_remove_lower(self):
        l = self.getRange()
        l.remove(25, 35)
        self.assertEqual(str(l), "[(10, 20), (36, 40), (50, 60), (70, 80), (90, 100)]")

    def test_remove_span(self):
        l = self.getRange()
        l.remove(25, 75)
        self.assertEqual(str(l), "[(10, 20), (76, 80), (90, 100)]")

        l = self.getRange()
        l.remove(15, 65)
        self.assertEqual(str(l), "[(10, 14), (70, 80), (90, 100)]")

    def test_remove_innerOne(self):
        l = self.getRange()
        l.remove(31, 39)
        self.assertEqual(str(l), "[(10, 20), (30, 30), (40, 40), (50, 60), (70, 80), (90, 100)]")


    def test_intersection(self):
        # input cases from the leetcode problem
        a = RangeList([(0,2),(5,10),(13,23),(24,25)], inc=lambda x: x+1, dec=lambda x: x-1)
        b = RangeList([(1,5),(8,12),(15,24),(25,26)], inc=lambda x: x+1, dec=lambda x: x-1)
        self.assertEqual(str(a.intersection(b)), "[(1, 2), (5, 5), (8, 10), (15, 23), (24, 24), (25, 25)]")

        a = RangeList([(1,3), (5,9)], inc=lambda x: x+1, dec=lambda x: x-1)
        b = RangeList([], inc=lambda x: x+1, dec=lambda x: x-1)
        self.assertEqual(str(a.intersection(b)), "[]")

        a = RangeList([], inc=lambda x: x+1, dec=lambda x: x-1)
        b = RangeList([(1,3), (5,9)], inc=lambda x: x+1, dec=lambda x: x-1)
        self.assertEqual(str(a.intersection(b)), "[]")

        a = RangeList([(1, 7)], inc=lambda x: x+1, dec=lambda x: x-1)
        b = RangeList([(3, 10)], inc=lambda x: x+1, dec=lambda x: x-1)
        self.assertEqual(str(a.intersection(b)), "[(3, 7)]")


if __name__ == "__main__":
    unittest.main()