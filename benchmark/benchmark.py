from __future__ import print_function
import timeit
import math
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
        self.accepted = list()
        self.rejected = list()

        try:
            re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=False)

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
        except Exception:
            # self.db.execute("""
            #     UPDATE tests
            #     SET pre_time=0, eval_time=0, error=?
            #     WHERE re_math=?;
            # """, [str(e) + "\nwhile generating words", self.re_math])
            raise

    def benchmark(self):
        """Runs the benchmark and updates the `pre_time` & `eval_time` in the `tests` table"""
        try:
            BenchExpr.OUTPUT.overwrite(str(self), "pre-processing")
            processed = self.preprocess()
            pre_time = timeit.timeit(self.preprocess, number=1000)

            eval_time = 0.0
            for word in self.accepted:
                BenchExpr.OUTPUT.overwrite(str(self), "should match '{0}'".format(word.encode("utf-8")))
                assert self.testMembership(processed, word) == True, str(self) + " didn't accept '{0}'".format(word)
                eval_time += timeit.timeit(lambda: self.testMembership(processed, word), number=1)

            for word in self.rejected:
                BenchExpr.OUTPUT.overwrite(str(self), "should reject '{0}'".format(word.encode("utf-8")))
                assert self.testMembership(processed, word) == False, str(self) + " didn't reject '{0}'".format(word)
                eval_time += timeit.timeit(lambda: self.testMembership(processed, word), number=1)

            self.db.execute("""
                UPDATE tests
                SET pre_time=?, eval_time=?
                WHERE re_math=? AND method=? AND error='';
            """, [pre_time, eval_time, self.re_math, self.method])
        except (errors.FAdoExtError, AssertionError) as err:
            self.db.execute("""
                UPDATE tests
                SET pre_time=0, eval_time=0, error=?
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
                INSERT OR IGNORE INTO methods (method) VALUES ('derivative');
                INSERT OR IGNORE INTO methods (method) VALUES ('pd');
                INSERT OR IGNORE INTO methods (method) VALUES ('pdo');
                INSERT OR IGNORE INTO methods (method) VALUES ('backtrack');

                DROP TABLE IF EXISTS tests;

                CREATE TABLE tests AS
                    SELECT DISTINCT e.re_math, m.method, -1 as pre_time, -1 as eval_time, "" as error
                    FROM methods as m, expressions as e
                    WHERE e.re_math NOT LIKE '%Error%'
                    ORDER BY re_math ASC, method ASC;

                CREATE INDEX tests_by_method
                ON tests (method);

                DROP TABLE methods;
            """)

        self.printSampleStats()
        self.printBenchmarkStats()

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

    def printBenchmarkStats(self):
        """Prints (stdout) the result statistics from the last benchmark
        and returns (#completed, #todo)"""
        all = self.db.selectall("""
            SELECT method, sum(pre_time), sum(eval_time), sum(pre_time) + sum(eval_time) as time
            FROM tests
            WHERE pre_time>-1 AND error==''
            GROUP BY method
            ORDER BY time ASC;
        """)
        print("\n\nBENCHMARKED STATISTICS:\n")
        print("method           pre_time         eval_time        time")
        print("-"*(16*4 + 2))
        for row in all:
            print(row[0].ljust(16), str(row[1]).ljust(16), str(row[2]).ljust(16), str(row[3]).ljust(16))

        done = self.db.selectall("SELECT count(*) FROM tests WHERE pre_time>-1;")[0][0]
        todo = self.db.selectall("SELECT count(*) FROM tests WHERE pre_time==-1;")[0][0]
        return (done, todo)



if __name__ == "__main__":
    benchmarker = Benchmarker()

    completed, todo = benchmarker.printBenchmarkStats()
    print("\nCompleted: " + str(completed))
    print("Todo:      " + str(todo))

    print("\n========================================")
    print("1. Continue with {0} more tests".format(todo))
    print("2. Backup all results; {0}/{1} completed".format(completed, todo + completed))
    print("3. Reset without backing up")
    print("4. Exit\n")
    option = None
    while option not in list("1234"):
        option = raw_input("Choose option: ")
    print("\n")

    if option == "1":
        print("Running tests...")
    elif option == "2":
        from datetime import datetime
        newname = ("tests_" + str(datetime.now())).replace(" ", "_")
        benchmarker.db.execute("ALTER TABLE tests RENAME TO ?;", [newname])
        print("Table saved as", newname)
        exit(0)
    elif option == "3":
        benchmarker = Benchmarker(True)
        print("Reset test set")
        exit(0)
    elif option == "4":
        print("Bye!")
        exit(0)
    else:
        print("Unknown option")
        exit(1)

    lastExpr = BenchExpr(None, None, None)
    done = 0
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
            # disable the impact of the test for all methods if any method fails
            # better than deleting since it can be investigated later
            print("\n\n", r)
            raise

            # benchmarker.db.execute("""
            #     UPDATE tests
            #     SET time=0
            #     WHERE re_math=?;
            # """, [r.re_math])
        except KeyboardInterrupt:
            print("\n")
            benchmarker.printBenchmarkStats()
            print("\n\nBye!")
            exit(0)

        done += 1

    benchmarker.printBenchmarkStats()