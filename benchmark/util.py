import sqlite3
import subprocess
import regex
import lark
import sys
import json
from random import randint

charlist_grammar = None
class UniUtil():
    @staticmethod
    def charlist(word):
        """Splits a unicode string into its individual displayable
        characters and returns in list form.
        :param unicode word: the word to retrieve characters from
        :returns list<unicode>: the individual characters of word
        """
        if len(word) <= 1:
            return list(word)

        if globals()["charlist_grammar"] is None:
            class Transformer(lark.Transformer):
                utf8 = lambda _, t: t
                ASCII = lambda _, s: s.value
                BYTES = lambda _, b: b.value.decode("string-escape").decode("utf-8")

            globals()["charlist_grammar"] = lark.Lark.open("benchmark/re.lark", start="utf8",
                parser="lalr", transformer=Transformer())

        encoded = repr(word.encode("utf-8"))[1:-1]
        return globals()["charlist_grammar"].parse(encoded)

    @staticmethod
    def ord(c):
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

    @staticmethod
    def chr(i):
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

class ConsoleOverwrite():
    """Print to console and overwrite the last printed item."""
    def __init__(self, prefix=""):
        self.prefix = prefix
        self._lastlen = 0
        self._width = self._terminal_size()[0] - 4

    def overwrite(self, *items):
        print "\r" + " "*self._lastlen + "\r",

        content = self.prefix + reduce(lambda p, c: p + " " + str(c), items, "")
        content = content.replace("\t", "    ")
        if len(content) > self._width:
            content = content[:self._width - 3] + "..."
        self._lastlen = len(content)

        print content,
        sys.stdout.flush()

    def _terminal_size(self):
        """Finds terminal size.
        https://www.w3resource.com/python-exercises/python-basic-exercise-56.php
        """
        import fcntl, termios, struct
        th, tw, hp, wp = struct.unpack('HHHH',
            fcntl.ioctl(0, termios.TIOCGWINSZ,
            struct.pack('HHHH', 0, 0, 0, 0)))
        return tw, th

