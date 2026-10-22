"""Pinned official source; existing bytes must match the manifest. No latest fallback."""
import json,urllib.request
from common import ROOT,sha
manifest=json.loads((ROOT/'data/source_manifest.json').read_text())
for item in manifest['files']:
    p=ROOT/'data/raw'/item['file']
    if not p.exists():
        req=urllib.request.Request(item['source_url'],headers={'User-Agent':'CommunitySafetyPortfolio/1.0'})
        data=urllib.request.urlopen(req,timeout=60).read()
        if sha(data)!=item['sha256']: raise RuntimeError('Source integrity mismatch: '+item['file'])
        p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
    assert sha(p.read_bytes())==item['sha256'], 'Integrity mismatch: '+str(p)
print('Verified official source hashes:',len(manifest['files']))
