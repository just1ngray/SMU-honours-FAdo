from __future__ import print_function
import time
import multiprocessing
import sys
import sqlite3

"""M.M. McKerns, L. Strand, T. Sullivan, A. Fang, M.A.G. Aivazis,
"Building a framework for predictive science", Proceedings of
the 10th Python in Science Conference, 2011;
http://arxiv.org/pdf/1202.1056

Michael McKerns and Michael Aivazis,
"pathos: a framework for heterogeneous computing", 2010- ;
https://uqfoundation.github.io/project/pathos"""
import dill

import util
import convert

class NFASizes():
    def __init__(self):
        pass

    def get_expressions_and_methods(self):
        """Retrieves all distinct non-error FAdoized regular expressions and all nfa construction
        methods as an ordered tuple.
        """
        db = util.DBWrapper()
        expressions = [(x[0], x[0].decode("utf-8")) for x in db.selectall("""
            SELECT DISTINCT re_math
            FROM expressions
            WHERE re_math NOT LIKE '%Error%';
        """)]
        methods = [x[0] for x in db.selectall("""
            SELECT method
            FROM methods
            WHERE method LIKE 'nfa%';
        """)]
        return (expressions, methods)

    def _db_exec(self, ftn):
        db = sqlite3.connect("nfa_constructions.db")
        db.text_factory = str
        cursor = db.cursor()
        result = ftn(cursor)
        db.commit()
        db.close()
        return result

    def _generate_one(self, re, re_math_encoded, method):
        def f(cursor):
            cursor.execute("SELECT count(*) from nfas WHERE re_math==? AND method==?;",
                [re_math_encoded, method])
            if cursor.fetchone()[0] == 0:
                t = time.time()
                nfa = re.toInvariantNFA(method)
                t = time.time() - t
                cursor.execute("""
                    INSERT INTO nfas(re_math, method, nfa, nstates, ntrans, time)
                    VALUES(?, ?, ?, ?, ?, ?);
                """, [re_math_encoded, method, dill.dumps(nfa), len(nfa.States), nfa.countTransitions(), t])

            pm = re.partialMatch()
            pmstr = str(pm).decode("utf-8")
            cursor.execute("SELECT count(*) from nfas WHERE re_math==? AND method==?;",
                [pmstr, method])
            if cursor.fetchone()[0] == 0:
                t = time.time()
                nfa = pm.toInvariantNFA(method)
                t = time.time() - t
                cursor.execute("""
                    INSERT INTO nfas(re_math, method, nfa, nstates, ntrans, time)
                    VALUES(?, ?, ?, ?, ?, ?);
                """, [pmstr, method, dill.dumps(nfa), len(nfa.States), nfa.countTransitions(), t])
        self._db_exec(f)

    def generate_db(self):
        """This saves all relevant NFA's sourced from practical regexps passed through
        all supported constructions. The resulting database should be approximately 600 mb.

        Note: this file is also available as a "release" on this project's GitHub:
            https://github.com/just1ngray/SMUHon-Practical-RE-Membership-Algs/releases/tag/v0.2.0
        """
        expressions, methods = self.get_expressions_and_methods()
        sys.setrecursionlimit(12000)

        self._db_exec(lambda cursor: cursor.executescript("""
            CREATE TABLE IF NOT EXISTS nfas (
                re_math TEXT,
                method  TEXT,
                nfa     BLOB,
                nstates INTEGER,
                ntrans  INTEGER,
                time    REAL,
                PRIMARY KEY (re_math, method)
            );
        """))

        n = 0
        total = len(expressions) * len(methods)
        converter = convert.Converter()
        for re_math_encoded, re_math_parsable in expressions:
            print("\r{}\r{}/{}: {}".format(" "*120, n, total, re_math_encoded[:100]), end="")
            re = converter.math(re_math_parsable)
            for method in methods:
                try:
                    proc = multiprocessing.Process(target=lambda: self._generate_one(re, re_math_encoded, method))
                    proc.start()
                    t = time.time()
                    while proc.is_alive():
                        if time.time() - t > 120:
                            proc.terminate()
                            raise Exception(re_math_encoded + " took too long to calculate " + method)

                except KeyboardInterrupt:
                    if proc is not None and proc.is_alive():
                        proc.terminate()
                    exit(0)
                except:
                    import traceback
                    print("\n" + "-"*80)
                    traceback.print_exc()
                    print("-"*80)
                    raw_input("Enter to continue ...")
                    if proc is not None and proc.is_alive():
                        proc.terminate()
                finally:
                    n += 1

        print("\n\nDone!")

    def extract(self, expression, method):
        def f(cursor):
            cursor.execute("SELECT nfa FROM nfas WHERE re_math==? AND method==?;", [expression, method])
            return cursor.fetchone()

        result = self._db_exec(f)
        if result is None:
            return None
        else:
            return dill.loads(result[0])

if __name__ == "__main__":
    sizes = NFASizes()
    if raw_input("Generate/review... this might take a while y/(n)?: ") == "y":
        sizes.generate_db()
    # todo more