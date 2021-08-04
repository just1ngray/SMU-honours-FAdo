from FAdo import fa, reex
from copy import deepcopy

from reex_ext import chars, dotany
from util import UniUtil

class InvariantNFA(fa.NFA):
    """A class that extends NFA to properly handle `chars` and `dotany`
    on an arbitrarily large alphabet without significant performance impacts.
    """

    @staticmethod
    def lengthNFA(n, m=None):
        """Create an InvariantNFA which accepts all words of length >= n and <= m
        :param int n: the minimum size of words (inclusive)
        :param int m: the maximum size of words (inclusive). If None, defaults to n
        :returns: the InvariantNFA which accepts any word of length s: n <= s <= m
        :rtype: InvariantNFA
        """
        if m is None: m = n
        lengthNFA = InvariantNFA()
        lengthNFA.addInitial(lengthNFA.addState())
        if n == 0: lengthNFA.addFinal(0)
        for i in range(1, m + 1):
            lengthNFA.addState()
            lengthNFA.addTransition(i - 1, dotany(), i)
            if i >= n: lengthNFA.addFinal(i)
        return lengthNFA

    def __init__(self, nfa=fa.NFA()):
        """Create an InvariantNFA.
        :param fa.NFA nfa: the NFA which includes `chars` transitions
        ..note: there is no deep copying involved; deep copy the NFA before
                passing as an argument if the NFA must be preserved
        """
        super(InvariantNFA, self).__init__()
        self.Final = nfa.Final
        self.Initial = nfa.Initial
        self.Final = nfa.Final
        self.States = nfa.States
        self.delta = nfa.delta

    def dup(self):
        return deepcopy(self)

    def evalWordP(self, word):
        ilist = self.epsilonClosure(self.Initial)
        for c in UniUtil.charlist(word):
            ilist = self.evalSymbol(ilist, c)
            if not ilist:
                return False
        for f in self.Final:
            if f in ilist:
                return True
        return False

    def evalSymbol(self, stil, sym):
        res = set()
        for p in stil:
            for t, qs in self.delta.get(p, dict()).items():
                if t == "@epsilon":
                    continue

                if type(t.derivative(sym)) == reex.epsilon:
                    res.update(qs)

        epres = set()
        for nxt in res:
            epres.update(self.epsilonClosure(nxt))
        return epres

    def addTransition(self, stateFrom, label, stateTo):
        if type(label) is str and label != "@epsilon":
            raise TypeError("InvariantNFA's use object transitions from 'reex_ext.py'")
        super(InvariantNFA, self).addTransition(stateFrom, label, stateTo)

    def delTransition(self, sti1, sym, sti2):
        if self.delta.has_key(sti1) and self.delta[sti1].has_key(sym):
            self.delta[sti1][sym].discard(sti2)

            if len(self.delta[sti1][sym]) == 0:
                if len(self.delta[sti1]) == 0:
                    del self.delta[sti1]
                else:
                    del self.delta[sti1][sym]

    def product(self, other):
        # note: s_... refers to `self` variables, and o_... refers to `other` variables
        new = InvariantNFA()
        notDone = []

        # initial state(s)
        for s_initial in self.Initial:
            for o_initial in other.Initial:
                index = new.addState((s_initial, o_initial))
                new.addInitial(index)
                notDone.append((s_initial, o_initial, index))

        # propagate
        while len(notDone) > 0:
            s_current, o_current, so_index = notDone.pop()

            s_next = self.delta.get(s_current, dict()).items()
            o_next = other.delta.get(o_current, dict()).items()

            for s_trans, s_states in s_next:
                for o_trans, o_states in o_next:
                    so_trans = None
                    if s_trans == o_trans:
                        so_trans = s_trans
                    elif s_trans != "@epsilon" and o_trans != "@epsilon":
                        so_trans = s_trans.intersect(o_trans)

                    if so_trans is None:
                        continue

                    destinations = set((s, o) for s in s_states for o in o_states)
                    for dest in destinations:
                        index = new.stateIndex(dest, autoCreate=True)
                        new.addTransition(so_index, so_trans, index)
                        notDone.append((dest[0], dest[1], index))

                        # check if final
                        if self.finalP(dest[0]) and other.finalP(dest[1]):
                            new.addFinal(index)
        return new

    def witness(self): # TODO: not working for nfaThompson
        notDone = list()
        pref = dict()
        for si in self.Initial:
            pref[si] = u""
            notDone.append(si)

        minWord = None
        while notDone:
            si = notDone.pop()
            if si in self.Final and len(pref[si]) > 0:
                if minWord is None:
                    minWord = pref[si]
                else:
                    minWord = min(minWord, pref[si])

            for t in self.delta.get(si, dict()):
                for so in self.delta[si][t]:
                    if so in notDone:
                        continue

                    word = pref[si] + ("" if t == "@epsilon" else t.next())
                    if so not in pref or pref[so] == "" or word < pref[so]:
                        pref[so] = word
                        notDone.append(so)
        return minWord






    def ewp(self):
        """Returns if the empty word is accepted by this automaton"""
        for i in self.Initial:
            for e in self.epsilonClosure(i):
                if self.finalP(e):
                    return True
        return False

    def closeEpsilon(self, state):
        targets = self.epsilonClosure(state)
        isFinal = any(map(lambda s: self.finalP(s), targets))
        targets.remove(state)

        for target in targets:
            self.delTransition(state, "@epsilon", target)

        for target in targets:
            for trans, adj in self.delta.get(target, dict()).items():
                if trans != "@epsilon":
                    for a in adj:
                        self.addTransition(state, trans, a)
        if isFinal:
            self.addFinal(state)

    def enumNFA(self):
        """Overridden: (gives access to the enumeration instance instead of returning
        words directly)
        :returns EnumInvariantNFA: access to an enumeration object (with internal memoization for speed)
        """
        cpy = deepcopy(self)
        cpy.elimEpsilon()
        cpy.trim()
        return EnumInvariantNFA(cpy)


