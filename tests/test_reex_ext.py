# coding: utf-8
import unittest
from FAdo import reex

from benchmark.reex_ext import uatom, chars, dotany
import benchmark.util as util


class TestUAtom(unittest.TestCase):
    def setUp(self):
        return super(TestUAtom, self).setUp()

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
            aord = util.unicode_ord(a)

            # str should not throw
            str(atom)

            # derivative
            self.assertEqual(atom.derivative(a), reex.epsilon())
            self.assertEqual(atom.derivative(util.unicode_chr(aord + 1)), reex.emptyset())
            self.assertEqual(atom.derivative(util.unicode_chr(aord - 1)), reex.emptyset())

            # __contains__
            self.assertTrue(a in atom)
            self.assertFalse(u"a" in atom)

            # next
            self.assertIsNone(atom.next(a))
            self.assertEqual(atom.next(None), a)
            self.assertEqual(atom.next(u"a"), a)

            # intersect
            self.assertIsNone(atom.intersect(reex.epsilon()), None)
            self.assertEqual(atom.intersect(dotany()), atom)
            self.assertEqual(atom.intersect(chars(u"a", neg=True)), atom)


class TestChars(unittest.TestCase):
    def setUp(self):
        self.unicode_source = u"🔑 ✞♄їṧ їṧ @ ẘḯ∂ℯ ґαᾔ❡℮ øƒ ʊᾔї¢øḓε ṧ⑂μß☺ℓṧ ρα﹩ṧℯ∂ ⊥няøʊ❡н αη ℮ᾔ¢◎øʟ" \
            + u"εη¢◎ḓℯґ▣ Ї☂ мα☤ᾔ☂α☤η﹩ ‴ґ℮@ḓ@♭ḯʟḯ⊥¥❞ ♭υ⊥ яε℘ℓα¢εṧ ☂♄ε αṧ¢ḯ☤ ṧƴღ♭◎ʟ﹩ ω☤тℌ " \
            + u"ʊᾔї¢ø∂ε @ℓтεґηα⊥ї♥℮ṧ❣ ✨ ASCII :) 567"
        self.posUnicode = chars(self.unicode_source)
        self.negUnicode = chars(self.unicode_source, neg=True)

        self.posHex = chars([u"a", u"b", u"c", (u"0", u"9"), u"d", u"e", u"f"])
        self.negHex = chars([u"a", u"b", u"c", (u"0", u"9"), u"d", u"e", u"f"], neg=True)
        return super(TestChars, self).setUp()

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
    def setUp(self):
        return super(TestDotAny, self).setUp()

    def test_derivative(self):
        self.assertEqual(dotany().derivative(u"a"), reex.epsilon())
        self.assertEqual(dotany().derivative(u"α"), reex.epsilon())
        self.assertEqual(dotany().derivative(u"🔥"), reex.epsilon())

    def test_next(self):
        arr = [3904, 14987, 24086, 3836, 2205, 3446, 13563, 2749, 1210, 1435, 65]
        for v in arr:
            self.assertEqual(dotany().next(util.unicode_chr(v)), util.unicode_chr(v + 1))

        self.assertEqual(dotany().next(), " ")

    def test_intersect(self):
        self.assertEqual(dotany().intersect(reex.epsilon()), None)
        self.assertEqual(dotany().intersect(dotany()), dotany())
        self.assertEqual(dotany().intersect(uatom(u"a")), uatom(u"a"))
        self.assertEqual(dotany().intersect(chars(u"a")), chars(u"a"))



if __name__ == "__main__":
    unittest.main()