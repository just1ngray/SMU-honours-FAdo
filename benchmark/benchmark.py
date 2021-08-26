import timeit
import re
import regex

from util import DBWrapper, ConsoleOverwrite
from convert import Converter


class BenchExpr(object):
    CONVERTER = Converter()

    # number of times each word set is evaluated for membership (higher to avoid float issues)
    NUM_WORD_SET_REPETITIONS = 100

    # number of times each benchmark is repeated... minimum taken time
    NUM_BENCHMARK_REPETITIONS = 3

    @staticmethod
    def evalWordP(obj, word):
        """returns if the word is accepted by the given object"""
        return obj.evalWordP(word)

    def __init__(self, db, url, lineNum, method, re_math, re_prog):
        super(BenchExpr, self).__init__()
        self.db = db
        self.url = url
        self.lineNum = lineNum
        self.method = method
        self.re_math = re_math
        self.re_prog = re_prog
        self.accepted = set()
        self.rejected = set()

    def __str__(self):
        return "{0}: {1} / {2}".format(self.method, self.re_prog, self.re_math)

    def genWords(self):
        """Populates the `accepted` and `rejected` attributes with words"""
        yield self.CONVERTER.math(self.re_math, partialMatch=True).toInvariantNFA("nfaPD").witness()
        # TODO MORE

    def setWords(self, accepted, rejected):
        """Sets the words used when running the benchmark"""
        self.accepted = accepted
        self.rejected = rejected

    def benchmark(self):
        """Runs the benchmark and updates the `time` in the `tests` table"""
        try:
            def _timed():
                processed = self.preprocess()
                for word in self.accepted:
                    assert self.evalWordP(processed, word) == True, \
                        "{0} should accept {1}".format(self.re_prog, word)

                for word in self.rejected:
                    assert self.evalWordP(processed, word) == False, \
                        "{0} should NOT accept {1}".format(self.re_prog, word)

            times = set()
            for _ in range(BenchExpr.NUM_BENCHMARK_REPETITIONS):
                times.add(timeit.timeit(stmt=_timed, setup="gc.enable()", number=BenchExpr.NUM_WORD_SET_REPETITIONS))

            self.db.execute("""
                UPDATE tests
                SET time=?
                WHERE url=? AND lineNum=? AND method=?;
            """, [min(times), self.url, self.lineNum, self.method])
        except:
            print "ERROR while running benchmark on:", self
            raise

    def preprocess(self):
        """One-time cost of parsing, compiling, etc into an object which can
        evaluate membership"""
        raise NotImplementedError("preprocess must be implemented in the child")

class derivativeBench(BenchExpr):
    def preprocess(self):
        return BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)

class reBench(BenchExpr):
    def preprocess(self):
        return re.compile(self.re_prog)

    @staticmethod
    def evalWordP(obj, word):
        return obj.search(word) is not None

class regexBench(reBench):
    def preprocess(self):
        return regex.compile(self.re_prog)

class nfaPDBench(BenchExpr):
    def preprocess(self):
        re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
        return re.toInvariantNFA("nfaPD")

class nfaPDOBench(BenchExpr):
    def preprocess(self):
        re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
        return re.toInvariantNFA("nfaPDO")

class nfaPositionBench(BenchExpr):
    def preprocess(self):
        re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
        return re.toInvariantNFA("nfaPosition")

class nfaFollowBench(BenchExpr):
    def preprocess(self):
        re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
        return re.toInvariantNFA("nfaFollow")

class nfaThompsonBench(BenchExpr):
    def preprocess(self):
        re = BenchExpr.CONVERTER.math(self.re_math, partialMatch=True)
        return re.toInvariantNFA("nfaThompson")

class nfaGlushkovBench(BenchExpr):
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
                    SELECT e.url, e.lineNum, m.method, -1 as time
                    FROM methods as m, (
                        SELECT *
                        FROM (
                            SELECT *, ROW_NUMBER() OVER(PARTITION BY re_math ORDER BY lineNum ASC, url ASC) rn
                            FROM expressions
                            WHERE re_math NOT LIKE '%Error%'
                        )
                        WHERE rn=1
                        ORDER BY re_math ASC
                    ) as e
                    ORDER BY re_math ASC, method ASC

                CREATE INDEX tests_by_method
                ON tests (method);
            """)

        self.printSampleStats()

    def __iter__(self):
        """Yields BenchExpr objects orderde by the distinct expression"""
        query = """
            SELECT t.url, t.lineNum, t.method, e.re_math, e.re_prog
            FROM tests as t, expressions as e
            WHERE t.time=-1
                AND t.url=e.url
                AND t.lineNum=e.lineNum
        """

        newCursor = self.db._connection.cursor() # o/w the main cursor may move
        newCursor.execute(query)
        for url, lineNum, method, re_math, re_prog in newCursor:
            yield eval(method + "Bench")(self.db, url, lineNum, method, re_math, re_prog)

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
        print "\n\nSAMPLING STATISTICS:\n"
        print "language           ntotal  ndistinct"
        print "------------------------------------"
        for row in all:
            print row[0].ljust(16), str(row[1]).rjust(8), str(row[2]).rjust(8)

        if all[-1][2] == 0: # 0 distinct
            print "\nNo regular expressions sampled - run `make sample` first"
            exit(0)

    def printBenchmarkStats(self):
        """Prints (stdout) the result statistics from the last benchmark
        and returns (#completed, #todo)"""
        all = self.db.selectall("""
            SELECT method, sum(time)
            FROM tests
            WHERE time!=-1
            GROUP BY method
            ORDER BY sum(time) ASC;
        """)
        print "\n\nBENCHMARKED STATISTICS:\n"
        print "method           sum(min_time)"
        print "------------------------------"
        for row in all:
            print row[0].ljust(16), str(row[1])

        done = self.db.selectall("SELECT count(*) FROM tests WHERE time!=-1;")[0][0]
        todo = self.db.selectall("SELECT count(*) FROM tests WHERE time==-1;")[0][0]
        return (done, todo)



if __name__ == "__main__":
    output = ConsoleOverwrite("Benchmarking: ")
    benchmarker = Benchmarker()

    completed, todo = benchmarker.printBenchmarkStats()
    print "\nCompleted: " + str(completed)
    print "Todo:      " + str(todo)

    if todo == 0:
        if raw_input("\nReset and run benchmark again? y/(n): ") == "y":
            if raw_input("Backup previous results first? (y)/n: ") != "n":
                from datetime import datetime
                newname = ("tests_" + str(datetime.now())).replace(" ", "_")
                benchmarker.db.execute("ALTER TABLE tests RENAME TO ?;", [newname])
                print "Table saved as", newname

            benchmarker = Benchmarker(True)
        else:
            print "Bye!"
            exit(0)
    elif raw_input("\nContinue with {0} more tests? (y)/n: ".format(todo)) == "n":
        print "Bye!"
        exit(0)

    lastExpr = BenchExpr("", "", "", "", "", "")
    done = 0
    for r in benchmarker:
        # take advantage of Benchmarker iteration being ordered by re_math and re-generate words sparingly
        if r.re_math == lastExpr.re_math:
            r.setWords(lastExpr.accepted, lastExpr.rejected)
        else:
            r.genWords()
            lastExpr = r

        try:
            output.overwrite("{0}/{1}:".format(done, todo), r)
            r.benchmark()
        except Exception as e:
            print e
            raw_input("Press Enter to continue ... ")
            print "\n"

        done += 1

    benchmarker.printBenchmarkStats()