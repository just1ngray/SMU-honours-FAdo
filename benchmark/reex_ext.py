from FAdo import reex, fa, common
import copy
from random import randint

from util import RangeList, UniUtil, WeightedRandomItem, pict
import fa_ext

class uregexp(reex.regexp):
    def wordDerivative(self, word):
        """Allows taking the word derivative of unicode strings with
        surrogate pairs.
        """
        d = self
        for sigma in UniUtil.charlist(word):
            d = d.derivative(sigma)
        return d

    def pairGen(self):
        """Generate the pairwise coverage test words
        :returns set<unicode>:

        L. Zheng et al., String Generating for Testing Regular Expressions
        The Computer Journal, Volume 63, Issue 1, January 2020, Pages 41-65
        https://doi.org/10.1093/comjnl/bxy137
        """
        raise NotImplementedError()

    def toInvariantNFA(self, method):
        """Convert self into an InvariantNFA using a construction method"""
        nfa = self.toNFA(method)
        return fa_ext.InvariantNFA(nfa)

class uconcat(reex.concat, uregexp):
    def __init__(self, arg1, arg2):
        super(uconcat, self).__init__(arg1, arg2, sigma=None)

    def __deepcopy__(self, memo):
        cpy = uconcat(copy.deepcopy(self.arg1), copy.deepcopy(self.arg2))
        memo[id(self)] = cpy
        return cpy

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

class udisj(reex.disj, uregexp):
    def __init__(self, arg1, arg2):
        super(udisj, self).__init__(arg1, arg2, sigma=None)

    def __deepcopy__(self, memo):
        cpy = udisj(copy.deepcopy(self.arg1), copy.deepcopy(self.arg2))
        memo[id(self)] = cpy
        return cpy

    def pairGen(self):
        return self.arg1.pairGen().union(self.arg2.pairGen())

class ustar(reex.star, uregexp):
    def __init__(self, arg):
        super(ustar, self).__init__(arg, sigma=None)

    def __deepcopy__(self, memo):
        cpy = ustar(copy.deepcopy(self.arg))
        memo[id(self)] = cpy
        return cpy

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

class uoption(reex.option, uregexp):
    def __init__(self, arg):
        super(uoption, self).__init__(arg, sigma=None)

    def __deepcopy__(self, memo):
        cpy = uoption(copy.deepcopy(self.arg))
        memo[id(self)] = cpy
        return cpy

    def __repr__(self):
        return "u" + super(uoption, self).__repr__()

    def pairGen(self):
        return set([u""]).union(self.arg.pairGen())

class uepsilon(reex.epsilon, uregexp):
    def __init__(self):
        super(uepsilon, self).__init__(sigma=None)

    def __deepcopy__(self, memo):
        cpy = uepsilon()
        memo[id(self)] = cpy
        return cpy

    def pairGen(self):
        return set([u""])

class uemptyset(reex.epsilon, uregexp):
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
        if hasattr(self, "pos"):
            return "marked({0}, {1})".format(self.val.encode("utf-8"), self.pos)
        else:
            return self.val.encode("utf-8")

    _strP = __str__

    def __repr__(self):
        return 'uatom(u"{0}")'.format(str(self))

    def derivative(self, sigma):
        return reex.epsilon() if sigma in self else reex.emptyset()

    def linearForm(self):
        return {self: {reex.epsilon()}}

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
        :rtype: Union(reex.regexp, NoneType)
        """
        return self if other.derivative(self.val) == reex.epsilon() else None

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

    def unmark(self):
        delattr(self, "pos")
        return self

    def symbol(self):
        return self

    def pairGen(self):
        return set([self.next()])

class chars(uatom):
    """A character class which can match any single character or a range of characters contained within it
    i.e., [abc] will match a, b, or c - and nothing else.
          [0-9] will match any symbol between 0 to 9 (inclusive)
          [^13579] will match anything of length 1 except odd digits
    ..note: Internally, characters are converted into their ordinal value to simplify merging intervals
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
        if type(symbols) is RangeList:
            self.ranges = symbols
            for a, b in self.ranges:
                if a == b:
                    self.val += a
                else:
                    self.val += a + u"-" + b
        else:
            self.ranges = RangeList(inc=lambda x: UniUtil.chr(UniUtil.ord(x)+1), dec=lambda x: UniUtil.chr(UniUtil.ord(x)-1))
            for s in symbols:
                if type(s) is tuple:
                    if s[0] == s[1]:
                        self.val += s[0]
                    else:
                        self.val += s[0] + "-" + s[1]
                    self.ranges.add(s[0], s[1])
                elif type(s) is unicode:
                    self.val += s
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
            return reex.emptyset() if sigma in self else reex.epsilon()
        else:
            return reex.epsilon() if sigma in self else reex.emptyset()

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
            if nxt < rnge[1]: # incrmement by one in this range
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
            if type(self.derivative(other.val)) is reex.epsilon:
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
        return UniUtil.chr(randint(s, e))

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
        return reex.epsilon()

    def __contains__(self, symbol):
        return len(symbol) == 1

    def next(self, current=None):
        if current is None:
            return u" " # the first printable character
        else:
            return UniUtil.chr(UniUtil.ord(current) + 1)

    def intersect(self, other):
        return None if type(other) is reex.epsilon else other

    def random(self):
        return UniUtil.chr(randint(32, 2**16 - 1))

class anchor(uregexp):
    """A class used temporarily in the conversion from programmer's string format
    to the equivalent strict mathematical version used in FAdo.
    """

    def __init__(self, label, sigma=None):
        super(anchor, self).__init__()
        self.label = label

    def __str__(self):
        return self.label

    _strP = __str__