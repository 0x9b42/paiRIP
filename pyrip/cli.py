from pyrip.utils import log
from pyrip.apkeditor import ApkEditor, Smali
from pathlib import Path
import sys

app = ApkEditor(sys.argv[1])


def patch_manifest():
    uses = '<uses-permission android:name="%s"/>\n'
    name = 'android.permission.%s_EXTERNAL_STORAGE'
    perm = ['READ', 'WRITE', 'MANAGE']

    log.i('Adding external storage permission...')
    tag = '</manifest>'

    for i in perm:
        n = name % i

        if app.manifest.find(n):
            log.i('Found:', n)
            continue

        app.manifest.sub(tag, uses % n + tag)
        log.s('Added:', n)

    legacy = 'android:requestLegacyExternalStorage='

    app.manifest.rsub(legacy + ".*?", '')
    tag = '<application'
    app.manifest.sub(tag, tag + '\n' + legacy + '"true"')
    log.s('Added:', legacy + '"true"')

    app.manifest.rsub('<activity(?s:[^<]+?)pairip.+LicenseActivity(?s:.+?)>', '')
    log.s('Removed pairip LicenseActivity')

    app.manifest.rsub('<provider(?s:[^<]+?)pairip.+LicenseContentProvider(?s:.+?)>', '')
    log.s('Removed pairip LicenseContentProvider')

    app.manifest.write()


def pairip_smali():
    patt = r'.field public static \w+:.+String;'

    alpha = '\n'.join([
        '.method public static %s()V',
        '\t.registers 2',
        '\t%s',
        '\treturn-void',
        '.end method'
    ])

    eta = '\n\t'.join([
        'sget-object v0, %s',
        'const-string v1, "%s"',
        '.line %d',
        '.local v0, "%s":V',
        'invoke-static {v0}, Lmt/Objectlogger;->logstring(Ljava/lang/Object;)V',
        'sput-object v0, %s'
    ])

    jav = '0x9b42_%d.java'
    #mob = 'ignoramus'
    mob = 'appkiller'
    #tet = 'ignorabimus'
    tet = 'callobjects'

    n = 0
    tot = 0
    beta = ''

    for file in app.search(patt, root = app.classes):
        if file.find('.method '):
            continue

        file = Smali(file)

        source = jav % n
        file.prepend(f'.source "{source}"\n')

        log.i('Injecting logger at', file.klass)

        zeta = ''
        line = 1

        for i in file.fields():
            faccess = f'{file.klass}->{i.name}:{i.rtype}'
            sline = f'{source}:{line}'
            zeta += eta % (faccess, sline, line, sline, faccess)
            line += 1 

        tot += line - 1
        beta += '\n\tinvoke-static {}, %s->%s()V' % (file.klass, mob)

        file.append(alpha % (mob, zeta))
        file.write()
        n += 1

    log.s(f'Processed {tot} pairip strings in {n} classes')

    entry = None

    for i in app.classes.glob('*/com/pairip/application/Application.smali'):
        entry = Smali(i)
        break

    if not entry:
        log.e('Application.smali not found')
        raise

    entry.append(alpha % (tet, beta))

    pinit = r'(?s)(\.method\s.+<init>\(.+?)[\n\s]+return-void'

    for i in entry.rfindall(pinit):
        new = '\n\tinvoke-static {}, %s->%s()V' % (entry.klass, tet)
        entry.sub(i.group(1), i.group(1) + new)
        break

    entry.write()
    log.s('Added objects caller to', entry.klass)

    lg = Smali('assets/mt/Objectlogger.smali')
    lg.sub('MOBPKAGE', app.package)

    logger = app.classes / f'classes{app.dexcount() + 1}' / 'mt' / 'Objectlogger.smali'
    logger.parent.mkdir(parents=True)
    logger.write_text(lg.text)
    


def bypass_checks():
    v3 = None
    c3 = None

    for i in app.classes.glob('*/com/pairip/**/LicenseClientV3.smali'):
        v3 = str(i)
        break

    if not v3:
        for i in app.classes.glob('*/com/pairip/**/LicenseClient.smali'):
            v3 = str(i)
            break

    v3 = Smali(v3)

    for i in app.classes.glob('*/com/pairip/**/SignatureCheck.smali'):
        c3 = str(i)
        break

    c3 = Smali(c3)

    cek = [
        'connectToLicensingService',
        'initializeLicenseCheck',
        'processResponse',
        'verifyIntegrity',
        'verifySignatureMatches',
    ]
    
    def mclear(x):
        m = '\n'.join([
            '.method %s %s(%s)%s' % (x.mod, x.name, x.param, x.rtype),
            '\t.%s %s' % (x.reg, x.regcount),
            '\t%s',
            '.end method'
        ])

        if x.rtype == 'V':
            return m % 'return-void'
        else:
            return m % 'const/4 p0, 0x1\n\treturn p0'

    p = r'\.method\s.+?%s\((?s:.+?)\.end method'

    for x in [v3, c3]:
        for y in x.methods():
            if y.name in cek:
                x.rsub(p % y.name, mclear(y))
                log.s('Bypassed:', y.name)

        x.write()


def rip():
    log.i('Starting...')
    app.edit()

    log.i('Patching manifest...')
    patch_manifest()

    log.i('Scanning smali for pairip strings...')
    pairip_smali()

    log.i('Bypassing other checks...')
    bypass_checks()

    log.i('Building modified source...')
    app.build('apps.apk', '-f')

    log.w('Cleaning up...')
    app.cleanup()

