import os
import re
import sys
import shutil
import subprocess
import urllib.request
from zipfile import ZipFile
from tempfile import gettempdir



class Log:
    def log(self, level, *msg):
        print(f'[{level}]', *msg)

    def e(self, *msg):
        self.log('x', *msg)

    def d(self, *msg):
        self.log('=', *msg)

    def w(self, *msg):
        self.log('!', *msg)

    def i(self, *msg):
        self.log('*', *msg)


LOG = Log()


def mkdir(path):
    LOG.i('mkdir -p', path)
    os.makedirs(path, exist_ok=True)


def nope(*q):
    LOG.w(*q)
    y = input('[y/N]: ').strip().lower()
    return False if y in ['y', 'yes'] else True


class TextFile:
    def __init__(self, path):
        self.PATH = path

        with open(path, 'r', encoding='utf-8') as f:
            self.TEXT = f.read()

    @property
    def lines(self):
        return self.TEXT.splitlines()

    def sub(self, pat, rep):
        if isinstance(pat, str):
            pat = re.compile(pat)
        self.TEXT = pat.sub(rep, self.TEXT)

    def replace(self, old, new):
        self.TEXT = self.TEXT.replace(old, new)

    def append(self, string):
        self.TEXT += string

    def find(self, pat):
        for line in self.lines:
            if pat in line:
                return line
        return ''

    def findall(self, pat):
        return [line for line in self.lines if pat in line]

    def write(self, path=''):
        path = path or self.PATH
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.TEXT)


class Smali(TextFile):
    def __init__(self, path):
        super().__init__(path)

        class_line = self.find('.class')
        match = re.search(r'L[^;]+;', class_line)
        self.KLASS = match.group() if match else None

        self.ZUPER = ''
        super_line = self.find('.super ')
        if super_line.startswith('.super '):
            self.ZUPER = super_line[len('.super '):].strip()

    def methods(self):
        return re.findall(r'^\.method.*?^\.end method', self.TEXT, flags=re.M | re.S)

    def fields(self):
        return re.findall(r'^\.field.+', self.TEXT, flags=re.M)

    def get_method_names(self):
        return re.findall(r'^\.method.* (\S+)', '')


class Apk(ZipFile):
    def __init__(self, path, *opt, **kv):
        super().__init__(path, *opt, **kv)

        valid = False
        self.isUnity = False
        self.protection = []

        for i in self.namelist():
            
            if i == 'AndroidManifest.xml':
                valid = True

            elif i == 'libil2cpp.so':
                self.isUnity = True

            elif i == 'libpairipcore.so':
                self.protection.append('pairip')
                
            elif i == 'ijiami.dat':
                self.protection.append('ijiami')

        if not valid:
            raise ValueError(f'berkas tidak valid: {path}')


class APKEditor:
    URL = 'https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar'
    JAR = os.path.join('assets', 'APKEditor.jar')
    TMP = os.path.join(gettempdir(), f'apk.{os.getpid()}')
    CMD = ['java', '-jar', JAR]

    def __init__(self, path):

        if not os.path.isfile(self.JAR):
            mkdir('assets')
            LOG.i('mengunduh APKEditor.jar...')
            urllib.request.urlretrieve(self.URL, self.JAR)
            LOG.i('disimpan ke:', self.JAR)

        if not shutil.which('java'):
            LOG.e('java tidak ditemukan')
            raise Exception(f'jdk dibutuhkan untuk menjalankan {self.JAR}')

        self.PATH = path

        if not os.path.isfile(path):
            raise Exception(f"file tidak ditemukan: {path}")

    def edit(self):
        self.APK = self.swap_ext(self.PATH, 'apk')
        self.SRC = os.path.join(self.TMP, 'src')
        self.MANIFEST = os.path.join(self.SRC, 'AndroidManifest.xml')
        self.SMALI_DIR = os.path.join(self.SRC, 'smali')

        mkdir(self.TMP)

        if self.is_split(self.PATH):
            self.merge(self.PATH, self.APK)

        self.decode(self.APK, self.SRC)

    def is_split(self, path=''):
        exts = ['apkm', 'apks', 'xapk']
        return True if path.split('.')[-1].lower() in exts else False

    def swap_ext(self, file, ext):
        ext_len = len(file.split('.')[-1]) 
        return file[:-ext_len] + ext

    def dex_count(self):
        classes = os.scandir(self.SMALI_DIR)
        cnum = [i.name[7:-4] or 1 for i in classes]
        return max([int(i) for i in cnum])

    def listfile(self):
        s = []
        for r,_,f in os.walk(self.SRC):
            s = s + [os.path.join(r, i) for i in f]
        return s

    def find(self, file):
        return [x for x in self.listfile() if file in os.path.basename(x)]

    def search(self, pat):
        s = []
        for i in self.listfile():
            with open(i, 'r') as f:
                if pat in f.read():
                    s.append(i)
        return s


    def exec(self, c, i, o, *opts):
        cmd = self.CMD + [c, '-i', i, '-o', o] + list(opts)

        LOG.log('APKEditor', c.upper(), f'{i} => {o}')

        try:
            subprocess.run(
                cmd,
                #stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

        except Exception as e:
            print(e)
            raise Exception(f'galat saat menjalankan: {' '.join(cmd)}')

    def merge(self, apks, apk):
        LOG.i(f'mengkonversi ke APK:', apks)
        self.exec('merge', apks, apk)
        LOG.d('konversi sukses:', apk)

    def decode(self, apk, out):
        LOG.i('dekompilasi APK:', apk)
        self.exec('decode', apk, out, '-no-dex-debug')
        LOG.d('dekompilasi sukses:', out)

    def build(self, src, out):
        LOG.i('kompilasi source code:', src)

        if os.path.isfile(out) and nope(f'file ditemukan: {out}. timpa file?'):
            raise Exception('operasi dibatalkan oleh user')

        self.exec('build', src, out, '-f')
        LOG.d('kompilasi sukses:', out)


