# [@GHOST]{[@file<test.py>]}
# [@VBSTYLE]{[@role<test>]}
# [@SUMMARY]{test}
# [@CLASS]{WillBeRenamed}
# [@METHOD]{Run}

MYVAR = "test"

class BadClass:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {}

    def Run(self, command, params=None):
        return (1, {"ok": True}, None)
