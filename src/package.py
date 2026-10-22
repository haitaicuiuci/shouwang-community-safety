"""Create a public-safe source and portfolio bundle; no raw text, local DB or model."""
import zipfile
from common import ROOT,dump,sha
allowed_files={'README.md','NOTICE','LICENSE','.gitignore','requirements.txt','run.sh','portfolio.html','dashboard-preview.png'}
allowed_dirs={'src','sql','config','docs','tests','dashboard'}
allowed_artifacts={'verification-tests.txt','results.json','quality.json','policy.json','validation_search.json','sql_results.json','run_manifest.json','reproducibility.json','verification.json','http_verification.json','predictions.csv'}
files=[]
for p in ROOT.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts or '.venv' in p.parts:continue
 rel=p.relative_to(ROOT)
 if (str(rel) in allowed_files or rel.parts[0] in allowed_dirs or str(rel)=='data/source_manifest.json' or str(rel) in ('data/raw/LICENSE','data/raw/README.md') or (rel.parts[0]=='artifacts' and p.name in allowed_artifacts)):files.append(p)
archive=ROOT.parent/'community-safety-share.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,'community-safety/'+str(p.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:
 for n in z.namelist():assert not n.endswith(('.sqlite','.joblib')) and not ('/data/raw/' in n and n.endswith('.csv'))
dump(ROOT.parent/'share_manifest.json',{'archive':archive.name,'sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size,'file_count':len(files),'exclusions':['raw CSV','SQLite DBs','trained model','split hashes','human events'],'files':[str(p.relative_to(ROOT)) for p in sorted(files)]})
print(archive)
