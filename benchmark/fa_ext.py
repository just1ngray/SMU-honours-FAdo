from FAdo import fa, reex
from copy import deepcopy
from Queue import PriorityQueue
from random import randint

from reex_ext import dotany
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
        if m is None:
            m = n
        lengthNFA = InvariantNFA()
        lengthNFA.addInitial(lengthNFA.addState())
        if n == 0:
            lengthNFA.addFinal(0)

        for i in range(1, m + 1):
            lengthNFA.addState()
            lengthNFA.addTransition(i - 1, dotany(), i)
            if i >= n: lengthNFA.addFinal(i)
        return lengthNFA

    def __init__(self, nfa=None):
        """Create an InvariantNFA.
        :param fa.NFA nfa: the NFA which includes `chars` transitions
        ..note: there is no deep copying involved; deep copy the NFA before
                passing as an argument if the NFA must be preserved
        """
        super(InvariantNFA, self).__init__()
        if nfa is None:
            nfa = fa.NFA()

        self.Final = nfa.Final
        self.Initial = nfa.Initial
        self.Final = nfa.Final
        self.States = nfa.States
        self.delta = nfa.delta

    def dup(self):
        return deepcopy(self)

    def succintTransitions(self):
        transitions = super(InvariantNFA, self).succintTransitions()
        return list(map(lambda x: (x[0], "SPACE", x[2]) if x[1] == " " else x, transitions))

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
        notDone = set()

        # initial state(s)
        for s_initial in self.Initial:
            for o_initial in other.Initial:
                so_index = new.addState((s_initial, o_initial))
                new.addInitial(so_index)
                notDone.add((s_initial, o_initial, so_index))

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
                        notDone.add((dest[0], dest[1], index))

                        # check if final
                        if self.finalP(dest[0]) and other.finalP(dest[1]):
                            new.addFinal(index)
        return new

    def witness(self):
        """Generates the minimal word w accepted by self where |w|>0
        Inspired by Dijkstra's algorithm
        """
        cpy = self.dup()
        cpy.elimEpsilon()
        cpy.trim()

        toVisit = PriorityQueue()
        for s in cpy.Initial:
            toVisit.put_nowait((u"", s))

        # propogate
        while len(toVisit.queue) > 0:
            w, p = toVisit.get_nowait()

            if cpy.finalP(p) and len(w) > 0:
                return w

            for t in cpy.delta.get(p, dict()):
                for q in cpy.delta[p][t]:
                    word = w + t.next()
                    toVisit.put_nowait((word, q))
        return None

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
        cpy = self.dup()
        cpy.elimEpsilon()
        cpy.trim()
        return EnumInvariantNFA(cpy)

    def minTransition(self, state, label=None):
        """Find the minimum transition outgoing from state greater than label
        ..note: @epsilon is considered minimal and returned as u""

        :param int state: the current index
        :param unicode label: the non-inclusive lower-bound for the return value
        :returns Tuple(unicode, set<int>): the minimal transition > label outgoing from state
        """
        curMin = None
        successors = None
        for t, qs in self.delta.get(state, dict()).items():
            sigma = None
            if t == "@epsilon":
                sigma = u""
            else:
                sigma = t.next(label)
            if sigma is None:
                continue

            if curMin is None or (label < sigma and sigma < curMin):
                curMin = sigma
                successors = qs

        if curMin is None:
            return None, set()
        else:
            return curMin, successors


