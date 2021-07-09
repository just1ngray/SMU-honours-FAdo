import unittest
from FAdo import reex

from benchmark.convert import Converter
from benchmark.fa_ext import InvariantNFA
from benchmark.reex_ext import chars, dotany


class TestReexExtAny(unittest.TestCase):
    def setUp(self):
        self.convert = Converter()
        return super(TestReexExtAny, self).setUp()

    def test_dunder_contains(self):
        atAny = self.convert.one("@any")
        self.assertTrue("a" in atAny)
        self.assertTrue("b" in atAny)
        self.assertTrue("F" in atAny)
        self.assertTrue("Z" in atAny)
        self.assertTrue("0" in atAny)
        self.assertTrue("8" in atAny)
        self.assertFalse("" in atAny)

    def test_evalWordP(self):
        atAny = self.convert.one("@any")
        self.assertTrue(atAny.evalWordP("a"))
        self.assertTrue(atAny.evalWordP("0"))
        self.assertTrue(atAny.evalWordP("Z"))

        self.assertFalse(atAny.evalWordP("aa"))
        self.assertFalse(atAny.evalWordP("any"))
        self.assertFalse(atAny.evalWordP("@any"))
        self.assertFalse(atAny.evalWordP("0Ab"))

        re = self.convert.one("((@any*)abc(@any*))")
        self.assertTrue(re.evalWordP("abc"))
        self.assertTrue(re.evalWordP("junkabc"))
        self.assertTrue(re.evalWordP("abcjunk"))
        self.assertTrue(re.evalWordP("012345abcjunk"))

        re = self.convert.one("((a + (@any*))@any)")
        self.assertTrue(re.evalWordP("ab"))
        self.assertTrue(re.evalWordP("b"))
        self.assertTrue(re.evalWordP("bbbbb"))

    def test_next(self):
        re = self.convert.one("@any")
        self.assertEqual(re.next("a"), "b")
        self.assertEqual(re.next("Z"), "a")
        self.assertEqual(re.next("3"), "4")
        self.assertEqual(re.next("z"), None)
        self.assertEqual(re.next("!"), "0")

    def test_intersect(self):
        re = self.convert.one("@any")
        self.assertEqual(re.intersect(self.convert.one("a")), self.convert.one("a"))
        self.assertEqual(re.intersect(self.convert.one("[abc]")), self.convert.one("[abc]"))
        self.assertEqual(re.intersect(self.convert.one("[^abc]")), self.convert.one("[^abc]"))
        self.assertEqual(re.intersect(self.convert.one("@epsilon")), None)


