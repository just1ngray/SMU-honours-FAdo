import sqlite3
from lark.exceptions import UnexpectedToken as LarkUnexpectedToken
from random import randint

from convert import Converter
from fa_ext import InvariantNFA

def main():
    # db_connection = sqlite3.connect("database.db")
    # db_cursor = db_connection.cursor()
    # db_cursor.executescript("""
    #     CREATE TABLE IF NOT EXISTS words (
    #         expr_id INTEGER NOT NULL,
    #         word    TEXT NOT NULL,
    #         PRIMARY KEY (expr_id, word),
    #         FOREIGN KEY (expr_id) REFERENCES expression (id)
    #     );
    #     CREATE INDEX IF NOT EXISTS words_expr_id on words (expr_id);
    # """)
    # db_connection.commit()

    convert = Converter()
    file = open("export.csv", "r")

    succ, fail = 0, 0
    for expr in file.readlines():
        expr = expr[:-1] # remove newline encoding

        try:
            print "\n", expr[:80]
            convert.one(expr, partialMatch=True)            # must work both with partialMatch
            # regexp = convert.one(expr, partialMatch=False)  # and without (this is how words are generated)
            # infa = InvariantNFA(regexp.nfaPD())
            # db_cursor.execute("INSERT OR IGNORE INTO expression (regexp) VALUES (?);", [expr])
            # db_cursor.execute("SELECT seq FROM sqlite_sequence WHERE name='expression';")
            # expr_id = db_cursor.fetchone()[0]

            # i = 0
            # for word in infa.language():
            #     db_cursor.execute("INSERT OR IGNORE INTO words (expr_id, word) VALUES (?, ?);", [expr_id, word])
            #     i += 1
            #     if i > 100: break

            # db_connection.commit()
            succ += 1
        except LarkUnexpectedToken:
            fail += 1
            # db_connection.rollback()
        except Exception as exception:
            if "character class contains no accepted characters" in exception.args[0] \
                    or "maximum recursion depth exceeded" in exception.args[0]:
                pass
            else:
                raise

            fail += 1
            # db_connection.rollback()

    file.close()
    # db_connection.close()
    print "\n Read", succ, "expressions successfully, and", fail, "failures"


if __name__ == "__main__":
    main()