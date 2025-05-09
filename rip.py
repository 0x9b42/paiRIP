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


def rmdir(dir):
    LOG.i('rmdir', dir)

    try: shutil.rmtree(dir)
    except Exception as e:
        print(e)
        sys.exit(1)

    LOG.d('deleted:', dir)


def mkdir(dir):
    LOG.i('mkdir', dir)
    os.makedirs(dir, exist_ok=True)


def nope(q):
    LOG.w(q, end='')
    y = input(' [y/N]: ').strip().lower()
    return False if y in ['y', 'yes'] else True


def civis(t):
    sys.stdout.write('\x1b[?25' + ('l' if t else 'h'))
    sys.stdout.flush()


if len(sys.argv) < 2:
    LOG.e(f'usage: python {sys.argv[0]} {os.path.join(*'path to apk'.split())}')
    sys.exit(1)


class Apk:
    isPairip = False
    isUnity = False
    isIjiami = False

    def __init__(self, path):
        if not path.endswith('.apk'):
            raise Exception(f'{path} bukan format APK')

        self.PATH = path
        self.DATA = self.data()
        
        crc = {}
        for i in self.DATA.infolist():
            crc[i.filename] = i.CRC

            lib = lambda x: re.match(f'lib/.+/lib{x}.so', i.filename)

            if lib('pairipcore'): self.isPairip = True
            if lib('il2cpp'): self.isUnity = True

        self.CRC = crc

    def data(self, path=''):
        path = path or self.PATH
        with ZipFile(self.PATH, 'r') as z:
            return z

    def infolist(self, path=''):
        path = path or self.PATH
        with ZipFile(path) as z:
            return z.infolist()


class APKEditor:
    jar = os.path.join('assets', 'APKEditor.jar')
    url = 'https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar'

    def __init__(self):

        if not os.path.isfile(self.jar):
            mkdir('assets')
            LOG.i('mengunduh APKEditor.jar...')
            urllib.request.urlretrieve(self.url, self.jar)
            LOG.i('disimpan ke:', self.jar)

        if not shutil.which('java'):
            LOG.e('java tidak ditemukan')
            LOG.i('jdk dibutuhkan untuk menjalankan APKEditor', self.jar)
            sys.exit(1)

    def exec(self, c, i, o, *opts):
        cmd = ['java', '-jar', self.jar, c, '-i', i, '-o', o] + list(opts)
        LOG.log(C.y + 'APKEditor', c.upper(), f'{i} => {o}')

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        except Exception as e:
            print(e)
            raise Exception(f'failed to run {C.y + ' '.join(cmd)}')

    def merge(self, apks, out):
        self.exec('merge', apks, out)
        LOG.d('konversi berhasil:', out)

    def decode(self, apk, out):
        self.exec('decode', apk, out, '-no-dex-debug')
        LOG.d('dekompilasi berhasil:', out)

    def build(self, src, out):

        if os.path.isfile(out):
            LOG.w('file ditemukan:', out)

            if nope('timpa file?'):
                raise Exception('operasi dibatalkan oleh user')

        self.exec('build', src, out, '-f')
        LOG.d('kompilasi berhasil:', out)


class Smali:
    def __init__(self, path):
        with open(path, 'r') as f:
            d = f.read()

        self.path = path
        self.content = d
        self.klas = re.search('.class.+ (L.+)', d).group(1)
        self.zuper = re.search('.super (.+)', d).group(1)

    def replace(self, pat, rep):
        self.content = re.sub(pat, rep, self.content)

    def append(self, dat):
        self.content = self.content + dat

    def write(self):
        with open(self.path,'w') as f:
            f.write(self.content)


