import os
import re
import shutil
import subprocess
from urllib.request import urlretrieve
from zipfile import ZipFile
from pathlib import PosixPath, WindowsPath

Path = PosixPath if os.name == 'posix' else WindowsPath
url = 'https://github.com/0x9b42/termux-config/raw/refs/heads/main/.local/tools/jar/APKEditor-1.4.1.jar'
rgx = {
    'method': re.compile(r'(?s)\.method\s.+?\.end method'),
    'methinfo': re.compile(r'(?s)\.method\s+(.+?)([^\s]+?)\((.*?)\)(.+?)\n.+?\.((?:local|register)s)\s+(\d)(.+?)\.end method'),
    'fieldinfo': re.compile(r'\.field\s+(.+)\s+(\w+?):(L?.+;?)(?:\s?=\s(.+))?'),
}

class Apk(ZipFile):
    def __init__(self, *a, **kv):
        super().__init__(*a, **kv)

        self.isPairip = False
        self.dexcount = 0

        for i in self.namelist():
            if i == 'libpairipcore.so':
                self.isPairip = True
            elif i.startswith('classes') and i.endswith('.dex'):
                self.dexcount += 1


class TextFile(Path):
    def __init__(self, *a, **kv):
        super().__init__(*a, **kv)
        self.text = self.read_text(encoding='utf-8')

    def findall(self, txt):
        for line in self.text.splitlines():
            if txt in line:
                yield line

    def find(self, txt):
        for line in self.text.splitlines():
            if txt in line:
                return line

    def finditer(self, pat):
        return re.finditer(pat, self.text)

    def sub(self, old, new):
        self.text = self.text.replace(old, new)

    def rsub(self, pat, rep):
        self.text = re.sub(pat, rep, self.text)

    def prepend(self, dat):
        self.text = dat + self.text

    def append(self, dat):
        self.text += dat

    def write(self):
        self.write_text(self.text)


class Smali(TextFile):

    class _method:
        def __init__(self, meth):
            (
                self.mod,
                self.name,
                self.param,
                self.rtype,
                self.reg,
                self.regcount,
                self.content

            ) = rgx['methinfo'].findall(meth)[0]

            self.mod = self.mod.strip()

    class _field:
        def __init__(self, field):
            (
                self.mod,
                self.name,
                self.rtype,
                self.value,

            ) = rgx['fieldinfo'].findall(field)[0]

    def __init__(self, *a, **kv):
        super().__init__(*a, **kv)
        self.klass = self.find('.class ').split()[-1]
        self.zuper = self.find('.super ').split()[-1]
    
    def methods(self):
        for i in rgx['method'].findall(self.text):
            yield self._method(i)

    def fields(self):
        for i in self.text.splitlines():
            if i.startswith('.field'):
                yield self._field(i)


class ApkEditor:
    jar = Path('assets/apkeditor.jar')
    tmp = Path(__import__('tempfile').gettempdir())
    src = tmp / f'apkeditor.{os.getpid()}'

    def __init__(self, apk):
        if not shutil.which('java'):
            raise Exception('Java executable not found!')

        if not self.jar.exists():
            print('Apkeditor not found. downloading ...')

            try:
                self.jar.parent.mkdir(exist_ok=True)
                urlretrieve(url, str(self.jar))
            except:
                raise Exception('Error while downloading apkeditor')

            print('Saved to:', str(self.jar))

        self.apk = Path(apk)
        #self.apk = Apk(apk)

    def edit(self):
        self.editing = True

        splits = ['apks', 'xapk', 'apkm']
        if self.apk.name.split('.')[-1] in splits:
            self.merge()

        self.decode('-no-dex-debug')

        self.manifest = TextFile(self.src / 'AndroidManifest.xml')
        self.package = self.manifest.find('package=')
        self.classes = self.src / 'smali'

    def dexcount(self):
        if self.editing:
            return len(list(self.classes.iterdir()))
        return 0

    def search(self, content, root=None):
        root = root or self.src
        patt = re.compile(content)

        for r,_,files in os.walk(str(root)):
            for i in files:
                file = os.path.join(r, i)

                if file.endswith('.smali'):
                    f = Smali(file)
                else:
                    f = TextFile(file)

                found = False
                for i in f.finditer(patt):
                    if i: found = True
                    break

                if not found: continue

                yield f

    def exec(self, c, i, o, *a):
        cmd = ['java', '-jar', str(self.jar)]
        arg = [c, '-i', str(i), '-o', str(o)] + list(a)

        try:
            subprocess.run(cmd + arg, check=True)
        except:
            self.cleanup()
            raise Exception(f'Apkeditor error : {" ".join(arg)}')

    def merge(self):
        apk = str(self.apk).split('.')
        apk[-1] = 'apk'
        apk = '.'.join(apk)
        self.exec('m', self.apk, apk)
        self.apk = Path(apk)

    def decode(self, *a):
        self.exec('d', self.apk, self.src, *a)

    def build(self, out, *a):
        if self.src.is_dir():
            self.exec('b', self.src, out, *a)
            return

        print('Decompiled source missing, build nothing.')

    def cleanup(self):
        shutil.rmtree(self.src)
