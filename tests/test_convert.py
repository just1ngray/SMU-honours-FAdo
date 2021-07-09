import unittest
from FAdo import reex

from benchmark.convert import Converter


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.convert = Converter()
        return super(TestConverter, self).setUp()

    def test_standard_FAdo(self):
        expressions = [ "a",                        "@epsilon",
                        "(abc)",                    "((a + b)*)",
                        "((@epsilon + (ab))*)",     "(a + (bc) + (d*))" ]
        for expr in expressions:
            fado = reex.str2regexp(expr)
            mine = self.convert.one(expr)
            self.assertEqual(mine, fado)

    def eq(self, expr, expected, pm):
            self.assertEqual(self.convert.one(expr, partialMatch=pm).__str__(), expected)

    def test_anchor_noPartialMatch(self):
        eq = lambda expr, expected: self.eq(expr, expected, False)
        eq("<ASTART>",                          "@epsilon")
        eq("<AEND>",                            "@epsilon")
        eq("a",                                 "a")
        eq("@any",                              "@any")
        eq("(<ASTART>(a*))",                    "@epsilon a*")
        eq("(<ASTART>(a*)<AEND>)",              "(@epsilon a*) @epsilon")
        eq("((a*)(0+1)(0+1)(0+1))",             "((a* (0 + 1)) (0 + 1)) (0 + 1)")
        eq("((a*)(0+1)(0+1)(0+1)<AEND>)",       "(((a* (0 + 1)) (0 + 1)) (0 + 1)) @epsilon")

    def test_anchor_yesPartialMatch(self):
        eq = lambda expr, expected: self.eq(expr, expected, True)
        eq("<ASTART>",                          "@any*")
        eq("<AEND>",                            "@any*")
        eq("a",                                 "@any* (a @any*)")
        eq("@any",                              "@any* (@any @any*)")
        eq("(<ASTART>(a*))",                    "@epsilon (a* @any*)")
        eq("(<ASTART>(a*)<AEND>)",              "(@epsilon a*) @epsilon")
        eq("((a*)(0+1)(0+1)(0+1))",             "(((@any* a*) (0 + 1)) (0 + 1)) ((0 + 1) @any*)")
        eq("((a*)(0+1)(0+1)(0+1)<AEND>)",       "((((@any* a*) (0 + 1)) (0 + 1)) (0 + 1)) @epsilon")

    def test_char_class(self):
        self.eq("(0[a])", "0 [a]", False)
        self.eq("(0[^a])", "0 [^a]", False)
        self.eq("(0[a-z])", "0 [a-z]", False)
        self.eq("(0[^a-z])", "0 [^a-z]", False)
        self.eq("(0[0-9a-fA-FxX])", "0 [0-9a-fA-FxX]", False)
        self.eq("(0[^0-9a-fA-FxX])", "0 [^0-9a-fA-FxX]", False)
        self.eq("([01]*)", "[01]*", False)

    def test_convert_all(self):
        expressions = ["(a*)", "(a+b)", "((ac)+(b*))"]
        fadoized = list(map(lambda e: e.__repr__(), self.convert.all(expressions)))
        self.assertEqual(fadoized, [
            "star(atom(a))",
            "disj(atom(a),atom(b))",
            "disj(concat(atom(a),atom(c)),star(atom(b)))"
        ])

    def test_error(self):
        errors = ["(abc", "abc)", "a*", "a + b", "*", "[0-9", "^a]", "(<ASTART> + A)", "(<AEND>*)"]
        regexps = self.convert.all(errors)
        for i in range(len(errors)):
            self.assertIsNone(regexps[i])


if __name__ == "__main__":
    unittest.main()