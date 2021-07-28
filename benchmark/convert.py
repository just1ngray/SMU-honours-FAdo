from lark import Lark, Transformer
from FAdo import reex

import reex_ext as ext
from .util import FAdoize

class Converter(object):
    """ A class to convert from `export.csv` regular expressions in the `re.lark`
        grammar to FAdo classes using the `reex` & `reex_ext` modules.
    """
    def __init__(self):
        self._parser = Lark.open("benchmark/re.lark", start="expression",
            parser="lalr", transformer=LarkToFAdo())

    def math(self, expression, partialMatch=False):
        """Convert a `benchmark/re.lark` formatted string into a FAdo regexp tree.
        :param unicode|str expression: the expression to convert
        ..note: if there are non-ascii symbols in the expression, it must be passed
                as unicode type (i.e., u"non-ascii")
        ..note: all symbols must be representable in <= 4 bytes using utf-8 (this
                excludes emoji flags and maybe some other characters)
        :param bool partialMatch: given any text T, U, and word weL(expression),
                                  should the regexp tree match text 'TwL'?
        :returns: the parsed regexp tree
        :rtype: reex.regexp
        :raises: if there's a parsing error, or if anchors are found in non-"edge"
                 leaf positions
        """
        # print "CONVERTING", expression, "\t\t", repr(expression.encode("utf-8"))[1:-1]
        re = self._parser.parse(repr(expression.encode("utf-8"))[1:-1])

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
            if type(current) is reex.concat:
                stack.append((current, "arg2", False, anchorAllowedRight))
                stack.append((current, "arg1", anchorAllowedLeft, False))
            elif type(current) is reex.disj:
                stack.append((current, "arg2", anchorAllowedLeft, anchorAllowedRight))
                stack.append((current, "arg1", anchorAllowedLeft, anchorAllowedRight))
            elif type(current) is reex.star \
              or type(current) is reex.option:
                stack.append((current, "arg", False, False))
                expand = True

            # terminals
            elif type(current) is ext.anchor:
                if ((attr[-1] == "2" and anchorAllowedRight and current.label == "<AEND>")
                    or (attr[-1] == "1" and anchorAllowedLeft and current.label == "<ASTART>")
                    or (attr == "arg" and (anchorAllowedLeft or anchorAllowedRight))):

                    setattr(parent, attr, reex.epsilon())
                    stack.append((parent, attr, current.label == "<AEND>" and anchorAllowedLeft,
                            current.label == "<ASTART>" and anchorAllowedRight))
                else:
                    raise Exception("Unexpected anchor found in " + expression)
            elif isinstance(current, ext.uatom) \
              or type(current) is reex.epsilon:
                expand = True
            else:
                raise Exception("Unknown item in tree: " + str(type(current)))

            if partialMatch and expand:
                if anchorAllowedLeft:
                    setattr(parent, attr, reex.concat(reex.star(ext.dotany()), getattr(parent, attr)))
                if anchorAllowedRight:
                    setattr(parent, attr, reex.concat(getattr(parent, attr), reex.star(ext.dotany())))

        return d.arg

    def prog(self, expression, partialMatch=True):
        r"""Convert a regular expression used in programming into a FAdo regexp tree.
            i.e., supports [+,*,?,{x},{x,},{x,y},{,y}] repetitions,
                  character classes like \d,
                  ^ and $ are used as anchors,
                  and uses the | (pipe) for disjunctive "or's"
        :param unicode|str expression: the expression to convert
        :param bool partialMatch: given any text T, U, and word weL(expression),
                                  should the regexp tree match text 'TwL'?
        :returns: the parsed regexp tree
        :rtype: reex.regexp
        :raises: if there's a parsing error, or if anchors are found in non-"edge"
                 leaf positions
        ..note: self.prog is much slower than self.math since it has to spin up a
            NodeJS process in order to execute additional logic
        """
        formatted = FAdoize(expression)
        return self.math(formatted, partialMatch=partialMatch)


class LarkToFAdo(Transformer):
    """Used with parser="lalr" to transform the tree in real-time into FAdo objects.
    ..see: `benchmark/re.lark`
    """
    def expression(self, e):
        return e[0]

    def option(self, e):
        return reex.option(e[0])

    def kleene(self, e):
        return reex.star(e[0])

    def concat(self, e):
        return reex.concat(e[0], e[1])

    def disjunction(self, e):
        return reex.disj(e[0], e[1])

    def chars(self, items):
        items = list(map(lambda c: c.val if isinstance(c, reex.atom) else c, items))
        return ext.chars(items, neg=False)

    def neg_chars(self, items):
        items = list(map(lambda c: c.val if isinstance(c, reex.atom) else c, items))
        return ext.chars(items, neg=True)

    def char_range(self, s):
        return (s[0].val, s[1].val)

    def SYMBOL(self, s):
        return ext.uatom(s.value.decode("string-escape").decode("utf-8"))

    def EPSILON(self, _):
        return reex.epsilon()

    def DOTANY(self, _):
        return ext.dotany()

    def ANCHOR(self, a):
        return ext.anchor(a)