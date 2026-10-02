import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Keep all Phase 61 route/disclaimer/source-link/browser regressions.
await import('./phase61-browser.mjs');
const tool = process.env.PLAYWRIGHT_MODULE ?? new URL('../../backups/phase61-tools/node_modules/playwright-core/index.mjs', import.meta.url).href;
const { chromium } = await import(tool);
const baseUrl = process.env.PHASE61_UI_URL ?? 'http://127.0.0.1:5173';
const output = new URL('../../backups/phase62-visual/', import.meta.url);
await mkdir(output, { recursive: true });
const result = {
  project_name: 'TEST_PHASE62_DO_NOT_USE', location: 'TEST_LOCATION_DO_NOT_USE',
  area_square_meters: 100000, implementation_method: 'mixed', implementer_type: 'public',
  local_government: 'TEST_SAVED_REGION_DO_NOT_USE', as_of: '2099-06-15',
  project_id: 1, analysis_id: 1, created_at: '2099-06-15T00:00:00Z', warnings: [],
  procedures: [{ step_code: 'TEST_STEP_DO_NOT_USE', step_name: 'TEST 표준 절차', sequence: 1,
    description: 'TEST 표준 절차 검증', required_documents: [], related_agencies: [],
    estimated_duration: 'TODO_EXPERT_REVIEW', legal_basis_placeholder: [], legal_references: [],
    official_article_candidates: [], legal_reference_status: 'missing', notes: [] }],
  assessments: [{ assessment_code: 'TEST_ASSESSMENT', name: 'TEST 평가', status: 'needs_review',
    threshold: 'TEST', legal_basis: 'TEST', required_action: 'TEST 확인', missing_inputs: [], notes: [] }]
};
const browser = await chromium.launch({ channel: 'chrome', headless: true });
let passed = 0;
let failAnalysis = false;
let failDetail = false;
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    let body;
    let status = 200;
    if (path === '/api/analyze') {
      const request = route.request().postDataJSON();
      body = failAnalysis ? { detail: 'TEST_ANALYSIS_ERROR' } : { ...result, local_government: request.local_government };
      if (failAnalysis) status = 503;
    } else if (path === '/api/analyses/1') {
      body = failDetail ? { detail: 'TEST_DETAIL_ERROR' } : { analysis_id: 1, project_id: 1,
        project_name: result.project_name, result_payload: result, request_payload: {}, created_at: result.created_at };
      if (failDetail) status = 503;
    } else if (path === '/api/cases') body = { items: [{ id: 1, name: 'TEST_CASE_DO_NOT_USE',
      location: null, area_m2: null, method: null, operator_type: null, timeline: [], history: [] }] };
    else if (path === '/api/analyses' || path === '/api/law-updates') body = { items: [], total: 0, limit: 20, offset: 0 };
    else if (path.endsWith('/moleg/diagnostic')) body = { live_enabled: false, transport_ok: false, reason_message: 'TEST', reason_type: 'TEST', fallback_available: false };
    else if (path.endsWith('/official-law-seeds/status')) body = { total_files: 0, total_articles: 0, confirmed_articles: 0, unconfirmed_articles: 0 };
    else throw new Error(`Unexpected fixture request: ${path}`);
    return route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
  });

  async function noticesFit() {
    await page.locator('.ordinanceNotice-global').waitFor({ state: 'visible' });
    assert.ok(await page.locator('.referenceDisclaimer-global').isVisible());
    const overflow = await page.evaluate(() => {
      if (document.documentElement.scrollWidth <= innerWidth + 1) return null;
      return { width: document.documentElement.scrollWidth, viewport: innerWidth,
        offenders: [...document.querySelectorAll('main *')]
          .filter(el => el.getBoundingClientRect().right > innerWidth + 1 && !el.closest('.tableWrap'))
          .slice(0, 12).map(el => ({ tag: el.tagName, className: el.className, text: el.textContent.slice(0, 80), right: el.getBoundingClientRect().right })) };
    });
    assert.equal(overflow, null, JSON.stringify(overflow));
    for (const notice of await page.locator('.ordinanceNotice').all()) {
      const dimensions = await notice.evaluate(el => {
        const heading = document.getElementById(el.getAttribute('aria-labelledby'));
        const rect = el.getBoundingClientRect();
        return { className: el.className, named: Boolean(heading && el.contains(heading)),
          left: rect.left, right: rect.right, viewport: innerWidth, scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth, position: getComputedStyle(el).position };
      });
      assert.ok(dimensions.named && dimensions.left >= 0 && dimensions.right <= dimensions.viewport + 1
        && dimensions.scrollWidth <= dimensions.clientWidth + 1 && dimensions.position !== 'fixed', JSON.stringify(dimensions));
      assert.ok((await notice.innerText()).includes('표준'));
      assert.equal(await notice.locator('a, [role="alert"]').count(), 0);
    }
  }
  async function resultChecks(region) {
    const notice = page.locator('.ordinanceNotice-result');
    await notice.waitFor({ state: 'visible' });
    const text = await notice.innerText();
    for (const value of [region, '미연동', '표준 절차', '확정된 절차를 의미하지 않습니다', '자치법규', '인허가권자']) assert.ok(text.includes(value));
    await page.locator('.caseSelectorItem').waitFor({ state: 'visible' });
    assert.ok(await page.locator('.procedureDetailCard').isVisible());
    assert.ok(await page.locator('.assessmentChecklistGrid').isVisible());
    assert.equal(await page.locator('.errorBox').count(), 0);
    await noticesFit();
  }

  for (const [label, width, height] of [['desktop', 1440, 1000], ['tablet', 768, 1024], ['mobile', 360, 800], ['small', 320, 800]]) {
    await page.setViewportSize({ width, height });
    for (const route of ['/', '/analyze', '/analyses', '/analyses/1', '/law-updates', '/analyses/invalid', '/missing']) {
      await page.goto(baseUrl + route);
      await noticesFit();
      if (route === '/analyses/1') await resultChecks(result.local_government);
      if (route === '/' || route === '/analyses/1') {
        await page.screenshot({ path: fileURLToPath(new URL(`${label}-${route === '/' ? 'main' : 'saved'}.png`, output)), fullPage: true });
      }
      passed += 1;
      console.log(`PASS: Phase 62 ${label} ${route}`);
    }
    await page.goto(baseUrl + '/analyze');
    const region = 'TEST_INPUT_REGION_DO_NOT_USE';
    await page.getByLabel(/관할 지자체/).fill(region);
    assert.ok((await page.locator('.ordinanceNotice-input').innerText()).includes(region));
    await page.getByRole('button', { name: '분석 실행', exact: true }).click();
    await resultChecks(region);
    await page.getByLabel(/관할 지자체/).fill('TEST_CHANGED_REGION_DO_NOT_USE');
    assert.ok((await page.locator('.ordinanceNotice-result').innerText()).includes(region));
    await page.locator('.caseSelectorItem input').uncheck();
    await page.locator('.caseSelectorItem input').check();
    await page.locator('.ordinanceNotice-result').scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -document.querySelector('.topbar').getBoundingClientRect().height - 16));
    await page.screenshot({ path: fileURLToPath(new URL(`${label}-new-result.png`, output)) });
    await page.emulateMedia({ media: 'print' });
    assert.ok(await page.locator('.ordinanceNotice-report').isVisible());
    assert.ok(await page.locator('.referenceDisclaimer-report').isVisible());
    await page.emulateMedia({ media: 'screen' });
    passed += 1;
    console.log(`PASS: ${label} unlinked input, successful standard analysis, result region isolation, case selection and print`);
  }

  failAnalysis = true;
  await page.goto(baseUrl + '/analyze');
  await page.getByRole('button', { name: '분석 실행', exact: true }).click();
  await page.getByText('분석 요청 중 오류가 발생했습니다.', { exact: true }).waitFor();
  assert.equal(await page.locator('.ordinanceNotice-result').count(), 0);
  assert.equal(await page.locator('.procedureRoadmap').count(), 0);
  await noticesFit();
  passed += 1;
  failDetail = true;
  await page.goto(baseUrl + '/analyses/1');
  await page.getByText('분석 상세 정보를 불러오지 못했습니다.', { exact: true }).waitFor();
  assert.equal(await page.locator('.ordinanceNotice-result').count(), 0);
  await noticesFit();
  passed += 1;
  assert.deepEqual(errors, []);
  console.log(`Phase 62 browser: ${passed} passed, 0 failed (plus Phase 61 browser regression; TEST API only)`);
} finally {
  await browser.close();
}
