from FAdo import reex, fa, common
from lark import Lark, Transformer
from builtins import chr
import copy
import bisect

from .util import unicode_chr, unicode_ord, SortedList

class uatom(reex.atom):
    def __init__(self, val):
        super(uatom, self).__init__(val, sigma=None)
        assert type(val) is unicode, "uatoms strictly represent unicode type, not " + str(type(val))

    def __str__(self):
        return self.val.encode("utf-8")

    _strP = __str__

    def repr(self):
        return "uatom(" + str(self.val) + ")"

    def derivative(self, sigma):
        return reex.epsilon() if sigma in self else reex.emptyset()

    def linearForm(self):
        return {self: {reex.epsilon()}}

    def __contains__(self, other):
        """Returns if the character other is accepted by self"""
        return other == self.val

    def stringLength(self):
        return len(self.val)

    def next(self, current=None):
        """Finds the next character accepted by self after current
        :param str|unicode|None current: character to succeed
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
        t = type(other)
        if t is uatom:
            return self if other.val == self.val else None
        elif t is dotany:
            return self
        elif t is chars:
            return self if self.val in other else None
        elif t is reex.epsilon:
            return None
        else:
            raise Exception("Could not intersect: other object unrecognized! " + str(type(other)))

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
        self.atoms = SortedList() # ordinals
        self.ranges = SortedList(lambda x: x[0]) # ordinal ranges as 2-tuples
        for s in symbols:
            if type(s) is tuple:
                self.val += s[0] + "-" + s[1]
                self.ranges.add((unicode_ord(s[0]), unicode_ord(s[1])))
            elif type(s) is unicode:
                self.val += s
                self.atoms.add(unicode_ord(s))
            else:
                raise TypeError("Unknown type 's', must be unicode/2-tuple of unicode's, not " + str(type(s)))

        self.val = "[" + ("^" if self.neg else "") + self.val+ "]"

        # merge overlapping ranges TODO understand the algorithm behind this and maybe re-write
        self.ranges.set(merge_intervals(self.ranges))

    def __repr__(self):
        return "chars(" + self.val + ")"

    def __contains__(self, symbol):
        if type(symbol) is not int:
            if len(symbol) == 0:
                return False
            else:
                symbol = unicode_ord(symbol)

        if self.ranges[self.ranges.index_lte(symbol)][1] > symbol or self.atoms.index(symbol) > -1:
            return not self.neg

        return self.neg

    def next(self, current=None):
        if current is None or current not in self:
            a = None if len(self.atoms) < 1 else self.atoms[0]
            r = None if len(self.ranges) < 1 else self.ranges[0][0]
            m = min(filter(lambda x: x is not None, [a, r]))
            return None if m is None else unicode_chr(m)
        if type(current) is not int:
            current = unicode_ord(unicode(current))

        if self.neg:
            offset = 1
            while current + offset < 10000:
                n = current + offset
                if bisect_eq(self.atoms, n) != -1:
                    offset += 1
                    break
                inRange = False
                for s, e in self.ranges:
                    if s <= n and n <= e:
                        offset += e - n + 1
                        inRange = True
                        break
                if not inRange:
                    return unicode_chr(n)

        else: # not neg
            for i in xrange(bisect_gt(self.ranges, current), len(self.ranges)):
                s, e = self.ranges[i]
                if current == e: # at the end of this range => pick the next lowest
                    nxt = None if i+1 >= len(self.ranges) else self.ranges[i + 1][0]
                    atom_index = bisect_gt(self.atoms, current)
                    if atom_index < len(self.atoms):
                        if nxt is None: nxt = self.atoms[atom_index]
                        else: nxt = min(nxt, self.atoms[atom_index])

                    return None if nxt is None else unicode_chr(nxt)

                elif s <= current and current < e:
                    return unicode_chr(current + 1)

            index = bisect_eq(self.atoms, current)
            if index > -1 and index + 1 < len(self.atoms):
                return unicode_chr(current + 1)
            else:
                return None

    def intersect(self, other):
        if type(other) is dotany:
            return self
        if type(other) is reex.atom:
            if other.val in self: return other
            else: return None
        if type(other) is chars:
            ranges = set()
            atoms = set()
            if self.neg == other.neg:
                # s_ is for self; o_ is for other
                for s_s, s_e in self.ranges: # find overlap of ranges
                    for o_s, o_e in other.ranges:
                        if s_s > o_s:
                            break
                        s = max(s_s, o_s)
                        e = min(s_e, o_e)
                        if s < e:
                            ranges.add((s, e))
                        elif s == e:
                            atoms.add(s)

                for a in self.atoms:
                    if a in other:
                        included = False
                        for s, e in ranges:
                            if s <= a and a <= e:
                                included = True
                                break
                        if not included:
                            atoms.add(a)
                for a in other.atoms:
                    if a in self:
                        included = False
                        for s, e in ranges:
                            if s <= a and a <= e:
                                included = True
                                break
                        if not included:
                            atoms.add(a)

                return chars(map(to_chr, atoms.union(ranges)), neg=self.neg)
            else:
                # remove negative chars from the positive chars
                pos, neg = (other, self) if self.neg else (self, other)
                ranges = set(copy.copy(pos.ranges))
                for p_s, p_e in pos.ranges:
                    for n_s, n_e in neg.ranges:
                        if n_s <= p_s and p_e <= n_e:
                            ranges.discard((p_s, p_e))
                            break
                        for s, e in [(p_s, min(p_e, n_s - 1)), (max(n_e + 1, p_s), p_e)]:
                            if s > e:
                                ranges.discard((s, e))

                # split ranges while they contain neg.atoms neg.atoms
                cpy = copy.copy(neg.atoms)
                while len(cpy) > 0:
                    a = cpy.pop()
                    for s, e in ranges:
                        if s <= a and a <= e: # split the range around a
                            ranges.remove((s, e))
                            for r in [(s, a - 1), (a + 1, e)]:
                                if r[0] < r[1]:
                                    ranges.add(r)
                                elif r[0] == r[1]:
                                    atoms.add(r[0])
                            break

                for a in pos.atoms:
                    if a in neg:
                        atoms.add(a)

                return chars(map(to_chr, atoms.union(ranges)))
        return None


class dotany(uatom):
    """Class that represents the wildcard symbol that accepts everything.
    """
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

    def derivative(self, sigma):
        return reex.epsilon()

    def linearForm(self):
        return {self: {reex.epsilon()}}

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

    def treeLength(self):
        return 0

    def __str__(self):
        return self.label

    _strP = __str__


def to_chr(item):
    """Converts an integer or tuple of integers to a character or tuple of characters
    respectively
    """
    if type(item) is int:
        return unicode_chr(item)
    elif type(item) is tuple:
        l = []
        for i in item:
            l.append(unicode_chr(i))
        return tuple(l)
    else:
        raise TypeError("Unrecognized type " + str(type(item)))

def merge_intervals(intervals):
    """Merge overlapping numeric intervals
    https://gist.github.com/praveen97uma/8a4398dd42fb7b8497fb866190360998#file-merge-overlapping-intervals
    Modified to expect sorted intervals
    """
    if not intervals:
        return []

    data = []
    for interval in intervals:
        data.append((interval[0], 0))
        data.append((interval[1], 1))

    data.sort()

    merged = []
    stack = [data[0]]
    for i in xrange(1, len(data)):
        d = data[i]
        if d[1] == 0:
            # this is a lower bound, push this onto the stack
            stack.append(d)
        elif d[1] == 1:
            if stack:
                start = stack.pop()
            if len(stack) == 0:
                # we have found our merged interval
                merged.append((start[0], d[0]))
    return merged