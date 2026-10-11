import json,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
accounts=json.loads((Path(__file__).resolve().parents[1]/'work/demo-access.json').read_text())
base='http://localhost:8081'
ids=[]
for account in [a for a in accounts if a['role']=='staff']:
    jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request=urllib.request.Request(base+'/api/auth/login',data=json.dumps({'email':account['email'],'password':account['password']}).encode(),headers={'Content-Type':'application/json'},method='POST')
    result=json.load(client.open(request));assert result['csrf_token']
    me=json.load(client.open(base+'/api/auth/me'));ids.append(me['tenant_id'])
    assert me['venue']['slug']==account['slug']
    resources=json.load(client.open(base+'/api/admin/resources'));assert len(resources)==5
    events=json.load(client.open(base+'/api/admin/notifications'))
    assert events and all(e['status'] in {'done','pending','cancelled'} for e in events)
    print(account['slug']+': login, sede, tavoli e outbox verificati')
assert len(set(ids))==2
ready=json.load(urllib.request.urlopen(base+'/ready'));assert ready['status']=='ready'
print('Demo Compose pronta; due tenant distinti. Nessun invio reale.')