class EnumInvariantNFA(object):
    """An object to enumerate an InvariantNFA efficiently.
    ..note: InvariantNFA's can rely on the @any transition instead of an entire alphabet
    """
    def __init__(self, aut):
        """:param InvariantNFA aut: must be an e-free InvariantNFA"""
        self.aut = aut
        self.lengthProductTrim = dict()
        self.tmin = dict() # k: length, v: (k: index, minWord)

    def ewp(self):
        """:returns bool: if L(aut) includes the empty word"""
        return self.aut.ewp()

    def witness(self):
        """:returns unicode|NoneType: witness word of non-emptiness"""
        return self.aut.witness()

    def minWord(self, length, start=None):
        """Finds the minimal word of length in L(aut) and memoizes the value
        :param int length: the length of the desired word
        :param int|NoneType start: the index to get the minimal word from (defaults to Initial)
        :returns unicode|NoneType: the minimal word of in the length cross-section of L(aut)
        that starts at `start` and ends at any final state
        """
        if length == 0:
            return u"" if self.aut.ewp() else None
        nfa = self._sized(length)
        if len(nfa.Final) == 0:
            return None

        # nfa.Initial always has 1 initial state
        current = [(start, u"")] if start is not None else [(next(iter(nfa.Initial)), u"")]
        start = current[0][0]

        while len(current) > 0:
            candidates = []
            nxt = []
            for s, word in current:
                # check if final
                if nfa.finalP(s):
                    candidates.append(word)
                    continue

                # expect tmin to sometimes store memoized @ length,s
                memoized = self.tmin.get(length, dict()).get(s, None)
                if memoized is not None:
                    candidates.append(word + memoized)
                    continue

                # find the next transition to take
                t, states = nfa.minTransition(s)
                if t is None:
                    continue
                word += t

                # update nxt for next iteration
                minNxtWord = None if len(nxt) == 0 else nxt[0][1]
                if minNxtWord is None or word <= minNxtWord:
                    if word == minNxtWord: # tie for the minNxtWord
                        nxt.extend([(u, word) for u in states])
                    else: # new minWord found
                        nxt = [(u, word) for u in states]

            current = nxt
            if len(candidates) > 0:
                word = min(candidates)
                self.tmin[length][start] = word
                return word

        return None

    def nextWord(self, current):
        """Finds the next word in L(aut) with the same length of current according to radix order.
        :param unicode current: the current word to succeed
        :returns unicode|NoneType: the next word after current, or None if current is the last
        word in its cross-section
        """
        current = UniUtil.charlist(current)
        length = len(current)
        nfa = self._sized(length)
        stack = [nfa.Initial] # possible set of states after processing each letter in current

        for c in current[:-1]:
            stack.append(nfa.evalSymbol(stack[-1], c))

        while len(stack) > 0:
            states = stack.pop()
            lastSym = None if len(current) == 0 else current.pop() # to succeed

            for s in states:
                t, states = nfa.minTransition(s, lastSym)
                if t is None:
                    continue

                # find tmin from any in states
                minWord = None
                for st in states:
                    word = self.minWord(length, start=st)
                    if word is not None and (minWord is None or word < minWord):
                        minWord = word

                if minWord is not None:
                    return reduce(lambda p, c: p + c, current, u"") + t + minWord

        return None

    def enumCrossSection(self, n):
        """Yield words of length n in L(aut)
        :param int n: the length of the cross-section
        :yields unicode: words in n-cross-section of L(aut)
        """
        if n == 0:
            if self.aut.ewp():
                yield u""
            return

        current = self.minWord(n)
        while current is not None:
            yield current
            current = self.nextWord(current)

    def enum(self, lo=0, hi=float("inf")):
        """Enumerate all words such that each yielded word w has length |w| in [lo, hi]
        :param int lo: the smallest length of a desired yielded word
        :param int hi: the highest length of a desired yielded word
        :yields unicode: words in L(aut) where each word w has length in [lo, hi]
        """
        for l in range(lo, hi + 1):
            for word in self.enumCrossSection(l):
                yield word

    def randomWord(self, length):
        """Generates a random word in length's cross-section
        :param int length: the length of the desired word
        :returns unicode: the random word, or None if the cross-section is empty
        """
        nfa = self._sized(length)
        if length == 0:
            return u"" if self.ewp() else None
        elif len(nfa.Final) == 0:
            return None

        word = u""
        current = next(iter(nfa.Initial))
        while not nfa.finalP(current):
            transitions = nfa.delta[current]
            toTake = transitions.keys()[randint(0, len(transitions)-1)]
            word += toTake.random()
            successors = list(transitions[toTake])
            current = successors[randint(0, len(successors)-1)]
        return word


    def _sized(self, size):
        """Computes and memoizes the product of self.aut and lengthNFA of size `size`
        :param int size: the size of the words to be accepted
        :returns InvariantNFA: the trim InvariantNFA that only accepts words of length `size` in the
        language defined by self.aut
        """
        if not self.lengthProductTrim.has_key(size):
            nfa = self.aut.product(InvariantNFA.lengthNFA(size)).trim()
            self.lengthProductTrim[size] = nfa
            self.tmin[size] = dict()
        return self.lengthProductTrim[size]