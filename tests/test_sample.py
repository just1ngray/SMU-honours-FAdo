# coding: utf-8
import unittest

from benchmark.convert import Converter
from benchmark.errors import FAdoizeError, InvalidExpressionError
from benchmark.sample import *

def isNone(self, line):
    self.assertIsNone(self.sampler.get_line_expression(line))

def isEq(self, line, expr):
    self.assertEqual(self.sampler.get_line_expression(line), expr)

def shouldRaise(self, line, err):
    try:
        self.sampler.get_line_expression(line)
    except err:
        pass

class TestPythonSampler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampler = PythonSampler(Converter())

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")

    def test_raises(self):
        shouldRaise(self, '''abc = re.compile()''', InvalidExpressionError)
        shouldRaise(self, '''abc = re.compile("abc')''', InvalidExpressionError)
        shouldRaise(self, """abc = re.compile("abc''')""", InvalidExpressionError)
        shouldRaise(self, '''abc = re.compile("abc%s" % var)''', InvalidExpressionError)
        shouldRaise(self, '''        r = re.compile('|'.shouldRaise(self,('%d'%x for x in range(10000))))''', InvalidExpressionError)
        shouldRaise(self, r'''res = regex.findall(re.escape('\u2620'.encode('utf-8')), b)''', InvalidExpressionError)
        shouldRaise(self, u'''        re.compile('(?P<𝔘𝔫𝔦𝔠𝔬𝔡𝔢>x)(?P=𝔘𝔫𝔦𝔠𝔬𝔡𝔢)(?(𝔘𝔫𝔦𝔠𝔬𝔡𝔢)y)')''', FAdoizeError)

    def test_extracts(self):
        isEq(self, r'''abc = re.compile('x[\dabcdef]{1,}') # comment''', r'x[\dabcdef]{1,}')
        isEq(self, r'''        re.compile("(\")")''', r'(\")')
        isEq(self, r'''        self.assertIsNone(re.fullmatch(r"abc\Z", "abc\n"))''', "abc\\Z")
        isEq(self, r'''iter = re.finditer(r":+", "a:b::c:::d")''', ":+")
        isEq(self, r'''self.assertEqual(re.search('x+', 'axx').span(), (1, 3))''', "x+")
        isEq(self, r'''self.assertEqual(re.split("(?::+)", ":a:b::c"), ['', 'a', 'b', 'c'])''', "(?::+)")
        isEq(self, r'''self.assertEqual(re.match('(a)(?:((b)*)c)*', 'abb').groups(),''', "(a)(?:((b)*)c)*")

class TestJavaScriptSampler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampler = JavaScriptSampler(Converter())

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")
        isNone(self, "somevar.search('abc')")
        isNone(self, "somevar.search(new RegExp(`abc`))")

    def test_raises(self):
        shouldRaise(self, '''somevar.search(/abcdef''', InvalidExpressionError)
        shouldRaise(self, '''somevar.search(/   \\/)''', InvalidExpressionError)

    def test_extracts(self):
        isEq(self, '''.match(/abc/)''', 'abc')
        isEq(self, '''.match(/ab\\/c/)''', 'ab/c')
        isEq(self, '''.search(/abc/g)''', 'abc')
        isEq(self, '''.search(/abc/g)''', 'abc')
        isEq(self, '''.replace(/a(0|1|001)?/gi)''', 'a(0|1|001)?')
        isEq(self, '''.split(/ /)''', ' ')

class TestJavaSampler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampler = JavaSampler(Converter())

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")
        isNone(self, "Pattern.compile(var)")
        isNone(self, 'Pattern.compile(')

    def test_raises(self):
        shouldRaise(self, '''Pattern.compile("''', InvalidExpressionError)
        shouldRaise(self, '''Pattern.compile("valid" + bad + "more")''', InvalidExpressionError)
        shouldRaise(self, '''Pattern.compile("valid" + bad)''', InvalidExpressionError)
        shouldRaise(self, '''Pattern.compile("esc_closed\\\\")''', InvalidExpressionError)

    def test_extracts(self):
        isEq(self, '''Pattern.compile("valid\\\\"")''', 'valid\\"')
        isEq(self, '''Pattern.compile("simple")''', 'simple')
        isEq(self, '''Pattern.compile("simple", FLAGS)''', 'simple')
        isEq(self, '''Pattern.compile("\\\\w", FLAGS)''', '\\w')

class TestPerlSampler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampler = PerlSampler(Converter())

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")
        isNone(self, "$var =~ bad_flags/abc/")

    def test_raises(self):
        shouldRaise(self, "$var =~ /abc", InvalidExpressionError)
        shouldRaise(self, '$var =~ /abc\\/', InvalidExpressionError)

    def test_extracts(self):
        isEq(self, '$var =~ /abc/', 'abc')
        isEq(self, '$var =~ /abc\\//', 'abc/')

if __name__ == "__main__":
    unittest.main()