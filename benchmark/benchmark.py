from __future__ import print_function
import timeit
import matplotlib.pyplot as plt
import copy
import lark.exceptions
import random

from util import DBWrapper, ConsoleOverwrite, Deque
from convert import Converter
import errors

class BenchExpr(object):
    CONVERTER = Converter()
    OUTPUT = ConsoleOverwrite("Bench:")
    CODE_LINES = Deque(filter(lambda l: len(l) > 0, open("./benchmark/reex_ext.py", "r").read().splitlines()))

    def __init__(self, db, re_math, method):
        super(BenchExpr, self).__init__()
        self.db = db
        self.method = method
        self.re_math = re_math
        self.accepted = list()
        self.rejected = list()

    def __str__(self):
        return "{0}: {1}".format(self.method, self.re_math.encode("utf-8"))

    def genWords(self):
        """Populates the `accepted` and `rejected` attributes with words"""
        BenchExpr.OUTPUT.overwrite("generating words for", self.re_math)
        self.accepted = list()
        self.rejected = set(copy.copy(BenchExpr.CODE_LINES))

        try:
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=False)

            # ACCEPTING: pairGen inserted into lines of code
            BenchExpr.OUTPUT.overwrite("generating pairGen words for", self.re_math)
            testwords = Deque(re.pairGen())
            if len(testwords) == 0:
                return
            word = testwords.iter_cycle()               # cyclically iterate through pairGen words... next(word)
            line = BenchExpr.CODE_LINES.iter_cycle()    # cyclically iterate through code lines...... next(line)

            hasASTART = "<ASTART>" in self.re_math
            hasAEND = "<AEND>" in self.re_math
            addAccepting = lambda line: 0
            if hasASTART and hasAEND: # no leading/trailing from the line
                addAccepting = lambda line: self.accepted.append(next(word))
            elif hasASTART: # insert word at beginning of line
                addAccepting = lambda line: self.accepted.append(next(word) + line)
            elif hasAEND: # insert word at end of line
                addAccepting = lambda line: self.accepted.append(line + next(word))
            else: # insert word in middle of line
                addAccepting = lambda line: self.accepted.append(
                    line[:len(line)//2] + next(word) + line[len(line)//2:])

            for _ in xrange(max(len(testwords), len(BenchExpr.CODE_LINES))):
                addAccepting(next(line))


            # ACCEPTING: language enumeration
            BenchExpr.OUTPUT.overwrite("generating enumerated words for", self.re_math)
            enumerate = re.toInvariantNFA("nfaPosition").enumNFA()
            minlen = enumerate.shortestWordLength()
            maxlen = min(minlen + 50, enumerate.longestWordLength())
            for l in xrange(minlen, maxlen + 1):
                n = 0
                for word in enumerate.enumCrossSection(l):
                    if n > 10: break
                    n += 1
                    self.accepted.append(word)

                    # REJECTING: slightly changed words may not be accepted...
                    # 1. delete one character
                    for i in xrange(0, len(word)):
                        self.rejected.add(word[:i] + word[i+1:])
                    # 2. swap all neighbouring character pairs
                    for i in xrange(1, len(word)):
                        self.rejected.add(word[:i-1] + word[i] + word[i-1] + word[i+1:])


            # REJECTING: filter out words which are really accepted
            BenchExpr.OUTPUT.overwrite("filtering", len(self.rejected), "rejecting words for", self.re_math)
            pmre = re.partialMatch()
            pmNFA = pmre.toInvariantNFA("nfaPDO") # TODO: consider switching to compressed pdo evaluation if it can be optimized further
            self.rejected = list(w for w in self.rejected if not pmNFA.evalWordP(w))

            # choose a pseudo-random sample of up to 10,000 words
            r = random.Random(1)
            self.accepted = r.sample(self.accepted, min(len(self.accepted), 10000))
            self.rejected = r.sample(self.rejected, min(len(self.rejected), 10000))
        except Exception:
            # self.db.execute("""
            #     UPDATE tests
            #     SET pre_time=0, eval_time=0, error=?
            #     WHERE re_math=?;
            # """, [str(e) + "\nwhile generating words", self.re_math])
            raise

    def benchmark(self):
        """Runs the benchmark and updates the `tests` table"""
        GROUP_SIZE = 100
        ntotal = len(self.accepted) + len(self.rejected)
        ndone = 0

        try:
            BenchExpr.OUTPUT.overwrite("pre-processing", str(self))
            processed = self.preprocess()
            pre_time = timeit.timeit(self.preprocess, number=1000)

            eval_A_time = 0.0
            def _assertion(b, word):
                assert b == True, str(self) + " didn't accept '{0}'".format(word.encode("utf-8"))
            for i in xrange(0, len(self.accepted), GROUP_SIZE):
                BenchExpr.OUTPUT.overwrite("{0}% - {1}".format(format(ndone*100.0/ntotal, "00.2f"), str(self)))
                eval_A_time += timeit.timeit(lambda: self._benchGroup(processed, self.accepted[i:i+GROUP_SIZE], _assertion), number=1)
                ndone += GROUP_SIZE

            eval_R_time = 0.0
            def _assertion(b, word):
                assert b == True, str(self) + " didn't reject '{0}'".format(word.encode("utf-8"))
            ndone = len(self.accepted)
            for i in xrange(0, len(self.rejected), GROUP_SIZE):
                BenchExpr.OUTPUT.overwrite("{0}% - {1}".format(format(ndone*100.0/ntotal, "00.2f"), str(self)))
                eval_R_time += timeit.timeit(lambda: self._benchGroup(processed, self.accepted[i:i+GROUP_SIZE], _assertion), number=1)
                ndone += GROUP_SIZE

            self.db.execute("""
                UPDATE tests
                SET pre_time=?, eval_A_time=?, eval_R_time=?, n_accept=?, n_reject=?
                WHERE re_math=? AND method=? AND error='';
            """, [pre_time, eval_A_time, eval_R_time, len(self.accepted), len(self.rejected), self.re_math, self.method])
        except (errors.FAdoExtError, AssertionError) as err:
            self.db.execute("""
                UPDATE tests
                SET pre_time=0, eval_A_time=0, eval_R_time=0, n_accept=0, n_reject=0, error=?
                WHERE re_math=?;
            """, [str(err) + "\nin method " + self.method, self.re_math])

    def _benchGroup(self, processed, words, assertion):
        for word in words:
            assertion(self.testMembership(processed, word), word)

    def preprocess(self):
        """One-time cost of parsing, compiling, etc into an object which can
        evaluate membership"""
        raise NotImplementedError("preprocess must be implemented in the child")

    def testMembership(self, obj, word):
        """returns if the word is accepted by the given object"""
        return obj.evalWordP(word)

class MethodImplementation:
    """Method-specific implementations of BenchExpr"""
    class derivative(BenchExpr):
        def preprocess(self):
            return BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)

        def testMembership(self, obj, word):
            return obj.evalWordP_Derivative(word)

    class pd(BenchExpr):
        def preprocess(self):
            return BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)

        def testMembership(self, obj, word):
            return obj.evalWordP_PD(word)

    class pdo(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            re.compress()
            return re

        def testMembership(self, obj, word):
            return obj.evalWordP_PDO(word)

    class backtrack(BenchExpr):
        def preprocess(self):
            return BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)

        def testMembership(self, obj, word):
            return obj.evalWordP_Backtrack(word)

    class nfaPD(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaPD")

    class nfaPDO(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaPDO")

    class nfaPosition(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaPosition")

    class nfaFollow(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaFollow")

    class nfaThompson(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaThompson")

    class nfaGlushkov(BenchExpr):
        def preprocess(self):
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
            return re.toInvariantNFA("nfaGlushkov")


class Benchmarker(object):
    def __init__(self, reset=False):
        super(Benchmarker, self).__init__()
        self.memo_expr = dict()
        self.memo_words = set()
        self.db = DBWrapper()

        exists = len(self.db.selectall("""
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='tests';
        """)) > 0
        if not exists or reset:
            self.db.executescript("""
                DROP TABLE IF EXISTS methods;
                CREATE TABLE methods (
                    method TEXT PRIMARY KEY,
                    colour TEXT
                );
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPD', '#42d4f4');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPDO', '#469990');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaPosition', '#e6194B');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaFollow', '#dcbeff');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaThompson', '#800000');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('nfaGlushkov', '#f58231');
                -- INSERT OR IGNORE INTO methods (method, colour) VALUES ('derivative', '#a9a9a9');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('pd', '#4363d8');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('pdo', '#000075');
                INSERT OR IGNORE INTO methods (method, colour) VALUES ('backtrack', '#000000');

                DROP TABLE IF EXISTS tests;

                CREATE TABLE tests AS
                    SELECT DISTINCT e.re_math, m.method,
                        -1 as pre_time,
                        -1 as eval_A_time,
                        -1 as eval_R_time,
                        -1 as n_accept,
                        -1 as n_reject,
                        "" as error
                    FROM methods as m, expressions as e
                    WHERE e.re_math NOT LIKE '%Error%'
                    ORDER BY length(re_math) ASC, re_math ASC, method ASC;

                CREATE INDEX tests_by_method
                ON tests (method);
            """)

    def __iter__(self):
        """Yields BenchExpr objects ordered by the distinct expression"""
        minlen, maxlen = self.db.selectall("SELECT min(length(re_math)), max(length(re_math)) FROM tests WHERE pre_time==-1;")[0]
        while self.db.selectall("SELECT count(*) FROM tests WHERE pre_time==-1;")[0][0] > 0:
            newCursor = self.db._connection.cursor()
            for length in xrange(minlen, maxlen):
                newCursor.execute("""
                    SELECT re_math, method, error
                    FROM tests
                    WHERE re_math==(
                        SELECT min(re_math)
                        FROM tests
                        WHERE pre_time==-1
                            AND length(re_math)==?
                            AND error==''
                    );
                """, [length])
                for re_math, method, error in newCursor:
                    if len(error) == 0:
                        yield eval("MethodImplementation." + method)(self.db, re_math.decode("utf-8"), method)
            newCursor.close()

    def printSampleStats(self):
        """Prints (stdout) the statistics of the sample collected using `make sample`"""
        all = self.db.selectall("""
            SELECT lang, ntotal, ndistinct
            FROM (
                -- main content --
                SELECT 0 as rn, lang, count(re_math) as ntotal, count(DISTINCT re_math) as ndistinct
                FROM expressions
                WHERE re_math NOT LIKE '%Error%'
                GROUP BY lang

                -- blank line --
                UNION SELECT 1 as rn, '', '', ''

                -- total row --
                UNION SELECT 2 as rn, 'Total', count(re_math), count(DISTINCT re_math)
                FROM expressions
                WHERE re_math NOT LIKE '%Error%'

                ORDER BY rn ASC, ntotal DESC
            );
        """)
        print("\n\nSAMPLING STATISTICS:\n")
        print("language           ntotal  ndistinct")
        print("------------------------------------")
        for row in all:
            print(row[0].ljust(16), str(row[1]).rjust(8), str(row[2]).rjust(8))

        if all[-1][2] == 0: # 0 distinct
            print("\nNo regular expressions sampled - run `make sample` first")
            exit(0)

    def getProgress(self):
        done = self.db.selectall("SELECT count(*) FROM tests WHERE pre_time>-1;")[0][0]
        todo = self.db.selectall("SELECT count(*) FROM tests WHERE pre_time==-1;")[0][0]
        return (done, todo)

    def displayMembershipStats(self):
        fig, ax = plt.subplots()
        line2d = dict()

        for method, colour in self.db.selectall("SELECT method, colour from methods;"):
            x = []
            y = []
            for complexity, ta, na, tr, nr in self.db.selectall("""
                SELECT length(re_math) as complexity,
                    sum(eval_A_time),
                    sum(n_accept),
                    sum(eval_R_time),
                    sum(n_reject)
                FROM tests
                WHERE method==?
                    AND pre_time>-1
                    AND error==''
                GROUP BY complexity
                ORDER BY complexity ASC;
            """, [method]):
                x.append(complexity)
                if na == 0: na = float("inf")
                if nr == 0: nr = float("inf")
                y.append(ta/na + tr/nr) # weighted average time for accept & reject
            line2d[method] = ax.plot(x, y, label=method, linewidth=1.5, color=colour)[0]

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
        plt.connect("pick_event", _on_pick)

        plt.title("Membership Time by Expression Complexity")
        plt.xlabel("re_math length")
        plt.ylabel("avg membership time (s)")
        plt.show()

    def displayConstructionStats(self):
        fig, ax = plt.subplots()
        line2d = dict()

        for method, colour in self.db.selectall("SELECT method, colour from methods;"):
            x = []
            y = []
            for complexity, t in self.db.selectall("""
                SELECT length(re_math) as complexity,
                    sum(pre_time)
                FROM tests
                WHERE method==?
                    AND pre_time>-1
                    AND error==''
                GROUP BY complexity
                ORDER BY complexity ASC;
            """, [method]):
                x.append(complexity)
                y.append(t/1000.0)
            line2d[method] = ax.plot(x, y, label=method, linewidth=1.5, color=colour)[0]

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
        plt.connect("pick_event", _on_pick)

        plt.title("Construction Time by Expression Complexity")
        plt.xlabel("re_math length")
        plt.ylabel("avg construction time (s)")
        plt.show()


if __name__ == "__main__":
    benchmarker = Benchmarker()
    benchmarker.printSampleStats()

    choice = "-1"
    while choice != "6":
        completed, todo = benchmarker.getProgress()
        print("\nCompleted: " + str(completed))
        print("TODO:      " + str(todo))

        print("\n========================================")
        print("1. Display membership results")
        print("2. Display construction results")
        print("3. Continue with {0} more tests".format(todo))
        print("4. Backup all results; {0}/{1} completed".format(completed, todo + completed))
        print("5. Reset without backing up")
        print("6. Exit\n")

        choice = raw_input("Choose menu option: ")
        print("\n")

        if choice == "1":
            benchmarker.displayMembershipStats()
        elif choice == "2":
            benchmarker.displayConstructionStats()
        elif choice == "3":
            print("Running benchmark... (Ctrl+C to stop)")
            lastExpr = BenchExpr(None, None, None)
            for r in benchmarker:
                try:
                    # take advantage of Benchmarker iteration being ordered by re_math and re-generate words sparingly
                    if r.re_math == lastExpr.re_math:
                        r.accepted = copy.copy(lastExpr.accepted)
                        r.rejected = copy.copy(lastExpr.rejected)
                    else:
                        r.genWords()
                        lastExpr = r

                    r.benchmark()
                except (lark.exceptions.UnexpectedToken, errors.AnchorError):
                    print("\n\n", r)
                    raise
                except KeyboardInterrupt:
                    print("\nStopping...")
                    break
        elif choice == "4":
            print("Currently disabled!")
            exit(0)
        elif choice == "5":
            if raw_input("Are you sure? y/(n): ") == "y":
                benchmarker = Benchmarker(True)
                print("Reset!")
            else:
                print("Cancelled!")

    print("\n\nExiting...")