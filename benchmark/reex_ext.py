from __future__ import print_function
from FAdo import reex, fa, common
import copy
import random

from util import RangeList, UniUtil, WeightedRandomItem
import errors
import fa_ext

class uregexp(reex.regexp):
    def __init__(self):
        super(uregexp, self).__init__(sigma=None)
        self.expression = None

    def pairGen(self):
        """Generate the pairwise coverage test words
        :returns set<unicode>:

        L. Zheng et al., String Generating for Testing Regular Expressions
        The Computer Journal, Volume 63, Issue 1, January 2020, Pages 41-65
        https://doi.org/10.1093/comjnl/bxy137
        """
        raise NotImplementedError()

    def toInvariantNFA(self, method):
        """Convert self into an InvariantNFA using a construction method
        methods include: nfaPD, nfaPDO, nfaPosition, nfaFollow, nfaGlushkov, nfaThompson
        :raises exceptions.UnknownREtoNFAMethod: if the provided method is not recognized
        """
        if method not in set(["nfaPD", "nfaPDO", "nfaPosition", "nfaFollow", "nfaGlushkov", "nfaThompson"]):
            raise errors.UnknownREtoNFAMethod(method)

        nfa = self.toNFA(method)
        return fa_ext.InvariantNFA(nfa)

    def evalWordP_Backtrack(self, word):
        """Using an algorithm similar to native programming language implementations to
        solve the membership problem. Allows for extended functionality such as backreferences,
        but leads to exponential worst-case time complexity.

        i.e., The evil expression `(a + a)*` will take a long time for words of the form "a"*i + "b"
        for sufficiently large i (typically > 25). However, standard derivative approach using
        evalWordP will be fast.

        Inspired from:
            Berglund, Martin & Drewes, Frank & Van Der Merwe, Brink. (2014).
            Analyzing Catastrophic Backtracking Behavior in Practical Regular Expression Matching.
            Electronic Proceedings in Theoretical Computer Science. 151. 10.4204/EPTCS.151.7.
        """
        if len(word) == 0:
            return self.ewp()

        for res in self._backtrackMatch(word):
            if len(res) == 0:
                return True
        return False

    def _backtrackMatch(self, word):
        """Called by evalWordPBacktrack using Algorithm 1 as described in the cited paper.
        Yields possible sub-words with matched prefixes removed from param word
        """
        raise NotImplementedError()

    def evalWordP_Derivative(self, word):
        return self.evalWordP(word)

    def evalWordP_PD(self, word):
        current = set([self])
        for sigma in word:
            nxt = set()
            for c in current:
                nxt.update(c.partialDerivatives(sigma))
            current = nxt

        for c in current:
            if c.ewp():
                return True
        return False

    def evalWordP_PDO(self, word):
        current = set([self])
        for sigma in word:
            nxt = set()
            for c in current:
                if not hasattr(c, "_pds"):
                    setattr(c, "_pds", dict())
                pds = c._pds.get(sigma, None)
                if pds is None:
                    pds = c.partialDerivatives(sigma)
                    c._pds[sigma] = pds
                nxt.update(pds)
            current = nxt

        for c in current:
            if c.ewp():
                return True
        return False

    def partialDerivatives(self, sigma):
        """Set of partial derivatives of the regular expression in relation to given symbol.

        :param sigma: symbol in relation to which the derivative will be calculated.
        :return: set of regular expressions

        .. seealso:: Antimirov, 95"""
        raise NotImplementedError()

    def display(self, fileName=None):
        """Displays the uregexp tree using `graphviz`
        """
        import tempfile
        import os
        import subprocess
        from IPython.display import SVG, display
        from FAdo.common import run_from_ipython_notebook

        ext = ".svg" if run_from_ipython_notebook() else ".pdf"

        if fileName is not None:
            fnameGV = fileName + ".gv"
            filenameOut = fileName + ext
        else:
            f = tempfile.NamedTemporaryFile(suffix=".gv")
            f.close()
            fnameGV = f.name
            fname, _ = os.path.splitext(fnameGV)
            filenameOut = fname + ext

        foo = open(fnameGV, "w")
        foo.write("strict digraph {\n"
            + 'label="{0}";\n'.format(str(self).encode("string-escape"))
            + 'labelloc="t";\n'
            + self._dotFormat()
            + "\n}\n")
        foo.close()

        if run_from_ipython_notebook():
            callstr = "dot -Tsvg %s -o %s" % (fnameGV, filenameOut)
        else:
            callstr = "dot -Tpdf %s -o %s" % (fnameGV, filenameOut)

        result = subprocess.call(callstr, shell=True)
        if result:
            print("Need graphviz to visualize objects")
            return

        if run_from_ipython_notebook():
            display(SVG(filename=filenameOut))
        elif os.name == 'nt':
            os.system("start %s" % filenameOut)
        else:
            os.system("open %s" % filenameOut)

    def _dotFormat(self):
        """Returns a string representation of self in graphviz dot format"""
        raise NotImplementedError()

    def partialMatch(self, force=False):
        """Returns a copy of self which accepts partially matched words.
        I.e., if L(self) = {w : w is accepted by self}
              then L(self.partialMatch()) = {pws : forall weW ^ p,s as any text length>=0}
        :raises errors.AnchorError: if an anchor is found to be misplaced or partialMatching has
            already been executed on this
        """
        if hasattr(self, "_partialMatch") and not force:
            raise errors.AnchorError(self, "partialMatching already enabled, pass force=True to override")

        re = self._pmBoth()
        re._partialMatch = 0
        return re

    def _pmBoth(self):
        """The beginning can be the word start, and after can be the word end"""
        raise NotImplementedError()

    def _pmStart(self):
        """The beginning can be the word start, and after can NOT be the word end"""
        raise NotImplementedError()

    def _pmEnd(self):
        """The beginning can NOT be the word start, and after can be the word end"""
        raise NotImplementedError()

    def _pmNeither(self):
        """The beginning can NOT be the word start, and after can NOT be the word end"""
        raise NotImplementedError()

    def _containsT(self, T):
        """Traverses the subtree searching for T(s). Returns bool"""
        raise NotImplementedError()

    def compress(self, uniqueSubtrees=dict()):
        """Mutates self to a compressed version where duplicate subtrees
            reference the same objects in memory.
        :param dict uniqueSubtrees: <repr, reference> to unique subtrees
        :post: compress method is overwritten to be trivial, and self is of
            compressed form.

        ..see: S. Konstantinidis, et al. "Partial Derivative Automaton by
            Compressing Regular Expressions"
        """
        self.compress = lambda u=dict(): None # prevent needless re-compression

