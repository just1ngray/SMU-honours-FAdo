from __future__ import print_function
import matplotlib
matplotlib.use('WebAgg') # TkAgg work well for native display
import matplotlib.pyplot as plt
import sys
import os
import psutil
import time
import timeit
import random
import gc
import datetime

from util import DBWrapper, Deque, parseIntSafe # ConsoleOverwrite
from convert import Converter

WORD_SAMPLE_SIZE = 10000            # maximum number words in the accepting or rejecting word sets
MAX_EVAL_PER_WORD_TIME = .25        # maximum allowable time per word evaluation before the total time is estimated

class Benchmarker():
    def __init__(self):
        self.db = DBWrapper()
        # console = ConsoleOverwrite()
        self.write = lambda *x: print(datetime.datetime.now().strftime("%H:%M:%S"), *x)
        self.convert = Converter()
        self.code_lines = Deque(open("./example_code_file.txt", "r").read().splitlines())
        self.methods = list(x[0] for x in self.db.selectall("SELECT method FROM methods;"))

    def isDone(self):
        return self.db.selectall("SELECT sum(itersleft) FROM in_tests WHERE error='' AND length<1600;")[0][0] == 0

    def __iter__(self):
        for re_math, itersleft, error in self.db.selectall("""
            SELECT re_math, itersleft, error
            FROM in_tests;
        """):
            yield (re_math.decode("utf-8"), itersleft, error)

    def initTestTables(self):
        """Overwrites current in_tests and out_tests tables."""
        self.write("Creating in_tests and out_tests")
        self.db.executescript("""
            DROP TABLE IF EXISTS methods;
            CREATE TABLE methods (
                method TEXT PRIMARY KEY,
                colour TEXT
            );
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('pd', '#4363d8');
            -- INSERT OR IGNORE INTO methods (method, colour) VALUES ('derivative', '#a9a9a9');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('backtrack', '#000000'); -- NOTE: backtracking is almost always catastrophic for randomized regular expressions... delete manually if it is an issue
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPDRPN', '#42d4f4');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPDO', '#469990');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPDDAG', '#a9a9a9');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPosition', '#e6194B');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaFollow', '#dcbeff');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaThompson', '#800000');
            INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaGlushkov', '#f58231');

            DROP TABLE IF EXISTS in_tests;
            CREATE TABLE in_tests AS
                SELECT DISTINCT e.re_math,
                    -1 as n_evalA,
                    -1 as n_evalR,
                    -1 as length,
                    1 as itersleft,
                    '' as error
                FROM expressions as e
                WHERE e.re_math NOT LIKE '%Error%'
                ORDER BY re_math ASC;
            CREATE INDEX in_tests_re_math
            ON in_tests (re_math);

            CREATE INDEX in_tests_length
            ON in_tests (length);

            DROP TABLE IF EXISTS out_tests;
            CREATE TABLE out_tests (
                re_math TEXT,
                method  TEXT,
                t_pre   REAL,
                t_evalA REAL,
                t_evalR REAL,
                PRIMARY KEY (re_math, method),
                FOREIGN KEY (method) REFERENCES methods (method),
                FOREIGN KEY (re_math) REFERENCES in_tests (re_math)
            );
        """)
        self.write("Setting in_tests length by python string length; this can be changed later")
        for re_math, in self.db.selectall("SELECT re_math FROM in_tests;"):
            self.db.execute("""
                UPDATE in_tests
                SET length=?
                WHERE re_math==?;
            """, [len(re_math), re_math])

    def generateWords(self, re_math):
        re = self.convert.math(re_math)
        pmre = re.partialMatch()
        nfa = pmre.toInvariantNFA("nfaPDDAG")
        enum = nfa.enumNFA()
        accepted = list()
        rejected = set()

        # ACCEPTING: pairGen inserted into lines of code
        self.write(re_math[:50], "generating accepting pairGen words")
        testwords = Deque(re.pairGen())
        word = testwords.iter_cycle()          # cyclically iterate through pairGen words... next(word)
        line = self.code_lines.iter_cycle()    # cyclically iterate through code lines...... next(line)

        hasASTART = "<ASTART>" in re_math
        hasAEND = "<AEND>" in re_math
        addAccepting = lambda line: 0
        if hasASTART and hasAEND: # no leading/trailing from the line
            addAccepting = lambda line: accepted.append(next(word))
        elif hasASTART: # insert word at beginning of line
            addAccepting = lambda line: accepted.append(next(word) + line)
        elif hasAEND: # insert word at end of line
            addAccepting = lambda line: accepted.append(line + next(word))
        else: # insert word in middle of line
            addAccepting = lambda line: accepted.append(
                line[:len(line)//2] + next(word) + line[len(line)//2:])
        for _ in xrange(max(len(testwords), len(self.code_lines))):
            addAccepting(next(line))

        # ACCEPTING: language enumeration
        self.write(re_math[:50], "generating enumerated words")
        minlen = enum.shortestWordLength()
        maxlen = min(minlen + 50, enum.longestWordLength())
        for l in xrange(minlen, maxlen + 1):
            n = 0
            for word in enum.enumCrossSection(l):
                if n > 10: break
                n += 1
                accepted.append(word)

                # REJECTING: slightly changed words may not be accepted...
                # 1. delete one character
                # 2. replace each character with '~'
                for i in xrange(0, len(word)):
                    rejected.add(word[:i] + word[i+1:])
                    rejected.add(word[:i] + "~" + word[i+1:])
                # 3. swap all neighbouring character pairs
                for i in xrange(1, len(word)):
                    rejected.add(word[:i-1] + word[i] + word[i-1] + word[i+1:])

        # REJECTING: filter out words which are really accepted
        self.write(re_math[:50], "filtering", len(rejected), "possibly rejected words")
        rejected = list(w for w in rejected if not nfa.evalWordP(w))

        # choose a pseudo-random sample of up to 10,000 words
        self.write(re_math[:50], "choosing pseudo-random sample up to size WORD_SAMPLE_SIZE for A and R")
        r = random.Random(1)
        accepted = r.sample(accepted, min(len(accepted), WORD_SAMPLE_SIZE))
        rejected = r.sample(rejected, min(len(rejected), WORD_SAMPLE_SIZE))
        return (accepted, rejected)

    def benchmark(self, re_math):
        prev_itersleft = self.db.selectall("SELECT itersleft FROM in_tests WHERE re_math=?;", [re_math])[0][0]
        def _rollback():
            self.db.execute("""
                DELETE FROM out_tests
                WHERE re_math=?;
            """, [re_math])
            self.db.execute("""
                UPDATE in_tests
                SET itersleft=?
                WHERE re_math=?;
            """, [prev_itersleft, re_math])

        try: # catch errors and delete the results of the test
            GROUP_SIZE = 25
            w_accepted, w_rejected = self.generateWords(re_math)
            self.write("running gc")
            gc.collect() # remove unused words from memory... especially the potentially rejected ones

            n_evalA, n_evalR = self.db.selectall("""
                SELECT n_evalA, n_evalR
                FROM in_tests
                WHERE re_math==?;
            """, [re_math])[0]
            if len(w_accepted) != n_evalA or len(w_rejected) != n_evalR: # different word generating scheme... reset
                self.db.execute("DELETE FROM out_tests WHERE re_math==?;", [re_math])
                self.db.execute("UPDATE in_tests SET itersleft=1 WHERE re_math==?;", [re_math])

            self.db.execute("""
                    INSERT OR IGNORE INTO out_tests (re_math, method, t_pre, t_evalA, t_evalR)
                        SELECT in_tests.re_math, methods.method,
                            1000000.0 as t_pre,
                            1000000.0 as t_evalA,
                            1000000.0 as t_evalR
                        FROM in_tests, methods
                        WHERE in_tests.re_math=?;
                """, [re_math])

            # run 1 constructions
            self.write(re_math[:50], "str to partial matching regular expression tree")
            pmre = self.convert.math(re_math, partialMatch=True)
            t_str2pmre = timeit.timeit(lambda: self.convert.math(re_math, partialMatch=True), number=1)

            for method in self.methods:
                try: # catch max. recursion errors and handle gracefully for the specific method
                    self.write(re_math[:50], method, "partial matching regular expression tree to final")
                    evalWord = self.getEvalMethod(pmre, method)
                    t_pmre2final = 0.0
                    if "nfa" in method: # finish the construction
                        t_pmre2final = timeit.timeit(lambda: pmre.toInvariantNFA(method), number=1)
                    self.db.execute("""
                        UPDATE out_tests
                        SET t_pre=?
                        WHERE re_math=? AND method=? AND t_pre>?;
                    """, [t_str2pmre+t_pmre2final, re_math, method, t_str2pmre+t_pmre2final])

                    t_evalA = 0.0
                    ndone = 0
                    self.write(re_math[:50], method, "accepting", len(w_accepted), "words...")
                    for i in xrange(0, len(w_accepted), GROUP_SIZE):
                        tperword = -1 if ndone == 0 else t_evalA/ndone
                        if ndone >= GROUP_SIZE and tperword > MAX_EVAL_PER_WORD_TIME: # if slower than X seconds per word estimate & move on
                            t_evalA = tperword * len(w_accepted)
                            self.write(re_math[:50], method, "too slow, estimating accepting time as", tperword, "per word")
                            break

                        words = w_accepted[i:i+GROUP_SIZE]
                        t_evalA += timeit.timeit(lambda: self.evalMany(evalWord, words, True, method), number=1)
                        ndone += GROUP_SIZE
                    self.db.execute("""
                        UPDATE out_tests
                        SET t_evalA=?
                        WHERE re_math=? AND method=? AND t_evalA>?;
                    """, [t_evalA, re_math, method, t_evalA])

                    t_evalR = 0.0
                    ndone = 0
                    self.write(re_math[:50], method, "rejecting", len(w_rejected), "words...")
                    for i in xrange(0, len(w_rejected), GROUP_SIZE):
                        tperword = -1 if ndone == 0 else t_evalR/ndone
                        if ndone >= GROUP_SIZE and tperword > MAX_EVAL_PER_WORD_TIME: # if slower than X seconds per word estimate & move on
                            t_evalR = tperword * len(w_rejected)
                            self.write(re_math[:50], method, "too slow, estimating rejecting time as", tperword, "per word")
                            break

                        words = w_rejected[i:i+GROUP_SIZE]
                        t_evalR += timeit.timeit(lambda: self.evalMany(evalWord, words, False, method), number=1)
                        ndone += GROUP_SIZE
                    self.db.execute("""
                        UPDATE out_tests
                        SET t_evalR=?
                        WHERE re_math=? AND method=? AND t_evalR>?;
                    """, [t_evalR, re_math, method, t_evalR])
                except RuntimeError as error:
                    if str(error) == "maximum recursion depth exceeded":
                        # leave whatever calculated value as-is... might be the default 1,000,000.0
                        # to indicate that this cannot be solved
                        pass
                    else:
                        raise

            self.write(re_math[:50], "finalizing")
            self.db.execute("""
                UPDATE in_tests
                SET itersleft=itersleft-1, n_evalA=?, n_evalR=?
                WHERE re_math=?;
            """, [len(w_accepted), len(w_rejected), re_math])
            print("\tSuccess", re_math[:50])
        except KeyboardInterrupt:
            _rollback()
            raise
        except Exception as error:
            self.db.execute("""
                UPDATE in_tests
                SET error=?, itersleft=1
                WHERE re_math=?;
            """, [str(error), re_math])
            _rollback()
            print(error)
        finally:
            self.write("running gc")
            gc.collect()

    def evalMany(self, evalWordFtn, words, expectedVal, method):
        for w in words:
            assert evalWordFtn(w) == expectedVal, w + " was not evaluated " + str(expectedVal) + " in " + method

    def getEvalMethod(self, pmre, method):
        if "nfa" in method:
            nfa = pmre.toInvariantNFA(method)
            return nfa.evalWordP
        elif method == "derivative":
            return pmre.evalWordP_Derivative
        elif method == "pd":
            return pmre.evalWordP_PD
        elif method == "backtrack":
            return pmre.evalWordP_Backtrack

    def statsToDo(self):
        return self.db.selectall("""
            SELECT length, count(*), sum(itersleft)
            FROM in_tests
            WHERE error==''
            GROUP BY length
            ORDER BY length ASC;
        """)

    def re_construct_times(self):
        """Manually re-compute the construction times for all items in the out_tests table"""
        sys.setrecursionlimit(12000)
        n = 1
        for re_math, method in self.db.selectall("SELECT re_math, method FROM out_tests"):
            try:
                re_math = re_math.decode("utf-8")
                print(n, re_math[:50], method)

                t_str2pmre = timeit.timeit(lambda: self.convert.math(re_math, partialMatch=True), number=1)
                pmre = self.convert.math(re_math, partialMatch=True)

                t_pmre2final = 0.0
                if "nfa" in method:
                    t_pmre2final = timeit.timeit(lambda: pmre.toInvariantNFA(method), number=1)

                self.db.execute("""
                    UPDATE out_tests
                    SET t_pre=?
                    WHERE re_math==? AND method==?;
                """, [t_str2pmre+t_pmre2final, re_math, method])
                n += 1
            except Exception as e:
                print("\n\nError!\n", e)
                raw_input("Press Enter to continue ... ")

        print("\n\nDone!")

    def cleanup(self):
        """Cleans up invalid tests!"""
        for re_math, in self.db.selectall("""
            SELECT tout.re_math
            FROM in_tests as tin, out_tests as tout
            WHERE tin.re_math==tout.re_math
                AND (
                    tin.n_evalA==-1
                    OR tin.n_evalR==-1
                    OR tout.t_pre==1000000.0
                );
        """):
            re_math = re_math.decode("utf-8")
            self.db.execute("""
                DELETE FROM out_tests
                WHERE re_math==?;
            """, [re_math])
            self.db.execute("""
                UPDATE in_tests
                SET itersleft=1, n_evalA=-1, n_evalR=-1
                WHERE re_math=?;
            """, [re_math])

    def displayResults(self, lengthBucketSize=50, nConstructions=1, nEvals=1, showBins=True):
        time_distribution = list()
        fig, ax = plt.subplots()
        line2d = dict()

        for method, colour in self.db.selectall("SELECT method, colour from methods;"):
            x = []
            y = []
            for row in self.db.selectall("""
                SELECT avg(tin.length),
                    avg(tout.t_pre) as avgpre,
                    sum(tout.t_evalA) as t_evalA,
                    sum(tin.n_evalA) as n_evalA,
                    sum(tout.t_evalR) as t_evalR,
                    sum(tin.n_evalR) as n_evalR
                FROM in_tests as tin, out_tests as tout
                WHERE tin.re_math==tout.re_math
                    AND tout.method==?
                    AND tin.length<1600
                GROUP BY length/?
                ORDER BY length ASC;
            """, [method, lengthBucketSize]):
                length, avgpre, t_evalA, n_evalA, t_evalR, n_evalR = row
                x.append(length)
                if n_evalA == 0: n_evalA = float("inf")
                if n_evalR == 0: n_evalR = float("inf")
                h = (nConstructions * avgpre) + (t_evalA/n_evalA + t_evalR/n_evalR)*nEvals
                y.append(h)
                time_distribution.append(h)
            line2d[method] = ax.plot(x, y, label=method, linewidth=1, color=colour)[0]
        time_distribution.sort()

        legend_to_line = dict()
        legend = plt.legend(loc="best")
        legendLines = legend.get_lines()
        for l in legendLines:
            l.set_picker(True)
            l.set_pickradius(10)
            legend_to_line[l] = line2d[l.get_label()]
        def _on_pick(event):
            line = event.artist
            legend_to_line[line].set_visible(not line.get_visible())
            line.set_visible(not line.get_visible())
            fig.canvas.draw()

        if showBins:
            for count, minlen in self.db.selectall("""
                    SELECT count(*), min(length)
                    FROM in_tests
                    WHERE n_evalA>-1
                        AND length<1600
                    GROUP BY length/?
                    ORDER BY length ASC;
                """, [lengthBucketSize]):
                xpos = minlen/lengthBucketSize * lengthBucketSize # the bottom left corner
                plt.bar(xpos, time_distribution[-1], width=lengthBucketSize, alpha=0.04, align="edge")
                plt.text(xpos + lengthBucketSize/2, 0, str(count), ha="center", va="top", rotation="vertical", clip_on=True)

        plt.ylim(ymin=0, ymax=time_distribution[int(len(time_distribution)*0.9)]) # scale to show 0.XX% of data
        plt.connect("pick_event", _on_pick)
        plt.title("Algorithm Comparison of {} Regular Expressions".format(
            self.db.selectall("SELECT count(re_math) FROM in_tests WHERE n_evalA>-1 AND error==''")[0][0]))
        plt.xlabel("Regular Expression Length\nGrouped in bins of size {}".format(lengthBucketSize))
        plt.ylabel("x{0} Construction(s), x{1} Word Evaluation(s)\n(seconds)".format(nConstructions, nEvals))
        plt.show()


def gbFree():
    """Returns an integer number of GB free on system"""
    return psutil.virtual_memory().available / 1000 / 1000 / 1000

def catchup(method):
    """Benchmark a new method while saving previous results.
    Important: Make sure the method exists in methods table!!
    """
    benchmarker = Benchmarker()
    todo = Deque()

    for re_math, itersleft in benchmarker.db.selectall("""
        SELECT re_math, itersleft
        FROM in_tests
        WHERE n_evalA>-1
            AND ? NOT IN (
                SELECT method
                FROM out_tests
                WHERE out_tests.re_math==in_tests.re_math
            )
        ORDER BY random();
    """, [method]):
        re_math = re_math.decode("utf-8")
        itersTodo = 1 - itersleft
        if itersTodo > 0:
            todo.insert_right((re_math, itersTodo, itersleft))

    benchmarker = None
    nworkers = parseIntSafe(raw_input("How many worker processes? (1): "), 1)
    print("Catching up. Press Ctrl+C to stop")
    print("---------------------------------")
    workers = set()
    try:
        while len(todo) > 0:
            while len(workers) >= nworkers or gbFree() < 5:
                for pid in workers.copy():
                    os.waitpid(pid, os.WNOHANG)
                    if not psutil.pid_exists(pid):
                        workers.discard(pid)
                time.sleep(0.25)

            re_math, itersTodo, itersDone = todo.pop_left()
            printable = re_math.encode("utf-8").encode("string-escape")
            pid = os.fork()
            if pid == 0: # child
                try:
                    gc.disable()
                    benchmarker = Benchmarker()
                    benchmarker.methods = set([method])
                    for i in range(itersTodo):
                        print("\t", "iteration", i+1, "of:", printable)
                        benchmarker.benchmark(re_math)
                except:
                    pass
                finally:
                    benchmarker.db.execute("""
                        UPDATE in_tests
                        SET itersleft=?
                        WHERE re_math==?;
                    """, [itersDone, re_math])
                    exit(0)
            else: # parent
                print("Catching up", printable, "...")
                workers.add(pid)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # Default recursion limit is 1,000. Backtracking algorithm would then only accept words of length < 1,000.
    # a^i in L(a*) can be answered for i upto ~17,000 before Python interpreter crashes.
    # Hence 12,000 is taken as a somewhat conservative value.
    sys.setrecursionlimit(12000)
    benchmarker = Benchmarker()
    benchmarker.cleanup()

    choice = "1"
    while choice != "Q":
        print("\n")
        print("D. Display summary of test results")
        print("L. Change how regular expression length is calculated")
        print("P. Print progress/regular expression length stats")
        print("T. Test through in_tests")
        print("R. Reset in_tests and out_tests")
        print("Q. Quit")
        choice = raw_input("Choose menu option: ").upper().lstrip()[0:]

        if choice == "T":
            nworkers = parseIntSafe(raw_input("How many worker processes? (1): "), 1)
            print("\nRunning tests. Press Ctrl+C to stop")
            print("-----------------------------------")

            workers = set()
            try:
                while True:
                    if benchmarker is None:
                        benchmarker = Benchmarker()
                    re_maths = [re_math for re_math, itersleft, error in benchmarker if itersleft > 0 and error == ""]
                    random.shuffle(re_maths)
                    benchmarker = None
                    if len(re_maths) == 0:
                        print("Done benchmarking!")
                        break

                    for expr in re_maths:
                        while len(workers) >= nworkers or gbFree() < 5:
                            for pid in workers.copy():
                                os.waitpid(pid, os.WNOHANG)
                                if not psutil.pid_exists(pid):
                                    workers.discard(pid)
                            time.sleep(0.25)

                        pid = os.fork()
                        if pid == 0: # child
                            try:
                                gc.disable()
                                Benchmarker().benchmark(expr)
                            except:
                                pass
                            finally:
                                exit(0)
                        else: # parent
                            print("Benchmarking", expr.encode("utf-8").encode("string-escape"), "...")
                            workers.add(pid)
            except KeyboardInterrupt:
                for pid in workers:
                    os.kill(pid, 2)
            finally:
                benchmarker = Benchmarker()
        elif choice == "P":
            stats = dict()
            for length, count, itersleft in benchmarker.statsToDo():
                prev_count, prev_iters = stats.get(length//25, (0, 0))
                stats[length//25] = (prev_count + count, prev_iters + itersleft)

            for lengthBin in sorted(stats.keys()):
                count, iters = stats[lengthBin]
                print(lengthBin*25, (lengthBin+1)*25, iters, "remaining;", count, "total")
            raw_input("Press Enter to continue ... ")
        elif choice == "R":
            if raw_input("Are you sure you want to permanently delete all results? y/(n): ") == "y":
                benchmarker.initTestTables()
                print("Reset!")
            else:
                print("Aborted. Did not reset.")
            raw_input("Press Enter to continue ... ")
        elif choice == "D":
            lengthBucketSize = parseIntSafe(raw_input("\tExpression length bin width (50): "), 50)
            showBins = not raw_input("\tDisplay bin bars (y)/n: ") == "n"
            nConstructions = parseIntSafe(raw_input("\tNumber of constructions (1): "), 1)
            nEvals = parseIntSafe(raw_input("\tNumber of average word evaluations (1): "), 1)
            print("lengthBucketSize =", lengthBucketSize)
            print("nConstructions =", nConstructions)
            print("nEvals =", nEvals)
            print("showBins = ", showBins)
            benchmarker.displayResults(lengthBucketSize, nConstructions, nEvals, showBins)
        elif choice == "L":
            print("\nHow should the length of the regular expression be evaluated?")
            print("\t1. Python string length")
            print("\t2. Tree length")
            choice = parseIntSafe(raw_input("\tMenu option: "), 1)
            lengthFtn = None
            if choice == 1:
                lengthFtn = lambda re_math: len(re_math)
            elif choice == 2:
                c = Converter()
                lengthFtn = lambda re_math: c.math(re_math).treeLength()
            else:
                print("Unknown option")
                continue
            i = 1
            for re_math, itersleft, error in benchmarker:
                print(i, re_math[:80])
                benchmarker.db.execute("""
                    UPDATE in_tests
                    SET length=?
                    WHERE re_math=?;
                """, [lengthFtn(re_math), re_math])
                i += 1
            print("\n\nDone!")



    print("\nBye!")