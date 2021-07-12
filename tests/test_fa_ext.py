import unittest
import time
import re
import copy
from FAdo import reex

from benchmark.convert import Converter
from benchmark.fa_ext import InvariantNFA
from benchmark.reex_ext import chars, dotany

class TestFAExt(unittest.TestCase):
    def setUp(self):
        self.convert = Converter()
        return super(TestFAExt, self).setUp()

    def test_nfaPD(self):
        self._test_all("nfaPD")

    def test_nfaThompson(self):
        self._test_all("nfaThompson")

    def test_nfaGlushkov(self):
        self._test_all("nfaGlushkov")

    def test_nfaPDO(self):
        self._test_all("nfaPDO")




    def _test_all(self, method):
        self._test_membership(method)
        self._test_witness(method)
        self._test_ewp(method)
        self._test_enumNFA(method)

    def _test_membership(self, method):
        tests = {
            "(0[ab]1)": [
                ("0a1", True),      ("0c1", False),
                ("0b1", True),      ("0ab1", False),
            ],
            "(0[^ab]1)": [
                ("0a1", False),      ("0c1", True),
                ("0b1", False),      ("0ab1", False),
            ],
            "(0[a-f]1)": [
                ("0a1", True),      ("0f1", True),
                ("0g1", False),     ("031", False),
            ],
            "(0[^a-f]1)": [
                ("0a1", False),     ("0f1", False),
                ("0g1", True),      ("031", True),
            ],
            "(0[abc0-9d-f]1)": [
                ("001", True),      ("051", True),
                ("091", True),      ("0a1", True),
                ("0b1", True),      ("0d1", True),
                ("0f1", True),      ("0x1", False),
            ],
            "(0@any1)": [
                ("001", True),      ("051", True),
                ("091", True),      ("0a1", True),
                ("0b1", True),      ("0x1", True),
                ("0f1", True),      ("0xx1", False),
            ]
        }
        for test in tests:
            infa = InvariantNFA(self.convert.one(test).toNFA(nfa_method=method))
            for word, mem in tests[test]:
                self.assertEqual(infa.evalWordP(word), mem, word + " should" + ("n't" if mem else "")
                        + " be in " + test)

    def _test_witness(self, method):
        def wit(expr, ness):
            infa = InvariantNFA(self.convert.one(expr).toNFA(method))
            self.assertEqual(infa.witness(), ness)

        wit("(000)", "000")
        wit("(1*)", "1")
        wit("((0 + 1)*)", "0")
        wit("(@epsilon + @any)", "0")

    def _test_ewp(self, method):
        def expect(expr, ewpVal):
            infa = InvariantNFA(self.convert.one(expr).toNFA(method))
            self.assertEqual(infa.ewp(), ewpVal)

        expect("(000)", False)
        expect("(000((0 + 1)*))", False)
        expect("((0 + 1)*)", True)
        expect("(@epsilon + @any)", True)

    def _test_enumNFA(self, method):
        def test(expr, upToLength, numExpected):
            infa = InvariantNFA(self.convert.one(expr).toNFA(nfa_method=method))
            words = list()
            for word in infa.enumNFA().enum(hi=upToLength):
                words.append(word)
            wordsCopy = copy.copy(words)
            wordsCopy.sort(radixOrder)
            self.assertListEqual(words, wordsCopy)
            self.assertEqual(len(set(words)), numExpected)

        test("([01]*)", 8, sum(2**x for x in range(0, 9)))
        test("(000)", 3, 1)
        test("(000)", 2, 0)
        test("(@any@any)", 2, 62**2)
        test("([bc]*)", 3, sum(2**x for x in range(0, 4)))
        test("((a + [bc])*)", 3, sum(3**x for x in range(0, 4)))

        enuminfa = InvariantNFA(self.convert.one("((0 + 1)*)").toNFA(nfa_method=method)).enumNFA()
        for i in xrange(0, 10):
            self.assertEqual(enuminfa.minWord(i), "0"*i)

        enuminfa = InvariantNFA(self.convert.one("(000)").toNFA(nfa_method=method)).enumNFA()
        self.assertIsNone(enuminfa.minWord(1))
        self.assertIsNone(enuminfa.minWord(2))
        self.assertEqual(enuminfa.minWord(3), "000")
        self.assertIsNone(enuminfa.minWord(4))


def radixOrder(a, b):
    if len(a) == len(b):
        return -1 if a < b else 1
    else:
        return len(a) - len(b)

if __name__ == "__main__":
    unittest.main()