class uconcat(reex.concat, uregexp):
    def __init__(self, arg1, arg2):
        super(uconcat, self).__init__(arg1, arg2, sigma=None)

    def __deepcopy__(self, memo):
        cpy = uconcat(copy.deepcopy(self.arg1), copy.deepcopy(self.arg2))
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        return "({0} {1})".format(str(self.arg1), str(self.arg2))

    def linearForm(self):
        arg1_lf = self.arg1.linearForm()
        lf = {}
        for head in arg1_lf:
            lf[head] = set()
            for tail in arg1_lf[head]:
                if tail.emptysetP():
                    lf[head].add(uemptyset())
                elif tail.epsilonP():
                    lf[head].add(self.arg2)
                else:
                    lf[head].add(uconcat(tail, self.arg2))
        if self.arg1.ewp():
            arg2_lf = self.arg2.linearForm()
            for head in arg2_lf:
                if head in lf:
                    lf[head].update(arg2_lf[head])
                else:
                    lf[head] = set(arg2_lf[head])
        return lf

    def partialDerivatives(self, sigma):
        pds = set()
        for pd in self.arg1.partialDerivatives(sigma):
            if pd.emptysetP():
                pass # pds.add(emptyset(self.Sigma))
            elif pd.epsilonP():
                pds.add(self.arg2)
            else:
                pds.add(uconcat(pd, self.arg2))
        if self.arg1.ewp():
            pds.update(self.arg2.partialDerivatives(sigma))
        return pds

    def _memoLF(self):
        if hasattr(self, "_lf"):
            return
        self.arg1._memoLF()
        self._lf = {}
        for head in self.arg1._lf:
            pd_set = set()
            self._lf[head] = pd_set
            for tail in self.arg1._lf[head]:
                if tail.emptysetP():
                    pd_set.add(uemptyset())
                elif tail.epsilonP():
                    pd_set.add(self.arg2)
                else:
                    pd_set.add(uconcat(tail, self.arg2))
        if self.arg1.ewp():
            self.arg2._memoLF()
            for head in self.arg2._lf:
                if head in self._lf:
                    self._lf[head].update(self.arg2._lf[head])
                else:
                    self._lf[head] = set(self.arg2._lf[head])

    def pairGen(self):
        # pairwise generation (aka 2-wise) is equivalent to combination generation for
        # 2 arguments as we have in concat (arg1 & arg2)
        words = set()
        for prefix in self.arg1.pairGen():
            for suffix in self.arg2.pairGen():
                words.add(prefix + suffix)
        return words

    def _backtrackMatch(self, word):
        for p1 in self.arg1._backtrackMatch(word):
            for p2 in self.arg2._backtrackMatch(p1):
                yield p2

    def _dotFormat(self):
        return str(id(self)) + '[label=".", shape="circle", ordering="out"];\n' \
            + self.arg1._dotFormat() + self.arg2._dotFormat() \
            + str(id(self)) + " -> " + str(id(self.arg1)) + ";\n" \
            + str(id(self)) + " -> " + str(id(self.arg2)) + ";\n"

    def _pmBoth(self):
        return uconcat(self.arg1._pmStart(), self.arg2._pmEnd())

    def _pmStart(self):
        return uconcat(self.arg1._pmStart(), self.arg2._pmNeither())

    def _pmEnd(self):
        return uconcat(self.arg1._pmNeither(), self.arg2._pmEnd())

    def _pmNeither(self):
        return uconcat(self.arg1._pmNeither(), self.arg2._pmNeither())

    def _containsT(self, T):
        if type(self) is T:
            return True
        return self.arg1._containsT(T) or self.arg2._containsT(T)

    def compress(self, uniqueSubtrees=dict()):
        for arg in ["arg1", "arg2"]:
            attr = getattr(self, arg)
            rep = repr(attr)

            if uniqueSubtrees.has_key(rep):
                setattr(self, arg, uniqueSubtrees[rep])
            else:
                attr.compress(uniqueSubtrees)
                uniqueSubtrees[repr(self)] = self

        super(uconcat, self).compress(uniqueSubtrees)

