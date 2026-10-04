import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'publish_android_download.sh'

class DownloadTests(unittest.TestCase):
    def run_publish(self, mode='success', digest=None, revision='a'*40):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp); root=p/'root'; (root/'android-incoming').mkdir(parents=True)
            payload=b'isolated-test-apk'; sha=hashlib.sha256(payload).hexdigest()
            (root/'android-incoming'/f'{sha}.apk').write_bytes(payload)
            bins=p/'bin'; bins.mkdir(); gateway=p/'gateway'; gateway.mkdir()
            docker='''#!/usr/bin/env python3
import os,sys,pathlib,shutil
args=sys.argv[1:]; base=pathlib.Path(os.environ['GATEWAY'])
with open(os.environ['COMMANDS'],'a') as f:f.write(' '.join(args)+'\\n')
if args[0]=='ps':
 print('gateway1' if os.environ['MODE']!='duplicate' else 'gateway1\\ngateway2')
elif args[0]=='cp':
 src,dst=args[1:]; dst=base/dst.split(':',1)[1].lstrip('/');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy(src,dst)
elif args[:3]==['exec','gateway1','mkdir']:
 (base/args[-1].lstrip('/')).mkdir(parents=True,exist_ok=True)
elif args[:3]==['exec','gateway1','mv']:
 (base/args[-2].lstrip('/')).rename(base/args[-1].lstrip('/'))
elif args[:3]==['exec','gateway1','ln']:
 dest=base/args[-1].lstrip('/');dest.unlink(missing_ok=True);dest.symlink_to(args[-2])
else:raise SystemExit('unexpected docker command')
'''
            curl='''#!/usr/bin/env python3
import os,sys,pathlib
url=next(a for a in sys.argv if a.startswith('https://'))
dest=pathlib.Path(sys.argv[sys.argv.index('-o')+1]); src=pathlib.Path(os.environ['GATEWAY'])/'srv/downloads'/url.rsplit('/',1)[1]
dest.write_bytes(b'wrong' if os.environ['MODE']=='bad-public' else src.read_bytes())
'''
            for name,body in [('docker',docker),('curl',curl)]:
                f=bins/name; f.write_text(body); f.chmod(0o755)
            script=p/'publish.sh'; script.write_text(SCRIPT.read_text().replace('root=/opt/job-lens',f'root={root}'))
            env=dict(os.environ,PATH=str(bins)+':'+os.environ['PATH'],GATEWAY=str(gateway),COMMANDS=str(p/'commands'),MODE=mode)
            if mode=='tampered': (root/'android-incoming'/f'{sha}.apk').write_bytes(b'changed')
            result=subprocess.run(['bash',str(script),digest or sha,revision],env=env,capture_output=True)
            latest=root/'downloads/joblens-android-test.apk'
            commands=(p/'commands').read_text() if (p/'commands').exists() else ''
            return result.returncode, latest.exists(), commands

    def test_success(self):
        code,latest,commands=self.run_publish(); self.assertEqual(code,0);self.assertTrue(latest)
        self.assertNotIn('restart',commands);self.assertNotIn('compose',commands.replace('com.docker.compose',''))
        self.assertNotIn('windup',commands.lower())
    def test_invalid_hash(self): self.assertNotEqual(self.run_publish(digest='bad')[0],0)
    def test_invalid_revision(self): self.assertNotEqual(self.run_publish(revision='bad')[0],0)
    def test_tampered_apk(self):
        code,latest,commands=self.run_publish('tampered');self.assertNotEqual(code,0);self.assertFalse(latest);self.assertEqual(commands,'')
    def test_multiple_gateways(self):
        code,latest,_=self.run_publish('duplicate');self.assertNotEqual(code,0);self.assertFalse(latest)
    def test_public_mismatch_does_not_set_latest(self):
        code,latest,_=self.run_publish('bad-public');self.assertNotEqual(code,0);self.assertFalse(latest)

if __name__=='__main__': unittest.main()
