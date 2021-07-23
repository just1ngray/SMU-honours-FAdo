# coding: utf-8
import unittest
from FAdo import reex

from benchmark.convert import Converter


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.convert = Converter()
        return super(TestConverter, self).setUp()

    def test_math_simple_str(self):
        self.runtest(self.convert.math, [
            ("a", "a"),
            ("@epsilon", "@epsilon"),
            ("@any", "@any"),
            ("a*", "a*"),
            ("(a + b)", "a + b"),
            ("(a b)", "a b"),
            ("(a)?", "(a)?"),
            ("<ASTART>", "@epsilon"),
            ("<AEND>", "@epsilon"),
            ("[abc]", "[abc]"),
            ("[0-9]", "[0-9]"),
            ("[ab0-9c]", "[ab0-9c]"),
            ("[^ab0-9c]", "[^ab0-9c]"),
        ])

    def test_programmers_simple_str(self):
        self.runtest(self.convert.prog, [
            ("a", "a"),
            ("a*", "a*"),
            ("a|b", "a + b"),
            ("ab", "a b"),
            ("a?", "(a)?"),
            ("^a", "@epsilon a"),
            ("a$", "a @epsilon"),
            ("..", "@any @any"),
            ("[abc]", "[abc]"),
            ("[0-9]", "[0-9]"),
            ("[ab0-9c]", "[ab0-9c]"),
            ("[^ab0-9c]", "[^ab0-9c]"),
        ])

    def test_math_simple_unicode(self):
        self.runtest(self.convert.math, [
            (u"α", u"α"),
            (u"∀", u"∀"),
            (u"@epsilon", u"@epsilon"),
            (u"@any", u"@any"),
            (u"🚀*", u"🚀*"),
            # (u"(🇨🇦 + 🇵🇹)", u"🇨🇦 + 🇵🇹"), # no support for 8-byte characters
            (u"(ë + Ĥ)", u"ë + Ĥ"),
            (u"(ǿ Ȍ)", u"ǿ Ȍ"),
            (u"(Ͽ)?", u"(Ͽ)?"),
            (u"[𐌸b♫]", u"[𐌸b♫]"),
            (u"[▢-▩]", u"[▢-▩]"),
            (u"[a⚡0-9c]", u"[a⚡0-9c]"),
            (u"[^ab0-好c]", u"[^ab0-好c]"),
        ])

    def test_programmers_simple_unicode(self):
        self.runtest(self.convert.prog, [
            (u"α", u"α"),
            (u'"α"', u'(" α) "'),
            (u"∀", u"∀"),
            (u".", u"@any"),
            (u"ë|Ĥ", u"ë + Ĥ"),
            (u"ǿȌ", u"ǿ Ȍ"),
            (u"Ͽ?", u"(Ͽ)?"),
            (u".", u"@any"),
            (u"[𐌸b♫]", u"[𐌸b♫]"),
            (u"[▢-▩]", u"[▢-▩]"),
            (u"[a⚡0-9c]", u"[a⚡0-9c]"),
            (u"[^α➸ƒ0✏9Ѧ➸ℱ]", u"[^α➸ƒ0✏9Ѧ➸ℱ]"),
            (u"[^α➸ƒ0✏9Ѧ-ℱ]", u"[^α➸ƒ0✏9Ѧ-ℱ]"),
            (u"€ᾔ¢◎øℓ   тℯ|ϰт", u"((((((((((€ ᾔ) ¢) ◎) ø) ℓ)  )  )  ) т) ℯ) + (ϰ т)"),
        ])






    def runtest(self, convert, expressions, partialMatch=False):
        for prog, fado in expressions:
            val = convert(prog, partialMatch=False)
            # self.assertEqual(str(val), fado.encode("utf-8")) # this shows byte string
            self.assertEqual(str(val), fado.encode("utf-8"), str(val) + " != " + fado.encode("utf-8"))

    # def test_anchor_noPartialMatch(self):
    #     eq = lambda expr, expected: self.eq(expr, expected, False)
    #     eq("<ASTART>",                          "@epsilon")
    #     eq("<AEND>",                            "@epsilon")
    #     eq("a",                                 "a")
    #     eq("@any",                              "@any")
    #     eq("(<ASTART>(a*))",                    "@epsilon a*")
    #     eq("(<ASTART>(a*)<AEND>)",              "(@epsilon a*) @epsilon")
    #     eq("((a*)(0+1)(0+1)(0+1))",             "((a* (0 + 1)) (0 + 1)) (0 + 1)")
    #     eq("((a*)(0+1)(0+1)(0+1)<AEND>)",       "(((a* (0 + 1)) (0 + 1)) (0 + 1)) @epsilon")

    # def test_anchor_yesPartialMatch(self):
    #     eq = lambda expr, expected: self.eq(expr, expected, True)
    #     eq("<ASTART>",                          "@any*")
    #     eq("<AEND>",                            "@any*")
    #     eq("a",                                 "@any* (a @any*)")
    #     eq("@any",                              "@any* (@any @any*)")
    #     eq("(<ASTART>(a*))",                    "@epsilon (a* @any*)")
    #     eq("(<ASTART>(a*)<AEND>)",              "(@epsilon a*) @epsilon")
    #     eq("((a*)(0+1)(0+1)(0+1))",             "(((@any* a*) (0 + 1)) (0 + 1)) ((0 + 1) @any*)")
    #     eq("((a*)(0+1)(0+1)(0+1)<AEND>)",       "((((@any* a*) (0 + 1)) (0 + 1)) (0 + 1)) @epsilon")

    # def test_error(self):
    #     errors = ["(abc", "abc)", "a*", "a + b", "*", "[0-9", "^a]", "(<ASTART> + A)", "(<AEND>*)"]
    #     regexps = self.convert.all(errors)
    #     for i in range(len(errors)):
    #         self.assertIsNone(regexps[i])


if __name__ == "__main__":
    unittest.main()