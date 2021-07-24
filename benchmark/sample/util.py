import sqlite3
import subprocess
import time
import atexit

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

class NodeJSProcess():
    def __init__(self, filename):
        self.cmd = filename
        self.proc = subprocess.Popen(["node", filename],
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)

        atexit.register(lambda: self.proc.terminate())

    def send(self, data):
        """Send data to the NodeJS process, read stdout until "Done\n"
        """
        self.proc.stdin.write(data.encode("utf-8"))
        self.proc.stdin.flush()

        lines = [""]
        while lines[-1] != "Done\n":
            # very short-duration "spinlock"
            t = time.time()
            while time.time() - t < 0.00001:
                continue

            lines.append(self.proc.stdout.readline())

        return list(map(lambda x: x[0:-1], lines))


proc = None
def FAdoize(expression, log=lambda *m: None):
    """Convert an "ambiguous" expression used by a programmer into an expression
    ready to parse into FAdo via the `benchmark/convert.py#Converter` using the
    `benchmark/re.lark` grammar.
    :param str expression: the expression to convert into unambiguous FAdo
    :returns unicode: the parenthesized and formatted expression
    :throws: if `benchmark/sample/parse.js` throws
    ..note: FAdoize will include a cold start time as the NodeJS process is created.
            Subsequent calls will not incur this cost until this Python process finishes.
    """
    if globals()["proc"] is None:
        globals()["proc"] = NodeJSProcess("benchmark/sample/parse.js")

    output = globals()["proc"].send(expression)

    log("FAdoize output:--------\n", output, "\nend output--------")
    output = output[-2]

    if not output.startswith("ERROR"):
        return output.decode("utf-8")
    else:
        raise RuntimeError("Could not FAdoize `" + expression + "`\n" + output)