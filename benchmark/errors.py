class FAdoExtError(BaseException):
    """The general parent class which every other exception in this module inherits from"""
    def __init__(self):
        super(FAdoExtError, self).__init__()


class URegexpError(FAdoExtError):
    """An error which has occured within a URegexp"""
    def __init__(self):
        super(URegexpError, self).__init__()

class InvalidExpressionError(URegexpError):
    """When an expression semi-matched on a line of code, but is invalid for some reason"""
    def __init__(self, line, msg):
        super(InvalidExpressionError, self).__init__()
        self.line = line
        self.msg = msg

    def __str__(self):
        return "InvalidExpressionError on: {0}\n{1}".format(self.line, self.msg)

class AnchorError(URegexpError):
    """When <ASTART> and/or <AEND> are found to be illegally located in the regexp"""
    def __init__(self, re, msg):
        super(AnchorError, self).__init__()
        self.re = re
        self.msg = msg

    def __str__(self):
        return "AnchorError: {0}\n{1}".format(str(self.re), self.msg)

class FAdoizeError(URegexpError):
    """When a programmer's expression cannot be properly converted into FAdoized
    form via regexp-tree npm library"""
    def __init__(self, prog, trace):
        super(FAdoizeError, self).__init__()
        self.prog = prog
        self.trace = trace

    def __str__(self):
        return "FAdoizeError on: {0}\n{1}".format(self.prog, self.trace)

class CharRangeError(URegexpError):
    """When a character range is illegally formed"""
    def __init__(self, chars, lo, hi):
        super(CharRangeError, self).__init__()
        self.chars = chars
        self.lo = lo
        self.hi = hi

    def __str__(self):
        return "CharRangeError in {0}; {1} must be >= {2}".format(self.chars, self.lo.encode("utf-8"), self.hi.encode("utf-8"))


class InvariantNFAError(FAdoExtError):
    """An error which has occured in relation to an InvariantNFA"""
    def __init__(self):
        super(InvariantNFAError, self).__init__()

class UnknownREtoNFAMethod(InvariantNFAError):
    """When an unknown conversion method was attempted"""
    def __init__(self, invalidMethod):
        super(UnknownREtoNFAMethod, self).__init__()
        self.invalidMethod = invalidMethod

    def __str__(self):
        return "UnknownREtoNFAMethod: {0} not in ".format(str(self.invalidMethod)) \
            + "nfaPD, nfaPDO, nfaPosition, nfaFollow, nfaGlushkov, nfaThompson"