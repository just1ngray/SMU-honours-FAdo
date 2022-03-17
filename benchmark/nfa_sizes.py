from __future__ import print_function
import matplotlib
matplotlib.use('WebAgg') # TkAgg work well for native display
import matplotlib.pyplot as plt
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
    """Use as a command-line utility using `make sizes` unless extracting from the
    resulting database. If extracting, instantiate the object and call `#extract()`
    as needed.
    """
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

    def extract(self, expression, method):
        """Retrieve a NFA from the database given a regular expression and construction method.
        If no such NFA exists for that method, this returns None.

        Completion notes: (see `#print_completeness()`)
        - to get partial derivative NFA, use nfaPDDAG as your method (not nfaPDO or nfaRPN)
        - the Thompson construction is likely to be incomplete as well (since this construction has a
          lot of 'wasted' work when creating @epsilon transitions)
        """
        def f(cursor):
            cursor.execute("SELECT nfa FROM nfas WHERE re_math==? AND method==?;", [expression, method])
            return cursor.fetchone()

        result = self._db_exec(f)
        if result is None:
            return None
        else:
            return dill.loads(result[0])

    def print_completeness(self):
        """Prints to stdout the number of NFAs for each construction type and the time it took to make them.
        This is useful since some construction methods may have been too slow to add the resulting NFA to
        this database.
        """
        def f(cursor):
            cursor.execute("""
                SELECT method, count(re_math) as n, sum(time)
                FROM nfas
                GROUP BY method
                ORDER BY n DESC;
            """)
            for method, count, sum_time in cursor.fetchall():
                print(method[len("nfa"):].ljust(12), str(count).ljust(6), sum_time)
        print("construction count  sum(time)")
        print("-----------------------------")
        self._db_exec(f)

    def build_common_regexps(self):
        """Creates the common_re table if it does not exist. This table contains a set
        of regular expressions that could be converted into NFA's using every algorithm
        in less than 120 seconds.
        """
        def f(cursor):
            cursor.execute("SELECT DISTINCT method FROM nfas;")
            constructions = [x[0] for x in cursor.fetchall()]
            queries = list()
            for method in constructions:
                queries.append("SELECT DISTINCT re_math FROM nfas WHERE method=='{}'".format(method))
            query = "\nINTERSECT\n".join(queries) + ";"

            cursor.execute("CREATE TABLE IF NOT EXISTS common_re AS " + query)
        self._db_exec(f)

    def display(self, resolution=10):
        """Display NFA sizes for regular expression lengths by construction algorithm.

        Note: Since some construction times took too long, some RE->NFA's couldn't be done
            for some algorithms. Use `#print_completeness()` to see for yourself.
            Therefore the graph will only display construction data for regular expressions
            that could be converted using every NFA construction algorithm.
        """
        db = util.DBWrapper()
        methods = dict() # nfaMETHOD -> Color String
        for method, color in db.selectall("SELECT method, colour FROM methods WHERE method LIKE 'nfa%';"):
            methods[method] = color

        fig, ax = plt.subplots()
        line2d = dict()

        self.build_common_regexps()
        def _add_plots(cursor):
            for method, color in methods.items():
                x = []
                y = []
                cursor.execute("""
                    SELECT avg(length(re_math)) as length, avg(nstates+ntrans) as size
                    FROM nfas
                    WHERE method==?
                        AND length(re_math)<1600
                        AND re_math IN (SELECT re_math FROM common_re)
                    GROUP BY length(re_math)/?
                    ORDER BY length(re_math) ASC;
                """, [method, resolution])
                for length, size in cursor.fetchall():
                    x.append(length)
                    y.append(size)
                method = method[len("nfa"):] # remove prefix nfa
                line2d[method] = ax.plot(x, y, label=method, linewidth=1, color=color)[0]
        self._db_exec(_add_plots)

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

        plt.ylim(ymin=0)
        plt.connect("pick_event", _on_pick)
        plt.title("RE to NFA Size by Construction Algorithm")
        plt.xlabel("Regular Expression String Length (# chars)\nGrouped in bins of size {}".format(resolution))
        plt.ylabel("NFA Size (#states + #transitions)")
        plt.show()

if __name__ == "__main__":
    sizes = NFASizes()

    choice = "1"
    while choice != "Q":
        print("\n")
        print("C. Construct NFA's for yourself (rather than quick download)")
        print("P. Print completeness of each algorithm")
        print("D. Display graph")
        print("Q. Quit")
        choice = raw_input("Choose menu option: ").upper().lstrip()

        if choice == "C":
            print("This might take a while... Ctrl+C to interrupt")
            sizes.generate_db()
            raw_input("\nPress Enter to continue... ")
        elif choice == "P":
            sizes.print_completeness()
            raw_input("\nPress Enter to continue... ")
        elif choice == "D":
            print("\nDrawing NFA size graph by construction algorithm...")
            res = util.parseIntSafe(raw_input("How detailed should the graph be (higher=less detailed): "), 10)
            sizes.display(res)

    print("\nBye!")