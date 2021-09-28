# coding: utf-8
import unittest

import benchmark.util as util
from benchmark.reex_ext import *
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
            self.assertEqual(atom.derivative(a), uepsilon())
            self.assertEqual(atom.derivative(util.UniUtil.chr(aord + 1)), uemptyset())
            self.assertEqual(atom.derivative(util.UniUtil.chr(aord - 1)), uemptyset())

            # __contains__
            self.assertTrue(a in atom)
            self.assertFalse(u"a" in atom)

            # next
            self.assertIsNone(atom.next(a))
            self.assertEqual(atom.next(None), a)
            self.assertEqual(atom.next(util.UniUtil.chr(31)), a)
            self.assertEqual(atom.next(util.UniUtil.chr(util.UniUtil.ord(a))), None)
            self.assertEqual(atom.next(util.UniUtil.chr(util.UniUtil.ord(a) + 1)), None)

            # intersect
            self.assertIsNone(atom.intersect(uepsilon()), None)
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
            self.assertEqual(self.posUnicode.derivative(sigma), uepsilon())
            self.assertEqual(self.negUnicode.derivative(sigma), uemptyset())

        self.assertEqual(self.posUnicode.derivative("a"), uemptyset())
        self.assertEqual(self.negUnicode.derivative("a"), uepsilon())

        self.assertEqual(self.posHex.derivative("0"), uepsilon())
        self.assertEqual(self.posHex.derivative("5"), uepsilon())
        self.assertEqual(self.posHex.derivative("9"), uepsilon())
        self.assertEqual(self.posHex.derivative("b"), uepsilon())
        self.assertEqual(self.posHex.derivative("f"), uepsilon())
        self.assertEqual(self.posHex.derivative("F"), uemptyset())
        self.assertEqual(self.posHex.derivative("."), uemptyset())

        self.assertEqual(self.negHex.derivative("0"), uemptyset())
        self.assertEqual(self.negHex.derivative("5"), uemptyset())
        self.assertEqual(self.negHex.derivative("9"), uemptyset())
        self.assertEqual(self.negHex.derivative("b"), uemptyset())
        self.assertEqual(self.negHex.derivative("f"), uemptyset())
        self.assertEqual(self.negHex.derivative("F"), uepsilon())
        self.assertEqual(self.negHex.derivative("."), uepsilon())

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
        self.assertEqual(dotany().derivative(u"a"), uepsilon())
        self.assertEqual(dotany().derivative(u"α"), uepsilon())
        self.assertEqual(dotany().derivative(u"🔥"), uepsilon())

    def test_next(self):
        arr = [3904, 14987, 24086, 3836, 2205, 3446, 13563, 2749, 1210, 1435, 65]
        for v in arr:
            self.assertEqual(dotany().next(util.UniUtil.chr(v)), util.UniUtil.chr(v + 1))

        self.assertEqual(dotany().next(), " ")

    def test_intersect(self):
        self.assertEqual(dotany().intersect(uepsilon()), None)
        self.assertEqual(dotany().intersect(dotany()), dotany())
        self.assertEqual(dotany().intersect(uatom(u"a")), uatom(u"a"))
        self.assertEqual(dotany().intersect(chars(u"a")), chars(u"a"))

class TestEvalWordP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

    def test_evalWordP_Derivative(self):
        self.run_tests("evalWordP_Derivative")

    def test_evalWordP_PD(self):
        self.run_tests("evalWordP_PD")

    def test_evalWordP_PDO(self):
        self.run_tests("evalWordP_PDO")

    def test_evalWordP_Backtrack(self):
        self.run_tests("evalWordP_Backtrack")

    def run_tests(self, method):
        def test_concat(self):
            re = self.convert.prog(u"abcδεφ")
            evalWord = getattr(re, method)
            self.assertTrue(evalWord(u"abcδεφ"))
            self.assertFalse(evalWord("abcdef"))
            self.assertFalse(evalWord("000111"))

        def test_disj(self):
            re = self.convert.prog(u"(❶|❷|❸|_)")
            evalWord = getattr(re, method)
            self.assertTrue(evalWord("_"))
            self.assertTrue(evalWord(u"❶"))
            self.assertTrue(evalWord(u"❷"))
            self.assertTrue(evalWord(u"❸"))
            self.assertFalse(evalWord(u"❹"))
            self.assertFalse(evalWord(u"a"))

        def test_star(self):
            re = self.convert.math(u"✓*")
            evalWord = getattr(re, method)
            self.assertTrue(evalWord(""))
            self.assertTrue(evalWord(u"✓"))
            self.assertTrue(evalWord(u"✓✓✓✓✓"))
            self.assertFalse(evalWord(u"✓✓✕✓✓"))
            self.assertFalse(evalWord(u"✗"))

        def test_option(self):
            re = self.convert.math(u"舵?")
            evalWord = getattr(re, method)
            self.assertTrue(evalWord(""))
            self.assertTrue(evalWord(u"舵"))
            self.assertFalse(evalWord(u"舵舵"))

        test_concat(self)
        test_disj(self)
        test_star(self)
        test_option(self)

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