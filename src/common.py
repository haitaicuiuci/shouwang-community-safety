import hashlib,json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(data): return hashlib.sha256(data).hexdigest()
def normalize(text):
    text=unicodedata.normalize('NFKC',text).lower()
    return ''.join(c for c in text if c.isalnum())
def redact(text):
    text=re.sub(r'https?://\S+|www\.\S+','[链接]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[邮箱]',text)
    text=re.sub(r'@[^\s，。！？:：]+','[用户]',text)
    text=re.sub(r'\d{3,}','[数字]',text)
    return text
