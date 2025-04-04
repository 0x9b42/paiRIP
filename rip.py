import os
import re
import sys
import shutil
import subprocess
import urllib.request

while True:
    try:
        from colorama import init, Fore, Style
        break
    except Exception as e:
        print(e)
        subprocess.run(["pip", "install", "colorama"])

init(autoreset=False)

RED = Fore.RED
GRN = Fore.GREEN
YLW = Fore.YELLOW
BLU = Fore.BLUE
CYN = Fore.CYAN
RST = Fore.RESET
BLD = Style.BRIGHT
REG = Style.NORMAL


class Log:
    def log(self, level, *msg):
        fmt = f"{BLD+BLU}[{level + BLU}]" + REG + GRN
        print(fmt, *msg)

    def eror(self, *msg):
        self.log(RED + "ERROR" + RST, *msg)

    def done(self, *msg):
        self.log(GRN + "DONE" + RST, *msg)

    def warn(self, *msg):
        self.log(YLW + "WARN" + RST, *msg)

    def info(self, *msg):
        self.log(CYN + "INFO" + RST, *msg)


LOG = Log()


class Apk:
    def __init__(self, apk):
        self.apk = apk.strip()

        if not os.path.isfile(self.apk):
            LOG.eror("no such file:", YLW + self.apk)
            sys.exit(1)

    def is_split(self):
        return re.match(r"\.x?apk[sm]?$", self.apk.lower()[-5:])

    def ori(self):
        if self.is_split():
            return f"{self.apk[:-5]}_ori.apk"
        return self.apk[:-4] + "_ori.apk"

    def rip(self):
        if self.is_split():
            return f"{self.apk[:-5]}_rip.apk"
        return self.apk[:-4] + "_rip.apk"

    def crc(self, apk=''):
        apk = apk or self.ori()
        



class APKEditor:
    name = "APKEditor.jar"
    url = "https://github.com/REAndroid/APKEditor/releases/download/V1.4.1/APKEditor-1.4.1.jar"

    def __init__(self):
        tmpdir = __import__("tempfile").gettempdir()
        tmpid = __import__("random").randint(100000, 999999)
        self.tmp_src = os.path.join(tmpdir, f"rip_{tmpid}")

        if not os.path.isfile(self.name):
            LOG.info("downloading required jar file ...")
            urllib.request.urlretrieve(self.url, self.name)
            LOG.info("saved to:", YLW + self.name)

        if not shutil.which("java"):
            LOG.eror("java executable not found")
            LOG.info("jdk needed to run", self.name)
            sys.exit(1)

    def exec(self, c, i, o, *opts):
        cmd = ["java", "-jar", self.name, c, "-i", i, "-o", o] + list(opts)
        LOG.info(CYN + " ".join(cmd) + RST)
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(RST + str(e))
            sys.exit(1)

    def merge(self, apks, out):

        LOG.info(f"merging {YLW + apks + RST} ...")
        self.exec("m", apks, out)
        LOG.done("merged:", YLW + out)

    def decode(self, apk, out=""):
        self.tmp_src = out or self.tmp_src
        LOG.info(f"decompiling apk ...")
        self.exec("d", apk, self.tmp_src, "-no-dex-debug")
        LOG.done(f"decompiled to {YLW + self.tmp_src}")

    def clean_tmp(self):
        LOG.info("deleting decompiled source ...")

        try:
            shutil.rmtree(self.tmp_src)
        except Exception as e:
            print(e)
            sys.exit(1)

        LOG.info("deleted successfully.")


class PaiRIP:
    def __init__(self):
        pass


if len(sys.argv) < 2:
    LOG.eror(f"usage: python {sys.argv[0]} /path/to/apk")
    sys.exit(1)


JAR = APKEditor()
APK = Apk(sys.argv[1])


def nope(q): # counter-intuitive? why not?
    y = input(BLD + YLW + q + " [y/N]: ").strip().lower()
    return False if y in ['y', 'yes'] else True


if __name__ == "__main__":
    if APK.is_split():
        LOG.warn("split apk detected, will be merged soon.")

        if os.path.isfile(APK.ori()):
            LOG.warn(f"file exists: {YLW + APK.ori() + GRN}.")
            if nope('continue with it?'):
                LOG.info(f"delete or move {YLW + APK.ori() + GRN} first")
                sys.exit(0)
        else:
            JAR.merge(APK.apk, APK.ori())
    else:
        shutil.move(APK.apk, APK.ori())

    JAR.decode(APK.ori())
    JAR.clean_tmp()
