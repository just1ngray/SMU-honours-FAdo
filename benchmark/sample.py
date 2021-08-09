import urllib
import json
import regex

from util import DBWrapper, FAdoize, ConsoleOverwrite

class CodeSampler(object):
    def __init__(self, language, search):
        """Create a new sampler
        :param str language: the language being sampled
        :param str search: the search to preform on grep.app
        :param int verbose: the level of logging
            0 => silent
            1 => errors only
            2 => all logging
        """
        super(CodeSampler, self).__init__()
        self.language = language
        self.search_expr = search
        self.cow = ConsoleOverwrite()

    def _printTask(self, *items):
        items = list(items)
        items.insert(0, self.language + "Sampler:")
        self.cow.overwrite(items)

    def grep_search(self, re, minMatches):
        """A function that collects GitHub URLs that match a language and
        regular expression indexed by the https://grep.app API.
        :param str re: the RE2 syntax expression for searching
            (https://github.com/google/re2/wiki/Syntax)
        :param int minMatches: the minimum number of matches desired (reflects
            the number of `re` matches, not returned URLs). Note that a search
            for `re` is not guaranteed to have enough pages of results to meet
            this number.
            Additionally - grep.app utilizes a simplified search and will match
            more lines of code than #get_line_expression
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
        pageNum = 0
        while matches < minMatches:
            pageNum += 1
            self._printTask("grep_search {0}".format(pageNum))

            page = urllib.urlopen(baseurl + "&page=" + str(pageNum))
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
        self._printTask("get_github: " + url)
        page = urllib.urlopen(url)
        return page.read().splitlines()

    def process_codefile(self, lines, fromFile="Unspecified"):
        """Processes lines of code and searches for contained regular expressions using
        the #get_line_expression method.
        :param list<unicode> lines: the lines to search for regular expressions
        :param unicode fromFile: the URL of the codefile to be stored in the database
        :returns list<unicode>: formatted and working expressions
        """
        self._printTask("process_codefile 0")
        db = DBWrapper()
        expressions = list()

        lineNum = 0
        for line in lines:
            lineNum += 1

            expr = self.get_line_expression(line)
            if expr is None:
                continue

            try:
                formatted = FAdoize(expr)
                db.execute("""
                    INSERT OR IGNORE INTO expressions (re, url, lineNum, line, lang)
                    VALUES (?, ?, ?, ?, ?);""", [formatted, fromFile, lineNum, line, self.language])
                expressions.append(formatted)
                self._printTask("process_codefile {1} found - {0}".format(fromFile, len(expressions)))
            except Exception as e:
                print e

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


class PythonSampler(CodeSampler):
    def __init__(self):
        super(PythonSampler, self).__init__("Python",
            r"""re(gex)?\.(search|match|compile|split|sub|find(all|iter|match))\(""")

        self.re_begin = regex.compile(
            r"""re(gex)?\.(search|match|compile|split|sub|findall|finditer|fullmatch)\([bur ]*("|'|("")"|''')""")

        self.re_expr_single = regex.compile(r"""^(\\.|[^\\])*?'[,)]""")
        self.re_expr_double = regex.compile(r"""^(\\.|[^\\])*?"[,)]""")
        self.re_expr_1triple = regex.compile(r"^(\\.|[^\\])*?'''[,)]")
        self.re_expr_2triple = regex.compile(r'^(\\.|[^\\])*?"""[,)]')

    def get_line_expression(self, line):
        match = self.re_begin.search(line)
        if match is None:
            return None
        end = line[match.end():] # start of the expression to the end of the line

        extract = lambda _: None
        delim = match.group(0)[match.group(0).rfind("("):]
        isRaw = delim.find("r") > -1

        def getExpr(re, word, endindex):
            match = re.search(word)
            if match is None:
                return None
            else:
                return match.group(0)[:endindex]

        if delim.endswith('"""'):
            extract = lambda x: getExpr(self.re_expr_2triple, x, -4)
        elif delim.endswith("'''"):
            extract = lambda x: getExpr(self.re_expr_1triple, x, -4)
        elif delim.endswith('"'):
            extract = lambda x: getExpr(self.re_expr_double, x, -2)
        elif delim.endswith("'"):
            extract = lambda x: getExpr(self.re_expr_single, x, -2)
        else:
            return None

        expression = extract(end)
        if expression is None:
            return None

        if not isRaw:
            expression = expression.replace("\\\\", "\\")

        try:
            FAdoize(expression)
            return expression
        except:
            return None


if __name__ == "__main__":
    samplers = [PythonSampler]
    for sampler in samplers:
        obj = sampler()

        print "\n\nSampling: ", sampler.__name__, "\n"

        urls = obj.grep_search(obj.search_expr, 10000)
        for url in urls:
            code = obj.get_github(url)
            obj.process_codefile(code, url)

    print "\n"*3, "Done!"