class EnumInvariantNFA(object):
    """An object to enumerate an InvariantNFA efficiently.
    """
    def __init__(self, aut):
        """:param aut: must be an e-free InvariantNFA
        """
        self.aut = aut
        self.lengthProductTrim = dict()

    def minWord(self, m):
        """Finds the minimal word of length m
        :param int m: the length of the desired word
        :returns: the minimal word of length m
        :rtype: str|NoneType
        """
        if m == 0: return "" if self.aut.ewp() else None
        nfa = self._sized(m)

        current = next(iter(nfa.Initial))
        word = ""
        for _ in xrange(0, m):
            t, s = self._minTransition(nfa, current)
            if t is None: return None
            word += t
            current = s

        return word

    def nextWord(self, current):
        """Given an word, returns next word in the the nth cross-section of L(aut)
        according to the radix order
        :param str w: non-empty word
        :rtype: str or None
        :returns: the next word in radix order if it exists
        """
        nfa = self._sized(len(current))

        stack = [nfa.Initial]
        for c in current: # TODO: add cacheing to improve speed
            stack.append(nfa.evalSymbol(stack[-1], c))

        # "backtrack"
        while len(stack) > 0:
            numBacktracked = len(current) - len(stack) + 2
            lastSym = current[1 - numBacktracked]
            baseword = current[:1 - numBacktracked]
            states = stack.pop()

            minT = None
            minS = None
            for state in states:
                t, s = self._minTransition(nfa, state, lastSym)
                if t is not None and (minT is None or t < minT):
                    minT = t
                    minS = s
            if minT is not None:
                # "forward track"
                while not nfa.finalP(minS):
                    t, minS = self._minTransition(nfa, minS)
                    minT += t
                return baseword + minT

        return None

    def enumCrossSection(self, n):
        """Enumerates the nth cross-section of L(A)
        :param int n: nonnegative integer representing the size of yielded words
        :yields str: words in the nth cross-section of L(A)
        """
        if n == 0:
            if self.aut.ewp():
                yield ""
            return

        current = self.minWord(n)
        while current is not None:
            yield current
            current = self.nextWord(current)

    def enum(self, lo=0, hi=float("inf")):
        """Enumerate all words such that each yielded word w has length |w| in [lo, hi]
        :param int lo: the smallest length of a desired yielded word
        :param int hi: the highest length of a desired yielded word
        :yields str: words in L(self.aut)
        """
        for l in xrange(lo, hi + 1):
            for word in self.enumCrossSection(l):
                yield word

    def _minTransition(self, infa, stateIndex, sym=None):
        """Finds the minimum transition from a state (optionally greater than sym)
        :param int stateIndex: the index of the origin state
        :param string sym: the lower bounding symbol (i.e., if sym="b", "c" will be accepted but "a" will not)
        :returns: (label, next state index) 2-tuple
        :rtype: Tuple(str, int)
        """
        minNextLabel = None
        minNextState = None
        successors = infa.transitionFunction(stateIndex).items()

        for transition, nextStates in successors:
            if len(nextStates) == 0:
                raise Exception("TODO: remove if not necessary")
            if isinstance(transition, chars):
                nextSym = transition.next(sym)
                if nextSym is not None and (nextSym < minNextLabel or minNextLabel is None):
                    minNextLabel = nextSym
                    minNextState = next(iter(nextStates))
            else:
                if sym < str(transition) and (str(transition) < minNextLabel or minNextLabel is None):
                    minNextLabel = str(transition)
                    minNextState = next(iter(nextStates))

        return (None, None) if minNextState is None else (minNextLabel, minNextState)

    def _sized(self, size):
        """Computes and memoizes the product of self.aut and lengthNFA of size `size`
        :param int size: the size of the words to be accepted
        :returns: the trim InvariantNFA that only accepts words of length `size` in the
        language defined by self.aut
        :rtype: InvariantNFA
        """
        if not self.lengthProductTrim.has_key(size):
            nfa = self.aut.product(InvariantNFA.lengthNFA(size)).trim()
            self.lengthProductTrim[size] = nfa
        return self.lengthProductTrim[size]