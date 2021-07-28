import urllib
import json
import sqlite3
import lark.exceptions
import regex

from .util import DBWrapper, FAdoize

class Sampler(object):
    def __init__(self, language, search, verbose=0):
        """Create a new sampler
        :param str language: the language being sampled
        :param str search: the search to preform on grep.app
        :param int verbose: the level of logging
            0 => silent
            1 => errors only
            2 => all logging
        """
        super(Sampler, self).__init__()
        self.language = language
        self.full_sample_search = search

        self.log = lambda *m: None
        self.error = lambda *m: None
        if verbose > 0:
            def printit(*items):
                if len(items) > 0:
                    for i in items[:-1]:
                        print self.language + ": ", i,
                    print self.language + ": ", items[-1]
            if verbose >= 1:
                self.error = printit
            if verbose >= 2:
                self.log = printit

    def full_sample(self, maxTotalMatches=350):
        """Runs a the full sampling process for a collection of searches
        :param list<unicode> searches: the RE2-formatted searches to perform
        :param int maxTotalMatches: the maximum number of matches that should be
            returned (used only as a guideline)
        :returns set<unicode>: valid expressions inputted into the database
        """
        self.log("full_sample")
        expressions = set()

        urls = self.grep_search(self.full_sample_search, maxTotalMatches)
        for url in urls:
            code = self.get_github(url)
            expressions.update(self.process_codefile(code, url))

        return expressions

    def grep_search(self, re, minMatches):
        """A function that collects GitHub URLs that match a language and
        regular expression indexed by the https://grep.app API.
        :param str re: the RE2 syntax expression for searching
            (https://github.com/google/re2/wiki/Syntax)
        :param int minMatches: the minimum number of matches desired (reflects
            the number of `re` matches, not returned URLs). Note that a search
            for `re` is not guaranteed to have enough pages of results to meet
            this number.
        :returns set<unicode>: set of raw.githubusercontent.com URLs which
            contain at least one match of `re`
        """
        results = set()
        matches = 0

        params = {
            'q': re,
            'lang': self.language,
            'regexp': True
        }
        baseurl = "https://grep.app/api/search?" + urllib.urlencode(params)
        page = 0
        while matches < minMatches:
            page += 1

            page = urllib.urlopen(baseurl + "page=" + str(page))
            content = json.loads("\n".join(page.readlines()))
            hits = content["hits"]["hits"] # type: list<dict>
            if len(hits) == 0:
                break

            for hit in hits:
                user_repo = hit["repo"]["raw"]
                branch = hit["branch"]["raw"] if hit.has_key("branch") else "master"
                filename = hit["path"]["raw"]
                matches += int(hit["total_matches"]["raw"].split("+")[0])

                url = u"https://raw.githubusercontent.com/{user_repo}/{branch}/{path}" \
                    .format(user_repo=user_repo, branch=branch, path=filename)
                results.add(url)
                self.log("grep_search found: " + url)

        # add to DB
        db = DBWrapper()
        for res in results:
            db.execute("INSERT OR IGNORE INTO github_urls (url) VALUES (?);", [res])

        return results

    def get_github(self, url):
        """Gets the code from a raw github page and returns line-delimited list
        :param unicode url: the raw github url where the code can be downloaded
        :returns list<unicode>: the code line by line
        """
        self.log("get_github: " + url)
        page = urllib.urlopen(url)
        return page.read().splitlines()

    def process_codefile(self, lines, fromFile="Unspecified"):
        """Processes lines of code and searches for contained regular expressions using
        the #get_line_expression method.
        :param list<unicode> lines: the lines to search for regular expressions
        :param unicode fromFile: the URL of the codefile to be stored in the database
        :returns list<unicode>: formatted and working expressions
        """
        db = DBWrapper()
        expressions = list()

        lineNum = 0
        for line in lines:
            lineNum += 1

            expr = self.get_line_expression(line)
            if expr is None:
                continue
            self.log(str(lineNum) + "\t" + line[:50] + " => " + expr)

            try:
                formatted = FAdoize(expr, log=self.log)
                db.execute("""
                    INSERT OR IGNORE INTO expressions (re, url, lineNum, lang)
                    VALUES (?, ?, ?, ?);""", [formatted, fromFile, lineNum, self.language])
                expressions.append(formatted)
            except Exception as e:
                self.error(e)

        db.execute("""
            UPDATE github_urls
            SET searched=datetime('now', 'localtime')
            WHERE url=?;
        """, [fromFile])
        return expressions

    # abstractmethod
    def get_line_expression(self, line):
        """Extracts a regular expression from a line of code, or None if the line
        doesn't include a regular expression.
        :param unicode line: the line of code on which to search for an expression
        :returns unicode|None: the extracted expression

        >>> sampler = SamplerChild()
        >>> sampler.get_line_expression(u"matchObj = re.match(r'(.*) are (.*?) .*', line, re.M|re.I)")
        (.*) are (.*?) .*
        """
        raise NotImplementedError("get_line_expression must be overridden in child")


class PythonSampler(Sampler):
    def __init__(self, verbose=0):
        super(PythonSampler, self).__init__("Python",
            r"""re\.(search|match|compile|split|sub|findall|finditer)\(""",
            verbose=verbose)

    def get_line_expression(self, line):
        match = regex.search(r"""re\.(search|match|compile|split|sub|findall|finditer)\([bur ]*["']""", line)
        if match is None:
            return None

        sub = line[match.end():]
        # if regex.search(r"""\([bu ]*r[bu]*["']""", match.group(0)):
        #     pass

        match = regex.search(r"""^(\\.|[^\\])*?["'][,)]""", sub)
        if match is None:
            return None

        expression = match.group(0)[:-2] # remove ["'][,)]
        expression = expression.replace("(?i", "(") # local case insensitive

        return expression


if __name__ == "__main__":
    pass