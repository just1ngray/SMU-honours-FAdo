# coding=utf-8
"""This package collects a sample of regular expressions used by programmers in
real-world projects.

1. https://grep.app indexes top GitHub projects and allows searching for text
    inside code files. This application is used to find URLs of GitHub files
    which contain regular expressions.
2. Given a URL (from grep.app), download the code using GitHub's page:
    https://raw.githubusercontent.com/{user}/{repo}/{branch}/{filename}
3. Feed each line of code into the appropriate Lark grammar (depending on the
    programming language used). Extract the regular expression from the line.
4. Using https://github.com/DmitrySoshnikov/regexp-tree, parse the regular
    expression into its corresponding abstract syntax tree (AST).
5. Given the AST, make the following changes:
    i)  Throw away lookaheads, lookbehinds, and backreferences since they
        overcomplicate regular expression engines and cannot be solved in
        polynomial time.
    ii) α+ => αα*
    iii) α{x,y} => αα...α(x times)(ε|α)(ε|αα)(ε|αααα)...(etc. until no more
         than y-x α's can be chosen)
    iv) Character classes such as '\d' are replaced with their equivalent
        ranges '[0-9]'.
6. Finally, convert into FAdo classes and output the __str__ representation.
"""