from FAdo import fa, reex
from copy import deepcopy
from random import randint

import reex_ext
from util import WeightedRandomItem, Deque

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
            lengthNFA.addTransition(i - 1, reex_ext.dotany(), i)
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

    def acyclicP(self):
        """Rewritten since its implementation seems incorrect and error-prone
        :returns bool: if the InvariantNFA is acyclic

        ..see: Introduction to algorithms / Thomas H. Cormen, et al. - 3rd ed.
        """
        class CycleFound(Exception):
            def __init__(self, state):
                super(CycleFound, self).__init__("Cycle found originating in state " + str(state))

        color = dict()
        def colorOf(state):
            return color.get(state, "white")

        def dfsVisit(u):
            color[u] = "gray"
            for t in self.delta.get(u, dict()):
                for v in self.delta[u][t]:
                    col = colorOf(v)
                    if col == "white":
                        dfsVisit(v)
                    elif col == "gray":
                        raise CycleFound(u)
            color[u] = "black"

        try:
            for u in self.Initial:
                if colorOf(u) == "white":
                    dfsVisit(u)
            return True
        except CycleFound:
            return False

    def product(self, other):
        # both self and other must be e-free
        seq_self = self.dup().elimEpsilon()
        seq_other = other.dup().elimEpsilon()

        # note: s_... refers to `self` variables, and o_... refers to `other` variables
        new = InvariantNFA()
        notDone = set()

        # initial state(s)
        for s_initial in seq_self.Initial:
            for o_initial in seq_other.Initial:
                so_index = new.addState((s_initial, o_initial))
                new.addInitial(so_index)
                notDone.add((s_initial, o_initial, so_index))

        # propagate
        while len(notDone) > 0:
            s_current, o_current, so_index = notDone.pop()

            s_next = seq_self.delta.get(s_current, dict()).items()
            o_next = seq_other.delta.get(o_current, dict()).items()

            for s_trans, s_states in s_next:
                for o_trans, o_states in o_next:
                    # note: both s_trans and o_trans will be reex_ext#uatom instances
                    so_trans = s_trans.intersect(o_trans)
                    if so_trans is None:
                        continue

                    destinations = set((s, o) for s in s_states for o in o_states)
                    for dest in destinations:
                        index = new.stateIndex(dest, autoCreate=True)
                        new.addTransition(so_index, so_trans, index)
                        notDone.add((dest[0], dest[1], index))

                        # check if final
                        if seq_self.finalP(dest[0]) and seq_other.finalP(dest[1]):
                            new.addFinal(index)
        return new

    def witness(self):
        """Witness of non emptiness
        :returns unicode: word
        ..note: Not necessarily len > 0
                Not necessarily the smallest non-empty word! If this is desired use
                `self.enumNFA().minWord(None)`
        """
        done = set()
        notDone = set()
        pref = dict()
        for si in self.Initial:
            pref[si] = u""
            notDone.add(si)
        while notDone:
            si = notDone.pop()
            done.add(si)
            if si in self.Final:
                return pref[si]
            for t in self.delta.get(si, []):
                for so in self.delta[si][t]:
                    if so in done or so in notDone:
                        continue
                    pref[so] = pref[si] + (u"" if t == "@epsilon" else t.next())
                    notDone.add(so)
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

    def stateChildren(self, state, selfLoopCounts=False):
        children = set()
        for t in self.delta.get(state, dict()):
            children.update(self.delta[state][t])

        if not selfLoopCounts:
            children.discard(state)

        return children

