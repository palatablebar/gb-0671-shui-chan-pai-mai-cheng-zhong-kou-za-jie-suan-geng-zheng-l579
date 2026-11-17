from app.modules.archive.rules import archive_decision
from app.archive import serialize
from copy import deepcopy
import zipfile,io,json

def test_archive_ready_real(sample):
    assert sample['archive']['status']=='可归档'
def test_archive_tickets_real(sample):
    assert sample['archive']['tickets']==20
def test_archive_isolation_real(sample):
    assert sample['archive']['reasons']==8
def test_archive_blocked(sample):
    s=deepcopy(sample);s['balance']['blocked']=1;assert archive_decision(s)['status']=='待处理'
def test_archive_seal_changed(sample):
    s=deepcopy(sample);s['final'][0]['due']='0';assert archive_decision(s)['seal']!=sample['archive']['seal']
def test_bundle_evidence_real(sample):
    z=zipfile.ZipFile(io.BytesIO(serialize(sample)));data=json.loads(z.read('evidence.json'));assert len(data['quarantine'])==8
def test_bundle_manifest_real(sample):
    z=zipfile.ZipFile(io.BytesIO(serialize(sample)));assert json.loads(z.read('manifest.json'))['run_id']==sample['manifest']['run_id']

def test_archive_unique_current_required(sample):
    s=deepcopy(sample);s['final'].append(dict(s['final'][0]))
    d=archive_decision(s);assert d['status']=='待处理';assert d['unique_current'] is False

def test_archive_decision_exposes_blocked(sample):
    assert sample['archive']['blocked']==0 and sample['archive']['unique_current'] is True
