import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const component = readFileSync(new URL('../src/components/GroundedLegalExplanation.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/api/rag.ts', import.meta.url), 'utf8');
const detail = readFileSync(new URL('../src/components/ProcedureStepDetail.tsx', import.meta.url), 'utf8');
const result = readFileSync(new URL('../src/views/AnalysisResult.tsx', import.meta.url), 'utf8');

assert.match(api, /\/api\/rag\/answer/);
assert.match(api, /requestJson/);
for (const status of ['insufficient_evidence', 'validation_failed', 'generation_unavailable', 'grounded_with_conflicts']) assert.match(component, new RegExp(status));
for (const field of ['result.answer', 'result.as_of', 'result.disclaimer', 'result?.evidence', 'result.citations', 'item.provenance', 'item.effective_date', 'attached_table']) assert.ok(component.includes(field));
assert.match(component, /role='status'/);
assert.match(component, /role='alert'/);
assert.ok(component.includes('disabled={loading || !asOf}'));
assert.doesNotMatch(component, /dangerouslySetInnerHTML/);
assert.match(detail, /GroundedLegalExplanation/);
assert.match(result, /asOf={result.as_of}/);
console.log('Phase 54 UI contract checks passed');
