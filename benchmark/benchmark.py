from __future__ import print_function
import timeit
import matplotlib.pyplot as plt
import copy
import lark.exceptions

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
        return "{0}: {1}".format(self.method, self.re_math.encode("utf-8")).encode("string-escape")

    def genWords(self):
        """Populates the `accepted` and `rejected` attributes with words"""
        BenchExpr.OUTPUT.overwrite("generating words for", self.re_math)
        self.accepted = list()
        self.rejected = list()

        try:
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=False)

            # pairGen inserted into lines of code
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
            elif hasASTART: # insert word at end of line
                addAccepting = lambda line: self.accepted.append(line + next(word))
            elif hasAEND: # insert word at beginning of line
                addAccepting = lambda line: self.accepted.append(next(word) + line)
            else: # insert word in middle of line
                addAccepting = lambda line: self.accepted.append(
                    line[:len(line)//2] + next(word) + line[len(line)//2:])

            for _ in range(max(len(testwords), len(BenchExpr.CODE_LINES))):
                addAccepting(next(line))


            # pre-computed rejecting words from the lines of code
            pmre = re.partialMatch()
            pmre.compress()
            for line in BenchExpr.CODE_LINES:
                if not pmre.evalWordP_PDO(line):
                    self.rejected.append(line)
        except Exception:
            # self.db.execute("""
            #     UPDATE tests
            #     SET pre_time=0, eval_time=0, error=?
            #     WHERE re_math=?;
            # """, [str(e) + "\nwhile generating words", self.re_math])
            raise

    def benchmark(self):
        """Runs the benchmark and updates the `tests` table"""
        try:
            BenchExpr.OUTPUT.overwrite(str(self), "pre-processing")
            processed = self.preprocess()
            pre_time = timeit.timeit(self.preprocess, number=1000)

            eval_A_time = 0.0
            ndone = 0.0
            ntotal = len(self.accepted) + len(self.rejected)
            for word in self.accepted:
                ndone += 1
                BenchExpr.OUTPUT.overwrite(format(ndone*100.0/ntotal, ".2f") + "%", \
                    "{0} should match '{1}'".format(str(self), word.encode("utf-8")))
                assert self.testMembership(processed, word) == True, str(self) + " didn't accept '{0}'".format(word)
                eval_A_time += timeit.timeit(lambda: self.testMembership(processed, word), number=1)

            eval_R_time = 0.0
            for word in self.rejected:
                ndone += 1
                BenchExpr.OUTPUT.overwrite(format(ndone*100.0/ntotal, ".2f") + "%", \
                    "{0} should reject '{1}'".format(str(self), word.encode("utf-8")))
                assert self.testMembership(processed, word) == False, str(self) + " didn't reject '{0}'".format(word)
                eval_R_time += timeit.timeit(lambda: self.testMembership(processed, word), number=1)

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
                    method TEXT PRIMARY KEY
                );
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaPD');
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaPDO');
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaPosition');
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaFollow');
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaThompson');
                INSERT OR IGNORE INTO methods (method) VALUES ('nfaGlushkov');
                -- INSERT OR IGNORE INTO methods (method) VALUES ('derivative');
                INSERT OR IGNORE INTO methods (method) VALUES ('pd');
                INSERT OR IGNORE INTO methods (method) VALUES ('pdo');
                INSERT OR IGNORE INTO methods (method) VALUES ('backtrack');

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
                    ORDER BY re_math ASC, method ASC;

                CREATE INDEX tests_by_method
                ON tests (method);
            """)

    def __iter__(self):
        """Yields BenchExpr objects ordered by the distinct expression"""
        newCursor = self.db._connection.cursor() # o/w the main cursor may move
        newCursor.execute("""SELECT re_math, method, error
                             FROM tests
                             WHERE pre_time=-1;""")
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

    def displayBenchmarkStats(self):
        for method, in self.db.selectall("SELECT method from methods;"):
            x = []
            y = []
            for complexity, ta, tr in self.db.selectall("""
                SELECT length(re_math) as complexity,
                    sum(eval_A_time)/n_accept,
                    sum(eval_R_time)/n_reject
                FROM tests
                WHERE method==?
                    AND pre_time>-1
                    AND error==''
                GROUP BY complexity
                ORDER BY complexity ASC;
            """, [method]):
                if ta is None: ta = 0.0
                if tr is None: tr = 0.0
                x.append(complexity)
                y.append(ta + tr)
            plt.plot(x, y, label=method)

        plt.title("RE Length vs. Avg time for Membership")
        plt.legend()
        plt.xlabel("re_math length")
        plt.ylabel("avg time (s) for membership")
        plt.show()



if __name__ == "__main__":
    benchmarker = Benchmarker()
    benchmarker.printSampleStats()

    choice = "-1"
    while choice != "5":
        completed, todo = benchmarker.getProgress()
        print("\nCompleted: " + str(completed))
        print("TODO:      " + str(todo))

        print("\n========================================")
        print("1. Display results")
        print("2. Continue with {0} more tests".format(todo))
        print("3. Backup all results; {0}/{1} completed".format(completed, todo + completed))
        print("4. Reset without backing up")
        print("5. Exit\n")

        choice = raw_input("Choose menu option: ")
        print("\n")

        if choice == "1":
            benchmarker.displayBenchmarkStats()
        elif choice == "2":
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
            choice = "5"
        elif choice == "3":
            print("Currently disabled!")
            exit(0)
        elif choice == "4":
            if raw_input("Are you sure? y/(n): ") == "y":
                benchmarker = Benchmarker(True)

    print("\n\nBye!")