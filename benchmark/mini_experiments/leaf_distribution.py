"""This mini experiment finds the distribution of leaf nodes in a sample of
regular expressions. In this case we expect only 5 leaf variants, and each
regular expression comes from the database table `in_tests`.

Running:
    From the root directory:
    $ python -m benchmark.mini_experiments.leaf_distribution

Output:
    12019/12020 ... Done
    {
        "<class 'benchmark.reex_ext.uatom'>": 118783,
        "<class 'benchmark.reex_ext.dotany'>": 5625,
        "<class 'benchmark.reex_ext.anchor'>": 5164,
        "<class 'benchmark.reex_ext.chars'>": 21978,
        "<class 'benchmark.reex_ext.uepsilon'>": 1035
    }

Note:
    There are really only four leaf categories since the `anchor` behaves
    identically to `uepsilon` except during partial matching.
"""

from __future__ import print_function
import sys
import json
from ..reex_ext import *
from ..util import DBWrapper
from ..convert import Converter

db = DBWrapper()
convert = Converter()

completed = 0
total = db.selectall("SELECT count(*) FROM in_tests WHERE error='';")[0][0]
pos = sys.stdout.tell()

freq = {
    str(uepsilon): 0,
    str(anchor): 0,
    str(chars): 0,
    str(uatom): 0,
    str(dotany): 0
}
for expr, in db.selectall("SELECT re_math FROM in_tests WHERE error=='';"):
    sys.stdout.seek(pos)
    sys.stdout.write("\r{}/{}".format(completed, total))
    sys.stdout.flush()

    expr = expr.decode("utf-8")
    tree = convert.math(expr)

    for subexpr in tree:
        if subexpr.treeLength() == 1:
            freq[str(type(subexpr))] = freq[str(type(subexpr))] + 1

    completed += 1

print(" ... Done")
print(json.dumps(freq, indent=4))