class udisj(reex.disj, uregexp):
    def __init__(self, arg1, arg2):
        super(udisj, self).__init__(arg1, arg2, sigma=None)

    def __deepcopy__(self, memo):
        cpy = udisj(copy.deepcopy(self.arg1), copy.deepcopy(self.arg2))
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        return "({0} + {1})".format(str(self.arg1), str(self.arg2))

    def pairGen(self):
        return self.arg1.pairGen().union(self.arg2.pairGen())

    def _backtrackMatch(self, word):
        for possibility in self.arg1._backtrackMatch(word):
            yield possibility

        for possibility in self.arg2._backtrackMatch(word):
            yield possibility

    def _dotFormat(self):
        return str(id(self)) + '[label="+", shape="circle", ordering="out"];\n' \
            + self.arg1._dotFormat() + self.arg2._dotFormat() \
            + str(id(self)) + " -> " + str(id(self.arg1)) + ";\n" \
            + str(id(self)) + " -> " + str(id(self.arg2)) + ";\n"

    def _pmBoth(self):
        return udisj(self.arg1._pmBoth(), self.arg2._pmBoth())

    def _pmStart(self):
        return udisj(self.arg1._pmStart(), self.arg2._pmStart())

    def _pmEnd(self):
        return udisj(self.arg1._pmEnd(), self.arg2._pmEnd())

    def _pmNeither(self):
        return udisj(self.arg1._pmNeither(), self.arg2._pmNeither())

    def _containsT(self, T):
        if type(self) is T:
            return True
        return self.arg1._containsT(T) or self.arg2._containsT(T)

    def compress(self, uniqueSubtrees=dict()):
        for arg in ["arg1", "arg2"]:
            attr = getattr(self, arg)
            rep = repr(attr)

            if uniqueSubtrees.has_key(rep):
                setattr(self, arg, uniqueSubtrees[rep])
            else:
                attr.compress(uniqueSubtrees)
                uniqueSubtrees[repr(self)] = self

        super(udisj, self).compress(uniqueSubtrees)