class EnumInvariantNFA(object):
    """An object to enumerate an InvariantNFA efficiently.
    ..note: InvariantNFA's can rely on the @any transition instead of an entire alphabet
    """
    def __init__(self, aut):
        """:param InvariantNFA aut: must be an e-free InvariantNFA"""
        self.aut = aut
        self.lengthProductTrim = dict()
        self.tmin = dict() # {k: v}
                           # {word_length: {state_index: minWord}}
        self.memo_longest = -1
        self.memo_shortest = dict()

    def ewp(self):
        """:returns bool: if L(aut) includes the empty word"""
        return self.aut.ewp()

    def minWord(self, length, start=None):
        """Finds the minimal word of length in L(aut) and memoizes the value
        :param int|None length: the length of the desired word, None for the smallest radix word
        :param int|None start: the index to get the minimal word from (defaults to Initial)
        :returns unicode|None: the minimal word of in the length cross-section of L(aut)
        that starts at `start` and ends at any final state
        """
        if length is None:
            length = self.shortestWordLength()
        if length is None:
            return None

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
        current = list(current)
        length = len(current)
        nfa = self._sized(length)
        stack = Deque([nfa.Initial])

        for c in current[:-1]:
            stack.insert_right(nfa.evalSymbol(stack.peek_right(), c))

        while len(stack) > 0:
            possibleStates = stack.pop_right()
            lastSym = None if len(current) == 0 else current.pop() # to succeed

            for s in possibleStates:
                t, nxt = nfa.minTransition(s, lastSym)
                if t is None:
                    continue

                # find tmin from any in states
                minWord = None
                for u in nxt:
                    word = self.minWord(length, start=u)
                    if word < minWord or minWord is None:
                        minWord = word

                if minWord is not None:
                    return reduce(lambda p, c: p + c, current, u"") + t + minWord

        return None

    def enumCrossSection(self, lo, hi=None):
        """Yield words with length in [lo, hi] in L(aut)
        :param int lo:
        :param int|None hi: None if only enumerating the lo_th cross-section
        :yields unicode: words in the cross-section(s) of L(aut)
        """
        if hi is None:
            hi = lo

        n = lo
        while n <= hi:
            current = self.minWord(n)
            while current is not None:
                yield current
                current = self.nextWord(current)
            n += 1

    def enum(self, n):
        """Enumerate the first n words accepted by L(aut) in radix order
        :yields unicode: words in L(aut)
        """
        minlen = self.shortestWordLength()
        maxlen = self.longestWordLength()
        if minlen is None:
            return

        crosssection = self.enumCrossSection(minlen, maxlen)
        for _ in xrange(n):
            yield next(crosssection)

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
            rndtrans = WeightedRandomItem()
            transitions = nfa.delta[current]
            for trans, succ in transitions.items():
                rndtrans.add(len(succ), (trans, succ))

            trans, succ = rndtrans.get()
            word += trans.random()
            current = list(succ)[randint(0, len(succ) - 1)]
        return word

    def shortestWordLength(self, gte=0):
        """Finds the shortest word length greater than or equal to gte
        :returns int|None:
        """
        if gte in self.memo_shortest:
            return self.memo_shortest[gte]

        current = Deque(self.aut.Initial)
        visited = set()
        depth = 0
        while not current.isEmpty():
            next = Deque()
            for s in current:
                if depth >= gte and self.aut.finalP(s):
                    self.memo_shortest[gte] = depth
                    return depth
                visited.add(s)

                for child in self.aut.stateChildren(s):
                    if child not in visited:
                        next.insert_right(child)
            current = next
            depth += 1

        self.memo_shortest[gte] = None
        return None

    def longestWordLength(self):
        """Finds the length of the longest word accepted by L(aut)
        ..note: commonly inf
        """
        if self.memo_longest != -1:
            return self.memo_longest

        if not self.aut.acyclicP():
            self.memo_longest = float("inf")
            return float("inf")

        depth = dict([(x, 0) for x in self.aut.Initial])
        stack = Deque(self.aut.Initial)
        while len(stack) > 0:
            u = stack.pop_left() # consider all v's for transitions u --> v
            for successors in self.aut.delta.get(u, dict()).values():
                for v in successors:
                    if depth[u] + 1 > depth.get(v, -1):
                        depth[v] = depth[u] + 1
                        stack.insert_right(v)

        maxDepth = 0
        for s in self.aut.Final:
            maxDepth = max(maxDepth, depth.get(s, 0))

        self.memo_longest = maxDepth
        return maxDepth

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