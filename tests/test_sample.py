# coding: utf-8
import unittest

from benchmark.util import FAdoize
from benchmark.sample import *

class TestPythonSampler(unittest.TestCase):
    def test_get_line_expression_none(self):
        sampler = PythonSampler()
        def n(line):
            self.assertIsNone(sampler.get_line_expression(line))

        n("abc")
        n("")
        n('''abc = re.compile()''')
        n('''abc = re.compile("abc')''')
        n("""abc = re.compile("abc''')""")
        n('''abc = re.compile("abc%s" % var)''')
        n('''        r = re.compile('|'.join(('%d'%x for x in range(10000))))''')
        n(r'''res = regex.findall(re.escape('\u2620'.encode('utf-8')), b)''')
        n(u'''        re.compile('(?P<𝔘𝔫𝔦𝔠𝔬𝔡𝔢>x)(?P=𝔘𝔫𝔦𝔠𝔬𝔡𝔢)(?(𝔘𝔫𝔦𝔠𝔬𝔡𝔢)y)')''')

    def test_get_line_expression_match(self):
        sampler = PythonSampler()
        def eq(line, expr):
            extracted = sampler.get_line_expression(line)
            self.assertEqual(extracted, expr)
            FAdoize(extracted)

        eq(r'''abc = re.compile('x[\dabcdef]{1,}') # comment''', 'x[\dabcdef]{1,}')
        eq(r'''        re.compile("(\")")''', r'(\")')
        eq(r'''        self.assertIsNone(re.fullmatch(r"abc\Z", "abc\n"))''', "abc\\Z")
        eq(r'''iter = re.finditer(r":+", "a:b::c:::d")''', ":+")
        eq(r'''self.assertEqual(re.search('x+', 'axx').span(), (1, 3))''', "x+")
        eq(r'''self.assertEqual(re.split("(?::+)", ":a:b::c"), ['', 'a', 'b', 'c'])''', "(?::+)")
        eq(r'''self.assertEqual(re.match('(a)(?:((b)*)c)*', 'abb').groups(),''', "(a)(?:((b)*)c)*")

if __name__ == "__main__":
    unittest.main()