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
    LOG.i('[RMDIR]', dir)

    try: shutil.rmtree(dir)
    except Exception as e:
        print(e)
        sys.exit(1)

    LOG.d('removed successfully')


def mkdir(dir):
    LOG.i('[MKDIR]', dir)
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
    LIB = {
        'pairipcore': False,
        'il2cpp': False
    }
    isIjiami = False

    def __init__(self, path):
        if not path.endsWith('.apk'):
            raise Exception(f'{path} is not an APK file')

        self.PATH = path
        
        crc = {}
        for i in self.infolist():
            crc[i.filename] = i.CRC

            lib = lambda x: re.match(f'lib/.+/lib{x}.so', i.filename)

            for l in self.LIB:
                if lib(l):
                    self.LIB[l] = True

        self.CRC = crc

    def infolist(self, path=''):
        path = path or self.PATH
        with ZipFile(path) as z:
            return z.infolist()

    def patch_CRC(self, apk):
        crc_byte = lambda x: x.to_bytes(4, byteorder='little')

        with open(self.PATH, 'rb') as f:
            dat = bytearray(f.read())

        for k, v in self.CRC.items():

            if k not in apk.crc: continue

            if v != apk.CRC[k]:
                m = crc_byte(v)
                n = crc_byte(apk.CRC[k])
                dat = dat.replace(m, n)

        return dat


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
            raise Exception(f'failed to run {C.y + ' '.join(cmd)}')

    def merge(self, apks, out):
        LOG.i(f'[MERGE] {apks} => {out}')
        self.exec('m', apks, out)
        LOG.d('merged successfully')

    def decode(self, apk, out):
        LOG.i(f'[DECODE] {apk} => {out}')
        self.exec('d', apk, out, '-no-dex-debug')
        LOG.d('decompiled successfully')

    def build(self, src, out):
        LOG.i(f'[BUILD] {src} => {out}')
        self.exec('b', src, out, '-f')
        LOG.d('built successfully')


class MobLogger:
    def __init__(self, src):
        self.SRC = src


class Rip:
    POS = f'rip.{os.getpid()}'
    TMP = os.path.join(tempfile.gettempdir(), POS)
    ESP = {  # External Storage Permission
        'READ': False, 'WRITE': False, 'MANAGE': False
    }

    def __init__(self, path):
        self.PATH = path
        self.OUT = self.ext_swap(path, '_rip.apk')
        self.ANU = self.ext_swap(path, '_getlog.apk')
        self.ORI = os.path.join(
            self.TMP, os.path.basename(self.OUT)
        )
        self.SRC = self.ORI + '_src'
        self.AMX = os.path.join(self.SRC, 'AndroidManifest.xml')

    def fuck(self):
        J = APKEditor()

        LOG.i('creating temporary folder...')
        mkdir(self.TMP)

        if self.is_split():
            LOG.w('split apk detected')
            J.merge(self.PATH, self.ORI)

        else:
            shutil.copy(self.PATH, self.ORI)

        J.decode(self.ORI, self.SRC)

        #self.manifest_patch()
        self.inject_logger()
        self.bypass_checks()

        if os.path.isfile(self.OUT):
            LOG.w('file exists:', C.y + self.OUT)

            if nope('overwrite it?'):
                LOG.w('operation aborted. cleaning up...')
                rmdir(self.TMP)
                sys.exit(1)

        J.build(self.SRC, self.OUT)

        self.patch_crc()
        self.pairip_fuck()

        LOG.i('operation finished, cleaning up...')
        rmdir(self.TMP)

    def ext_swap(self, path, ext, o='.'):
        return o.join(path.split(o)[:-1] + [ext])

    def is_split(self, path=''):
        path = path or self.PATH
        return re.match(r'\.x?apk[sm]?', path.lower()[-5:])

    def manifest_patch(self):
        uses = '<uses-permission android:name="{}"/>'
        name = 'android.permission.{}_EXTERNAL_STORAGE"'
        tag = '</manifest>'

        with open(self.AMX, 'r') as f:
            mnf = f.read()

        for i in self.ESP:
            x = name.format(i)
            m = re.search(x, mnf)

            if m: self.ESP[i] = True

            else:
                y = uses.format(x) + '\n' + tag
                mnf = re.sub(tag, y, mnf)
                LOG.d('added permission:', x)

        with open(self.AMX, 'w') as f:
            f.write(mnf)

    def inject_logger(self):
        pass

    def bypass_checks(self):
        pass

    def patch_crc(self):
        crc_byte = lambda x: x.to_bytes(4, byteorder='little')

        ori = Apk(self.ORI)
        mod = Apk(self.ANU)

        with open(mod.PATH, 'rb') as f:
            dat = bytearray(f.read())

        for file, mod_crc in mod.CRC.items():

            if file not in ori.CRC: continue

            if mod_crc != ori.CRC[file]:
                m = crc_byte(mod_crc)
                n = crc_byte(ori.CRC[file])
                dat = dat.replace(m, n)

                LOG.d(f'[PATCHED] {os.path.basename(file)} ({m} => {n})')

        with open(self.ANU, 'wb') as f:
            f.write(dat)

    def pairip_fuck(self):
        mtd = input('generated mtd file path: ')
        return mtd

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
        LOG.w('cleaning up...')
        rmdir(rip.TMP)
        raise
