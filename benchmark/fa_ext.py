from FAdo import fa, reex, graphs
from copy import copy, deepcopy
from builtins import chr

from reex_ext import chars, dotany

class InvariantNFA(fa.NFA):
    """A class that extends NFA to properly handle `chars` and `dotany`"""

    @staticmethod
    def lengthNFA(n, m=None):
        """Create an InvariantNFA which accepts all words of length >= n and <= m
        :arg int n: the minimum size of words (inclusive)
        :arg int m: the maximum size of words (inclusive). If None, defaults to n
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

    def __init__(self, nfa=None):
        """Create a NFA which can accept `reex_ext.any_sym` and `reex_ext.char_class` transitions.
        :arg nfa: the nfa which should use invariant functions
        ..note: there is no deep copying involved; deep copy the NFA before passing as an argument
                if the NFA must be preserved
        """
        super(InvariantNFA, self).__init__()
        if nfa is None: nfa = fa.NFA()

        self.Final = nfa.Final
        self.Initial = nfa.Initial
        self.Final = nfa.Final
        self.States = nfa.States

        self.delta = dict()
        self.chars_delta = dict()
        for p in nfa.delta:
            for t in nfa.delta[p]:
                for q in nfa.delta[p][t]:
                    self.addTransition(p, t, q)

    def dup(self):
        return deepcopy(self)

    def evalSymbol(self, stil, sym):
        res = set()
        for state in stil:
            out = self.delta.get(state, dict())
            if sym in out.keys():
                res.update(out[sym])
            if out.has_key(dotany()):
                res.update(out[dotany()])

            out = self.chars_delta.get(state, dict())
            for chrs, successors in out.items():
                if sym in chrs:
                    res.update(successors)
        epres = set()
        for nxt in res:
            epres.update(self.epsilonClosure(nxt))
        return epres

    def addTransition(self, stateFrom, label, stateTo):
        """Adds a new transition.

        :param int stateFrom: state index of departure
        :param label: symbol consumed (string, epsilon, char_class, any_sym)
        :param int stateTo: state index of arrival
        """
        delta = self.chars_delta if type(label) is chars else self.delta

        if stateFrom not in delta:
            delta[stateFrom] = dict([[label, set([stateTo])]])
        elif label not in delta[stateFrom]:
            delta[stateFrom][label] = set([stateTo])
        else:
            delta[stateFrom][label].add(stateTo)

    def delTransition(self, sti1, sym, sti2):
        delta = self.chars_delta if type(sym) is chars else self.delta
        if delta.has_key(sti1) and delta[sti1].has_key(sym):
            delta[sti1][sym].discard(sti2)

    def deleteStates(self, states):
        self.delta = self.transitionFunction()
        super(InvariantNFA, self).deleteStates(states)

        delta = self.delta
        self.delta = dict()
        self.chars_delta = dict()
        for p in delta:
            for t in delta[p]:
                for q in delta[p][t]:
                    self.addTransition(p, t, q)

    def product(self, other):
        """Product construction between self and other
        :arg other: Union(fa.NFA, InvariantNFA)
        :rtype: InvariantNFA
        """
        def intersect(a, b):
            """A helper function to find the intersection of two transitions a and b"""
            if a == b:
                return a
            if isinstance(a, chars):
                return a.intersect(b)
            if isinstance(b, chars):
                return b.intersect(a)
            return None

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

            s_next = self.transitionFunction(s_current).items()
            o_next = other.delta.get(o_current, dict()).items()
            o_next.extend(getattr(other, "chars_delta", dict()).get(o_current, dict()).items())

            for s_trans, s_states in s_next:
                for o_trans, o_states in o_next:
                    so_trans = intersect(s_trans, o_trans)
                    if so_trans is None: continue

                    destinations = set((s, o) for s in s_states for o in o_states)
                    for dest in destinations:
                        index = new.stateIndex(dest, autoCreate=True)
                        new.addTransition(so_index, so_trans, index)
                        notDone.append((dest[0], dest[1], index))

                        # check if final
                        if self.finalP(dest[0]) and other.finalP(dest[1]):
                            new.addFinal(index)

        return new

    def usefulStates(self, initial_states=None):
        """Set of states reacheable from the given initial state(s) that have a path to a final state.

        :param initial_states: set of initial states
        :type initial_states: set of int or list of int
        :returns: set of state indexes
        :rtype: set of int
        ..note: this function is only slightly modified from it's super definition"""
        if initial_states is None:
            initial_states = self.Initial
        useful = set([s for s in initial_states if s in self.Final])
        stack = list(initial_states)
        preceding = {}
        for i in stack:
            preceding[i] = []
        while stack:
            state = stack.pop()
            if state not in self.delta and state not in self.chars_delta:
                continue

            successors = set()
            for adj in self.transitionFunction(state).values():
                successors.update(adj)

            for adjacent in successors:
                is_useful = adjacent in useful
                if adjacent in self.Final or is_useful:
                    useful.add(state)
                    if not is_useful:
                        useful.add(adjacent)
                        preceding[adjacent] = []
                        stack.append(adjacent)
                    inpath_stack = [p for p in preceding[state] if p not in useful]
                    preceding[state] = []
                    while inpath_stack:
                        previous = inpath_stack.pop()
                        useful.add(previous)
                        inpath_stack += [p for p in preceding[previous] if p not in useful]
                        preceding[previous] = []
                    continue
                if adjacent not in preceding:
                    preceding[adjacent] = [state]
                    stack.append(adjacent)
                else:
                    preceding[adjacent].append(state)

        if not useful and self.Initial:
            useful.add(min(self.Initial))
        return useful

    def witness(self):
        """Witness of non emptyness
        :return: word
        :rtype: str"""
        done = set()
        notDone = set()
        for init in self.Initial:
            notDone.update((x, "") for x in self.epsilonClosure(init))

        while len(notDone) > 0:
            state, word = notDone.pop()
            if self.finalP(state) and len(word) > 0:
                return word
            if len(word) > 0:
                done.add(state)

            transitions = self.delta.get(state, dict()).items()
            transitions.extend(self.chars_delta.get(state, dict()).items())
            for transition, successors in transitions:
                if isinstance(transition, chars):
                    t = transition.next()
                elif transition == "@epsilon":
                    continue
                else:
                    t = str(transition)

                for successor in successors:
                    if successor not in done:
                        for ep in self.epsilonClosure(successor):
                            if ep not in done:
                                notDone.add((ep, word + t))
        return None

    def ewp(self):
        """Returns if the empty word is accepted by this automaton"""
        states = set()
        for init in self.Initial:
            states.update(self.epsilonClosure(init))
        return any(map(lambda s: self.finalP(s), states))

    def closeEpsilon(self, state):
        targets = self.epsilonClosure(state)
        isFinal = any(map(lambda s: self.finalP(s), targets))
        targets.remove(state)

        for target in targets:
            self.delTransition(state, "@epsilon", target)

        for target in targets:
            for trans, adj in self.transitionFunction(target).items():
                if trans != "@epsilon":
                    for a in adj:
                        self.addTransition(state, trans, a)

        if isFinal:
            self.addFinal(state)

    def succintTransitions(self):
        transitions = dict() # k,v => (from, to), {labels}

        delta = self.transitionFunction()
        for p in delta:
            for t in delta[p]:
                for q in delta[p][t]:
                    vertex = (p, q)
                    if vertex not in transitions:
                        transitions[vertex] = [t]
                    else:
                        transitions[vertex].append(t)

        l = []
        for vertex, labels in transitions.items():
            s = "%s" % graphs.graphvizTranslate(str(labels[0]))
            for c in labels[1:]:
                s += ", %s" % graphs.graphvizTranslate(str(c))
            l.append((str(self.States[vertex[0]]), s, str(self.States[vertex[1]])))
        return l

    def enumNFA(self):
        """NOTE: this is a differently intentioned method than the overridden enumNFA, but I think
        having access to EnumInvariantNFA is useful
        :returns: access to an enumeration object (with internal memoization for speed)
        :rtype: EnumInvariantNFA
        """
        cpy = deepcopy(self)
        cpy.elimEpsilon()
        cpy.trim()
        return EnumInvariantNFA(cpy)

    def transitionFunction(self, fromState=None):
        """Combines delta and chars_delta into one collection
        If fromState=None (default):
            {stateIndex: {transition: set(states)}}
        Otherwise:
            {transition: set(states)}
        """
        if fromState is not None:
            delta = copy(self.delta.get(fromState, dict()))
            for trans, successors in self.chars_delta.get(fromState, dict()).items():
                delta[trans] = successors
            return delta
        else:
            delta = copy(self.delta)
            for state in self.chars_delta:
                if not delta.has_key(state):
                    delta[state] = self.chars_delta[state]
                else:
                    for trans, succ in self.chars_delta[state].items():
                        delta[state][trans] = succ
            return delta


