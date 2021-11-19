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


ID_EPSILON = 0
ID_STAR = 1
ID_OPTION = 2
ID_CONC = 3
ID_DISJ = 4
ID_SYMB = 5

class dnode(object):
    def __init__(self, op, arg1=None, arg2=None):
        self.dotl = set([])
        self.dotr = set([])
        self.star = None
        self.option = None
        self.plus = set([])
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.diff = dict()
        if op in [ID_OPTION, ID_STAR, ID_EPSILON]:
            self.ewp = True
        elif op in (ID_CONC, ID_DISJ):
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
        self.table = dict()
        self.table[0] = dnode(ID_EPSILON)
        self.count = 1
        self.leafs = dict()
        self.diff2do = set()
        self.root = self.getIdx(reg)

    def __len__(self):
        return self.count - 1

    def getIdx(self, reg):
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
        if reg.val in self.leafs:
            return self.leafs[reg.val]
        else:
            id = self.count
            self.count += 1
            self.leafs[reg.val] = id
            new = dnode(ID_SYMB)
            new.diff[reg] = set([0])
            self.table[id] = new
            return id

    def getStarIdx(self, argId):
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

    def ewpFixConc(self, obj, arg1Id, arg2Id):
        obj.ewp = self.table[arg1Id].ewp and self.table[arg2Id].ewp

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

    def ewpFixDisj(self, obj, arg1Id, arg2Id):
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

    def doDelayed0(self):
        if len(self.diff2do):
            self.beingDone = set(self.diff2do)
            self.diff2do = set()
            while self.beingDone:
                inode = self.beingDone.pop()
                node = self.table[inode]
                # assert node.op == ID_CONC
                if self.table[node.arg1].ewp:
                    node.diff = self.plusLF(self.catLF(node.arg1, node.arg2), self.table[node.arg2].diff)
                else:
                    node.diff = self.catLF(node.arg1, node.arg2)
            self.doDelayed()

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
        aut = InvariantNFA()
        todo, done = {self.root}, set()
        id = aut.addState(self.root)
        aut.addInitial(id)
        while len(todo):
            st = todo.pop() # integer index
            done.add(st)
            stn = self.table[st] # reference to the dnode
            sti = aut.stateIndex(st)
            if stn.ewp:
                aut.addFinal(sti)
            for c in stn.diff:
                for dest in stn.diff[c]:
                    if dest not in todo and dest not in done:
                        todo.add(dest)
                    desti = aut.stateIndex(dest, True)
                    aut.addTransition(sti, c, desti)
        return aut


def pddag(self):
    return dag(self).NFA()

setattr(reex_ext.uregexp,'nfaPDDAG', pddag)