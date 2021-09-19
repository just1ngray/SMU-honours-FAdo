# coding: utf-8
import unittest
from lark import LarkError

from benchmark.convert import Converter, FAdoizeError


class TestConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.convert = Converter()

    def test_rep_expansion(self):
        re = self.convert.prog("^a{4}$")
        self.assertTrue(re.evalWordP("aaaa"))
        self.assertFalse(re.evalWordP("aaa"))
        self.assertFalse(re.evalWordP("aaaaa"))

        re = self.convert.prog("^a{4,}$")
        self.assertTrue(re.evalWordP("aaaaa"))
        self.assertTrue(re.evalWordP("aaaa"))
        self.assertFalse(re.evalWordP("aaa"))
        self.assertFalse(re.evalWordP("aa"))

        re = self.convert.prog("^a{,3}$")
        self.assertTrue(re.evalWordP(""))
        self.assertTrue(re.evalWordP("a"))
        self.assertTrue(re.evalWordP("aa"))
        self.assertTrue(re.evalWordP("aaa"))
        self.assertFalse(re.evalWordP("aaaa"))

        re = self.convert.prog("^a{5,29}$")
        self.assertFalse(re.evalWordP("a"*4))
        for i in range(5, 30):
            self.assertTrue(re.evalWordP("a"*i))
        self.assertFalse(re.evalWordP("a"*30))

        re = self.convert.prog("[^abc]{0,}", partialMatch=False)
        self.assertTrue(re.evalWordP(""))
        self.assertTrue(re.evalWordP("d"))
        self.assertTrue(re.evalWordP("ddddddd"))
        self.assertFalse(re.evalWordP("a"))
        self.assertFalse(re.evalWordP("abc"))
        self.assertFalse(re.evalWordP("abcba"))

    def test_math_simple_str(self):
        self.runtest(self.convert.math, [
            ("a", "a"),
            ("@epsilon", "@epsilon"),
            ("@any", "@any"),
            ("a*", "a*"),
            ("(a + b)", "(a + b)"),
            ("(a b)", "(a b)"),
            ("a?", "a?"),
            ("<ASTART>", "<ASTART>"),
            ("<AEND>", "<AEND>"),
            ("[abc]", "[abc]"),
            ("(  [0-9 ])", "(  [0-9 ])"),
            ("[ab0-9c]", "[ab0-9c]"),
            ("[^ab0-9c]", "[^ab0-9c]"),
        ])

    def test_programmers_simple_str(self):
        self.runtest(self.convert.prog, [
            ("a", "a"),
            ("a+", "(a a*)"),
            ("a{3}", "((a a) a)"),
            ("a{3,}", "(((a a) a) a*)"),
            ("a{3,9}", "(((a a) a) ((((@epsilon + a) (@epsilon + (a a))) (@epsilon + a)) (@epsilon + (a a))))"),
            ("a{,9}", "(((((@epsilon + a) (@epsilon + (a a))) (@epsilon + (((a a) a) a))) (@epsilon + a)) (@epsilon + a))"),
            ("a*", "a*"),
            ("a|b", "(a + b)"),
            ("ab", "(a b)"),
            ("a?", "a?"),
            ("^a", "(<ASTART> a)"),
            ("a$", "(a <AEND>)"),
            ("..", "(@any @any)"),
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
            (u"썐*", u"썐*"),
            (u"(ë + Ĥ)", u"(ë + Ĥ)"),
            (u"(ǿ Ȍ)", u"(ǿ Ȍ)"),
            (u"Ͽ?", u"Ͽ?"),
            (u"[𐌸b♫]", u"[𐌸b♫]"),
            (u"[▢-▩]", u"[▢-▩]"),
            (u"[a⚡0-9c]", u"[a⚡0-9c]"),
            (u"[^ab0-好c]", u"[^ab0-好c]"),
        ])

    def test_programmers_simple_unicode(self):
        self.runtest(self.convert.prog, [
            (u"α", u"α"),
            (u'"α"', u'((" α) ")'),
            (u"∀", u"∀"),
            (u".", u"@any"),
            (u"ë|Ĥ", u"(ë + Ĥ)"),
            (u"ǿȌ", u"(ǿ Ȍ)"),
            (u"Ͽ?", u"Ͽ?"),
            (u".", u"@any"),
            (u"[𐌸b♫]", u"[𐌸b♫]"),
            (u"[▢-▩]", u"[▢-▩]"),
            (u"[a⚡0-9c]", u"[a⚡0-9c]"),
            (u"[^α➸ƒ0✏9Ѧ➸ℱ]", u"[^α➸ƒ0✏9Ѧ➸ℱ]"),
            (u"[^α➸ƒ0✏9Ѧ-ℱ]", u"[^α➸ƒ0✏9Ѧ-ℱ]"),
            (u"€ᾔ¢◎øℓ   тℯ|ϰт", u"(((((((((((€ ᾔ) ¢) ◎) ø) ℓ)  )  )  ) т) ℯ) + (ϰ т))"),
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
            except FAdoizeError:
                pass

    def test_lark_errors(self):
        exprs = [
            u"(🇨🇦 + 🇵🇹)",   # no support for 8-byte paired characters 🇨🇦 = '\U0001f1e8\U0001f1e6'
            u"(",           # '(' would need a \ in-front to indicate it's an atom not meta

            # incomplete
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
            ("<ASTART>",                "<ASTART>"),
            ("<AEND>",                  "<AEND>"),
            ("a",                       "a"),
            ("@any",                    "@any"),
            ("(<ASTART> a*)",           "(<ASTART> a*)"),
            ("((<ASTART> a*) <AEND>)",  "((<ASTART> a*) <AEND>)"),
            ("(a* (0 + 1))",            "(a* (0 + 1))"),
            ("((a* (0 + 1)) <AEND>)",   "((a* (0 + 1)) <AEND>)"),
        ]
        self.runtest(self.convert.math, exprs, partialMatch=False)

    def test_anchor_yesPartialMatch(self):
        exprs = [
            ("<ASTART>",                "(<ASTART> @any*)"),
            ("<AEND>",                  "(@any* <AEND>)"),
            ("a",                       "((@any* a) @any*)"),
            ("@any",                    "((@any* @any) @any*)"),
            ("(<ASTART> a*)",           "(<ASTART> (a* @any*))"),
            ("((<ASTART> a*) <AEND>)",  "((<ASTART> a*) <AEND>)"),
            ("(a* (0 + 1))",            "((@any* a*) ((0 @any*) + (1 @any*)))"),
            ("((a* (0 + 1)) <AEND>)",   "(((@any* a*) (0 + 1)) <AEND>)"),
        ]
        self.runtest(self.convert.math, exprs, partialMatch=True)

    def test_symbol_or_meta(self):
        exprs = [
            ("\\(", "\\("),
            ("\\)", "\\)"),
            ("\\[", "\\["),
            ("\\]", "\\]"),
            ("\\*", "\\*"),
            ("\\?", "\\?"),
            ("\\+", "\\+"),

            ("(\\( \\))",   "(\\( \\))"),
            ("(\\+ + \\*)", "(\\+ + \\*)"),
            ("\\??",        "\\??"),

            ("\\r", "\\r"),
            ("\\n", "\\n"),
            ("\\t", "\\t"),
        ]
        self.runtest(self.convert.math, exprs)


    def runtest(self, convert, expressions, partialMatch=False):
        for prog, fado in expressions:
            try:
                val = convert(prog, partialMatch=partialMatch)
                self.assertEqual(str(val), fado.encode("utf-8"), prog.encode("utf-8") + " => "
                    + str(val) + " != " + fado.encode("utf-8"))
            except Exception as e:
                if type(e) is not AssertionError:
                    print "\nerror on:"
                    print "prog:", prog
                    print "fado:", fado
                raise


class TestFAdoize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = Converter()
        cls.f = lambda _, expr: c.FAdoize(expr, validate=True)

    def test_charclass(self):
        self.assertEqual(self.f('\\d'), '[0-9]')
        self.assertEqual(self.f('\\D'), '[^0-9]')
        self.assertEqual(self.f('[\\d]'), '[0-9]')

        self.assertEqual(self.f('\\s'), ' ')
        self.assertEqual(self.f('\\S'), '[^ ]')
        self.assertEqual(self.f('[\\s]'), '[ ]')

        self.assertEqual(self.f('\\w'), '[0-9A-Za-z_]')
        self.assertEqual(self.f('\\W'), '[^0-9A-Za-z_]')
        self.assertEqual(self.f('[\\w]'), '[0-9A-Za-z_]')

    def test_almost_charclass(self):
        self.assertEqual(self.f('\\\\d'), '(\\\\ d)')
        self.assertEqual(self.f('\\\\D'), '(\\\\ D)')
        self.assertEqual(self.f('[\\\\d]'), '[\\\\d]')

        self.assertEqual(self.f('\\\\s'), '(\\\\ s)')
        self.assertEqual(self.f('\\\\S'), '(\\\\ S)')
        self.assertEqual(self.f('[\\\\s]'), '[\\\\s]')

        self.assertEqual(self.f('\\\\w'), '(\\\\ w)')
        self.assertEqual(self.f('\\\\W'), '(\\\\ W)')
        self.assertEqual(self.f('[\\\\w]'), '[\\\\w]')

    def test_forwardslash(self):
        self.assertEqual(Converter().FAdoize('//'), '(/ /)')

    def test_escaping(self):
        self.assertEqual(self.f("\\(\\)"), "(\\( \\))")
        self.assertEqual(self.f("\\[\\]"), "(\\[ \\])")
        self.assertEqual(self.f("\\*\\+\\?\\\\"), "(((\\* \\+) \\?) \\\\)")

        self.assertEqual(self.f("[\\]]"), "[\\]]")
        self.assertEqual(self.f("[\\[]"), "[\\[]")
        self.assertEqual(self.f("[\\^]"), "[\\^]")
        self.assertEqual(self.f("[\\-]"), "[\\-]")
        self.assertEqual(self.f("a[\\]]"), "(a [\\]])")
        self.assertEqual(self.f("a[\\]abc]"), "(a [\\]abc])")

    # some of the "edge cases" found while processing the sample
    def test_sampleIssues(self):
        self.assertEqual(self.f(r"\^\\circ"), r"(((((^ \\) c) i) r) c)")
        self.assertEqual(self.f(r"[.+\-\w]+"), "([.+\\-0-9A-Za-z_] [.+\\-0-9A-Za-z_]*)")
        self.assertEqual(self.f(r"^([.+\-\w]+)$"), "((<ASTART> ([.+\\-0-9A-Za-z_] [.+\\-0-9A-Za-z_]*)) <AEND>)")


if __name__ == "__main__":
    unittest.main()