# coding: utf-8
import unittest

from benchmark.convert import Converter
from benchmark.fa_ext import InvariantNFA
from benchmark.util import radixOrder

class TestInvariantNFA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

    def test_lengthNFA(self):
        nfa = InvariantNFA.lengthNFA(3)
        self.assertTrue(nfa.evalWordP("123"))
        self.assertTrue(nfa.evalWordP("abc"))
        self.assertFalse(nfa.evalWordP(""))
        self.assertFalse(nfa.evalWordP("12"))
        self.assertFalse(nfa.evalWordP("1234"))
        self.assertFalse(nfa.evalWordP("123456"))

        nfa = InvariantNFA.lengthNFA(3, 5)
        self.assertTrue(nfa.evalWordP("123"))
        self.assertTrue(nfa.evalWordP("abc"))
        self.assertTrue(nfa.evalWordP("abcd"))
        self.assertTrue(nfa.evalWordP("abcde"))
        self.assertFalse(nfa.evalWordP(""))
        self.assertFalse(nfa.evalWordP("12"))
        self.assertFalse(nfa.evalWordP("1234567"))

    def test_nfaPD(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaPD")
        self.runner()

    def test_nfaThompson(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaThompson")
        self.runner()

    def test_nfaGlushkov(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaGlushkov")
        self.runner()

    def test_nfaPDO(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaPDO")
        self.runner()

    def test_nfaFollow(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaFollow")
        self.runner()

    def test_nfaPosition(self):
        self.infa = lambda expr: self.convert.math(expr).toInvariantNFA("nfaPosition")
        self.runner()

    def runner(self):
        self.run_acyclicP()
        self.run_product()
        self.run_witness()
        self.run_ewp()
        self.run_membership()

    def run_acyclicP(self):
        infa = self.infa(u"((0 (a + b)*) 0)")
        self.assertFalse(infa.acyclicP())

        infa = self.infa(u"0")
        self.assertTrue(infa.acyclicP())

        infa = self.infa(u"((0 + 1) a)")
        self.assertTrue(infa.acyclicP())

    def run_product(self):
        infa = self.infa("(((0 [^0]) + 1)* @any)")
        len4 = InvariantNFA.lengthNFA(4)
        prod = infa.product(len4)

        subset_L_prod = set(["111a", "0n1a", "10na"])
        for w in subset_L_prod:
            self.assertTrue(infa.evalWordP(w), w)
            self.assertTrue(len4.evalWordP(w), w)
            self.assertTrue(prod.evalWordP(w), w)

        self.assertTrue(infa.evalWordP("a"))
        self.assertFalse(len4.evalWordP("a"))
        self.assertFalse(prod.evalWordP("a"))

        self.assertFalse(infa.evalWordP("001a"))
        self.assertTrue(len4.evalWordP("001a"))
        self.assertFalse(prod.evalWordP("001a"))

    def run_witness(self):
        def _f(expr):
            infa = self.infa(expr)
            wit = infa.witness()
            self.assertTrue(infa.evalWordP(wit))

        _f(u"(a + b)*")
        _f(u"[a-fbcdef]*")
        _f(u"((z + a) + γ)")
        _f(u"((a b) c)")
        _f(u"((a b) c)?")
        _f(u"((α + a) (β + b))")

    def run_ewp(self):
        self.assertTrue(self.infa("a*").ewp())
        self.assertTrue(self.infa("(a + b)*").ewp())
        self.assertTrue(self.infa("(a + @epsilon)").ewp())
        self.assertTrue(self.infa("a?").ewp())
        self.assertFalse(self.infa("(a + b)").ewp())
        self.assertFalse(self.infa(u"((a + β) c)").ewp())

    def run_membership(self):
        tests = {
            u"((@any η) @any)":
                ([u" η_", u"'η'", u"丂η七"],
                 [u"η η", u"丂七七", u"_η"]),
            u"(((｟ + (｟ ｠)) + ｠) @any*)":
                ([u"｟｠", u"｟", u"｠", u"｠anything"],
                 [u"(", u"()", u"anything ｠"]),
            u"((꧂ ((т + ๏) + 卄)) (☝ ꧁?))":
                ([u"꧂т☝", u"꧂๏☝꧁"],
                 [u"т☝", u"꧂卄꧁", u"꧂꧂꧂๏☝꧁"]),
            u"(0 + 1)*":
                (["", "0", "1", "00", "01", "101010100101101001"],
                 ["001a", "zero"])
        }

        for expr in tests:
            infa = self.infa(expr)
            yeses, noes = tests[expr]

            for word in yeses:
                self.assertTrue(infa.evalWordP(word), word.encode("utf-8") + " should be in "
                    + expr.encode("utf-8"))

            for word in noes:
                self.assertFalse(infa.evalWordP(word), word.encode("utf-8") + " should NOT be in "
                    + expr.encode("utf-8"))

class TestEnumInvariantNFA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

        def verifyRadix(self, lang):
            for i in xrange(1, len(lang)):
                self.assertLess(radixOrder(lang[i-1], lang[i]), 0, "'{0}' should be < '{1}'".format(
                    lang[i-1].encode("utf-8"), lang[i].encode("utf-8")))
        cls.verifyRadix = verifyRadix

        def construct(cls, expr, method, prog):
            infa = None
            if prog:
                infa = cls.convert.prog(expr, partialMatch=False).toInvariantNFA(method)
            else:
                infa = cls.convert.math(expr).toInvariantNFA(method)

            enum = infa.enumNFA()
            return (infa, enum)
        cls.construct = construct

    def test_nfaPD(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaPD", prog=prog)
        self.runner()

    def test_nfaThompson(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaThompson", prog=prog)
        self.runner()

    def test_nfaGlushkov(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaGlushkov", prog=prog)
        self.runner()

    def test_nfaPDO(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaPDO", prog=prog)
        self.runner()

    def test_nfaFollow(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaFollow", prog=prog)
        self.runner()

    def test_nfaPosition(self):
        self.infaEnum = lambda expr, prog=False: self.construct(expr, "nfaPosition", prog=prog)
        self.runner()

    def runner(self):
        self.run_minWord()
        self.run_minWord_None()
        self.run_nextWord()
        self.run_enumCrossSection()
        self.run_enum()
        self.run_randomWord()
        self.run_wordlen()

    def run_minWord(self):
        self.assertEqual(self.infaEnum("(a + b)*")[1].minWord(4), "aaaa")
        self.assertEqual(self.infaEnum("[a-fbcdef]*")[1].minWord(1), "a")
        self.assertEqual(self.infaEnum(u"((z + a) + γ)")[1].minWord(0), None)
        self.assertEqual(self.infaEnum("((a b) c)")[1].minWord(4), None)
        self.assertEqual(self.infaEnum("((a b) c)?")[1].minWord(0), "")

    def run_minWord_None(self):
        self.assertEqual(self.infaEnum("(a + b)*")[1].minWord(None), "")
        self.assertEqual(self.infaEnum("[a-fbcdef]*")[1].minWord(None), "")
        self.assertEqual(self.infaEnum(u"((z + a) + γ)")[1].minWord(None), "a")
        self.assertEqual(self.infaEnum("((a b) c)")[1].minWord(None), "abc")
        self.assertEqual(self.infaEnum("((a b) c)?")[1].minWord(None), "")

    def run_nextWord(self):
        self.assertEqual(self.infaEnum("(a + b)*")[1].nextWord("aaaa"), "aaab")
        self.assertEqual(self.infaEnum("(a + b)*")[1].nextWord("abbb"), "baaa")
        self.assertEqual(self.infaEnum("[a-fbcdef]*")[1].nextWord("bcdef"), "bcdfa")
        self.assertEqual(self.infaEnum("[^def]*")[1].nextWord("aac"), "aag")
        self.assertEqual(self.infaEnum("((a b) c)")[1].nextWord("abc"), None)

    def run_enumCrossSection(self):
        infa, enum = self.infaEnum("(0 + 1)*")
        for nth in xrange(5):
            lang = list(enum.enumCrossSection(nth))
            self.assertEqual(len(lang), 2**nth)
            for w in lang:
                self.assertTrue(infa.evalWordP(w))
            self.verifyRadix(lang)

        lang = list(enum.enumCrossSection(0, 5))
        self.assertEqual(len(lang), sum(2**x for x in xrange(0, 6)))
        self.verifyRadix(lang)

    def run_enum(self):
        _, enum = self.infaEnum(u"((a + α) (b + β))*")
        lang = list(enum.enum(50))
        self.assertEqual(len(lang), 50)
        self.assertEqual(lang[0], "")
        self.verifyRadix(lang)

    def run_randomWord(self):
        infa, enum = self.infaEnum(u"((\\+ + -) (√ ([0-9] [0-9]*)))")
        for length in xrange(0, 3):
            self.assertIsNone(enum.randomWord(length))
        for length in xrange(3, 25):
            word = enum.randomWord(length)
            self.assertTrue(infa.evalWordP(word))
            self.assertEqual(len(word), length)

    def run_wordlen(self):
        _, enum = self.infaEnum("x{3}|y{10,15}|z{30}", prog=True)
        self.assertEqual(enum.shortestWordLength(), 3)
        self.assertEqual(enum.shortestWordLength(3), 3)
        self.assertEqual(enum.shortestWordLength(4), 10)
        self.assertEqual(enum.shortestWordLength(11), 11)
        self.assertEqual(enum.longestWordLength(), 30)


if __name__ == "__main__":
    unittest.main()