import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';

// Reuse Phase 61's TypeScript rendering harness and run its disclaimer regression.
await import('./phase61-ui-contract.mjs');
const { MunicipalityOrdinanceNotice, ORDINANCE_AVAILABILITY } = await import('../src/components/MunicipalityOrdinanceNotice.tsx');
const { App } = await import('../src/App.tsx');
const { AnalysisResult } = await import('../src/views/AnalysisResult.tsx');
const { analysisDetailToResult } = await import('../src/api/analyses.ts');
let passed = 0;
function check(name, run) { run(); passed += 1; console.log(`PASS: ${name}`); }
const result = {
  project_name: 'TEST_PHASE62_DO_NOT_USE', location: 'TEST_LOCATION_DO_NOT_USE',
  area_square_meters: 100000, implementation_method: 'mixed', implementer_type: 'public',
  local_government: 'TEST_UNLINKED_DO_NOT_USE', as_of: '2099-06-15', project_id: 1,
  analysis_id: 1, created_at: null, procedures: [], assessments: [], warnings: []
};

for (const variant of ['global', 'input', 'result', 'report']) {
  check(`${variant}: semantic notice, standard fallback, variance and final verification`, () => {
    const html = renderToStaticMarkup(createElement(MunicipalityOrdinanceNotice, { variant, municipality: result.local_government }));
    for (const text of ['조례', '미연동', '표준 절차', '달라질 수 있습니다', '자치법규 원문', '인허가권자']) assert.ok(html.includes(text));
    const id = html.match(/aria-labelledby="([^"]+)"/)[1];
    assert.ok(html.includes(`id="${id}"`));
    assert.ok(html.startsWith('<aside'));
    assert.doesNotMatch(html, /href=|role="alert"|errorBox|<dialog/);
    if (variant !== 'global') {
      assert.ok(html.includes('확정된 절차를 의미하지 않습니다'));
      assert.ok(html.includes('근거 미확인·후보·검토 필요'));
      assert.ok(html.includes(result.local_government));
    }
  });
}
check('system capability stays not-linked for any region; no fake available state', () => {
  assert.equal(ORDINANCE_AVAILABILITY, 'not_linked');
  for (const municipality of [null, undefined, '', '  ', '<script>TEST</script>', 'TEST_OTHER_REGION_DO_NOT_USE']) {
    const html = renderToStaticMarkup(createElement(MunicipalityOrdinanceNotice, { municipality, variant: 'input' }));
    assert.ok(html.includes('조례 미연동'));
    assert.doesNotMatch(html, /<script>|href=/);
    if (!municipality?.trim()) assert.ok(html.includes('관할 지자체 입력·확인 필요'));
  }
});
for (const pathname of ['/', '/analyze', '/analyses', '/analyses/1', '/law-updates', '/analyses/invalid', '/missing']) {
  check(`${pathname}: shared ordinance notice and Phase 61 notice remain`, () => {
    globalThis.window = { location: { pathname } };
    const html = renderToStaticMarkup(createElement(App));
    assert.equal((html.match(/ordinanceNotice-global/g) ?? []).length, 1);
    assert.ok(html.includes('referenceDisclaimer-global'));
    if (pathname === '/analyze') assert.ok(html.includes('ordinanceNotice-input'));
  });
}
for (const saved of [false, true]) {
  check(`${saved ? 'saved' : 'new'} result without ordinance data keeps standard UI and comparison`, () => {
    const value = saved ? analysisDetailToResult({ result_payload: result, analysis_id: 1, project_id: 1 }) : result;
    const before = JSON.stringify(value);
    const html = renderToStaticMarkup(createElement(AnalysisResult, { result: value }));
    assert.ok(html.includes('ordinanceNotice-result'));
    assert.ok(html.includes('ordinanceNotice-report'));
    assert.ok(html.includes('referenceDisclaimer-analysis'));
    assert.ok(html.includes('referenceDisclaimer-report'));
    assert.ok(html.indexOf('ordinanceNotice-result') < html.indexOf('caseComparison'));
    assert.ok(html.includes('절차 진행 흐름'));
    assert.ok(html.includes('현재 사업과 등록 사례 비교'));
    assert.doesNotMatch(html, /errorBox/);
    assert.equal(JSON.stringify(value), before);
  });
}
check('real analysis error/empty-result semantics are not replaced by synthetic fallback results', () => {
  const html = renderToStaticMarkup(createElement(AnalysisResult, { result: null }));
  assert.ok(html.includes('아직 실행된 분석 결과가 없습니다'));
  assert.ok(!html.includes('ordinanceNotice-result'));
  const form = readFileSync(new URL('../src/views/AnalysisForm.tsx', import.meta.url), 'utf8');
  assert.ok(form.includes('setResult(data)'));
  assert.ok(form.includes('setError(err instanceof Error'));
});
console.log(`Phase 62 UI contract: ${passed} passed, 0 failed (plus Phase 61 regression)`);
