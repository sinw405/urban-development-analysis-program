import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const comparison = readFileSync(new URL('../src/components/CaseComparison.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/api/cases.ts', import.meta.url), 'utf8');
const result = readFileSync(new URL('../src/views/AnalysisResult.tsx', import.meta.url), 'utf8');
const rag = readFileSync(new URL('../src/components/GroundedLegalExplanation.tsx', import.meta.url), 'utf8');
const procedureChecklist = readFileSync(new URL('../src/components/ProcedureChecklist.tsx', import.meta.url), 'utf8');
const assessmentChecklist = readFileSync(new URL('../src/components/AssessmentChecklist.tsx', import.meta.url), 'utf8');

assert.match(api, /\/api\/cases\?similar_to=/);
assert.match(api, /requestJson/);
assert.match(result, /CaseComparison currentProject=\{result\}/);
for (const text of [
  '사례 비교', '현재 분석 사업', '비교 사례', 'MAX_SELECTED_CASES = 2',
  '비교 사례를 불러오는 중입니다.', '등록된 비교 사례가 없습니다.',
  '사례 정보를 불러오지 못했습니다.', '정보 없음', '진행 이력',
  '등록된 진행 이력이 없습니다.', 'timeline', 'history', '다시 시도'
]) assert.ok(comparison.includes(text), `missing CaseComparison contract: ${text}`);
for (const rawLabel of ['>case_id<', '>operator_type<', '>method_code<', '>similar_to<', '>null<', '>undefined<']) {
  assert.ok(!comparison.includes(rawLabel), `raw field exposed: ${rawLabel}`);
}
assert.doesNotMatch(comparison, /dangerouslySetInnerHTML|javascript:/);
assert.match(rag, /citation|citations/);
assert.match(rag, /evidence/);
assert.match(procedureChecklist, /saveChecklist/);
assert.match(assessmentChecklist, /saveChecklist/);
console.log('Phase 56 UI contract checks passed');
