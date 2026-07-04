# [@GHOST]{[@file<test.py>]}
# [@VBSTYLE]{[@role<test>]}
# [@SUMMARY]{test}
# [@CLASS]{TestClass}
# [@METHOD]{Run,helper}

class TestClass:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {}

    def Run(self, command, params=None):
        return (0, None, None)
    def helper(self):
        return (0, None, None)