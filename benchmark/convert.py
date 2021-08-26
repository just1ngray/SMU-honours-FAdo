from lark import Lark, Transformer
from lark.exceptions import LarkError

from reex_ext import *
from util import FAdoize

class Converter(object):
    """A class to parse a string/unicode expression into FAdo objects.
    """
    def __init__(self):
        self._parser = Lark.open("benchmark/re.lark", start="expression",
            parser="lalr", transformer=LarkToFAdo())

    def math(self, expression, partialMatch=False):
        """Convert a `benchmark/re.lark` formatted string into a FAdo regexp tree.
        :param unicode|str expression: the expression to convert
        ..note: if there are non-ascii symbols in the expression, it must be passed
                as unicode type (i.e., u"non-ascii")
        ..note: all symbols must be representable in <= 4 bytes using utf-8
                (ordinals up to 2**16 (65,536) exclusive)
        :param bool partialMatch: given any text T, U, and word weL(expression),
                                  should the regexp tree match text 'TwU'?
        :returns reex.regexp: the parsed regexp tree
        :raises: if there's a parsing error, or if anchors are found in non-"edge"
                 leaf positions
        """
        re = self._parser.parse(unicode(expression)) # type: uregexp

        class DummyClass():
            def __init__(self, arg):
                self.arg = arg
        d = DummyClass(re)

        stack = [(d, "arg", True, True)]
        while len(stack) > 0:
            parent, attr, anchorAllowedLeft, anchorAllowedRight = stack.pop()
            current = getattr(parent, attr)
            expand = False

            # non-terminals
            if type(current) is uconcat:
                stack.append((current, "arg2", False, anchorAllowedRight))
                stack.append((current, "arg1", anchorAllowedLeft, False))
            elif type(current) is udisj:
                stack.append((current, "arg2", anchorAllowedLeft, anchorAllowedRight))
                stack.append((current, "arg1", anchorAllowedLeft, anchorAllowedRight))
            elif type(current) is ustar \
              or type(current) is uoption:
                stack.append((current, "arg", False, False))
                expand = True

            # terminals
            elif type(current) is anchor:
                if ((attr[-1] == "2" and anchorAllowedRight and current.label == "<AEND>")
                    or (attr[-1] == "1" and anchorAllowedLeft and current.label == "<ASTART>")
                    or (attr == "arg" and (anchorAllowedLeft or anchorAllowedRight))):

                    setattr(parent, attr, uepsilon())
                    stack.append((parent, attr, current.label == "<AEND>" and anchorAllowedLeft,
                            current.label == "<ASTART>" and anchorAllowedRight))
                else:
                    raise Exception("Unexpected anchor found in " + expression)
            elif isinstance(current, uatom) \
              or type(current) is uepsilon:
                expand = True
            else:
                raise Exception("Unknown item in tree: " + str(type(current)))

            if partialMatch and expand:
                if anchorAllowedLeft:
                    setattr(parent, attr, uconcat(ustar(dotany()), getattr(parent, attr)))
                if anchorAllowedRight:
                    setattr(parent, attr, uconcat(getattr(parent, attr), ustar(dotany())))

        d.arg.expression = expression
        return d.arg

    def prog(self, expression, partialMatch=True):
        r"""Convert a regular expression used in programming into a FAdo regexp tree.
            i.e., supports [+,*,?,{x},{x,},{x,y},{,y}] repetitions,
                  character classes like \d,
                  ^ and $ are used as anchors,
                  and uses the | (pipe) for disjunctive "or's"
        :param unicode|str expression: the expression to convert
        :param bool partialMatch: given any text T, U, and word weL(expression),
                                  should the regexp tree match text 'TwU'?
        :returns reex.regexp: the parsed regexp tree
        :raises: if there's a parsing error, or if anchors are found in non-"edge"
                 leaf positions
        ..note: self.prog is much slower than self.math since it has to spin up a
            NodeJS process in order to execute additional logic
        """
        formatted = FAdoize(expression)
        try:
            re = self.math(formatted, partialMatch=partialMatch)
            re.expression = expression
            return re
        except LarkError as e:
            print expression, "was formatted as", formatted
            raise e

class LarkToFAdo(Transformer):
    """Used with parser="lalr" to transform the tree in real-time into FAdo objects.
    ..see: `benchmark/re.lark`
    """
    expression = lambda _, e: e[0]
    kleene = lambda _, e: ustar(e[0])
    option = lambda _, e: uoption(e[0])
    concat = lambda _, e: uconcat(e[0], e[1])
    disjunction = lambda _, e: udisj(e[0], e[1])

    char_range = lambda _, e: (e[0].val, e[1].val)

    def pos_chars(self, items):
        items = list(map(lambda c: c.val if isinstance(c, uatom) else c, items))
        return chars(items, neg=False)

    def neg_chars(self, items):
        items = list(map(lambda c: c.val if isinstance(c, uatom) else c, items))
        return chars(items, neg=True)

    symbol = lambda _, e: uatom(e[0].value)
    EPSILON = lambda _0, _1: uepsilon()
    DOTANY = lambda _0, _1: dotany()
    ANCHOR = lambda _, e: anchor(e.value)