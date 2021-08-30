# coding: utf-8
import unittest
from FAdo import reex

import benchmark.util as util
from benchmark.reex_ext import uatom, chars, dotany
from benchmark.convert import Converter


class TestUAtom(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(AssertionError):
            uatom("a")
        self.assertEqual(str(uatom(u"a")), "a")

    def test_extensive(self):
        # note u"a" does not occur in the next line's string
        atoms = list(u"🔑 ✞♄їṧ їṧ @ ẘḯ∂ℯ ґαᾔ❡℮ øƒ ʊᾔї¢øḓε ṧ⑂μß☺ℓṧ ρα﹩ṧℯ∂ ⊥няøʊ❡н αη ℮ᾔ¢◎øʟ"
            + u"εη¢◎ḓℯґ▣ Ї☂ мα☤ᾔ☂α☤η﹩ ‴ґ℮@ḓ@♭ḯʟḯ⊥¥❞ ♭υ⊥ яε℘ℓα¢εṧ ☂♄ε αṧ¢ḯ☤ ṧƴღ♭◎ʟ﹩ ω☤тℌ "
            + u"ʊᾔї¢ø∂ε @ℓтεґηα⊥ї♥℮ṧ❣ ✨ ASCII :)")
        for a in atoms:
            atom = uatom(a)
            aord = util.UniUtil.ord(a)

            # str should not throw
            str(atom)

            # derivative
            self.assertEqual(atom.derivative(a), reex.epsilon())
            self.assertEqual(atom.derivative(util.UniUtil.chr(aord + 1)), reex.emptyset())
            self.assertEqual(atom.derivative(util.UniUtil.chr(aord - 1)), reex.emptyset())

            # __contains__
            self.assertTrue(a in atom)
            self.assertFalse(u"a" in atom)

            # next
            self.assertIsNone(atom.next(a))
            self.assertEqual(atom.next(None), a)
            self.assertEqual(atom.next(util.UniUtil.chr(31)), a)
            self.assertEqual(atom.next(util.UniUtil.chr(2**16 - 1)), None)

            # intersect
            self.assertIsNone(atom.intersect(reex.epsilon()), None)
            self.assertEqual(atom.intersect(dotany()), atom)
            self.assertEqual(atom.intersect(chars(u"a", neg=True)), atom)


class TestChars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unicode_source = u"🔑 ✞♄їṧ їṧ @ ẘḯ∂ℯ ґαᾔ❡℮ øƒ ʊᾔї¢øḓε ṧ⑂μß☺ℓṧ ρα﹩ṧℯ∂ ⊥няøʊ❡н αη ℮ᾔ¢◎øʟ" \
            + u"εη¢◎ḓℯґ▣ Ї☂ мα☤ᾔ☂α☤η﹩ ‴ґ℮@ḓ@♭ḯʟḯ⊥¥❞ ♭υ⊥ яε℘ℓα¢εṧ ☂♄ε αṧ¢ḯ☤ ṧƴღ♭◎ʟ﹩ ω☤тℌ " \
            + u"ʊᾔї¢ø∂ε @ℓтεґηα⊥ї♥℮ṧ❣ ✨ ASCII :) 567"
        cls.posUnicode = chars(cls.unicode_source)
        cls.negUnicode = chars(cls.unicode_source, neg=True)

        cls.posHex = chars([u"a", u"b", u"c", (u"0", u"9"), u"d", u"e", u"f"])
        cls.negHex = chars([u"a", u"b", u"c", (u"0", u"9"), u"d", u"e", u"f"], neg=True)

    def test_derivative(self):
        for sigma in self.unicode_source:
            self.assertEqual(self.posUnicode.derivative(sigma), reex.epsilon())
            self.assertEqual(self.negUnicode.derivative(sigma), reex.emptyset())

        self.assertEqual(self.posUnicode.derivative("a"), reex.emptyset())
        self.assertEqual(self.negUnicode.derivative("a"), reex.epsilon())

        self.assertEqual(self.posHex.derivative("0"), reex.epsilon())
        self.assertEqual(self.posHex.derivative("5"), reex.epsilon())
        self.assertEqual(self.posHex.derivative("9"), reex.epsilon())
        self.assertEqual(self.posHex.derivative("b"), reex.epsilon())
        self.assertEqual(self.posHex.derivative("f"), reex.epsilon())
        self.assertEqual(self.posHex.derivative("F"), reex.emptyset())
        self.assertEqual(self.posHex.derivative("."), reex.emptyset())

        self.assertEqual(self.negHex.derivative("0"), reex.emptyset())
        self.assertEqual(self.negHex.derivative("5"), reex.emptyset())
        self.assertEqual(self.negHex.derivative("9"), reex.emptyset())
        self.assertEqual(self.negHex.derivative("b"), reex.emptyset())
        self.assertEqual(self.negHex.derivative("f"), reex.emptyset())
        self.assertEqual(self.negHex.derivative("F"), reex.epsilon())
        self.assertEqual(self.negHex.derivative("."), reex.epsilon())

    def test_next(self):
        self.assertEqual(self.posUnicode.next(), " ")
        self.assertEqual(self.posUnicode.next(u" "), ")")

        self.assertEqual(self.negUnicode.next(), "!")
        self.assertEqual(self.negUnicode.next(u"α"), u"β")
        self.assertEqual(self.negUnicode.next(u"5"), u"8")

        self.assertEqual(self.posHex.next(), u"0")
        self.assertEqual(self.posHex.next(u"9"), u"a")
        self.assertEqual(self.posHex.next(u"f"), None)

        self.assertEqual(self.negHex.next(), u" ")
        self.assertEqual(self.negHex.next(u"$"), u"%")
        self.assertEqual(self.negHex.next(u"/"), u":")
        self.assertEqual(self.negHex.next(u"f"), u"g")

    def test_intersect(self):
        self.assertEqual(self.posUnicode.intersect(chars(u"123456789")), chars(u"567"))
        self.assertEqual(self.posUnicode.intersect(chars(u"π")), None)
        self.assertEqual(self.posUnicode.intersect(chars(u"π", neg=True)).ranges.__str__(),
            self.posUnicode.ranges.__str__())

        self.assertEqual(self.negUnicode.intersect(chars(u"a")), chars(u"a"))
        self.assertEqual(self.negUnicode.intersect(uatom(u"a")), uatom(u"a"))
        self.assertEqual(self.negUnicode.intersect(dotany()), self.negUnicode)

        self.assertEqual(self.posHex.intersect(chars([(u"a", u"z"), u"2", u"4", u"6", u"8"])).__repr__(),
            "chars([2468abcdef])")
        self.assertEqual(self.posHex.intersect(chars([(u"a", u"z"), u"2", u"4", u"6", u"8"],
            neg=True)).__repr__(), "chars([0-13579])")

        self.assertEqual(self.negHex.intersect(chars([(u"a", u"z")])).__repr__(), "chars([g-z])")

class TestDotAny(unittest.TestCase):
    def test_derivative(self):
        self.assertEqual(dotany().derivative(u"a"), reex.epsilon())
        self.assertEqual(dotany().derivative(u"α"), reex.epsilon())
        self.assertEqual(dotany().derivative(u"🔥"), reex.epsilon())

    def test_next(self):
        arr = [3904, 14987, 24086, 3836, 2205, 3446, 13563, 2749, 1210, 1435, 65]
        for v in arr:
            self.assertEqual(dotany().next(util.UniUtil.chr(v)), util.UniUtil.chr(v + 1))

        self.assertEqual(dotany().next(), " ")

    def test_intersect(self):
        self.assertEqual(dotany().intersect(reex.epsilon()), None)
        self.assertEqual(dotany().intersect(dotany()), dotany())
        self.assertEqual(dotany().intersect(uatom(u"a")), uatom(u"a"))
        self.assertEqual(dotany().intersect(chars(u"a")), chars(u"a"))

class TestEvalWordP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

    def test_concat(self):
        re = self.convert.prog(u"abcδεφ")
        self.assertTrue(re.evalWordP(u"abcδεφ"))
        self.assertFalse(re.evalWordP("abcdef"))
        self.assertFalse(re.evalWordP("000111"))

    def test_disj(self):
        re = self.convert.prog(u"(❶|❷|❸|_)")
        self.assertTrue(re.evalWordP("_"))
        self.assertTrue(re.evalWordP(u"❶"))
        self.assertTrue(re.evalWordP(u"❷"))
        self.assertTrue(re.evalWordP(u"❸"))
        self.assertFalse(re.evalWordP(u"❹"))
        self.assertFalse(re.evalWordP(u"a"))

    def test_star(self):
        re = self.convert.math(u"✓*")
        self.assertTrue(re.evalWordP(""))
        self.assertTrue(re.evalWordP(u"✓"))
        self.assertTrue(re.evalWordP(u"✓✓✓✓✓"))
        self.assertFalse(re.evalWordP(u"✓✓✕✓✓"))
        self.assertFalse(re.evalWordP(u"✗"))

    def test_option(self):
        re = self.convert.math(u"舵?")
        self.assertTrue(re.evalWordP(""))
        self.assertTrue(re.evalWordP(u"舵"))
        self.assertFalse(re.evalWordP(u"舵舵"))

class TestPairGen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()


    def test_disj_trivial(self):
        re = self.convert.math("(((0 + 1) + 2) + 3)")
        self.assertSetEqual(re.pairGen(), set("0123"))

    def test_option_trivial(self):
        re = self.convert.math("a?")
        self.assertSetEqual(re.pairGen(), set(["", "a"]))


    def test_concat_trivial(self):
        re = self.convert.math("(((0 1) 2) 3)")
        self.assertSetEqual(re.pairGen(), set(["0123"]))

    def test_concat_nontrivial(self): # {0,1}{a,b,c}
        re = self.convert.math("((0 + 1) ((a + b) + c))")
        words = re.pairGen()
        self.assertEqual(len(words), 2*3)
        for w in words:
            self.assertTrue(re.evalWordP(w))


    def test_kleene_trivial(self):
        re = self.convert.math("a*")
        self.assertSetEqual(re.pairGen(), set(["", "a", "aa"]))

    def test_kleene_nontrivial(self):
        re = self.convert.math("((0 a) + 1)*")
        words = re.pairGen()
        for w in words:
            self.assertTrue(re.evalWordP(w))

        # length 0: ε
        # length 1: 0a or 1
        # length 2: <0a,0a>, <0a,1>, <1,0a>, <1,1>
        #           11 => 110a => 110a0a (or similar)
        #           0a1
        self.assertEqual(len(words), 1 + 2 + 2)

if __name__ == "__main__":
    unittest.main()