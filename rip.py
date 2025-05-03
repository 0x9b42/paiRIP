import os
import re
import sys
import shutil
import tempfile
import subprocess
import urllib.request
from zipfile import ZipFile
from colorama import init, Fore, Style


init(autoreset=True)


class C:
    r = Fore.RED
    g = Fore.GREEN
    b = Fore.BLUE
    c = Fore.CYAN
    y = Fore.YELLOW
    B = Style.BRIGHT
    N = Style.NORMAL


class Log:
    def log(self, level, *msg, **kv):
        print(level + ':', *msg, **kv)

    def e(self, *msg, **kv):
        self.log(C.r + 'ERROR', *msg, **kv)

    def d(self, *msg, **kv):
        self.log(C.g + 'DONE', *msg, **kv)

    def w(self, *msg, **kv):
        self.log(C.y + 'WARN', *msg, **kv)

    def i(self, *msg, **kv):
        self.log(C.c + 'INFO', *msg, **kv)


LOG = Log()

if len(sys.argv) < 2:
    LOG.e(
        f'usage: python {sys.argv[0]} {os.path.join(*'path to apk'.split())}'
    )
    sys.exit(1)

APK = sys.argv[1]

if not os.path.isfile(APK):
    LOG.e('no such file:', APK)
    sys.exit(1)

POS = f'_rip.{os.getpid()}'
OUT = '.'.join(APK.split('.')[:-1]) + POS + '.apk'
TMP = os.path.join(tempfile.gettempdir(), POS)
BES = os.path.join(TMP, 'base.apk')
SRC = BES + '_src'


def is_split(apk):
    return re.match(r'\.x?apk[sm]?', apk.lower()[-5:])


def rmdir(dir):
    try:
        shutil.rmtree(dir)
    except Exception as e:
        print(e)
        sys.exit(1)

    LOG.d('deleted successfully:', C.r + dir)


def mkdir(dir):
    os.makedirs(dir, exist_ok=True)
    LOG.i('created:', C.b + dir + '/')


def nope(q):  # counter-intuitive? why not?
    LOG.w(q, end='')
    y = input(' [y/N]: ').strip().lower()
    return False if y in ['y', 'yes'] else True


def civis(t):
    sys.stdout.write('\x1b[?25' + ('l' if t else 'h'))
    sys.stdout.flush()


class APKEditor:
    jar = os.path.join('assets', 'APKEditor.jar')
    url = 'https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar'

    def __init__(self):

        if not os.path.isfile(self.jar):
            mkdir('assets')
            LOG.i('downloading required jar file ...')
            urllib.request.urlretrieve(self.url, self.jar)
            LOG.i('saved to:', self.jar)

        if not shutil.which('java'):
            LOG.e('java executable not found')
            LOG.i('jdk needed to run', self.jar)
            sys.exit(1)

    def exec(self, c, i, o, *opts):
        cmd = ['java', '-jar', self.jar, c, '-i', i, '-o', o] + list(opts)

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        except Exception as e:
            print(e)
            sys.exit(1)

    def merge(self, apks, out):
        LOG.i('merging split apks...')
        self.exec('m', apks, out)
        LOG.d('merged successfully')

    def decode(self, apk, out):
        LOG.i('decompiling apk...')
        self.exec('d', apk, out, '-no-dex-debug')
        LOG.d('decompiled successfully')

    def build(self, src, out):
        LOG.i('building source...')
        self.exec('b', src, out, '-f')
        LOG.d('built:', C.y + out)


class ApkUtils:
    def is_split(self, apk):
        return re.match(r'\.x?apk[sm]?', apk.lower()[-5:])

    def getCRCs(self, apk):
        crc = {}
        with ZipFile(apk) as z:
            for i in z.infolist():
                crc[i.filename] = i.CRC

        return crc

    def patchCRCs(self, ori, mod):
        pass



J = APKEditor()

if __name__ == '__main__':
    LOG.i('creating temporary folder...')
    mkdir(TMP)

    if is_split(APK):
        LOG.w('split apk detected')
        J.merge(APK, BES)
        APK = APK[:-5]

    else:
        shutil.copy(APK, BES)
        APK = APK[:-4]

    # add logger dex from ./assets to apk
    #shutil.copy('assets/classes0.dex', '')

    # decompile apk
    J.decode(BES, SRC)

    # modify manifest to add storage permission
    #patch_manifest()

    # add logger invokes to smali to log pairip strings
    #inject_logger()

    # build modified source, user then run the app to get .mtd
    if os.path.isfile(OUT):
        LOG.w('file exists:', C.y + OUT)

        if nope('overwrite it?'):

            LOG.w('operarion aborted. cleaning up...')
            rmdir(TMP)

            sys.exit(1)

    J.build(SRC, OUT)

    # take .mtd file from user to further restore pairip strings
    #input('mtd file: ')

    # 

    # clean up
    LOG.i('deleting temporary folder...')
    rmdir(TMP)