class EnumInvariantNFA(object): # should this inherit?
    """An object to enumerate an InvariantNFA efficiently.
    """
    def __init__(self, aut):
        """:arg aut: must be an e-free InvariantNFA
        """
        self.aut = aut
        self.lengthProductTrim = dict()

    def minWord(self, m):
        """Finds the minimal word of length m
        :arg m: the length of the desired word
        :rtype: string or None
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
        for c in current:
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

    def enum(self, lo=0, hi=float("inf")):
        """Enumerate all words such that each yielded word w has length |w| in [lo, hi]
        :arg int lo: the smallest length of a desired yielded word
        :arg int hi: the highest length of a desired yielded word
        :yields str: words in L(self.aut)
        """
        if lo == 0 and self.aut.ewp():
            yield ""

        for l in xrange(max(lo, 1), hi + 1):
            current = self.minWord(l)
            while current is not None:
                yield current
                current = self.nextWord(current)

    def _minTransition(self, infa, stateIndex, sym=None):
        """Finds the minimum transition from a state (optionally greater than sym)
        :arg int stateIndex: the index of the origin state
        :arg string sym: the lower bounding symbol (i.e., if sym="b", "c" will be accepted but "a" will not)
        :returns: (label, next state index) 2-tuple
        :rtype: (str, int)
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
        :arg int size: the size of the words to be accepted
        :returns: the trim InvariantNFA that only accepts words of length `size` in the
        language defined by self.aut
        :rtype: InvariantNFA
        """
        if not self.lengthProductTrim.has_key(size):
            nfa = self.aut.product(InvariantNFA.lengthNFA(size)).trim()
            self.lengthProductTrim[size] = nfa
        return self.lengthProductTrim[size]