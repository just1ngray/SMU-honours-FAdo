import urllib
import json
import regex

import util

class InvalidExpressionError(ValueError):
    def __init__(self, line, message):
        super(InvalidExpressionError, self).__init__()
        self.line = line
        self.message = message

    def __str__(self):
        return "InvalidExpressionError on line {0}\n{1}".format(self.line, self.message)

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
        self.output = util.ConsoleOverwrite(self.language + "Sampler: ")
        self.db = util.DBWrapper()

    def grep_search(self, numResults):
        """A function that populates the database with GitHub URLs that match a language and
        regular expression indexed by the https://grep.app API.
        :param int numResults: the desired number of results to retrieve (github links)
        """
        # first check if we already have sufficient results in the DB
        urls = set(map(lambda x: x[0],
            self.db.selectall("SELECT url FROM github_urls WHERE lang=?;", [self.language])))
        if len(urls) >= numResults:
            return

        # find results from grep.app
        params = {
            'q': self.search_expr,
            'f.lang': self.language,
            'regexp': True
        }
        baseurl = "https://grep.app/api/search?" + urllib.urlencode(params)
        pageNum = len(urls) // 10
        lastResponse = "n/a"
        while len(urls) < numResults:
            pageNum += 1
            pageAddr = baseurl + "&page=" + str(pageNum)
            self.output.overwrite("grep_search {0} - {1}".format(pageNum, pageAddr))

            page = urllib.urlopen(pageAddr)
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

                if len(urls) < (urls.add(url), len(urls))[1]: # if url was added for the first time
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
            self.save_expression(fromFile, line, lineNum)

        self.db.execute("""
            UPDATE github_urls
            SET searched=datetime('now', 'localtime')
            WHERE url=?;
        """, [fromFile])
        return expressions

    def reprocess_lines(self):
        """Reprocesses all previously collected lines to ensure they're up to date with the
        current FAdoize spec."""
        rows = self.db.selectall("""SELECT re_math, re_prog, line, url, lineNum, lang
                                    FROM expressions WHERE lang=?;""", [self.language])
        for _, _, line, url, lineNum, _ in rows:
            self.output.overwrite("reprocess_lines:", line)
            self.db.execute("DELETE FROM expressions WHERE url=? AND line=?;", [url, line])
            self.save_expression(url, line, lineNum)

    def save_expression(self, url, line, lineNum):
        """Save a potential expression to the database if one exists on line"""
        expr = "none_found"
        try:
            self.output.overwrite("get_line_expression @ " + line)
            expr = self.get_line_expression(line)
            if expr is None:
                return None
            self.output.overwrite("save_expression @ " + line)

            formatted = util.FAdoize(expr)
            self.db.execute("""
                INSERT OR IGNORE INTO expressions (re_math, re_prog, url, lineNum, line, lang)
                VALUES (?, ?, ?, ?, ?, ?);""", [formatted, expr, url, lineNum, line, self.language])
            return formatted
        except (InvalidExpressionError, util.FAdoizeError) as err:
            self.db.execute("""
                INSERT OR IGNORE INTO expressions (re_math, re_prog, url, lineNum, line, lang)
                VALUES (?, ?, ?, ?, ?, ?);""", [str(err), expr, url, lineNum, line, self.language])
            return err

    # abstractmethod
    def get_line_expression(self, line):
        """Extracts a regular expression from a line of code
        :param unicode line: the line of code on which to search for an expression
        :returns unicode|None: the extracted expression if it exists, None if there is no sign of
        an expression on the line
        :raises InvalidExpressionError: if there is an issue with extracting the expression, but
        there's a good chance one exists on line

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
                raise InvalidExpressionError(line, "Incomplete - no end of expression found")
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
            raise InvalidExpressionError(line, "Unknown delimiter: %s" % delim)

        expression = extract(end)
        if not isRaw:
            expression = expression.replace("\\\\", "\\")

        return expression


class JavaScriptSampler(CodeSampler):
    # Note: expressions initialized using `new RegExp(...)` contain many variables and cannot be used
    def __init__(self, lang="JavaScript"):
        super(JavaScriptSampler, self).__init__(lang, r"""\.(search|replace|test|split|match(All)?)\(/.+""")
        self.start = regex.compile(r"""\.(search|replace|test|split|match(All)?)\(/""")

    def get_line_expression(self, line):
        match = self.start.search(line)
        if match is None:
            return None
        end = line[match.end():] # start of the expression to the end of the line
        if len(end) == 0:
            raise InvalidExpressionError(line, "EOL found, expected the expression")

        end = end.decode("utf-8")
        expression = u""
        i = 0
        success = False
        while i < len(end):
            c = end[i]
            if c == "\\":
                if end[i + 1] == "/":
                    expression += end[i + 1]
                else:
                    expression += c + end[i + 1]
                i += 1
            elif c == "/":
                success = True
                break
            else:
                expression += c

            i += 1

        if not success:
            raise InvalidExpressionError(line, "Could not find terminator of the expression")

        return expression


class TypeScriptSampler(JavaScriptSampler):
    def __init__(self):
        super(TypeScriptSampler, self).__init__("TypeScript")


class JavaSampler(CodeSampler):
    def __init__(self):
        super(JavaSampler, self).__init__("Java", r"""Pattern\.compile\("/.+\)""")
        self.start = regex.compile(r'''Pattern\.compile\("''')
        self.extract = regex.compile(r'''(\\.|[^"])+"[,)]''')

    def get_line_expression(self, line):
        match = self.start.search(line)
        if match is None:
            return None
        end = line[match.end():] # start of the expression to the end of the line
        if len(end) == 0:
            raise InvalidExpressionError(line, "EOL found, expected the expression")

        expression = self.extract.search(end)
        if expression is None:
            raise InvalidExpressionError(line, "Could not extract the expression")
        expression = expression.group(0).decode("utf-8")[:-2] # remove the `"[,)]` from end

        return expression.replace("\\\\", "\\")


class PerlSampler(CodeSampler):
    def __init__(self, lang="Perl"):
        super(PerlSampler, self).__init__(lang, r"""\$.+ =~ [miosg]*/.+/""")
        self.start = regex.compile(r"""\$.+ =~ [miosg]*/""")
        self.extract = regex.compile(r"""(\\.|[^/])+/""")

    def get_line_expression(self, line):
        match = self.start.search(line)
        if match is None:
            return None
        end = line[match.end():] # start of the expression to the end of the line
        if len(end) == 0:
            raise InvalidExpressionError(line, "EOL found, expected the expression")

        expression = self.extract.search(end)
        if expression is None:
            raise InvalidExpressionError(line, "Could not extract the expression")
        expression = expression.group(0).decode("utf-8")[:-1] # remove the `/` from end

        return expression.replace("\\/", "/")

if __name__ == "__main__":
    SAMPLE_SIZE = 400

    samplers = [PerlSampler, JavaSampler, TypeScriptSampler, JavaScriptSampler, PythonSampler]
    for sampler in samplers:
        obj = sampler()

        print "\n\nSampling: ", sampler.__name__

        obj.grep_search(SAMPLE_SIZE)
        obj.reprocess_lines()
        for url in obj.get_urls():
            code = obj.get_github_code(url)
            obj.process_code(code, url)
        obj.output.overwrite("Done!")

    print "\n"*3, "Done - Sampled All"