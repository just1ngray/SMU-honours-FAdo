# coding: utf-8
import unittest

from benchmark.util import FAdoizeError
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
        cls.sampler = PythonSampler()

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")

    def test_raises(self):
        shouldRaise(self, '''abc = re.compile()''', InvalidExpressionError)
        shouldRaise(self, '''abc = re.compile("abc')''', InvalidExpressionError)
        shouldRaise(self, """abc = re.compile("abc''')""", InvalidExpressionError)
        shouldRaise(self, '''abc = re.compile("abc%s" % var)''', InvalidExpressionError)
        shouldRaise(self, '''        r = re.compile('|'.joishouldRaise(self,('%d'%x for x in range(10000))))''', InvalidExpressionError)
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
        cls.sampler = JavaScriptSampler()

    def test_none(self):
        isNone(self, "abc")
        isNone(self, "")

    def test_raises(self):
        shouldRaise(self, '''myregex = new RegExp(''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp()''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp(an_object)''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp("string" + "another")''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp("string" + somevar)''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp(somevar + "string")''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp("string)''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp("string)"''', InvalidExpressionError)
        shouldRaise(self, '''myregex = new RegExp("string\\")''', InvalidExpressionError)
        shouldRaise(self, '''       rcomma = new RegExp( "^" + whitespace + "*," + whitespace + "*" ),''', InvalidExpressionError)

    def test_extracts(self):
        isEq(self, '''new RegExp("re")''', 're')
        isEq(self, '''new RegExp('re')''', 're')
        isEq(self, '''new RegExp(`re`)''', 're')
        isEq(self, '''new RegExp(/re/)''', 're')
        isEq(self, '''new RegExp(/re/ug)''', 're')
        isEq(self, '''new RegExp("re", "g")''', 're')
        isEq(self, '''aregexp = new RegExp("\\"re\\"")''', '\\"re\\"')
        isEq(self, '''aregexp = new RegExp("\\"re\\" more")''', '\\"re\\" more')
        isEq(self, '''    code: String.raw`var r = new RegExp("[\\uD83D\\uDC4D]", "")`,''', '[\\uD83D\\uDC4D]')
        isEq(self, '''new RegExp("//")''', '//')

if __name__ == "__main__":
    unittest.main()