class ustar(reex.star, uregexp):
    def __init__(self, arg):
        super(ustar, self).__init__(arg, sigma=None)

    def __deepcopy__(self, memo):
        cpy = ustar(copy.deepcopy(self.arg))
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        return "{0}*".format(str(self.arg))

    def linearForm(self):
        arg_lf = self.arg.linearForm()
        lf = {}
        for head in arg_lf:
            lf[head] = set()
            for tail in arg_lf[head]:
                if tail.emptysetP():
                    lf[head].add(uemptyset())
                elif tail.epsilonP():
                    lf[head].add(self)
                else:
                    lf[head].add(uconcat(tail, self))
        return lf

    def partialDerivatives(self, sigma):
        arg_pdset = self.arg.partialDerivatives(sigma)
        pds = set()
        for pd in arg_pdset:
            if pd.emptysetP():
                pass # pds.add(uemptyset())
            elif pd.epsilonP():
                pds.add(self)
            else:
                pds.add(uconcat(pd, self))
        return pds

    def _memoLF(self):
        if hasattr(self, "_lf"):
            return
        self.arg._memoLF()
        self._lf = {}
        for head in self.arg._lf:
            pd_set = set()
            self._lf[head] = pd_set
            for tail in self.arg._lf[head]:
                if tail.emptysetP():
                    pd_set.add(uemptyset())
                elif tail.epsilonP():
                    pd_set.add(self)
                else:
                    pd_set.add(uconcat(tail, self))

    def __repr__(self):
        return "u" + super(ustar, self).__repr__()

    def pairGen(self):
        uncovered = self.arg.pairGen()
        covered = copy.copy(uncovered)
        cross = dict([x, copy.copy(uncovered)] for x in uncovered)

        for word in uncovered:
            word = [word]
            while True:
                last = word[-1]
                nxt = cross.get(last, None) # type: set|None
                if nxt is None:
                    covered.add(reduce(lambda p,c: p+c, word, u""))
                    break
                word.append(nxt.pop())
                if len(nxt) == 0:
                    del cross[last]

        return set([u""]).union(covered)

    def _backtrackMatch(self, word):
        for remaining in self.arg._backtrackMatch(word):
            for item in self._backtrackMatch(remaining):
                yield item

        yield word

    def _dotFormat(self):
        return str(id(self)) + '[label="*", shape="circle"];\n' \
            + self.arg._dotFormat() \
            + str(id(self)) + " -> " + str(id(self.arg)) + ";\n"

    def _pmBoth(self):
        if self._containsT(anchor):
            return udisj(self.arg._pmBoth(), uepsilon())
        else:
            return uconcat(uconcat(ustar(dotany()), ustar(self.arg._pmNeither())), ustar(dotany()))

    def _pmStart(self):
        if self._containsT(anchor):
            return udisj(self.arg._pmStart(), uepsilon())
        else:
            return uconcat(ustar(dotany()), ustar(self.arg._pmNeither()))

    def _pmEnd(self):
        if self._containsT(anchor):
            return udisj(self.arg._pmEnd(), uepsilon())
        else:
            return uconcat(ustar(self.arg._pmNeither()), ustar(dotany()))

    def _pmNeither(self):
        return ustar(self.arg._pmNeither())

    def _containsT(self, T):
        if type(self) is T:
            return True
        return self.arg._containsT(T)

    def compress(self, uniqueSubtrees=dict()):
        reprArg = repr(self.arg)
        if uniqueSubtrees.has_key(reprArg):
            self.arg = uniqueSubtrees[reprArg]
        else:
            self.arg.compress(uniqueSubtrees)
            uniqueSubtrees[repr(self)] = self

        super(ustar, self).compress(uniqueSubtrees)

class uoption(reex.option, uregexp):
    def __init__(self, arg):
        super(uoption, self).__init__(arg, sigma=None)

    def __deepcopy__(self, memo):
        cpy = uoption(copy.deepcopy(self.arg))
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        return "{0}?".format(str(self.arg))

    def __repr__(self):
        return "u" + super(uoption, self).__repr__()

    def pairGen(self):
        return set([u""]).union(self.arg.pairGen())

    def _backtrackMatch(self, word):
        yield word # skip optional vertex

        for possibility in self.arg._backtrackMatch(word):
            yield possibility

    def _dotFormat(self):
        return str(id(self)) + '[label="?", shape="circle"];\n' \
            + self.arg._dotFormat() \
            + str(id(self)) + " -> " + str(id(self.arg)) + ";\n"

    def _pmBoth(self):
        return udisj(self.arg._pmBoth(), uepsilon())

    def _pmStart(self):
        return udisj(self.arg._pmStart(), uepsilon())

    def _pmEnd(self):
        return udisj(self.arg._pmEnd(), uepsilon())

    def _pmNeither(self):
        return udisj(self.arg._pmNeither(), uepsilon())

    def _containsT(self, T):
        if type(self) is T:
            return True
        return self.arg._containsT(T)

    def compress(self, uniqueSubtrees=dict()):
        reprArg = repr(self.arg)
        if uniqueSubtrees.has_key(reprArg):
            self.arg = uniqueSubtrees[reprArg]
        else:
            self.arg.compress(uniqueSubtrees)
            uniqueSubtrees[repr(self)] = self

        super(uoption, self).compress(uniqueSubtrees)

