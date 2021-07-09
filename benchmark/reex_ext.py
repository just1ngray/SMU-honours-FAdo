from FAdo import reex, fa, common
from lark import Lark, Transformer
from builtins import chr
import copy
import bisect


class chars(reex.regexp):
    """A character class which can match any single atom or a range of symbols
    contained within it
    i.e., [abc] will match a, b, or c - and nothing else.
          [0-9] will match any symbol between 0 to 9 (inclusive)
          [^13579] will match anything except odd digits
    """

    def __init__(self, symbols, neg=False):
        """Create a new chars class
        :param symbols: an iterable collection of symbols (single-character strings),
                        and 2-tuple ranges of symbols - i.e., ("a", "z")
        :param bool neg: if the chars class matches everything except the listed symbols
                         i.e., [^abc] would use the neg=True option
        """
        super(chars, self).__init__()

        self.neg = neg
        self.str = ""
        self.atoms = list()  # ordinals
        self.ranges = list() # ordinal ranges as 2-tuples
        for s in symbols:
            if type(s) is tuple:
                self.str += s[0] + "-" + s[1]
                self.ranges.append((ord(s[0]), ord(s[1])))
            elif type(s) is str or type(s) is unicode:
                self.str += s
                bisect.insort(self.atoms, ord(s))
            else:
                raise TypeError(str(s) + " must be str/2-tuple of str's, not " + str(type(s)))

        self.ranges = merge_intervals(self.ranges) # note: this function returns sorted ranges

    def __str__(self):
        return "[" + ("^" if self.neg else "") + self.str + "]"

    _strP = __str__

    def __repr__(self):
        return "chars(" + ("^" if self.neg else "") + self.str + ")"

    def __contains__(self, symbol):
        if type(symbol) is not int:
            if len(symbol) == 0:
                return False
            else:
                symbol = ord(str(symbol))
        if bisect_eq(self.atoms, symbol) > -1:
            return not self.neg
        for s, e in self.ranges:
            if s <= symbol and symbol <= e:
                return not self.neg
        return self.neg

    def derivative(self, sigma):
        """Overridden:
        Derivative of the regular expression in relation to the given symbol.
        :param sigma: an arbitrary symbol.
        :rtype: Union[reex.epsilon, reex.emptyset]
        """
        return reex.epsilon() if sigma in self else reex.emptyset()

    def treeLength(self):
        """Overridden:
        Number of nodes of the regular expression's syntactical tree.
        :rtype: integer
        """
        return 1

    def linearForm(self):
        """Overridden:
        Linear form of the regular expression.
        ..note: Used for nfaPD/nfaPDO constructions
        """
        return {self: {reex.epsilon()}}

    def nfaThompson(self):
        """Overridden:
        Epsilon-NFA constructed with Thompson's method that accepts the regular
        expression's language.
        :rtype: fa.NFA
        """
        aut = fa.NFA()
        i = aut.addState()
        aut.addInitial(i)
        f = aut.addState()
        aut.addFinal(f)
        aut.addTransition(i, self, f)
        return aut

    def _nfaGlushkovStep(self, nfa, initial, final):
        """Overridden:
        Append transitions onto initial to a distinct state accepting self
        :param fa.NFA nfa: the NFA to add to
        :param initial: an iterable collection of state indices
        :param set final: TODO: figure out
        :returns: ...
        :rtype: Tuple(..., ...)
        ..note: Used by nfaGlushkov construction
        """
        try:
            target = nfa.addState(self)
        except common.DuplicateName:
            target = nfa.addState()

        for source in initial:
            nfa.addTransition(source, self, target)

        final.add(target)
        return initial, final

    def next(self, current=None):
        """Finds the next symbol accepted by self after current
        :param str current: unicode/str/None character to succeed
        :returns: the next allowable character (ascending)
        :rtype: str
        ..note: if current is not in self, the first character is returned
        """
        if current is None or current not in self:
            a = None if len(self.atoms) < 1 else self.atoms[0]
            r = None if len(self.ranges) < 1 else self.ranges[0][0]
            m = min(filter(lambda x: x is not None, [a, r]))
            return None if m is None else chr(m)
        if type(current) is not int:
            current = ord(str(current))

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
                    return chr(n)

        else: # not neg
            for i in xrange(bisect_gt(self.ranges, current), len(self.ranges)):
                s, e = self.ranges[i]
                if current == e: # at the end of this range => pick the next lowest
                    nxt = None if i+1 >= len(self.ranges) else self.ranges[i + 1][0]
                    atom_index = bisect_gt(self.atoms, current)
                    if atom_index < len(self.atoms):
                        if nxt is None: nxt = self.atoms[atom_index]
                        else: nxt = min(nxt, self.atoms[atom_index])

                    return None if nxt is None else chr(nxt)

                elif s <= current and current < e:
                    return chr(current + 1)

            index = bisect_eq(self.atoms, current)
            if index > -1 and index + 1 < len(self.atoms):
                return chr(current + 1)
            else:
                return None

    def intersect(self, other):
        """Find the intersection of another regexp leaf.
        :param other: can be an atom, epsilon, any_sym, or chars
        :returns: the intersection between self and other
        :rtype: Union(reex.regexp, NoneType)
        """
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


class dotany(chars):
    """Class that represents the wildcard symbol that accepts everything.
    """
    def __init__(self, sigma=None):
        super(dotany, self).__init__([("0", "9"), ("A", "Z"), ("a", "z")])

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
        """Overridden:
        Derivative of the regular expression in relation to the given symbol.
        :param sigma: an arbitrary symbol.
        :rtype: reex.epsilon
        """
        return reex.epsilon()

    def linearForm(self):
        """Overridden:
        Linear form of the regular expression.
        ..note: Used for nfaPD/nfaPDO constructions
        """
        return {self: {reex.epsilon()}}

    def intersect(self, other):
        """Find the intersection of another regexp leaf.
        :param other: can be an atom, epsilon, any_sym, or chars
        :returns: the intersection between self and other
        :rtype: Union(reex.regexp, NoneType)
        """
        if type(other) is not reex.epsilon:
            return other
        else:
            return None


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
        return chr(item)
    elif type(item) is tuple:
        l = []
        for i in item:
            l.append(chr(i))
        return tuple(l)
    else:
        raise TypeError("Unrecognized type " + str(type(item)))

def bisect_eq(a, x):
    """Locate the leftmost *index* exactly equal to `x`
    https://docs.python.org/3/library/bisect.html
    :param list a: the list to search through
    :param x: the item to search for
    :returns: the index of the item x in a, or -1 if not found
    :rtype: int
    """
    i = bisect.bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i
    return -1

def bisect_gt(a, x):
    """Locate the leftmost *index* of an item greater than value `x`
    https://docs.python.org/3/library/bisect.html
    :param list a: the list to search through
    :param x: the item's value to get an index gt for
    :returns: the index of the item greater than x in a, or len(a) if not found
    :rtype: int
    """
    i = bisect.bisect_left(a, x)
    if i != len(a):
        return i
    return len(a)

def merge_intervals(intervals):
    """Merge overlapping numeric intervals
    https://gist.github.com/praveen97uma/8a4398dd42fb7b8497fb866190360998#file-merge-overlapping-intervals
    Modified to expect (mostly) sorted intervals
    """
    if not intervals:
        return []

    data = [float("-inf")]
    isSorted = True
    for interval in intervals:
        data.append((interval[0], 0))
        data.append((interval[1], 1))
        isSorted = isSorted and data[-3] <= data[-2] and data[-2] <= data[-1]

    data = data[1:]
    if not isSorted:
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