import os
import sys

class C:
    _ = lambda x: f'\x1b[{x}m' if os.name == 'posix' else ''
    r = _(91)
    g = _(92)
    b = _(94)
    c = _(96)
    y = _(93)
    B = _(1)
    N = _(0)

class Log:
    def log(self, level, *msg):
        print(C.B + C.c + f'[{level + C.c}]', *msg, C.N)

    def i(self, *msg):
        self.log(C.g + '*', *msg)

    def w(self, *msg):
        self.log(C.y + 'W', *msg)

    def e(self, *msg):
        self.log(C.r + 'E', *msg)

    def s(self, *msg):
        self.log(C.g + 'OK', *msg)


log = Log()