class uepsilon(reex.epsilon, uregexp):
    def __init__(self):
        super(uepsilon, self).__init__(sigma=None)

    def __deepcopy__(self, memo):
        cpy = uepsilon()
        memo[id(self)] = cpy
        return cpy

    def pairGen(self):
        return set([u""])

    def _backtrackMatch(self, word):
        yield word

    def _dotFormat(self):
        return str(id(self)) + '[label="' + str(self) + '", shape="none"];\n'

    def _pmBoth(self):
        # @any* e @any*
        return uconcat(uconcat(ustar(dotany()), copy.deepcopy(self)), ustar(dotany()))

    def _pmStart(self):
        # @any* e
        return uconcat(ustar(dotany()), copy.deepcopy(self))

    def _pmEnd(self):
        # e @any*
        return uconcat(copy.deepcopy(self), ustar(dotany()))

    def _pmNeither(self):
        return copy.deepcopy(self)

    def _containsT(self, T):
        return type(self) is T

    def compress(self, uniqueSubtrees=dict()):
        if not uniqueSubtrees.has_key(repr(self)):
            uniqueSubtrees[repr(self)] = self
        super(uepsilon, self).compress(uniqueSubtrees)

class uemptyset(reex.emptyset, uregexp):
    def __init__(self):
        super(uemptyset, self).__init__(sigma=None)

    def __deepcopy__(self, memo):
        cpy = uemptyset()
        memo[id(self)] = cpy
        return cpy

    def pairGen(self):
        return set()

class uatom(reex.atom, uregexp):
    def __init__(self, val):
        super(uatom, self).__init__(val, sigma=None)
        assert type(val) is unicode, "uatoms strictly represent unicode type, not " + str(type(val))

    def __deepcopy__(self, memo):
        cpy = uatom(self.val)
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        printable = self.val.encode("utf-8")
        if printable in set("()[]+*?\\"):
            printable = "\\" + printable
        elif printable in set("\r\n\t"):
            printable = printable.encode("string-escape")

        if hasattr(self, "pos"):
            return "marked({0}, {1})".format(printable, self.pos)
        else:
            return printable

    def __repr__(self):
        return 'uatom(u"{0}")'.format(str(self))

    def derivative(self, sigma):
        return uepsilon() if sigma in self else uemptyset()

    def partialDerivatives(self, sigma):
        return set([uepsilon()] if sigma in self else [])

    def linearForm(self):
        return {self: {uepsilon()}}

    def __contains__(self, other):
        """Returns if the character other is listed (or included) in self"""
        return other == self.val

    def stringLength(self):
        return len(self.val)

    def next(self, current=None):
        """Finds the next character accepted by self after current
        :param unicode|None current: character to succeed
        :returns unicode: the next allowable character (ascending)
        """
        if current is None:
            return self.val
        elif current < self.val:
            return self.val
        else:
            return None

    def intersect(self, other):
        """Find the intersection of another regexp leaf instance object.
        :param other: can be an atom, epsilon, dotany, or chars
        :returns: the intersection between self and other
        :rtype: Union(uregexp, NoneType)
        """
        return self if other.derivative(self.val) == uepsilon() else None

    def random(self):
        """Retrieves a random symbol accepted by self
        :returns unicode: the symbol"""
        return self.val

    def nfaThompson(self):
        aut = fa.NFA()
        i = aut.addState()
        aut.addInitial(i)
        f = aut.addState()
        aut.addFinal(f)
        aut.addTransition(i, self, f)
        return aut

    def _nfaGlushkovStep(self, nfa, initial, final):
        try:
            target = nfa.addState(self)
        except common.DuplicateName:
            target = nfa.addState()

        for source in initial:
            nfa.addTransition(source, self, target)

        final.add(target)
        return initial, final

    def _memoLF(self):
        if not hasattr(self, "_lf"):
            self._lf = self.linearForm()

    def _nfaFollowEpsilonStep(self, conditions):
        nfa, initial, final = conditions
        nfa.addTransition(initial, self, final)

    def _marked(self, pos):
        pos += 1
        cpy = copy.deepcopy(self)
        cpy.pos = pos
        return cpy, pos

    def symbol(self):
        # ensure there is no pos attribute
        if hasattr(self, "pos"):
            return copy.deepcopy(self)
        return self

    def pairGen(self):
        return set([self.val])

    def _backtrackMatch(self, word):
        if len(word) > 0 and word[0] == self.val:
            yield word[1:]

    def _dotFormat(self):
        val = str(self) if self.val != " " else "SPACE"
        return str(id(self)) + '[label="' + val.encode("string-escape") + '", shape="none"];\n'

    def _pmBoth(self):
        return uconcat(uconcat(ustar(dotany()), copy.deepcopy(self)), ustar(dotany()))

    def _pmStart(self):
        return uconcat(ustar(dotany()), copy.deepcopy(self))

    def _pmEnd(self):
        return uconcat(copy.deepcopy(self), ustar(dotany()))

    def _pmNeither(self):
        return copy.deepcopy(self)

    def _containsT(self, T):
        return type(self) is T

    def compress(self, uniqueSubtrees=dict()):
        if not uniqueSubtrees.has_key(repr(self)):
            uniqueSubtrees[repr(self)] = self
        super(uatom, self).compress(uniqueSubtrees)

