# coding: utf-8
import unittest

from benchmark.convert import Converter
from benchmark.fa_ext import InvariantNFA

def radixOrder(a, b): # this fails for some unicode when len=2
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
                self.assertFalse(infa.evalWordP(word), word.encode("utf-8") + " should NOT be in "
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
            self.assertEqual(len(lang), size)
            for i in range(1, len(lang)):
                self.assertLess(radixOrder(lang[i-1], lang[i]), 0,
                    "'{0}' should be < '{1}'".format(lang[i-1].encode("utf-8"), lang[i].encode("utf-8")))
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
        self.run_unicode(method)
        self.run_complex(method)
        self.run_randomEnumerate(method)

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

    def run_unicode(self, method):
        enum = self.infa(u"\\d{1,2}% => (α|β)+( !)?", method).enumNFA()
        self.assertFalse(enum.ewp())
        self.assertEqual(enum.witness(), u"0% => α")

        self.assertEqual(enum.minWord(7), u"0% => α")
        words = [u"0% => α", u"0% => β", u"1% => α", u"1% => β", u"2% => α", u"2% => β"]
        for i in range(1, len(words)):
            self.assertEqual(enum.nextWord(words[i-1]), words[i])

        self.verifyRadixOrder([x for x in enum.enum(0, 8)], 216)

    def run_complex(self, method):
        enum = self.infa(u"(x[αβψδεφ0-9]{2,4} :: (😀|😄|😊😊)?)*", method).enumNFA()
        self.assertTrue(enum.ewp())
        self.assertEqual(enum.witness(), "x00 :: ")

        self.assertEqual(enum.minWord(7), u"x00 :: ")
        self.assertEqual(enum.nextWord(u"x00 :: "), u"x01 :: ")

        self.verifyRadixOrder([x for x in enum.enumCrossSection(7)], 225)

    def run_randomEnumerate(self, method):
        enum = self.infa(u"([a-z01]㪘(α|β|ψ))*", method).enumNFA()

        self.assertEqual(enum.randomWord(0), u"")
        for l in range(1, 3):
            self.assertIsNone(enum.randomWord(l))

        start_count = 0
        end_count = 0
        for _ in range(1000):
            word = enum.randomWord(3)
            if word[0] == u"0" or word[0] == u"1":
                start_count += 1
            if word[-1] == u"α":
                end_count += 1

        rate = start_count / 1000.0
        self.assertLess(abs(rate - 2.0/28.0), 0.025, "Non-uniform random word generation "\
            +"[charclass] - run again to be sure - " + str(rate))

        rate = end_count / 1000.0
        self.assertLess(abs(rate - 1.0/3.0), 0.05, "Non-uniform random word generation "\
            +"DISJUNCTION - run again to be sure - " + str(rate))

        for l in range(4, 25):
            word = enum.randomWord(l)
            if l % 3 == 0:
                self.assertIsNotNone(word)
            else:
                self.assertIsNone(word)



if __name__ == "__main__":
    unittest.main()