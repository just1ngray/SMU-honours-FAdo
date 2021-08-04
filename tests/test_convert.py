# coding: utf-8
import unittest
from FAdo import reex
from lark import LarkError

from benchmark.convert import Converter


class TestConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

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
            ("a+", "a a*"),
            ("a{3}", "(a a) a"),
            ("a{3,}", "((a a) a) a*"),
            ("a{3,9}", "((a a) a) ((((@epsilon + a) (@epsilon + (a a))) (@epsilon + a)) (@epsilon + (a a)))"),
            ("a{,9}", "((((@epsilon + a) (@epsilon + (a a))) (@epsilon + (((a a) a) a))) (@epsilon + a)) (@epsilon + a)"),
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

    def test_prog_errs(self):
        exprs = [
            r"a \b",        r"a \B",        "a(?=b)",       "a(?!b)",       "(?<=a)b",
            "(?<!a)b",      r"(ab)\1",      r"[^\D]",       "[z-a]",        "*",
            "a{3,2}"
        ]
        for expr in exprs:
            try:
                re = self.convert.prog(expr)
                raise Exception(expr + " should raise, but instead returns " + str(re))
            except RuntimeError as err:
                self.assertTrue(str(err.message).startswith("Could not FAdoize"))

    def test_lark_errors(self):
        exprs = [
            '\\"',          # will attempt to parse \\\\" and raise UnexpectedToken "
            u"(🇨🇦 + 🇵🇹)",   # no support for 8-byte paired characters 🇨🇦 = '\U0001f1e8\U0001f1e6'
            "(a b",         "(ab c)",       "a + b",    "[0-9",     "^a]"
        ]
        for expr in exprs:
            try:
                re = self.convert.math(expr)
                raise Exception(expr + " should raise, but instead returns " + str(re))
            except LarkError:
                pass

    def test_anchor_noPartialMatch(self):
        exprs = [
            ("<ASTART>",                "@epsilon"),
            ("<AEND>",                  "@epsilon"),
            ("a",                       "a"),
            ("@any",                    "@any"),
            ("(<ASTART> a*)",           "@epsilon a*"),
            ("((<ASTART> a*) <AEND>)",  "(@epsilon a*) @epsilon"),
            ("(a* (0 + 1))",            "a* (0 + 1)"),
            ("((a* (0 + 1)) <AEND>)",   "(a* (0 + 1)) @epsilon"),
        ]
        self.runtest(self.convert.math, exprs, partialMatch=False)

    def test_anchor_yesPartialMatch(self):
        exprs = [
            ("<ASTART>",                "@epsilon @any*"),
            ("<AEND>",                  "@any* @epsilon"),
            ("a",                       "(@any* a) @any*"),
            ("@any",                    "(@any* @any) @any*"),
            ("(<ASTART> a*)",           "@epsilon (a* @any*)"),
            ("((<ASTART> a*) <AEND>)",  "(@epsilon a*) @epsilon"),
            ("(a* (0 + 1))",            "(@any* a*) ((0 @any*) + (1 @any*))"),
            ("((a* (0 + 1)) <AEND>)",   "((@any* a*) (0 + 1)) @epsilon"),
        ]
        self.runtest(self.convert.math, exprs, partialMatch=True)


    def runtest(self, convert, expressions, partialMatch=False):
        for prog, fado in expressions:
            val = convert(prog, partialMatch=partialMatch)
            self.assertEqual(str(val), fado.encode("utf-8"), prog.encode("utf-8") + " => "
                + str(val) + " != " + fado.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()