class DBWrapper(object):
    def __init__(self, name="database.db"):
        super(DBWrapper, self).__init__()
        self.name = name
        self._connection = sqlite3.connect(self.name)
        self._connection.text_factory = str
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
                lang        TEXT,
                searched    INTEGER DEFAULT -1,
                FOREIGN KEY (lang) REFERENCES languages (lang)
            );

            CREATE TABLE IF NOT EXISTS expressions (
                re_math TEXT,
                re_prog TEXT,
                line    TEXT,
                url     TEXT,
                lineNum INTEGER,
                lang    TEXT,
                FOREIGN KEY (lang) REFERENCES languages (lang),
                FOREIGN KEY (url) REFERENCES github_urls (url),
                PRIMARY KEY (url, line)
            );
        """)

    def executescript(self, script):
        """Executes a script that can have extra parameters, but cannot contain
        dynamic data"""
        self._commit_rollback(lambda: self._cursor.executescript(script))

    def execute(self, cmd, params=[]):
        """Executes a command with optional parameters"""
        self._commit_rollback(lambda: self._cursor.execute(cmd, params))

    def _commit_rollback(self, ftn):
        try:
            ftn()
            self._connection.commit()
        except:
            self._connection.rollback()
            raise

    def selectall(self, cmd, params=[]):
        """Query via SELECT cmd all that match predicate"""
        self._cursor.execute(cmd, params)
        return self._cursor.fetchall()

class FAdoizeError(Exception):
    def __init__(self, expression, node_callback):
        super(FAdoizeError, self).__init__()
        self.expression = expression
        self.node_callback = node_callback

    def __str__(self):
        return "FAdoizeError on '{0}':\n{1}".format(self.expression, self.node_callback)

nodejs_proc = None
def FAdoize(expression):
    """Convert an "ambiguous" expression used by a programmer into an expression
    ready to parse into FAdo via the `benchmark/convert.py#Converter` using the
    `benchmark/re.lark` grammar.
    :param unicode|str expression: the expression to convert into unambiguous FAdo
    :returns unicode: the parenthesized and formatted expression
    :raises FAdoizeError: if `benchmark/parse.js` throws
    ..note: FAdoize will include a cold start time as the NodeJS process is created.
            Subsequent calls will not incur this cost until this Python process finishes.
    """
    # regexp-tree doesn't support repetition in the form a{,n} as a{0,n}... convert manually
    def repl(match):
        return "{0," + match[2:-1] + "}"
    expression = regex.sub(r"\{,[0-9]+\}", lambda x: repl(x.group()), expression)

    # remove redundant (and invalid) escapes
    valids = set("sSwWdDtnrfvuU\\^$.()[]+*{}bB0123456789")
    i = 0
    while True:
        try:
            index = expression.index("\\", i)
            if expression[index + 1] not in valids:
                expression = expression[:index] + expression[index+1:]
                i = index
            else:
                i = index + 1
        except (IndexError, ValueError):
            break

    if globals()["nodejs_proc"] is None:
        globals()["nodejs_proc"] = subprocess.Popen(["node", "benchmark/parse.js"],
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)

        import atexit
        atexit.register(lambda: globals()["nodejs_proc"].terminate())

    if len(expression) == 0:
        raise FAdoizeError(expression, "Expression must have a length > 0")

    if type(expression) is unicode: # ensure expression is utf-8 encoded string
        expression = expression.encode("utf-8")

    proc = globals()["nodejs_proc"]
    proc.stdin.write(expression)
    proc.stdin.flush()
    output = json.loads(proc.stdout.readline())

    if output["error"] != 0:
        logs = reduce(lambda p, c: p + "\n" + c, output["logs"])
        logs_and_callback = (logs + "\n\n" + output["error"]).encode("utf-8")
        raise FAdoizeError(expression, logs_and_callback)
    else:
        return output["formatted"] # unicode


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

class WeightedRandomItem():
    """A class to choose a random item according to their weight values"""
    def __init__(self):
        self.items = list()
        self.minWeight = None
        self.totalWeight = 0

    def add(self, weight, item):
        """Add an item with positive (>0) weight to the collection"""
        assert weight > 0, "Weight must be an int > 0"
        if self.minWeight is None:
            self.minWeight = weight

        self.totalWeight += weight
        self.items.append((self.totalWeight, item))

    def get(self):
        """Retrieve a random item from the collection respective to weightage"""
        if self.minWeight is None:
            return None

        randweight = randint(self.minWeight, self.totalWeight)

        lo, hi = 0, len(self.items)
        mid = (lo + hi) // 2
        while lo <= mid and mid < hi:
            weight = self.items[mid][0]
            if weight > randweight:
                hi = mid # bisect low
            elif weight < randweight:
                lo = mid + 1 # bisect high
            else:
                break
            mid = (lo + hi) // 2

        if mid == len(self.items):
            mid -= 1
        return self.items[mid][1]

class Deque(object):
    """Double ended-queue implementation with constant-time operations unless
    otherwise noted.
    """
    def __init__(self, iterable=[]):
        super(Deque, self).__init__()
        self._head = None
        self._tail = None
        self._size = 0

        for item in iterable:
            self.insert_right(item)

    def __iter__(self):
        """O(n)"""
        current = self._head
        while current is not None:
            yield current[1]
            current = current[2]

    def __str__(self):
        """O(n)"""
        return "[{0}]".format(reduce(lambda p,c: p+", "+str(c), self, "")[2:])

    def __repr__(self):
        """O(n)"""
        return "Deque({0})".format(str(self))

    def __len__(self):
        return self._size

    def isEmpty(self):
        return self._size == 0

    def insert_left(self, item):
        self._size += 1

        mem = [None, item, self._head]
        if self._head is None:
            self._head = mem
        else:
            self._head[0] = mem
            self._head = mem
        if self._tail is None:
            self._tail = mem

    def insert_right(self, item):
        self._size += 1

        mem = [self._tail, item, None]
        if self._tail is None:
            self._tail = mem
        else:
            self._tail[2] = mem
            self._tail = mem
        if self._head is None:
            self._head = mem

    def peek_left(self):
        return self._head[1]

    def peek_right(self):
        return self._tail[1]

    def pop_left(self):
        if self.isEmpty():
            raise IndexError("Cannot pop an empty deque")

        item = self._head[1]
        self._head = self._head[2]
        self._size -= 1
        if self._size == 0:
            self._head = None
            self._tail = None
        else:
            self._head[0] = None

        return item

    def pop_right(self):
        if self.isEmpty():
            raise IndexError("Cannot pop an empty deque")

        item = self._tail[1]
        self._tail = self._tail[0]
        self._size -= 1
        if self._size == 0:
            self._head = None
            self._tail = None
        else:
            self._tail[2] = None

        return item