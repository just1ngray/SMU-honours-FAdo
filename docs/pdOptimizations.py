"""RUN THIS TEST FROM PROJECT ROOT USING
    $ python2 -m docs.pdOptimizations
    $ sudo nice -n -20 python2 -m docs.pdOptimizations

This test will test the performance of several partial derivative algorithms.
Each algorithm is given a brief description in its function declaration.

The results of this experiment can be re-created by running this program, or
viewed in the "docs/pd_results_saved.rtf" file.
"""
import copy
import os
import psutil
import time
from timeit import timeit
from benchmark.convert import Converter
from benchmark.benchmark import Benchmarker
from benchmark.fa_ext import InvariantNFA
from benchmark.reex_ext import uatom, uepsilon
from benchmark.util import DBWrapper, Deque

OUTPUT_FILE = "docs/pd_results.txt" # where the results will be posted
WIDTH = 16                          # the column width (# chars) in the output file
PROC_WORKERS = 2                    # number of worker processes to evaluate expressions (keep sufficiently low to avoid throttling)
NUM_EXPRESSIONS = 50                # number of expressions to sample and test against the algorithms
ITERATIONS_PER_METHOD = 2           # number of times each method will test each expression, then minimum time is taken

benchmarker = Benchmarker()
converter = Converter()
print "\n"*25

def naive(re, word):
    """Simple partial derivative evaluation without any memoization.
    The regexp tree is added directly to the set."""
    current = set([re])
    for sigma in word:
        nxt = set()
        for c in current:
            nxt.update(c.partialDerivatives(sigma))
        current = nxt
    for c in current:
        if c.ewp():
            return True
    return False

def memo1(re, word):
    """Naive algorithm improved to save every computed partial derivative
    so it will never be computed again."""
    memo = dict() # re: {str.sigma: set(pds)}
    current = set([re])
    for sigma in word:
        nxt = set()
        for pd in current:
            if not memo.has_key(pd):
                memo[pd] = dict([(sigma, pd.partialDerivatives(sigma))])
            elif not memo[pd].has_key(sigma):
                memo[pd][sigma] = pd.partialDerivatives(sigma)
            nxt.update(memo[pd][sigma])
        current = nxt
    for pd in current:
        if pd.ewp():
            return True
    return False

def memo2(re, word):
    """Partial derivatives are memoized and indexed by their str representation.
    Note that the successors are saved as their tree form."""
    memo = dict() # str(re): {str.sigma: set(pds)}
    current = set([re])
    for sigma in word:
        nxt = set()
        for pd in current:
            pdstr = str(pd)
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, pd.partialDerivatives(sigma))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = pd.partialDerivatives(sigma)
            nxt.update(memo[pdstr][sigma])
        current = nxt
    for pd in current:
        if pd.ewp():
            return True
    return False

def memo2rpn(re, word):
    """Partial derivatives are memoized and indexed by their rpn representation.
    RPN: reverse polish notation (this yields a shorter string than str(re))
    Note that the successors are saved as their tree form."""
    memo = dict() # re.rpn(): {str.sigma: set(pds)}
    current = set([re])
    for sigma in word:
        nxt = set()
        for pd in current:
            pdstr = pd.rpn()
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, pd.partialDerivatives(sigma))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = pd.partialDerivatives(sigma)
            nxt.update(memo[pdstr][sigma])
        current = nxt
    for pd in current:
        if pd.ewp():
            return True
    return False

def memo3(re, word):
    """Similar to memo2 in that we are memoizing partial derivatives and indexing them by
    their str representation. However, we change the 'current' structure into a duplicate-allowing
    Deque to save on insertion time into the set. We add a check on the length of 'current' to
    ensure it remains <= alphabet length of the root of the tree."""
    alphabetLength = re.alphabeticLength()
    memo = dict() # str(re): {str.sigma: set(pds)}
    current = Deque([re])
    for sigma in word:
        nxt = Deque()
        for pd in current:
            pdstr = str(pd)
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, pd.partialDerivatives(sigma))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = pd.partialDerivatives(sigma)
            for pd_successor in memo[pdstr][sigma]:
                nxt.insert_right(pd_successor)
        if len(nxt) > alphabetLength:
            current = set(nxt)
        else:
            current = nxt
    for pd in current:
        if pd.ewp():
            return True
    return False

def memo4(re, word):
    """Partial derivatives are always identified by their str representation. This is a linear time
    operation and only has to be done once per subtree in this algorithm. All comparisons are indexed
    using this saved string instead of the tree directly."""
    memo = dict() # str(re): {str.sigma: dict(str(pd), pd)}
    current = dict([(str(re), re)])
    for sigma in word:
        nxt = dict()
        for pdstr, pd in current.items():
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, dict([(str(x), x) for x in pd.partialDerivatives(sigma)]))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = dict([(str(x), x) for x in pd.partialDerivatives(sigma)])
            nxt.update(memo[pdstr][sigma])
        current = nxt
    for pd in current.values():
        if pd.ewp():
            return True
    return False

def memo4rpn(re, word):
    """Same methodology as memo4, but uses the more succinct rpn representation of the regexp tree
    than the str representation. This results in a smaller hashing cost and therefore faster
    insertions and lookups."""
    memo = dict() # re.rpn(): {str.sigma: dict(pd.rpn(), pd)}
    current = dict([(re.rpn(), re)])
    for sigma in word:
        nxt = dict()
        for pdstr, pd in current.items():
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, dict([(x.rpn(), x) for x in pd.partialDerivatives(sigma)]))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = dict([(x.rpn(), x) for x in pd.partialDerivatives(sigma)])
            nxt.update(memo[pdstr][sigma])
        current = nxt
    for pd in current.values():
        if pd.ewp():
            return True
    return False

