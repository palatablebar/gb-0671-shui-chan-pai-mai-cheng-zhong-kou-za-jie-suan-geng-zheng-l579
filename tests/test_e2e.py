from fastapi.testclient import TestClient
from app import main,store
from app.engine import evaluate
from app.errors import BusinessError
import pytest

def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB_PATH',str(tmp_path/'test.sqlite'))
    return TestClient(main.app)
def test_api_run_idempotent(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);a=c.post('/api/runs',json={}).json();b=c.post('/api/runs',json={}).json();assert a['manifest']['run_id']==b['manifest']['run_id'];assert len(c.get('/api/runs').json())==1
def test_review_stale_http(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);a=c.post('/api/runs',json={}).json();url='/api/runs/'+a['manifest']['run_id']+'/review';assert c.post(url,json={'revision':1}).status_code==200;assert c.post(url,json={'revision':1}).status_code==409
def test_all_modules_and_pages(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    for k in main.MODULES:
        assert c.post('/api/'+k,json={}).status_code==200
        assert c.get('/'+k).status_code==200
def test_unknown_batch_http(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);assert c.get('/api/runs/missing').status_code==404
def test_bad_sample_http(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);assert c.post('/api/runs',json={'dataset':'../x'}).status_code==422
def test_persistence_after_new_connection(tmp_path,sample):
    path=str(tmp_path/'durable.sqlite');store.save(path,sample);assert store.get(path,sample['manifest']['run_id'])['balance']['due']=='22540.41'
def test_invalid_review_does_not_change(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);s=c.post('/api/runs',json={}).json();rid=s['manifest']['run_id'];assert c.post('/api/runs/'+rid+'/review',json={'revision':0}).status_code==422;assert c.get('/api/runs/'+rid).json()['revision']==1

def test_clean_navigation_run_preserved(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'dataset':'clean'}).json()
    rid=run['manifest']['run_id']
    for k in main.MODULES:
        html=c.get('/'+k+'?run_id='+rid).text
        assert '?run_id='+rid in html
        assert rid in html
    assert c.get('/api/export/'+rid).status_code==200

def test_custom_csv_snapshot_and_navigation(tmp_path,monkeypatch):
    from app.config import ROOT
    c=client(tmp_path,monkeypatch)
    original=(ROOT/'sample_data/clean.csv').read_text()
    # 改成独立于所有仓内样例的证据编号，追踪其跨页与重跑行为。
    first=original.splitlines()[1].split(',')[0]
    custom=original.replace(first,first+'-CUSTOM')
    result=c.post('/api/runs',json={'csv_text':custom}).json()
    rid=result['manifest']['run_id']
    assert '-CUSTOM' in str(result['records']) or '-CUSTOM' in str(result['quarantine'])
    for key in main.MODULES:
        response=c.get('/'+key+'?run_id='+rid)
        assert response.status_code==200
        assert '?run_id='+rid in response.text
    repeated=c.post('/api/runs/'+rid+'/rerun',json={})
    assert repeated.status_code==200
    assert repeated.json()['manifest']['run_id']==rid
    assert repeated.json()['manifest']['sha256']==result['manifest']['sha256']

def stale_batch():
    from app.config import ROOT
    clean=(ROOT/'sample_data/clean.csv').read_text()
    return (clean+
      '00001v3gross,00001,gross,130,kg,黄鱼,12.30,0.05,3,1,0\n'
      '00001v3tare,00001,tare,15,kg,黄鱼,12.30,0.05,3,1,0\n')

def test_rerun_adds_no_duplicate_payment(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={}).json();rid=run['manifest']['run_id']
    again=c.post('/api/runs/'+rid+'/rerun',json={}).json()
    assert again['manifest']['run_id']==rid
    assert len(c.get('/api/runs').json())==1
    assert again['balance']['paid']=='1168.50' and again['balance']['due']=='22540.41'

def test_review_rejected_when_archive_not_ready(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'csv_text':stale_batch()}).json()
    rid=run['manifest']['run_id']
    assert run['archive']['status']=='待处理' and run['balance']['blocked']==1
    assert c.post('/api/runs/'+rid+'/review',json={'revision':1}).status_code==409
    kept=c.get('/api/runs/'+rid).json()
    assert kept['status']=='待复核' and kept['revision']==1
    paid_rows=[r for r in kept['views']['auction']['rows'] if r['ticket']=='00001']
    assert any(r['paid']=='1168.50' for r in paid_rows)

def test_correction_page_shows_reference_and_breakpoint(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'csv_text':stale_batch()}).json();rid=run['manifest']['run_id']
    html=c.get('/correction?run_id='+rid).text
    assert '引用版本' in html and '断点' in html
    assert 'STALE_CORRECTION' in html and '过期引用' in html
    panel=html.split('primary-panel')[1].split('</section>')[0]
    row_00001=[line for line in panel.split('</tr>') if '00001' in line][0]
    assert 'STALE_CORRECTION' in row_00001 and '1285.35' not in row_00001
    archive_html=c.get('/archive?run_id='+rid).text
    assert '待处理' in archive_html and 'STALE_CORRECTION' in archive_html
    reconcile_html=c.get('/reconcile?run_id='+rid).text
    assert '逐票应付' in reconcile_html

def test_correction_page_clean_batch_shows_delta(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={}).json();rid=run['manifest']['run_id']
    html=c.get('/correction?run_id='+rid).text
    assert '116.85' in html and '补付' in html and '已更正' in html
