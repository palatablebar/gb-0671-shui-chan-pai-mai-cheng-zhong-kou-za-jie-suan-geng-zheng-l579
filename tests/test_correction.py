from app.modules.correction.rules import select_versions
from app.engine import evaluate

def test_current_real(sample):
    assert sample['final'][0]['version']==2
def test_only_delta_paid_real(sample):
    assert sample['final'][0]['due']=='116.85'
def test_not_double_paid_real(sample):
    assert sample['balance']['paid']=='1168.50'
def test_stale_branch(clean):
    # TRAP-26
    rows=[dict(r) for r in clean['settlements'][:2]];rows.append(dict(rows[-1],version=3,replaces='1'));final,bad,_=select_versions(rows);assert not final;assert bad[0]['code']=='STALE_CORRECTION'
def test_missing_base(clean):
    final,bad,_=select_versions(clean['settlements'][1:2]);assert not final;assert bad[0]['code']=='MISSING_BASE'
def test_reverse_versions(clean):
    a=select_versions(clean['settlements']);b=select_versions(list(reversed(clean['settlements'])));assert a==b
def test_overpayment_credit(clean):
    row=dict(clean['settlements'][0],paid='1200');final,_,_=select_versions([row]);assert final[0]['due']=='-31.50'

def test_stale_conflict_pinpoints_break(clean):
    rows=[dict(r) for r in clean['settlements'][:2]];rows.append(dict(rows[-1],version=3,replaces='1'))
    final,bad,_=select_versions(rows)
    c=bad[0]
    assert c['replaces']=='1' and c['expected']==2 and c['lines'] and '断' in c['detail']
    assert 'amount' not in c and 'due' not in c and 'paid' not in c

def test_missing_base_pinpoints_break(clean):
    _,bad,_=select_versions(clean['settlements'][1:2])
    assert bad[0]['replaces']=='1' and '缺前版' in bad[0]['detail']
    assert 'amount' not in bad[0] and 'due' not in bad[0]

def test_direction_labels(clean):
    base=clean['settlements'][0]
    over=dict(base,paid='1200');assert select_versions([over])[0][0]['direction']=='收回'
    under=dict(base,paid='1000');assert select_versions([under])[0][0]['direction']=='补付'
    exact=dict(base,paid=base['amount']);assert select_versions([exact])[0][0]['direction']=='结清'

def test_replaces_leading_zero_normalized():
    csv_text=('id,ticket,kind,weight,unit,fish,price,rate,version,replaces,paid\n'
      '00001gross,00001,gross,115,kg,黄鱼,12.30,0.05,1,,0\n'
      '00001tare,00001,tare,15,kg,黄鱼,12.30,0.05,1,,0\n'
      '00001v2gross,00001,gross,125,kg,黄鱼,12.30,0.05,2,01,1168.50\n'
      '00001v2tare,00001,tare,15,kg,黄鱼,12.30,0.05,2,01,0\n')
    s=evaluate({'csv_text':csv_text})
    assert not s['version_conflicts'] and s['final'][0]['replaces']=='1'

def test_replaces_garbage_quarantined():
    csv_text=('id,ticket,kind,weight,unit,fish,price,rate,version,replaces,paid\n'
      '00001gross,00001,gross,115,kg,黄鱼,12.30,0.05,1,,0\n'
      '00001tare,00001,tare,15,kg,黄鱼,12.30,0.05,1,,0\n'
      '00001v2gross,00001,gross,125,kg,黄鱼,12.30,0.05,2,abc,1168.50\n'
      '00001v2tare,00001,tare,15,kg,黄鱼,12.30,0.05,2,abc,0\n')
    s=evaluate({'csv_text':csv_text})
    assert {r['code'] for r in s['quarantine']}=={'BAD_NUMBER'}
    assert [f['version'] for f in s['final']]==[1]

def test_correction_view_rows_sorted_with_conflicts(clean):
    rows=[dict(r) for r in clean['settlements'][:2]];rows.append(dict(rows[-1],version=3,replaces='1'))
    clean['settlements']=rows
    from app.modules.correction.rules import apply
    apply(clean)
    view_rows=clean['views']['correction']['rows']
    assert [(r['ticket'],r['version']) for r in view_rows]==sorted((r['ticket'],r['version']) for r in view_rows)
    assert any(r.get('code')=='STALE_CORRECTION' for r in view_rows)
