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
        self.output = ConsoleOverwrite(self.language + "Sampler: ")
        self.db = DBWrapper()

    def grep_search(self, numResults):
        """A function that populates the database with GitHub URLs that match a language and
        regular expression indexed by the https://grep.app API.
        :param int numResults: the desired number of results to retrieve (github links)
        """
        # first check if we already have sufficient results in the DB
        urls = list(map(lambda x: x[0],
            self.db.selectall("SELECT url FROM github_urls WHERE lang=?;", [self.language])))
        if len(urls) >= numResults:
            return

        # find results from grep.app
        results = set()
        params = {
            'q': self.search_expr,
            'f.lang': self.language,
            'regexp': True
        }
        baseurl = "https://grep.app/api/search?" + urllib.urlencode(params)
        pageNum = len(urls) // 10
        lastResponse = "n/a"
        while len(results) < numResults:
            pageNum += 1
            self.output.overwrite("grep_search {0}".format(pageNum))

            page = urllib.urlopen(baseurl + "&page=" + str(pageNum))
            response = "\n".join(page.readlines())
            content = json.loads(response)
            if response == lastResponse: # pageNum > max will return the last page's info
                break
            lastResponse = response
            hits = content["hits"]["hits"] # type: list<dict>

            for hit in hits:
                user_repo = hit["repo"]["raw"]
                branch = hit["branch"]["raw"] if hit.has_key("branch") else "master"
                filename = hit["path"]["raw"]
                url = u"https://raw.githubusercontent.com/{user_repo}/{branch}/{path}" \
                    .format(user_repo=user_repo, branch=branch, path=filename)

                if len(results) < (results.add(url), len(results))[1]: # if url was added for the first time in results
                    self.db.execute("INSERT OR IGNORE INTO github_urls (url, lang) VALUES (?, ?);", [url, self.language])

    def get_github_code(self, url):
        """Gets the code from a raw github page and returns line-delimited list
        :param unicode url: the raw github url where the code can be downloaded
        :returns list<unicode>: the code line by line
        """
        self.output.overwrite("get_github: " + url)
        page = urllib.urlopen(url)
        return page.read().splitlines()

    def get_urls(self):
        """Retrieves github_urls assigned to `self.language` that have yet to be searched"""
        return list(map(lambda x: x[0],
            self.db.selectall("SELECT url FROM github_urls WHERE lang=? AND searched=-1;", [self.language])))

    def process_code(self, lines, fromFile="Unspecified"):
        """Processes lines of code and searches for contained regular expressions using
        the #get_line_expression method.
        :param list<unicode> lines: the lines to search for regular expressions
        :param unicode fromFile: the URL of the codefile to be stored in the database
        :returns list<unicode>: formatted and working expressions
        """
        expressions = list()

        lineNum = 0
        for line in lines:
            lineNum += 1

            expr = self.get_line_expression(line)
            if expr is None:
                continue

            try:
                formatted = FAdoize(expr)
                self.db.execute("""
                    INSERT OR IGNORE INTO expressions (re, url, lineNum, line, lang)
                    VALUES (?, ?, ?, ?, ?);""", [formatted, fromFile, lineNum, line, self.language])
                expressions.append(formatted)
                self.output.overwrite("process_codefile {1} found - {0}".format(fromFile, len(expressions)))
            except Exception as e:
                print e

        self.db.execute("""
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

        obj.grep_search(300)
        for url in obj.get_urls():
            code = obj.get_github_code(url)
            obj.process_code(code, url)

    print "\n"*3, "Done!"