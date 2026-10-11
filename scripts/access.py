import json,base64,struct,hmac,hashlib,time
from pathlib import Path
accounts=json.loads((Path(__file__).resolve().parents[1]/'work/demo-access.json').read_text())
for a in accounts:
    print(f"{a['restaurant']} | {a['role']} | {a['email']} | {a['password']}")
    if a.get('mfa_secret'):
        secret=a['mfa_secret']; key=base64.b32decode(secret+'='*((8-len(secret)%8)%8))
        value=hmac.new(key,struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest();offset=value[-1]&15
        code=(struct.unpack('>I',value[offset:offset+4])[0]&0x7fffffff)%1000000
        print(f'  MFA corrente: {code:06d} (rigenerare ogni 30 secondi)')
