import subprocess
import urllib.request
from pathlib import Path


class Log:
    def log(self, level, *msg):
        print(level + ':', *msg)

    def i(self, *msg):
        self.log('I', *msg)

    def e(self, *msg):
        self.log('E', *msg)

    def d(self, *msg):
        self.log('√', *msg)

    def w(self, *msg):
        self.log('W', *msg)

class ApkTool:
    __jar = Path('assets/apktool.jar')

    def __init__(self):
        if not self.__jar.exists():
            urllib.request()

    def exec(self¸ cmd, inn, out, *args):
        c = ['java', '-jar', self.__jar]
        m = [cmd, inn, '-o', out]
        d = list(args)

        subprocess.run(c + m + d, check=True)

    def d(self, inn, out, *args):
        pass

    def b(self, inn, out, *args):
        pass
