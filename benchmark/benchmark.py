from __future__ import print_function
import timeit
import lark.exceptions

from util import DBWrapper, ConsoleOverwrite
from convert import Converter
import errors

class BenchExpr(object):
    CONVERTER = Converter()

    # number of times each word set is evaluated for membership (higher to avoid float issues)
    NUM_WORD_SET_REPETITIONS = 100

    # number of times each benchmark is repeated... minimum taken time
    NUM_BENCHMARK_REPETITIONS = 3

    def __init__(self, db, re_math, method):
        super(BenchExpr, self).__init__()
        self.db = db
        self.method = method
        self.re_math = re_math
        self.accepted = set()
        self.rejected = set()

    def __str__(self):
        return "{0}: {1}".format(self.method, self.re_math).encode("string-escape")

    def genWords(self):
        """Populates the `accepted` and `rejected` attributes with words"""
        self.accepted = set()
        self.rejected = set()
        infa = self.CONVERTER.math(self.re_math, partialMatch=True).toInvariantNFA("nfaPD")
        # enum = infa.enumNFA()

        self.accepted.add(infa.witness())
        # TODO MORE

    def setWords(self, accepted, rejected):
        """Sets the words used when running the benchmark"""
        self.accepted = accepted
        self.rejected = rejected

    def benchmark(self):
        """Runs the benchmark and updates the `time` in the `tests` table"""
        def _timed():
            processed = self.preprocess()
            for word in self.accepted:
                assert self.testMembership(processed, word) == True, \
                    str(self) + " should accept '{0}'".format(word)

            for word in self.rejected:
                assert self.testMembership(processed, word) == False, \
                    str(self) + " should NOT accept '{0}'".format(word)

        times = set()
        for _ in range(BenchExpr.NUM_BENCHMARK_REPETITIONS):
            times.add(timeit.timeit(stmt=_timed, setup="gc.enable()",
                number=BenchExpr.NUM_WORD_SET_REPETITIONS))

        self.db.execute("""
            UPDATE tests
            SET time=?
            WHERE re_math=? AND method=? AND time!=0;
        """, [min(times), self.re_math, self.method])

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

    class backtrack(BenchExpr):
        def preprocess(self):
            return BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)

        def testMembership(self, obj, word):
            return obj.evalWordPBacktrack(word)

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
                DROP TABLE IF EXISTS tests;

                CREATE TABLE tests AS
                    SELECT DISTINCT e.re_math, m.method, -1 as time
                    FROM methods as m, expressions as e
                    WHERE e.re_math NOT LIKE '%Error%'
                    ORDER BY re_math ASC, method ASC;

                CREATE INDEX tests_by_method
                ON tests (method);
            """)

        self.printSampleStats()

    def __iter__(self):
        """Yields BenchExpr objects orderde by the distinct expression"""
        newCursor = self.db._connection.cursor() # o/w the main cursor may move
        newCursor.execute("""SELECT re_math, method
                             FROM tests
                             WHERE time=-1;""")
        for re_math, method in newCursor:
            yield eval("MethodImplementation." + method)(self.db, re_math, method)

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
            SELECT method, sum(time)
            FROM tests
            WHERE time>0
            GROUP BY method
            ORDER BY sum(time) ASC;
        """)
        print("\n\nBENCHMARKED STATISTICS:\n")
        print("method           sum(min_time)")
        print("------------------------------")
        for row in all:
            print(row[0].ljust(16), str(row[1]))

        done = self.db.selectall("SELECT count(*) FROM tests WHERE time!=-1 AND time!=0;")[0][0]
        todo = self.db.selectall("SELECT count(*) FROM tests WHERE time==-1 AND time!=0;")[0][0]
        return (done, todo)



if __name__ == "__main__":
    output = ConsoleOverwrite("Benchmarking: ")
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
                r.setWords(lastExpr.accepted, lastExpr.rejected)
            else:
                r.genWords()
                lastExpr = r

            output.overwrite("{0}/{1}:".format(done, todo), r)
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
            print("\n\nBye!")
            exit(0)

        done += 1

    benchmarker.printBenchmarkStats()