class TestReexExtCharClass(unittest.TestCase):
    def setUp(self):
        self.convert = Converter()
        return super(TestReexExtCharClass, self).setUp()

    def test_dunder_contains(self):
        re = self.convert.one("[ab0-37-9YZ]")
        self.assertTrue("a" in re)
        self.assertTrue("b" in re)
        self.assertTrue("Y" in re)
        self.assertTrue("Z" in re)
        self.assertTrue("0" in re)
        self.assertTrue("1" in re)
        self.assertTrue("2" in re)
        self.assertTrue("3" in re)
        self.assertTrue("8" in re)
        self.assertFalse("4" in re)
        self.assertFalse("A" in re)

        re = self.convert.one("[^ab0-37-9YZ]")
        self.assertFalse("a" in re)
        self.assertFalse("b" in re)
        self.assertFalse("Y" in re)
        self.assertFalse("Z" in re)
        self.assertFalse("0" in re)
        self.assertFalse("1" in re)
        self.assertFalse("2" in re)
        self.assertFalse("3" in re)
        self.assertFalse("8" in re)
        self.assertTrue("4" in re)
        self.assertTrue("A" in re)

    def test_evalWordP(self):
        re = self.convert.one("[ab]")
        self.assertTrue(re.evalWordP("a"))
        self.assertTrue(re.evalWordP("b"))
        self.assertFalse(re.evalWordP("ab"))
        self.assertFalse(re.evalWordP("z"))

        re = self.convert.one("[^ab]")
        self.assertFalse(re.evalWordP("a"))
        self.assertFalse(re.evalWordP("b"))
        self.assertFalse(re.evalWordP("ab"))
        self.assertFalse(re.evalWordP("zz"))
        self.assertTrue(re.evalWordP("z"))

        re = self.convert.one("[0-4]")
        for i in range(5):
            self.assertTrue(re.evalWordP(str(i)))
        self.assertFalse(re.evalWordP("5"))

        re = self.convert.one("[^0-4]")
        for i in range(5, 10):
            self.assertTrue(re.evalWordP(str(i)))
        self.assertTrue(re.evalWordP("a"))
        for i in range(5):
            self.assertFalse(re.evalWordP(str(i)))

        re = self.convert.one("[ab0-37-9YZ]")
        self.assertTrue(re.evalWordP("b"))
        self.assertTrue(re.evalWordP("Z"))
        self.assertTrue(re.evalWordP("0"))
        self.assertTrue(re.evalWordP("2"))
        self.assertTrue(re.evalWordP("9"))
        self.assertFalse(re.evalWordP("4"))
        self.assertFalse(re.evalWordP("c"))

        re = self.convert.one("[^ab0-37-9YZ]")
        self.assertFalse(re.evalWordP("b"))
        self.assertFalse(re.evalWordP("Z"))
        self.assertFalse(re.evalWordP("0"))
        self.assertFalse(re.evalWordP("2"))
        self.assertFalse(re.evalWordP("9"))
        self.assertTrue(re.evalWordP("4"))
        self.assertTrue(re.evalWordP("c"))

        re = self.convert.one("(<ASTART>(@epsilon + [Xx])[0-9A-Fa-f]([0-9A-Fa-f]*)<AEND>)")
        self.assertTrue(re.evalWordP("x0AFb3"))
        self.assertTrue(re.evalWordP("X0AFb3"))
        self.assertTrue(re.evalWordP("0AFb3"))
        self.assertFalse(re.evalWordP("0xffff"))

    def test_next(self):
        re = self.convert.one("[abcdef0-85-9]")
        self.assertEqual(re.next("a"), "b")
        for i in range(0, 9):
            self.assertEqual(re.next(str(i)), str(i + 1))
        self.assertEqual(re.next("9"), "a")
        self.assertEqual(re.next("z"), "0")
        self.assertEqual(re.next("f"), None)
        self.assertEqual(re.next("!"), "0")

        re = self.convert.one("[^abcdef2-75-8]")
        self.assertEqual(re.next("g"), "h")
        self.assertEqual(re.next(":"), ";")
        self.assertEqual(re.next("0"), "1")
        self.assertEqual(re.next("1"), "9")

    def test_intersect(self):
        def eq(chrs, other, result):
            intersection = chrs.intersect(other)
            self.assertEqual(str(intersection), result)

        chrs = chars("abc")
        eq(chrs, chars("b"), "[b]")
        eq(chrs, chars("bcdef"), "[bc]")
        eq(chrs, chars([("a", "z")]), "[abc]")
        eq(chrs, chars("b", neg=True), "[ac]")
        eq(chrs, chars("bcdef", neg=True), "[a]")
        eq(chrs, chars([("a", "z")], neg=True), "[]")

        chrs = chars([("a", "c")])
        eq(chrs, chars("b"), "[b]")
        eq(chrs, chars("bcdef"), "[bc]")
        eq(chrs, chars([("a", "z")]), "[a-c]")
        eq(chrs, chars("b", neg=True), "[ac]")
        eq(chrs, chars("bcdef", neg=True), "[a]")
        eq(chrs, chars([("a", "z")], neg=True), "[]")


if __name__ == "__main__":
    unittest.main()