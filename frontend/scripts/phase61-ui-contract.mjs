import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import ts from 'typescript';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Use the repository's Node assertion convention, with actual React rendering.
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && context.parentURL) {
      const base = new URL(specifier, context.parentURL);
      for (const suffix of ['', '.ts', '.tsx']) {
        const candidate = new URL(base.href + suffix);
        if (existsSync(candidate) && /\.tsx?$/.test(candidate.pathname)) {
          return { url: candidate.href, shortCircuit: true };
        }
      }
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (/\.tsx?$/.test(new URL(url).pathname)) {
      let source = readFileSync(new URL(url), 'utf8');
      // Node has no Vite environment; use the same default API address.
      source = source.replaceAll('import.meta.env', '({})');
      return {
        format: 'module', shortCircuit: true,
        source: ts.transpileModule(source, {
          compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 }
        }).outputText
      };
    }
    return nextLoad(url, context);
  }
});

const { ReferenceDisclaimer } = await import('../src/components/ReferenceDisclaimer.tsx');
const { App } = await import('../src/App.tsx');
const { AnalysisResult } = await import('../src/views/AnalysisResult.tsx');
const { officialSourceUrl } = await import('../src/components/GroundedLegalExplanation.tsx');
const { getRouteFromLocation } = await import('../src/router.ts');
const result = {
  project_name: 'TEST_PHASE61_DO_NOT_USE', location: 'TEST_LOCATION_DO_NOT_USE',
  area_square_meters: 100000, implementation_method: 'mixed', implementer_type: 'public',
  local_government: 'TEST_LOCAL_GOVERNMENT_DO_NOT_USE', as_of: '2099-06-15',
  project_id: 1, analysis_id: 1, created_at: null, procedures: [], assessments: [], warnings: []
};
let passed = 0;
function check(name, run) {
  run(); passed += 1; console.log(`PASS: ${name}`);
}
function assertMeaning(html) {
  for (const text of ['참고용', '법적 유권해석', '공식 판단을 대체하지 않습니다',
    '법령·조문 원문', '최종 적용 여부', '인허가권자', '관련 전문가']) {
    assert.ok(html.includes(text), `missing notice meaning: ${text}`);
  }
  assert.doesNotMatch(html, /dangerouslySetInnerHTML|<dialog|role="alert"/);
}

for (const variant of ['global', 'analysis', 'report']) {
  check(`${variant} disclaimer renders semantic, consistent guidance`, () => {
    const html = renderToStaticMarkup(createElement(ReferenceDisclaimer, { variant }));
    assertMeaning(html);
    const label = html.match(/aria-labelledby="([^"]+)"/)[1];
    assert.ok(html.includes(`id="${label}"`));
    assert.ok(html.startsWith('<aside'));
    assert.equal(html.includes('절차, 근거 조문, 심의·평가'), variant !== 'global');
    assert.doesNotMatch(html, /href=/); // Guidance never fabricates a source link.
  });
}

for (const path of ['/', '/analyze', '/analyses', '/analyses/1', '/law-updates', '/analyses/invalid', '/missing']) {
  check(`shared notice covers actual route/fallback ${path}`, () => {
    globalThis.window = { location: { pathname: path } };
    const html = renderToStaticMarkup(createElement(App));
    assertMeaning(html);
    assert.equal((html.match(/referenceDisclaimer-global/g) ?? []).length, 1);
    assert.ok(html.indexOf('referenceDisclaimer-global') > html.indexOf('<main>'));
    if (path === '/missing') assert.equal(getRouteFromLocation(), '/');
  });
}

check('result and printed report retain detailed guidance and comparison', () => {
  const html = renderToStaticMarkup(createElement(AnalysisResult, { result }));
  assertMeaning(html);
  assert.ok(html.indexOf('referenceDisclaimer-analysis') < html.indexOf('분석 요약'));
  assert.ok(html.includes('referenceDisclaimer-report'));
  assert.ok(html.includes('현재 사업과 등록 사례 비교'));
  assert.ok(html.includes('절차 진행 흐름'));
});
check('empty result retains existing prompt', () => {
  assert.ok(renderToStaticMarkup(createElement(AnalysisResult, { result: null })).includes('아직 실행된 분석 결과가 없습니다'));
});
check('existing official source URL helper accepts provided sources only', () => {
  const url = 'https://www.law.go.kr/법령/도시개발법';
  assert.equal(officialSourceUrl({ official_source_url: url }), new URL(url).href);
  for (const value of [undefined, '', 'javascript:alert(1)', 'https://example.com/law', 'http://law.go.kr/law']) {
    assert.equal(officialSourceUrl({ official_source_url: value }), null);
  }
});
check('existing original-law anchors remain available and conditional', () => {
  const rag = readFileSync(new URL('../src/components/GroundedLegalExplanation.tsx', import.meta.url), 'utf8');
  const updates = readFileSync(new URL('../src/views/LawUpdates.tsx', import.meta.url), 'utf8');
  assert.ok(rag.includes("officialUrl ? <a href={officialUrl}"));
  assert.ok(rag.includes('noopener noreferrer'));
  assert.ok(updates.includes('event.official_url_status === "available"'));
  assert.ok(updates.includes('href={event.official_url}'));
});
console.log(`Phase 61 UI contract: ${passed} passed, 0 failed`);
