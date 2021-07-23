from lark import Lark, Transformer
from FAdo import reex

import reex_ext as ext
from sample.util import FAdoize

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
        # print "\n\nCONVERTING", expression
        re = self._parser.parse(repr(expression.encode("utf-8"))[1:-1])
        formatter = RegexpFormatter(re)

        if partialMatch: formatter.allowPartialMatches()
        formatter.replaceAnchors()
        return formatter.re

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


class RegexpFormatter(object):
    """A class to format a `reex.regexp` object"""

    def __init__(self, re=None):
        """Create a new RegexpFormatter
        :arg re: the reex.regexp to deep copy and modify in place
        """
        super(RegexpFormatter, self).__init__()
        self.re = re

    def allowPartialMatches(self):
        """Allow partialMatches for this reex.regexp by adding `(@any*)` at the start and
        end positions (using concatenation only) where no anchor is found.
        """
        anyStar = lambda: reex.star(ext.dotany())
        def repl(current, concat):
            if type(current) is ext.anchor:
                return reex.epsilon()
            elif type(current) is reex.epsilon:
                return anyStar()
            else:
                return concat

        self._anchorReplace("arg1", lambda c: repl(c, reex.concat(anyStar(), c)))
        self._anchorReplace("arg2", lambda c: repl(c, reex.concat(c, anyStar())))

    def replaceAnchors(self):
        """Replace "allowed" anchors with `@epsilon`.
        Raise an error if there is an unexpected anchor. An anchor is unexpected if it's in a position
        other than the leftmost leaf or rightmost leaf.
        """
        def repl(current):
            if type(current) is ext.anchor:
                return reex.epsilon()
            else:
                return current
        self._anchorReplace("arg1", repl)
        self._anchorReplace("arg2", repl)

        stack = [self.re]
        while len(stack) > 0:
            current = stack.pop()
            if type(current) is ext.anchor:
                raise Exception("Unexpected anchor in found in " + str(self.re))
            if getattr(current, "arg", None):
                stack.append(current.arg)
            elif getattr(current, "arg1", None):
                stack.append(current.arg2)
                stack.append(current.arg1)

    def _anchorReplace(self, arg, repl):
        """Replaces anchors found recursively in concat operations defined by the `arg` direction.
        :arg str arg: "arg1" or "arg2" depending on the direction to search
        :arg function repl: (leafnode) => replacement for that leafnode
        """
        if self.re.treeLength() <= 1:
            self.re = repl(self.re)
            return

        current = self.re
        while current is not None:
            if type(current) is reex.concat:
                child = getattr(current, arg)
                if child.treeLength() <= 1 or type(child) is reex.star or type(child) is reex.disj:
                    setattr(current, arg, repl(getattr(current, arg)))
                    break
                current = getattr(current, arg, None)
            else:
                current = None


class LarkToFAdo(Transformer):
    """Used with parser="lalr" to transform the tree in real-time into FAdo
    objects.
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
        # print ""
        # print "SYMBOL", s.value
        # print s.value.decode("string-escape"), type(s.value.decode("string-escape"))
        # print s.value.decode("string-escape").decode("utf-8")
        return ext.uatom(s.value.decode("string-escape").decode("utf-8"))

    def EPSILON(self, _):
        return reex.epsilon()

    def DOTANY(self, _):
        return ext.dotany()

    def ANCHOR(self, a):
        return ext.anchor(a)