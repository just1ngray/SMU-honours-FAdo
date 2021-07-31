from FAdo import reex, fa, common
import copy

from .util import unicode_chr, unicode_ord, RangeList

class uatom(reex.atom):
    def __init__(self, val):
        super(uatom, self).__init__(val, sigma=None)
        assert type(val) is unicode, "uatoms strictly represent unicode type, not " + str(type(val))

    def __str__(self):
        return self.val.encode("utf-8")

    _strP = __str__

    def repr(self):
        return 'uatom(u"' + str(self.val) + '")'

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
        ..note: if current is not accepted by self, the "first" character is returned
        """
        return None if current in self else self.val

    def intersect(self, other):
        """Find the intersection of another regexp leaf instance object.
        :param other: can be an atom, epsilon, dotany, or chars
        :returns: the intersection between self and other
        :rtype: Union(reex.regexp, NoneType)
        """
        return self if other.derivative(self.val) == reex.epsilon() else None

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
            self.ranges = RangeList(inc=lambda x: unicode_chr(unicode_ord(x)+1), dec=lambda x: unicode_chr(unicode_ord(x)-1))
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
            nxt = unicode_chr(unicode_ord(current) + 1)
            if nxt < rnge[1]: # incrmement by one in this range
                return nxt
            elif i + 1 < len(self.ranges): # go to next range
                return self.ranges[i + 1][0]
            else: # no ranges left
                return None

        else: # negative
            if current is None:
                current = unicode_chr(unicode_ord(u" ") - 1) # one less than first printable character

            nxt = unicode_chr(unicode_ord(current) + 1)
            i = self.ranges.search(nxt)
            while i <= len(self.ranges):
                if self.ranges.indexContains(i, nxt):
                    nxt = unicode_chr(unicode_ord(self.ranges[i][1]) + 1)
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
                pos = copy.copy(self.ranges)
                neg = other
                if self.neg:
                    pos = copy.copy(other.ranges)
                    neg = self

                for a, b in neg.ranges:
                    pos.remove(a, b)

                if len(pos) == 0:
                    return None
                else:
                    return chars(pos)
        else:
            return None


class dotany(uatom):
    """Class that represents the wildcard symbol that accepts everything."""
    def __init__(self):
        super(dotany, self).__init__(u" ")

    def __repr__(self):
        return "dotany()"

    def __str__(self):
        return "@any"

    _strP = __str__

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
            return unicode_chr(unicode_ord(current) + 1)

    def intersect(self, other):
        return None if type(other) is reex.epsilon else other


class anchor(reex.regexp):
    """A class used temporarily in the conversion from programmer's string format
    to the equivalent strict mathematical version used in FAdo.
    """

    def __init__(self, label, sigma=None):
        super(anchor, self).__init__()
        self.label = label

    def __str__(self):
        return self.label

    _strP = __str__