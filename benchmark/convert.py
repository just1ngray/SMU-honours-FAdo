from lark import Lark, Transformer
from lark.exceptions import LarkError
import regex
import subprocess
import json

from reex_ext import *

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
        # \r => \\r, \t => \\t, \n ==> \\n... this seems to be the fastest method
        expression = expression.replace("\r", "\\r")
        expression = expression.replace("\t", "\\t")
        expression = expression.replace("\n", "\\n")

        re = self._parser.parse(expression) # type: uregexp

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
                    raise AnchorError(re, expression)
            elif isinstance(current, uatom) \
              or type(current) is uepsilon:
                expand = True
            else:
                raise ConversionError("Unknown item in tree: " + str(type(current)))

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

    symbol = lambda _, e: uatom(unicode(e[0].value))

    def ESCAPED(self, e):
        e.value = e.value.decode("string-escape")
        return e

    EPSILON = lambda _0, _1: uepsilon()
    DOTANY = lambda _0, _1: dotany()
    ANCHOR = lambda _, e: anchor(e.value)


class ConversionError(Exception):
    def __init__(self, msg):
        super(ConversionError, self).__init__(msg)

class AnchorError(ConversionError):
    def __init__(self, re, expression):
        super(AnchorError, self).__init__("Unexpected anchor position in " + expression)
        self.re = re
        self.expression = expression

class FAdoizeError(ConversionError):
    def __init__(self, expression, node_callback):
        super(FAdoizeError, self).__init__("Error during FAdoization")
        self.expression = expression
        self.node_callback = node_callback

    def __str__(self):
        return "FAdoizeError on '{0}':\n{1}".format(self.expression, self.node_callback)

nodejs_proc = None
def FAdoize(expression):
    """Convert an "ambiguous" expression used by a programmer into an expression
    ready to parse into FAdo via the `benchmark/convert.py#Converter` using the
    `benchmark/re.lark` grammar.
    :param unicode|str expression: the expression to convert into unambiguous FAdo
    :returns unicode: the parenthesized and formatted expression
    :raises FAdoizeError: if `benchmark/parse.js` throws
    ..note: FAdoize will include a cold start time as the NodeJS process is created.
            Subsequent calls will not incur this cost until this Python process finishes.
    """
    # regexp-tree doesn't support repetition in the form a{,n} as a{0,n}... convert manually
    def repl(match):
        return "{0," + match[2:-1] + "}"
    expression = regex.sub(r"\{,[0-9]+\}", lambda x: repl(x.group()), expression)

    # remove redundant (and invalid) escapes
    valids = set("sSwWdDtnrfvuU\\^$.()[]+*{}bB0123456789")
    i = 0
    while True:
        try:
            index = expression.index("\\", i)
            if expression[index + 1] not in valids:
                expression = expression[:index] + expression[index+1:]
                i = index
            else:
                i = index + 1
        except (IndexError, ValueError):
            break

    if globals()["nodejs_proc"] is None:
        globals()["nodejs_proc"] = subprocess.Popen(["node", "benchmark/parse.js"],
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)

        import atexit
        atexit.register(lambda: globals()["nodejs_proc"].terminate())

    if len(expression) == 0:
        raise FAdoizeError(expression, "Expression must have a length > 0")

    if type(expression) is unicode: # ensure expression is utf-8 encoded string
        expression = expression.encode("utf-8")

    proc = globals()["nodejs_proc"]
    proc.stdin.write(expression)
    proc.stdin.flush()
    output = json.loads(proc.stdout.readline())

    if output["error"] != 0:
        logs = reduce(lambda p, c: p + "\n" + c, output["logs"])
        logs_and_callback = (logs + "\n\n" + output["error"]).encode("utf-8")
        raise FAdoizeError(expression, logs_and_callback)
    else:
        return output["formatted"] # unicode