def memo4rpn2(re, word):
    """Same methodology as memo4rpn, but rpn's are saved as attributes of the class."""
    memo = dict() # re.rpn(): {str.sigma: dict(pd.rpn(), pd)}
    current = dict([(re._memoRPN(), re)])
    for sigma in word:
        nxt = dict()
        for pdstr, pd in current.items():
            if not memo.has_key(pdstr):
                memo[pdstr] = dict([(sigma, dict([(x._memoRPN(), x) for x in pd.partialDerivatives(sigma)]))])
            elif not memo[pdstr].has_key(sigma):
                memo[pdstr][sigma] = dict([(x._memoRPN(), x) for x in pd.partialDerivatives(sigma)])
            nxt.update(memo[pdstr][sigma])
        current = nxt
    re._delAttr("_rpn") # off-tree _rpn's are automatically gc'd
    for pd in current.values():
        if pd.ewp():
            return True
    return False

def partialNFA(re, word):
    """Inspired by the nfaPDO algorithm, but only creates the states/transitions which are used
    by the given word. The list of currently occupied states are kept as their tree forms."""
    nfa = InvariantNFA()
    index = nfa.addState(re)
    nfa.addInitial(index)
    added_states = dict([(re, index)])
    current = set([(re, index)])
    for sigma in unicode(word):
        sigma = uatom(sigma)
        nextDerivatives = set()
        for re, index in current:
            re._memoLF()
            for transition in re._lf:
                if type(transition.derivative(sigma.val)) is not uepsilon:
                    continue
                for pd in re._lf[transition]:
                    pd_index = None
                    if pd in added_states:
                        pd_index = added_states[pd]
                        nextDerivatives.add((pd, pd_index))
                    else:
                        pd_index = nfa.addState(pd)
                        added_states[pd] = pd_index
                        nextDerivatives.add((pd, pd_index))
                    nfa.addTransition(index, transition, pd_index)
        current = nextDerivatives
    for re in added_states:
        if re.ewp():
            nfa.addFinal(added_states[re])
    answer = nfa.evalWordP(word)
    re._delAttr("_lf")
    return answer

def partialNFA2(re, word):
    """Like the partialNFA algorithm, but the currently occupied states are saved by their index."""
    nfa = InvariantNFA()
    index = nfa.addState(re)
    nfa.addInitial(index)
    currentIndicies = set([index])
    for sigma in unicode(word):
        nextIndices = set()
        for index in currentIndicies:
            re = nfa.States[index]
            re._memoLF()
            for transition in re._lf:
                if type(transition.derivative(sigma)) is not uepsilon:
                    continue
                for pd in re._lf[transition]:
                    pd_index = nfa.stateIndex(pd, autoCreate=True)
                    nextIndices.add(pd_index)
                    nfa.addTransition(index, transition, pd_index)
        currentIndicies = nextIndices
    for re in nfa.States:
        if re.ewp():
            nfa.addFinal(nfa.stateIndex(re))
    answer = nfa.evalWordP(word)
    re._delAttr("_lf")
    return answer

def construct(method):
    """Perform the given nfa construction, then evaluate on the word"""
    def f(re, word):
        return re.toInvariantNFA(method).evalWordP(word)
    f.__name__ = method
    return f

# SETUP the methods to evaluate and randomly sample some valid mathematized expressions to test
methods = [construct("nfaPDK"), construct("nfaPDDAG"), construct("nfaPDO")]
expressions = map(lambda row: row[0].decode("utf-8"), \
    DBWrapper().selectall("SELECT re_math FROM in_tests ORDER BY random() LIMIT ?;", [NUM_EXPRESSIONS]))


def handleExpression(re_math):
    """Generates words, and measures execution speed of every method in 'methods' against this list.
    Writes the result to the appropriate file in a standard format."""
    def timeAll(re, method, acc, rej):
        for w in acc:
            assert method(re, w) == True, w + " should have been accepted by " + str(re) + " in " + method.__name__
        for w in rej:
            assert method(re, w) == False

    re = converter.math(re_math, partialMatch=True)
    print "\tgenerating words for", re_math
    acc, rej = benchmarker.generateWords(re_math)
    output = ""
    for method in methods:
        try:
            print "\trunning method", method.__name__, re_math
            times = []
            for _ in range(ITERATIONS_PER_METHOD):
                times.append(timeit(lambda: timeAll(re, method, acc, rej), number=1))
            output += str(min(times)).rjust(WIDTH)
        except AssertionError as e:
            output += e.message

    f = open(OUTPUT_FILE, "a")
    f.write(output + "\t|\t" + str(len(acc)+len(rej)) + " - " + str(len(str(re))) + " - " + str(re) + "\n")
    f.close()


# DRIVE THE PROGRAM
f = None
workers = set()
try:
    f = open(OUTPUT_FILE, "w")
    for method in methods:
        f.write(method.__name__.rjust(WIDTH))
    f.write("\n")
    f.close()

    while len(expressions) > 0 or len(workers) > 0:
        while len(workers) >= PROC_WORKERS:
            for pid in copy.copy(workers):
                os.waitpid(pid, os.WNOHANG)
                if not psutil.pid_exists(pid):
                    workers.discard(pid)
            time.sleep(1)

        re_math = expressions.pop()
        print "Testing", re_math
        pid = os.fork()
        if pid == 0:
            handleExpression(re_math)
            exit(0)
        else:
            workers.add(pid)
except KeyboardInterrupt:
    for pid in workers:
        os.kill(pid, 9)
except:
    raise
finally:
    if type(f) is not None:
        f.close()
