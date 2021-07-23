import sqlite3
import subprocess

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

class OSCommand():
    def __init__(self, cmd=None):
        self.out = ""
        self.code = 0

        if cmd is not None:
            self.run(cmd)

    def run(self, command):
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT)
            self.out = output
            self.code = 0
        except subprocess.CalledProcessError as e:
            self.out = e.output
            self.code = e.returncode

        return (self.out, self.code)

def FAdoize(expression, log=lambda *m: None):
    """Convert an "ambiguous" expression used by a programmer into an expression
    ready to parse into FAdo via the `benchmark/convert.py#Converter` using the
    `benchmark/re.lark` grammar.
    :param str expression: the expression to convert into unambiguous FAdo
    :returns unicode: the parenthesized and formatted expression
    :throws: if `benchmark/sample/parse.js` throws
    """
    cmd = OSCommand()
    output, exitcode = cmd.run([
        'node',
        'benchmark/sample/parse.js',
        expression # automatically handles escaping
    ])

    log("FAdoize output:--------\n", output, "\nend output--------")
    output = output[:-1].splitlines()[-1] # remove the \n and focus on last line

    if exitcode == 0:
        return output.decode("utf-8")
    else:
        raise RuntimeError(str(exitcode) + " Could not FAdoize `" + expression + "`\n" + output)