class chars(uatom):
    """A character class which can match any single character or a range of characters contained within it
    i.e., [abc] will match a, b, or c - and nothing else.
          [0-9] will match any symbol between 0 to 9 (inclusive)
          [^13579] will match anything of length 1 except odd digits
    """

    def __init__(self, symbols, neg=False):
        """Create a new chars class
        :param list<unicode> symbols: an iterable collection of symbols (single-character strings),
                        and 2-tuple ranges of symbols - i.e., ("a", "z")
        :param bool neg: if the chars class matches everything except the listed symbols
                         i.e., [^abc] would use the neg=True option
        """
        super(chars, self).__init__(u"") # self.val set later in __init__

        self.neg = neg
        self.val = u""
        esc = set("[]^-")
        val = lambda c: "\\" + c if c in esc else c
        if type(symbols) is RangeList:
            self.ranges = symbols
            for a, b in self.ranges:
                if a == b:
                    self.val += val(a)
                else:
                    self.val += val(a) + u"-" + val(b)
        else:
            self.ranges = RangeList(inc=lambda x: UniUtil.chr(UniUtil.ord(x)+1), dec=lambda x: UniUtil.chr(UniUtil.ord(x)-1))
            for s in symbols:
                if type(s) is tuple:
                    if s[0] == s[1]:
                        self.val += val(s[0])
                    else:
                        self.val += val(s[0]) + "-" + val(s[1])
                    self.ranges.add(s[0], s[1])
                elif type(s) is unicode:
                    self.val += val(s)
                    self.ranges.add(s)
                else:
                    raise TypeError("Unknown type 's', must be unicode/2-tuple of unicode's, not " + str(type(s)))

        self.val = "[" + ("^" if self.neg else "") + self.val + "]"

    def __deepcopy__(self, memo):
        cpy = chars(copy.deepcopy(self.ranges), neg=self.neg)
        memo[id(cpy)] = cpy
        return cpy

    def __copy__(self):
        return chars(self.ranges, neg=self.neg)

    def __repr__(self):
        return "chars(" + str(self) + ")"

    def __contains__(self, symbol):
        return self.ranges.indexOf(symbol) > -1

    def derivative(self, sigma):
        if self.neg:
            return uemptyset() if sigma in self else uepsilon()
        else:
            return uepsilon() if sigma in self else uemptyset()

    def next(self, current=None):
        if not self.neg:
            i = self.ranges.indexOf(current)
            if i is -1: # return the first character
                if len(self.ranges) >= 1:
                    return self.ranges[0][0]
                else:
                    return None
            rnge = self.ranges[i]
            nxt = UniUtil.chr(UniUtil.ord(current) + 1)
            if nxt <= rnge[1]: # incrmement by one in this range
                return nxt
            elif i + 1 < len(self.ranges): # go to next range
                return self.ranges[i + 1][0]
            else: # no ranges left
                return None

        else: # negative
            if current is None:
                current = UniUtil.chr(UniUtil.ord(u" ") - 1) # one less than first printable character

            nxt = UniUtil.chr(UniUtil.ord(current) + 1)
            i = self.ranges.search(nxt)
            while i <= len(self.ranges):
                if self.ranges.indexContains(i, nxt):
                    nxt = UniUtil.chr(UniUtil.ord(self.ranges[i][1]) + 1)
                    i += 1
                else:
                    return nxt
            return None

    def intersect(self, other):
        if type(other) is dotany:
            return self
        elif type(other) is uatom:
            if type(self.derivative(other.val)) is uepsilon:
                return other
            else:
                return None
        elif type(other) is chars:
            if self.neg == other.neg:
                intersect = self.ranges.intersection(other.ranges)
                if len(intersect) == 0:
                    return None
                else:
                    return chars(intersect, neg=self.neg)
            else:
                pos = None
                neg = None
                if self.neg:
                    pos = copy.deepcopy(other.ranges)
                    neg = self
                else:
                    pos = copy.deepcopy(self.ranges)
                    neg = other

                for a, b in neg.ranges:
                    pos.remove(a, b)

                if len(pos) == 0:
                    return None
                else:
                    return chars(pos)
        else:
            return None

    def random(self):
        randrange = WeightedRandomItem()
        for s, e in self.ranges:
            s = UniUtil.ord(s)
            e = UniUtil.ord(e)
            randrange.add(e - s + 1, (s, e))

        s, e = randrange.get()
        return UniUtil.chr(random.randint(s, e))

    def _backtrackMatch(self, word):
        if len(word) == 0:
            return

        if self.neg:
            if word[0] not in self:
                yield word[1:]
        else:
            if word[0] in self:
                yield word[1:]

    def pairGen(self):
        symbols = set()
        for s, e in self.ranges:
            symbols.add(s)
            symbols.add(UniUtil.chr((UniUtil.ord(s) + UniUtil.ord(e)) // 2))
            symbols.add(e)

        r = random.Random(1)
        # max sample size arbitrarily chosen as 5
        return set(r.sample(symbols, min(5, len(symbols))))

class dotany(uatom):
    """Class that represents the wildcard symbol that accepts everything."""
    def __init__(self):
        super(dotany, self).__init__(u"@any")

    def __deepcopy__(self, memo):
        cpy = dotany()
        memo[id(cpy)] = cpy
        return cpy

    __copy__ = __deepcopy__

    def __repr__(self):
        return "dotany()"

    def __eq__(self, other):
        return type(other) is dotany

    def __hash__(self):
        return hash(self.__str__())

    def derivative(self, _):
        return uepsilon()

    def __contains__(self, symbol):
        return len(symbol) == 1

    def next(self, current=None):
        if current is None:
            return u" " # the first printable character
        else:
            return UniUtil.chr(UniUtil.ord(current) + 1)

    def intersect(self, other):
        return None if type(other) is uepsilon else other

    def random(self):
        return UniUtil.chr(random.randint(32, 2**16 - 1))

    def _backtrackMatch(self, word):
        if len(word) > 0:
            yield word[1:]

    def pairGen(self):
        return set(u"a. S") # arbitrarily chosen characters... there is likely a better scheme

class anchor(uepsilon):
    """A class used to keep anchors but treat them functionally as @epsilon."""

    def __init__(self, label):
        assert label in set(["<ASTART>", "<AEND>"]), "Unrecognized anchor type"
        super(anchor, self).__init__()
        self.label = label

    def __deepcopy__(self, memo):
        cpy = anchor(self.label)
        memo[id(self)] = cpy
        return cpy

    def __str__(self):
        return self.label

    def __repr__(self):
        return "anchor('{0}')".format(self.label)

    def _pmBoth(self):
        if self.label == "<ASTART>":
            return uconcat(anchor("<ASTART>"), ustar(dotany()))
        else: # <AEND>
            return uconcat(ustar(dotany()), anchor("<AEND>"))

    def _pmStart(self):
        if self.label == "<ASTART>":
            return anchor("<ASTART>")
        else: # <AEND>
            raise errors.AnchorError(self, "Expected start of expression but found end")

    def _pmEnd(self):
        if self.label == "<AEND>":
            return anchor("<AEND>")
        else:
            raise errors.AnchorError(self, "Expected end of expression but found start")

    def _pmNeither(self):
        raise errors.AnchorError(self, "Neither anchor type allowed here")