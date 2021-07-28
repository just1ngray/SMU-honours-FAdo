import sqlite3
import subprocess
import time
import regex
import bisect

def unicode_ord(c):
    """Get the unicode ordinal value of any <= 4-byte character.
    :param unicode|str c: the character to analyze
    :returns int: the ordinal value of c
    :raises: if c is not length 1
    """
    try:
        return ord(c)
    except:
        return int(repr(c)[4:-1], 16)

def unicode_chr(i):
    """Get the unicode character from an ordinal number.
    :param int i: the ordinal to retrieve the character of
    :returns unicode: the character with ordinal i
    ..based on: https://stackoverflow.com/a/7107319
    """
    try:
        return unichr(i)
    except:
        s = "\\U%08x" % i
        c = s.decode("unicode-escape")
        return c.encode("utf-8")

class DBWrapper(object):
    def __init__(self):
        super(DBWrapper, self).__init__()
        self.name = "database.db"
        self._connection = sqlite3.connect(self.name)
        self._cursor = self._connection.cursor()

        # setup tables
        self.executescript("""
            CREATE TABLE IF NOT EXISTS languages (
                lang TEXT PRIMARY KEY
            );
            INSERT OR IGNORE INTO languages (lang) VALUES ('C++');
            INSERT OR IGNORE INTO languages (lang) VALUES ('C#');
            INSERT OR IGNORE INTO languages (lang) VALUES ('Java');
            INSERT OR IGNORE INTO languages (lang) VALUES ('JavaScript');
            INSERT OR IGNORE INTO languages (lang) VALUES ('TypeScript');
            INSERT OR IGNORE INTO languages (lang) VALUES ('Python');
            INSERT OR IGNORE INTO languages (lang) VALUES ('Perl');
            INSERT OR IGNORE INTO languages (lang) VALUES ('PHP');


            CREATE TABLE IF NOT EXISTS github_urls (
                url         TEXT PRIMARY KEY,
                searched    INTEGER DEFAULT -1
            );

            CREATE TABLE IF NOT EXISTS expressions (
                re      TEXT PRIMARY KEY,
                url     TEXT,
                lineNum INTEGER,
                lang    TEXT,
                FOREIGN KEY (lang) REFERENCES languages (lang),
                FOREIGN KEY (url) REFERENCES github_urls (url)
            );
        """)

    def executescript(self, script):
        self._commit_rollback(lambda: self._cursor.executescript(script))

    # def executemany(self, cmd, params=[]):
    #     self._commit_rollback(lambda: self._cursor.executemany(cmd, params))

    def execute(self, cmd, params=[]):
        self._commit_rollback(lambda: self._cursor.execute(cmd, params))

    def _commit_rollback(self, ftn):
        try:
            ftn()
            self._connection.commit()
        except:
            self._connection.rollback()
            raise


nodejs_proc = None
def FAdoize(expression, log=lambda *m: None):
    """Convert an "ambiguous" expression used by a programmer into an expression
    ready to parse into FAdo via the `benchmark/convert.py#Converter` using the
    `benchmark/re.lark` grammar.
    :param str expression: the expression to convert into unambiguous FAdo
        note: Escaped characters must be preceeded with a single backslash
    :returns unicode: the parenthesized and formatted expression
    :throws: if `benchmark/parse.js` throws
    ..note: FAdoize will include a cold start time as the NodeJS process is created.
            Subsequent calls will not incur this cost until this Python process finishes.
    """
    # regexp-tree doesn't support repetition in the form a{,n} as a{0,n}... convert manually
    def repl(match):
        return "{0," + match[2:-1] + "}"
    expression = regex.sub(r"\{,[0-9]+\}", lambda x: repl(x.group()), expression)

    if globals()["nodejs_proc"] is None:
        import atexit
        class NodeJSProcess():
            def __init__(self, filename):
                self.cmd = filename
                self.proc = subprocess.Popen(["node", filename],
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE)

                atexit.register(lambda: self.proc.terminate())

            def send(self, data):
                self.proc.stdin.write(data.encode("utf-8"))
                self.proc.stdin.flush()

                lines = [""]
                while lines[-1] != "> Done0! <\n":
                    # very short-duration "spinlock"
                    t = time.time()
                    while time.time() - t < 0.00001:
                        continue

                    lines.append(self.proc.stdout.readline())
                return list(map(lambda x: x[0:-1], lines))

        globals()["nodejs_proc"] = NodeJSProcess("benchmark/parse.js")

    output = globals()["nodejs_proc"].send(expression)
    log("FAdoize output:--------\n", output, "\nend output--------")
    converted = output[-2]

    if not converted.startswith("ERROR"):
        return converted.decode("utf-8")
    else:
        raise RuntimeError("Could not FAdoize `" + expression + "`\n"
            + reduce(lambda p, c: p + "\n" + c, output))

class SortedList():
    """A sorted data structure, where each item is sorted by its representing item.
    I.e., this can be used to store sorted tuples, where each tuple is sorted by
        its first value
    """
    def __init__(self, rep=lambda x: x):
        super(SortedList, self).__init__()
        self.list = []
        self.reps = []
        self.rep = rep

    def __getitem__(self, index):
        return self.list[index]

    def add(self, item):
        """Add item to the internal list while maintaining sorted order
        :returns int: the index at which the item has been inserted
        """
        index = bisect.insort_left(self.reps, self.rep(item))
        self.list.insert(index, item)
        return index

    def set(self, sortedlist):
        """Sets the internal list structure
        :param list sortedlist: the list which is assumed to be sorted
        """
        self.list = sortedlist
        self.reps = list(map(self.rep, sortedlist))

    def get(self):
        """:returns list: the interal sorted list"""
        return self.list

    def index(self, item):
        """Finds the index of an item in the list
        :param rep: the item to search for
        :returns int: the index of the item, or -1 if it doesn't exist
        """
        i = bisect.bisect_left(self.reps, self.rep(item))
        if i != len(self.reps) and self.reps[i] == self.rep(item):
            return i
        return -1

    def index_lte(self, item):
        """Finds the first index of an item in the list where self[index]>=item
        :param item: the item to search for
        :returns int|None: the minimum index which satisfies self[index]>=item,
            or None if no index satisfies this property
        """
        i = bisect.bisect_right(self.reps, self.rep(item))
        return i if i else None