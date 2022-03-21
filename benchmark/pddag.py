# -*- coding: utf-8 -*-
"""**Compressed Regular Expressions**

Compressed Regular Expressions  Manipulation

.. *Authors:* Rogério Reis & Nelma Moreira

.. Contributions by
    - Stavros Konstantinidis

.. *This is part of FAdo project*   http://fado.dcc.fc.up.pt

.. *Version:* 1.4

.. *Copyright:* 1999-2021 Rogério Reis & Nelma Moreira {rvr,nam}@dcc.fc.up.pt


.. This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public
   License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any
   later version.

   This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
   details.


   You should have received a copy of the GNU General Public Licensealong with this program; if not, write to the
   Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA."""

import reex_ext
from fa_ext import InvariantNFA


# essentially an enum to easily identify node types
ID_EPSILON = 0  #               @epsilon
ID_STAR = 1     # star          a*
ID_OPTION = 2   # option        a?
ID_CONC = 3     # concatenation (a b)
ID_DISJ = 4     # disjunction   (a + b)
ID_SYMB = 5     # atomic symbol a

class dnode(object):
    def __init__(self, op, arg1=None, arg2=None):
        self.dotl = set([])
        self.dotr = set([])
        self.star = None    # the id of the star version of this node
        self.option = None  # the id of the option version of this node
        self.plus = set([])

        # given an operation and 0, 1, or 2 children...
        self.op = op        # node type (ID_[...] from globals)
        self.arg1 = arg1    # id in table of first  child id when: star, option, concat, or disj
        self.arg2 = arg2    # id in table of second child id when: concat, or disj

        self.diff = dict()  # partial derivative defined transitions<directed edge label, destination node id>

        # recall that partial derivative NFA has final state for any state "named" {@epsilon, a*, a?}
        if op in [ID_OPTION, ID_STAR, ID_EPSILON]:
            self.ewp = True
        elif op in (ID_CONC, ID_DISJ):
            # computed later in concat/disj cases
            # ewp (a b)   = ewp a AND ewp b
            # ewp (a + b) = ewp a OR  ewp b
            # either way: a and b need to be known
            pass
        else:
            self.ewp = False