class Rip:
    POS = f'rip.{os.getpid()}'
    TMP = os.path.join(tempfile.gettempdir(), POS)

    def __init__(self, path):
        self.PATH = path
        swp = lambda x, y: (x[:-5] if self.is_split() else x[:-4]) + y
        self.ANU = swp(path, '_log.apk')
        self.OUT = swp(path, '_rip.apk')
        self.ORI = os.path.join(self.TMP, os.path.basename(self.OUT))
        self.SRC = swp(self.ORI, '_src')
        self.AMX = os.path.join(self.SRC, 'AndroidManifest.xml')
        self.COM = os.path.join('com', 'pairip')

    def sfiles(self):
        p = os.path.join(self.SRC, 'smali')
        
        sml = []
        for r,_,f in os.walk(p):
            sml = sml + [os.path.join(r, i) for i in f]

        return sml

    def fuck(self):
        J = APKEditor()

        LOG.i('membuat folder dapur...')
        mkdir(self.TMP)

        if self.is_split():
            LOG.w('split apk detected')
            J.merge(self.PATH, self.ORI)

        else:
            shutil.copy(self.PATH, self.ORI)

        LOG.i('dekompilasi APK...')
        J.decode(self.ORI, self.SRC)

        self.manifest_patch()
        self.inject_logger()
        self.bypass_checks()

        LOG.i('kompilasi sumber termodifikasi...')
        J.build(self.SRC, self.SRC + '.apk')

        self.patch_crc()
        self.pairip_fuck()

        LOG.i('kompilasi APK tanpa pairip...')
        J.build(self.SRC, self.OUT)

        LOG.i('operasi selesai. menghapus sisa dapur...')
        rmdir(self.TMP)

    def is_split(self, path=''):
        path = path or self.PATH
        return re.match(r'\.x?apk[sm]?', path.lower()[-5:])

    def manifest_patch(self):
        uses = '<uses-permission android:name="{}"/>'
        name = 'android.permission.{}_EXTERNAL_STORAGE'
        perm = ['READ', 'WRITE', 'MANAGE']
        tag = '</manifest>'
        
        LOG.i('memodifikasi manifes...')
        shutil.copy(self.AMX, self.AMX + '.bak')

        with open(self.AMX, 'r') as f:
            mnf = f.read()

        for i in perm:
            x = name.format(i)
            m = re.search(x, mnf)

            if m:
                LOG.i('ijin ditemukan:', x)

            else:
                y = uses.format(x) + '\n' + tag
                mnf = re.sub(tag, y, mnf)
                LOG.d('ijin ditambahkan:', x)

        a = '<application'
        p = 'android:requestLegacyExternalStorage'
        mnf = re.sub(p + r'="\w*"', '', mnf)
        mnf = re.sub(a, f'{a}\n{p}="true"', mnf)

        with open(self.AMX, 'w') as f:
            f.write(mnf)

    def inject_logger(self):
        LOG.i('injecting logger...')

        mob = 'ignoramus'
        cid = 'ignorabimus'
        yor = lambda x, y: f'\ninvoke-static {{}}, {x}->{y}()V\n'
        zet = lambda x, y: f'\n.method public static {x}()V\n.registers 1\n{y}\nreturn-void\n.end method'
        log = '\nsget-object v0, {}\n.line {}\n.local v0, "{}:{}":V\ninvoke-static {{v0}}, Lmob/Logger;->log(Ljava/lang/Object;)V\nsput-object v0, {}'
        jav = '0x9b42_{}.java'
        pat = r'.field public static \w+:.+String;'
        sdir = os.path.join(self.SRC, 'smali')
        cdir = os.path.join(sdir, 'classes{}')
        ripentry = 'Application.smali'

        def ld():  # last dex number
            l = []
            for i in os.scandir(sdir):
                l.append(re.sub('[^0-9]*', '', i.name) or 1)
            return max([int(i) for i in l])

        sml = self.sfiles()
        LOG.i('mencari string pairip...')

        pai = {}
        iap = []
        for i in sml:

            if self.COM in i:

                if i.endswith(ripentry):
                    ripentry = i

                continue

            with open(i, 'r') as f:
                s = re.findall(pat, f.read())
                if s:
                    pai[i] = s
                    iap.append(
                        re.findall(r'.+\bclasses\d*.\w+', i)[0]
                    )

        iap = set(iap)

        LOG.i(f'memproses {len(pai)} class...')

        alpha = ''
        x = 0
        for k, v in pai.items():
            sf = Smali(k)
            alpha = alpha + yor(sf.klas, mob)
            xXx = jav.format(x)
            inv = ''

            LOG.i(f'menginjeksi logger untuk {len(v)} string di {sf.klas}')

            for n, i in enumerate(v):
                i = re.sub('.+static ', '', i)
                u = sf.klas + '->' + i
                inv = inv + log.format(u, n+1, xXx, n+1, u)

            m = zet(mob, inv)

            sf.append(m)
            
            s = '.super ' + sf.zuper
            t = s + f'\n.source "{xXx}"'

            sf.replace(s, t)
            sf.write()

            x = x + 1

        beta = Smali(list(pai.keys())[0])
        beta.append(zet(cid, alpha))
        beta.write()

        rp = Smali(ripentry)
        caller = yor(beta.klas, cid)
        pinit = r'(.method .+<init>(?s:.+?))(return-void(?s:.+?).end method)'
        pm = re.findall(pinit, rp.content)
        pm = list(pm[0])
        print(pm)
        rp.replace(pinit, pm[0] + caller + pm[1])
        rp.write()

        LOG.i('objek caller ditambahkan ke', os.path.basename(ripentry))

        mkdir(cdir.format(ld()+1))

        slog = os.path.join(cdir.format(ld()), 'mob')
        shutil.copytree(os.path.join('assets', 'mob'), slog)

        for i in iap:
            shutil.move(
                i, re.sub(r'\bclasses\d*', f'classes{ld()}', i)
            )

        LOG.d('berhasil menginjeksi logger')

    def bypass_checks(self):
        LOG.i('bypass pengecekan integrity dan signature...')
        
        f = ','.join(self.sfiles())
        p = lambda x: f'[^,]*{x}.smali'

        clases = re.findall(p('LicenseClientV3') + '|' + p('SignatureCheck'), f)

        met = r'(.method .+\b{}\b.+{}[\s\S]+?.locals \d+)(?s:.+?)(.end method)'
        cek = [
            ('connectToLicensingService', 'V'),
            ('initializeLicenseCheck', 'V'),
            ('processResponse', 'V'),
            ('verifyIntegrity', 'V'),
            ('verifySignatureMatches', 'Z'),
        ]

        v = '\nreturn-void\n'
        z = '\nconst/4 p0, 0x1\nreturn p0\n'
        rep = lambda x, y: x + (v if r == 'V' else z) + y

        for i in clases:
            s = Smali(i)

            for n, r in cek:
                p = met.format(n, r)
                m = re.findall(p, s.content)

                if m:
                    LOG.i(f'memodifikasi {os.path.basename(i)}->{n}')
                    n = rep(*m[0])
                    s.replace(p, n)

            s.write()

        LOG.d('bypass sukses')

    def patch_crc(self):
        LOG.i('memalsukan CRC data...')

        ori = Apk(self.ORI)
        mod = self.SRC + '.apk'

        with ZipFile(mod, 'r') as m:
            with ZipFile(self.ANU, 'w') as o:
                for i in m.infolist():
                    dat = m.read(i.filename)

                    if i.filename in ori.CRC:
                        i.CRC = ori.CRC[i.filename]

                    o.writestr(i, dat)

    def mtd2dict(self, mtd):
        with open(mtd, 'r') as f:
            d = re.findall(r'\{.+?\}', f.read())

        r = {}
        for i in d:
            m = list(re.findall('(".+")\n(".+")', i))
            r[m[0]] = m[1]

        return r

    def pairip_fuck(self):
        mtd = ''
        while not(mtd and os.path.isfile(mtd)):
            mtd = input('file .mtd: ')

        LOG.i('google asw...', mtd)
        #dic = self.mtd2dict(mtd)
        
        shutil.copy(self.AMX + '.bak', self.AMX)
        LOG.d('mengembalikan manifes ke semula')

        # restore pairip strings
        p = r'const.+(.\d+).+[\n\s]sget.+?(.\d+)'

        # remove pairip invokes

        # other replacements


banner = '''
#######################
 pairip removal script
#######################
'''

if __name__ == '__main__':
    print(banner)
    APK = sys.argv[1]
    rip = Rip(APK)

    try: rip.fuck()

    except Exception as e:
        LOG.e(e)
        LOG.w('membersihkan dapur...')
        rmdir(rip.TMP)
        raise

    except KeyboardInterrupt:
        LOG.e('operasi dibatalkan oleh user')
        rmdir(rip.TMP)
