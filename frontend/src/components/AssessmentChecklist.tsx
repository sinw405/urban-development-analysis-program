import { useState } from 'react';
import type { AssessmentItem } from '../api/types';
import { checklistKey, dataFingerprint, loadChecklist, saveChecklist } from '../utils/checklistPersistence';

export function AssessmentChecklist({ item, scope }: { item: AssessmentItem; scope: string }) {
  const id = item.assessment_code ?? item.name;
  const key = checklistKey(scope, 'assessment', id, dataFingerprint([item.status, item.required_action, item.missing_inputs, item.legal_basis]));
  const [checked, setChecked] = useState(() => loadChecklist(key, { reviewed: false }).reviewed);
  function toggle(value: boolean) { setChecked(value); saveChecklist(key, { reviewed: value }); }
  return <article className='procedureChecklist'>
    <div className='checklistHeader'><div><h4>{item.name}</h4><p className='muted'>분석 결과에 포함된 심의·평가 항목입니다.</p></div><span className={'checkStatusBadge ' + (checked ? 'complete' : 'pending')}>{checked ? '처리 완료' : '확인 필요'}</span></div>
    <dl className='definitionGrid'><dt>분석 상태</dt><dd>{item.status || '현재 등록된 정보 없음'}</dd><dt>필요 조치</dt><dd>{item.required_action || '현재 등록된 정보 없음'}</dd><dt>추가 확인사항</dt><dd>{item.missing_inputs?.length ? item.missing_inputs.join(', ') : '분석 결과상 추가 입력 없음'}</dd><dt>법령 근거</dt><dd>{item.legal_basis || '아직 데이터가 등록되지 않음'}</dd></dl>
    <label className='checklistItem'><input type='checkbox' checked={checked} onChange={event => toggle(event.target.checked)} /><span><strong>검토 완료</strong><small>심의·평가의 적용 여부를 새로 판단하지 않고 검토 상태만 저장합니다.</small></span></label>
  </article>;
}