class dag(object):
    """Class to support dags representing regexps

    ...seealso: P. Flajolet, P. Sipala, J.-M. Steyaert, Analytic variations on the common subexpression problem,
            in: Automata, Languages and Programmin, LNCS, vol. 443, Springer, New York, 1990, pp. 220–234.
    """

    def __init__(self, reg):
        """:var reex reg: regular expression"""
        self.table = dict() # <id, dnode>

        # index 0 is reserved for empty
        self.table[0] = dnode(ID_EPSILON)
        self.count = 1

        self.leafs = dict()
        self.diff2do = set()
        self.root = self.getIdx(reg) # recursively computes self.table

    def getIdx(self, reg):
        """Recursively gets the id of the regular expression while building self.table"""
        if isinstance(reg, reex_ext.uatom):
            return self.getAtomIdx(reg)
        elif isinstance(reg, reex_ext.udisj):
            id1 = self.getIdx(reg.arg1)
            id2 = self.getIdx(reg.arg2)
            return self.getDisjIdx(id1, id2)
        elif isinstance(reg, reex_ext.uconcat):
            id1 = self.getIdx(reg.arg1)
            id2 = self.getIdx(reg.arg2)
            return self.getConcatIdx(id1, id2)
        elif isinstance(reg, reex_ext.ustar):
            id = self.getIdx(reg.arg)
            return self.getStarIdx(id)
        elif isinstance(reg, reex_ext.uoption):
            id = self.getIdx(reg.arg)
            return self.getOptionIdx(id)
        else:  # It must be epsilon
            return 0

    def getAtomIdx(self, reg):
        """Gets the id of an atomic regular expression
        If this is already done, return the id of that instance
        Otherwise, create a new dnode and assign an increasing id (by count)"""
        if reg.val in self.leafs:
            return self.leafs[reg.val]
        else:
            id = self.count
            self.count += 1
            self.leafs[reg.val] = id
            new = dnode(ID_SYMB)
            new.diff[reg] = set([0]) # pd of reg in resulting NFA: (reg, @epsilon)
            self.table[id] = new
            return id

    def getStarIdx(self, argId):
        """Gets the id of a regular expression of the form `a*`
        :var argId int: id of `a`
        If this is already done, return the id of that instance
        Otherwise, create a new dnode and assign an increasing id (by count)"""
        if self.table[argId].star is not None:
            return self.table[argId].star
        else:
            id = self.count
            self.count += 1
            new = dnode(ID_STAR, argId)
            self.table[argId].star = id
            self.table[id] = new
            new.arg1 = argId
            new.diff = self.catLF(argId, id, True)
            self.doDelayed()
            return id

    def getOptionIdx(self, argId):
        """Gets the id of a regular expression of the form `a?`
        :var argId int: id of `a`
        If this is already done, return the id of that instance
        Otherwise, create a new dnode and assign an increasing id (by count)"""
        if self.table[argId].option is not None:
            return self.table[argId].option
        else:
            id = self.count
            self.count += 1
            new = dnode(ID_OPTION, argId)
            self.table[argId].option = id
            self.table[id] = new
            new.arg1 = argId
            new.diff = self.table[argId].diff
            return id

    def getConcatIdx(self, arg1Id, arg2Id, delay=False):
        if arg1Id == 0:
            return arg2Id
        if arg2Id == 0:
            return arg1Id
        a = self.table[arg1Id].dotl.intersection(self.table[arg2Id].dotr)
        if len(a):
            return a.pop()
        else:
            id = self.count
            self.count += 1
            new = dnode(ID_CONC, arg1Id, arg2Id)
            self.table[id] = new
            new.arg1, new.arg2 = arg1Id, arg2Id
            self.ewpFixConc(new, arg1Id, arg2Id)
            self.table[arg1Id].dotl.add(id)
            self.table[arg2Id].dotr.add(id)
            if not delay:
                if self.table[arg1Id].ewp:
                    new.diff = self.plusLF(self.catLF(arg1Id, arg2Id), self.table[arg2Id].diff)
                else:
                    new.diff = self.catLF(arg1Id, arg2Id)
            else:
                self.diff2do.add(id)
            return id

    def getDisjIdx(self, arg1Id, arg2Id):
        if arg1Id == arg2Id:
            return arg1Id
        a = self.table[arg1Id].plus.intersection(self.table[arg2Id].plus)
        if len(a):
            return a.pop()
        else:
            id = self.count
            self.count += 1
            new = dnode(ID_DISJ, arg1Id, arg2Id)
            self.table[id] = new
            new.arg1, new.arg2 = arg1Id, arg2Id
            self.ewpFixDisj(new, arg1Id, arg2Id)
            self.table[arg1Id].plus.add(id)
            self.table[arg2Id].plus.add(id)
            new.diff = self.plusLF(self.table[arg1Id].diff, self.table[arg2Id].diff)
            return id

    def ewpFixConc(self, obj, arg1Id, arg2Id):
        """Assign ewp for dnode of type concat
        Both of its children (lookup-able in self.table[by id] => dnode) must have ewp true"""
        obj.ewp = self.table[arg1Id].ewp and self.table[arg2Id].ewp

    def ewpFixDisj(self, obj, arg1Id, arg2Id):
        """Assign ewp for dnode of type disj
        One of its children (lookup-able in self.table[by id] => dnode) must have ewp true"""
        obj.ewp = self.table[arg1Id].ewp or self.table[arg2Id].ewp

    def catLF(self, idl, idr, delay=False):
        """both arguments are assumed to be already present in the dag"""
        nlf = dict()
        left = self.table[idl].diff
        for c in left:
            nlf[c] = {self.getConcatIdx(x, idr, delay) if x != 0 else idr for x in left[c]}
        return nlf

    def plusLF(self, diff1, diff2):
        """ Union of partial derivatives

        :arg dict diff1: partial diff of the first argument
        :arg dict diff2: partial diff of the second argument
        :rtype: dict
        """
        nfl = dict(diff1)
        for c in diff2:
            nfl[c] = nfl.get(c, set([])).union(diff2[c])
        return nfl

    def doDelayed(self):
        while self.diff2do:
            inode = self.diff2do.pop()
            node = self.table[inode]
            assert node.op == ID_CONC
            if self.table[node.arg1].ewp:
                node.diff = self.plusLF(self.catLF(node.arg1, node.arg2), self.table[node.arg2].diff)
            else:
                node.diff = self.catLF(node.arg1, node.arg2)

    def NFA(self):
        """Converts the dag of dnodes into a NFA"""
        aut = InvariantNFA()
        todo, done = {self.root}, set()
        id = aut.addState(self.root)
        aut.addInitial(id)
        while len(todo):
            st = todo.pop() # id of dnode to process
            done.add(st)
            stn = self.table[st] # reference to the dnode
            sti = aut.stateIndex(st)
            if stn.ewp:          # dnode already knows if it accepts empty word
                aut.addFinal(sti)
            for c in stn.diff:   # partial derivative defined transitions<directed edge label, destination node id>
                for dest in stn.diff[c]:
                    if dest not in todo and dest not in done:
                        todo.add(dest)
                    desti = aut.stateIndex(dest, True)
                    aut.addTransition(sti, c, desti)
        return aut


def pddag(self):
    return dag(self).NFA()

setattr(reex_ext.uregexp,'nfaPDDAG', pddag)