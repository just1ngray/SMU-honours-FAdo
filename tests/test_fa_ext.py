# coding: utf-8
import unittest
import copy

from benchmark.convert import Converter
from benchmark.fa_ext import InvariantNFA

def radixOrder(a, b):
    if len(a) == len(b):
        return -1 if a < b else 1
    else:
        return len(a) - len(b)

class TestInvariantNFA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

    def test_nfaPD(self):
        self.runner("nfaPD")

    def test_nfaThompson(self):
        self.runner("nfaThompson")

    def test_nfaGlushkov(self):
        self.runner("nfaGlushkov")

    def test_nfaPDO(self):
        self.runner("nfaPDO")

    def test_nfaFollow(self):
        self.runner("nfaFollow")

    def test_nfaPosition(self):
        self.runner("nfaPosition")



    def runner(self, method):
        self.run_membership(method)
        self.run_witness(method)

    def run_membership(self, method):
        tests = {
            u"((@any η) @any)":
                ([u" η_", u"'η'", u"😎η🌴"],
                 [u"η η", u"😎🌴🌴", u"_η"]),
            u"(((🏀 + (⚽ 🥅)) + 🎾) @any*)":
                ([u"⚽🥅", u"🏀", u"🎾", u"⚽🥅🎾🏀🎾⚽", u"🏀 ♭@ṧкε☂♭αʟʟ", u"🎾 ⊥ ℮ ᾔ ᾔ ḯ ṧ"],
                 [u"🏈", u"⚽ 🥅", u"soccer ⚽🥅 football", u"♭@ṧкε☂♭αʟʟ"]),
            u"((😝 ((т + ๏) + 卄)) (☝ (🐟)?))":
                ([u"😝т☝", u"😝๏☝🐟"],
                 [u"т☝", u"😝卄🐟", u"😝😝😝๏☝🐟"]),
            u"(0 + 1)*":
                (["", "0", "1", "00", "01", "101010100101101001"],
                 ["001a", "zero"])
        }

        for expr in tests:
            re = self.convert.math(expr)
            infa = InvariantNFA(re.toNFA(method))
            yeses, noes = tests[expr]

            for word in yeses:
                self.assertTrue(infa.evalWordP(word), word.encode("utf-8") + " should be in "
                    + expr.encode("utf-8"))

            for word in noes:
                self.assertFalse(infa.evalWordP(word), word.encode("utf-8") + " should be in "
                    + expr.encode("utf-8"))

    def run_witness(self, method):
        re = self.convert.math(u"(a + b)*")
        infa = InvariantNFA(re.toNFA(method))
        self.assertEqual(infa.witness(), u"a")

        re = self.convert.math(u"[a-fbcdef]*")
        infa = InvariantNFA(re.toNFA(method))
        self.assertEqual(infa.witness(), u"a")

        re = self.convert.math(u"((z + a) + γ)")
        infa = InvariantNFA(re.toNFA(method))
        self.assertEqual(infa.witness(), u"a")

        re = self.convert.math(u"((a b) c)")
        infa = InvariantNFA(re.toNFA(method))
        self.assertEqual(infa.witness(), u"abc")

        re = self.convert.math(u"(((a b) c))?")
        infa = InvariantNFA(re.toNFA(method))
        self.assertEqual(infa.witness(), u"abc")

class TestEnumInvariantNFA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

        def get_infa(_, expr, method):
            re = cls.convert.prog(expr, partialMatch=False)
            nfa = re.toNFA(method)
            return InvariantNFA(nfa)
        cls.infa = get_infa

        def verifyRadixOrder(self, lang, size):
            cpy = copy.copy(lang)
            cpy.sort(radixOrder)
            self.assertListEqual(lang, cpy)
            self.assertEqual(len(lang), size)
        cls.verifyRadixOrder = verifyRadixOrder

    def test_nfaPD(self):
        self.runner("nfaPD")

    def test_nfaThompson(self):
        self.runner("nfaThompson")

    def test_nfaGlushkov(self):
        self.runner("nfaGlushkov")

    def test_nfaPDO(self):
        self.runner("nfaPDO")

    def test_nfaFollow(self):
        self.runner("nfaFollow")

    def test_nfaPosition(self):
        self.runner("nfaPosition")



    def runner(self, method):
        self.run_simple(method)
        self.run_complex(method)

    def run_simple(self, method):
        enum = self.infa("(0|1)*", method).enumNFA()
        self.assertTrue(enum.ewp())
        self.assertEqual(enum.witness(), "0")

        self.assertEqual(enum.minWord(50), "0"*50)
        for i in range(10):
            self.assertEqual(enum.minWord(i), "0"*i)

        self.assertEqual(enum.nextWord("00010"), "00011")
        self.assertEqual(enum.nextWord("01101"), "01110")
        self.assertEqual(enum.nextWord("0111111111111"), "1000000000000")

        self.verifyRadixOrder([x for x in enum.enumCrossSection(5)], 2**5)
        self.verifyRadixOrder([x for x in enum.enum(0, 4)], sum(2**x for x in range(0, 5)))

    def run_complex(self, method): # TODO: THIS PART IS NOT WORKING
        enum = self.infa(u"(x[αβψδεφ0-9]{2,4} :: (😀|😄|😊😊)?)*", method).enumNFA()
        self.assertTrue(enum.ewp())
        self.assertEqual(enum.witness(), "x00 :: ")

        # self.assertEqual(enum.minWord(50), "0"*50)
        # for i in range(10):
        #     self.assertEqual(enum.minWord(i), "0"*i)

        # self.assertEqual(enum.nextWord("00010"), "00011")
        # self.assertEqual(enum.nextWord("01101"), "01110")
        # self.assertEqual(enum.nextWord("0111111111111"), "1000000000000")

        # self.verifyRadixOrder([x for x in enum.enumCrossSection(5)], 2**5)
        # self.verifyRadixOrder([x for x in enum.enum(0, 4)], sum(2**x for x in range(0, 5)))


if __name__ == "__main__":
    unittest.main()