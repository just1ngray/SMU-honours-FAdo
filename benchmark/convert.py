from lark import Lark, Transformer
from FAdo import reex
from copy import deepcopy

from reex_ext import chars, dotany, anchor

class Converter(object):
    """ A class to convert from `export.csv` regular expressions in the `re.lark`
        grammar to FAdo classes using the `reex` & `reex_ext` modules.
    """
    def __init__(self):
        self.parser = Lark.open("benchmark/re.lark", start="expression",
            parser="lalr", transformer=LarkToFAdo())

    def one(self, expression, partialMatch=False):
        """Get the FAdo regexp from an expression
        :arg expression: the expression to parse into FAdo
        :arg partialMatch:  if true, partial matches are allowed such as "a" matches "   a"
                            if false, perfect matches must be found (mathematical definition)
        :rtype: reex.regexp
        :throws: if parsing error
        """
        re = self.parser.parse(expression)
        formatter = RegexpFormatter(re)

        if partialMatch: formatter.allowPartialMatches()
        formatter.replaceAnchors()

        return formatter.get()

    def all(self, expressions, partialMatch=False):
        """Get FAdo regexps from a list of expressions.
        :arg expressions: the list of expressions to parse into FAdo
        :arg partialMatch:  if true, partial matches are allowed such as "a" matches "   a"
                            if false, perfect matches must be found (mathematical definition)
        :rtype: list<reex.regexp or None when parsing error>
        """
        converted = []
        for expr in expressions:
            try:    converted.append(self.one(expr, partialMatch=partialMatch))
            except: converted.append(None)

        return converted


class RegexpFormatter(object):
    """A class to format a `reex.regexp` object"""

    def __init__(self, re):
        """Create a new RegexpFormatter
        :arg re: the reex.regexp to deep copy and modify in place
        """
        super(RegexpFormatter, self).__init__()
        self.re = deepcopy(re)

    def allowPartialMatches(self):
        """Allow partialMatches for this reex.regexp by adding `(@any*)` at the start and
        end positions (using concatenation only) where no anchor is found.
        """
        anyStar = lambda: reex.star(dotany())
        def repl(current, concat):
            if type(current) is anchor:
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
            if type(current) is anchor:
                return reex.epsilon()
            else:
                return current
        self._anchorReplace("arg1", repl)
        self._anchorReplace("arg2", repl)

        stack = [self.re]
        while len(stack) > 0:
            current = stack.pop()
            if type(current) is anchor:
                raise Exception("Unexpected anchor in found in " + str(self.re))
            if getattr(current, "arg", None):
                stack.append(current.arg)
            elif getattr(current, "arg1", None):
                stack.append(current.arg2)
                stack.append(current.arg1)

    def get(self):
        """Gets the formatted & modified reex.regexp"""
        return self.re

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
    def expression(self, expr):
        return expr[0]

    def kleene(self, e):
        return reex.star(e[0])

    def concat(self, e):
        return reex.concat(e[0], e[1])

    def disjunction(self, d):
        return reex.disj(d[0], d[1])

    def char_class(self, items):
        neg = items[0] == "^"
        items = list(map(lambda c: str(c) if type(c) is reex.atom else c, items))
        return chars(items[(1 if neg else 0):], neg=neg)

    def CHAR_RANGE(self, rng):
        start, end = str(rng).split("-")
        return (start, end)

    def SYMBOL(self, s):
        s = str(s)
        if s == "@epsilon": return reex.epsilon()
        elif s == "@any": return dotany()
        return reex.atom(s)

    def ANCHOR(self, a):
        return anchor(a)