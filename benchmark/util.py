import sqlite3
import subprocess
import time
import regex

def unicode_ord(c):
    """Get the unicode ordinal value of any <= 4-byte character.
    :param unicode|str c: the character to analyze
    :returns int: the ordinal value of c
    :raises: if c is not length 1
    """
    try:
        return ord(c)
    except:
        try:
            return int(repr(c)[4:-1], 16)
        except ValueError as e:
            raise UnicodeError("Could not convert '" + c + "' to ordinal:", e)

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


def FunctionNotDefined(*x):
    raise NotImplementedError("A required function was not defined")

class RangeList(object):
    """A sorted range-list which automatically maintains sorted order and combines
    ranges as needed. Added items need to be:
        1. Comparable using boolean comparisons
        2. A member of a countable domain
    """
    def __init__(self, iterable=[], inc=FunctionNotDefined, dec=FunctionNotDefined):
        """Create a new RangeList.
        :param function inc: increment an element
        :param function dec: decrement an element
        :param list|set iterable: elements of type T as: Union(T, Tuple(T, T))
        """
        super(RangeList, self).__init__()
        self.inc = inc
        self.dec = dec
        self._list = []
        for i in iterable:
            if type(i) is tuple:
                self.add(i[0], i[1])
            else:
                self.add(i)

    def __str__(self):
        return str(self._list)

    def __getitem__(self, index):
        return self._list[index]

    def __len__(self):
        return len(self._list)

    def __iter__(self):
        return iter(self._list)

    def search(self, n):
        """Finds the range's index which contains n. If no range contains n,
        then the index where the range would be is returned.
        :param n: the item to search for
        :returns int: the index as described above
        """
        lo = 0
        hi = len(self) # exclusive index, but self._list[X][1] is inclusive
        mid = (hi + lo) // 2

        while lo <= mid and mid < hi:
            a, b = self[mid]        # ----a-----b----
            if n < a:               # -n--a-----b----
                hi = mid
            elif b < n:             # ----a-----b--n-
                lo = mid + 1
            else: # a <= n <= b     # ----a--n--b----
                return mid
            mid = (hi + lo) // 2
        return mid

    def indexOf(self, n):
        """Finds the index of item n in ranges
        :param n: the item to search for
        :returns int: the index of the range which contains n, or -1 if
        no range contains n
        """
        i = self.search(n)
        return i if self.indexContains(i, n) else -1

    def indexContains(self, index, n):
        """Tests if the range at an index contains n
        :param int index: the range index to check
        :param n: the item the range should contain
        :returns Bool: if the range at index contains n
        """
        if index < len(self):
            a, b = self[index]
            if a <= n and n <= b:
                return True
        return False

    def add(self, lo, hi=None):
        """Add a range to this list while maintaining sorted order and merging elements if needed.
        :param lo: the low-end of the range (inclusive)
        :param hi: the high-end of the range (inclusive)
            ..note: if None: defaults to lo
        """
        if hi is None:
            hi = lo
        assert lo <= hi, "Illegally formed range has a lower bound greater than its upper!"

        lo_i = self.search(lo)
        hi_i = lo_i if lo == hi else self.search(hi)

        if lo_i == hi_i:
            i = lo_i
            if i >= len(self) or hi < self[i][0] or lo > self[i][1]:
                # "insert no-overlap" case
                self._list.insert(i, (lo, hi))
            else:
                # "extend down/contained" case
                self._list[i] = (min(lo, self[i][0]), max(hi, self[i][1]))
        elif lo_i + 1 == hi_i and \
            (hi_i < len(self) and (self[hi_i][0] > hi or hi >= self[hi_i][1])): # eq. indexOf(hi) == -1
            # "extend up" case
            self._list[lo_i] = (self[lo_i][0], hi)
        else:
            # "merge" case
            if not (hi_i < len(self) and hi == self[hi_i][1]):
                hi_i -= 1

            end = self[hi_i][1]
            del self._list[lo_i + 1:hi_i + 1]
            self._list[lo_i] = (min(self[lo_i][0], lo), max(end, hi))

    def remove(self, lo, hi=None):
        """Remove [lo,hi] from this range list.
        :param lo: the low-end of the range (inclusive)
        :param hi: the high-end of the range (inclusive)
            ..note: if None: defaults to lo
        ..note: this function requires the inc and dec functions to be defined
        """
        if hi is None:
            hi = lo
        assert lo <= hi, "Illegally formed range has a lower bound greater than its upper!"

        lo_i = self.search(lo)
        hi_i = lo_i if lo == hi else self.search(hi)

        if lo_i == hi_i:
            i = lo_i
            if i < len(self) and hi >= self[i][0] and lo <= self[i][1]:
                toConsider = [(self[i][0], min(self[i][1], self.dec(lo))),
                              (max(self[i][0], self.inc(hi)), self[i][1])]
                del self._list[i]
                for a, b in toConsider:
                    if a <= b:
                        self._list.insert(i, (a, b))
                        i += 1
        elif lo_i + 1 == hi_i and \
            (hi_i < len(self) and (self[hi_i][0] > hi or hi >= self[hi_i][1])):
            self._list[lo_i] = (self[lo_i][0], self.dec(lo))
        else:
            if hi_i >= len(self):
                hi_i -= 1

            start, end = self[hi_i]
            del self._list[lo_i + 2:hi_i + 1]

            self._list[lo_i] = (self[lo_i][0], self.dec(lo))
            self._list[lo_i + 1] = (self.inc(hi) if hi >= start else start, end)

            if self[lo_i][0] > self[lo_i][1]:
                del self._list[lo_i]
            if self[lo_i][0] > self[lo_i][1]:
                del self._list[lo_i]

    def intersection(self, other):
        """Finds the intersection between self and other
        :param RangeList other: the other list to intersect with
        :returns RangeList: with the intersection of self and other
        ..see: https://leetcode.com/problems/interval-list-intersections/solution/
        """
        if type(other) is not RangeList:
            raise TypeError("Cannot intersection with type: " + str(type(other)))

        inter = []
        si = 0
        oi = 0
        while si < len(self) and oi < len(other):
            lo = max(self[si][0], other[oi][0])
            hi = min(self[si][1], other[oi][1])
            if lo <= hi:
                inter.append((lo, hi))

            if self[si][1] < other[oi][1]:
                si += 1
            else:
                oi += 1

        intersectList = RangeList(inc=self.inc, dec=self.dec)
        intersectList._list = inter
        return intersectList