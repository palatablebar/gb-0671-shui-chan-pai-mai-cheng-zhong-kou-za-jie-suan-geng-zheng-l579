from collections import defaultdict
from decimal import Decimal
from app.coerce import money

def direction(due):
    if due>0: return '补付'
    if due<0: return '收回'
    return '结清'

def select_versions(settlements):
    grouped=defaultdict(list)
    for row in settlements: grouped[row['ticket']].append(row)
    final=[];conflicts=[];audit=[]
    for ticket,versions in sorted(grouped.items()):
        current=None;invalid=False
        for row in sorted(versions,key=lambda r:r['version']):
            target=row['replaces'].strip()
            if current is None:
                if target:
                    conflicts.append({'ticket':ticket,'code':'MISSING_BASE','version':row['version'],'replaces':target,
                        'lines':row['lines'],'detail':f"缺前版：版本{row['version']}引用的前版{target}不在本批，版本链断于此"})
                    invalid=True;break
            elif target!=str(current['version']):
                conflicts.append({'ticket':ticket,'code':'STALE_CORRECTION','version':row['version'],'replaces':target,
                    'expected':current['version'],'lines':row['lines'],
                    'detail':f"过期引用：版本{row['version']}应替代当前生效版{current['version']}，实际引用{target}，版本链断于此"})
                invalid=True;break
            audit.append({'ticket':ticket,'version':row['version'],'replaces':target,'amount':row['amount'],'lines':row['lines']})
            current=row
        if current and not invalid:
            paid=max(Decimal(r['paid']) for r in versions)
            due=Decimal(current['amount'])-paid
            final.append({**current,'paid':money(paid),'due':money(due),'direction':direction(due),'code':'CORRECTED' if len(versions)>1 else 'ORIGINAL'})
    return final,conflicts,audit

def apply(state):
    final,conflicts,audit=select_versions(state['settlements'])
    state.update(final=final,version_conflicts=conflicts,version_audit=audit)
    rows=sorted(final+conflicts,key=lambda r:(r['ticket'],r['version']))
    state['views']['correction']={'title':'更正裁决','rows':rows,'metrics':{'生效票':len(final),'版本冲突':len(conflicts),'追溯版':len(audit)}}
