import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

// Optional local tool; no application dependency or real API/DB is required.
const tool = process.env.PLAYWRIGHT_MODULE ?? new URL('../../backups/phase61-tools/node_modules/playwright-core/index.mjs', import.meta.url).href;
const { chromium } = await import(tool);
const baseUrl = process.env.PHASE61_UI_URL ?? 'http://127.0.0.1:5173';
const output = new URL('../../backups/phase61-visual/', import.meta.url);
await mkdir(output, { recursive: true });
// Source URL is the existing Phase 55 test fixture, never a generated law URL.
const sourceUrl = 'https://www.law.go.kr/stored-official';
const step = {
  step_code: 'TEST_STEP_DO_NOT_USE', step_name: 'TEST 절차 검증', sequence: 1,
  description: 'TEST 화면 검증용 절차', required_documents: ['TEST 서류'], related_agencies: ['TEST 기관'],
  estimated_duration: 'TEST 기간', legal_basis_placeholder: [], legal_references: [],
  legal_reference_status: 'missing', official_article_candidates: [], legal_reference_candidates: [],
  reference_candidate_count: 0, reference_status: 'no_official_candidate', notes: []
};
const result = {
  project_name: 'TEST_PHASE61_DO_NOT_USE', location: 'TEST_LOCATION_DO_NOT_USE',
  area_square_meters: 100000, implementation_method: 'mixed', implementer_type: 'public',
  local_government: 'TEST_LOCAL_GOVERNMENT_DO_NOT_USE', as_of: '2099-06-15',
  project_id: 1, analysis_id: 1, created_at: '2099-06-15T00:00:00Z', procedures: [step],
  assessments: [{ assessment_code: 'TEST_ASSESSMENT', name: 'TEST 평가', status: 'needs_review',
    threshold: 'TEST', legal_basis: 'TEST 근거', required_action: 'TEST 확인', missing_inputs: [], notes: [] }], warnings: []
};
const summary = { ...result, procedures: undefined, assessments: undefined };
const detail = { ...summary, request_payload: {}, result_payload: result, rule_version: 'TEST' };
const cases = { items: [1, 2].map(id => ({ id, name: `TEST_CASE_${id}_DO_NOT_USE`, location: null,
  area_m2: null, method: null, operator_type: null, timeline: [], history: [] })) };
let missingSource = false;
let detailError = false;
let passed = 0;
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill({ status: 204, headers: { 'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS' } });
    }
    let body;
    let status = 200;
    if (path === '/api/analyses') body = { items: [summary], total: 1, limit: 20, offset: 0 };
    else if (path === '/api/analyses/1') {
      body = detailError ? { detail: 'TEST_UNAVAILABLE' } : detail;
      if (detailError) status = 503;
    }
    else if (path === '/api/analyze') body = result;
    else if (path === '/api/cases') body = cases;
    else if (path === '/api/rag/answer') body = {
      status: 'grounded', answer: 'TEST 근거 설명', claims: [], evidence: [],
      citations: [{ citation_id: 'TEST_CITATION', law_name: 'TEST LAW', source_type: 'article',
        title: 'TEST ARTICLE', effective_date: result.as_of, mst: null, excerpt: 'TEST 근거 내용',
        provenance: missingSource ? {} : { official_source_url: sourceUrl } }],
      as_of: result.as_of, disclaimer: 'TEST 참고용', warnings: []
    };
    else if (path === '/api/law-updates') body = { items: [{
      event_id: 1, event_kind: 'TEST', law_name: 'TEST LAW', article_no: 'TEST',
      change_type: 'TEST', mapping_status: 'unconfirmed', impacted_step_codes: [],
      official_url: sourceUrl, official_url_status: 'available', detected_at: result.created_at
    }] };
    else if (path.endsWith('/moleg/diagnostic')) body = { transport_ok: false, live_enabled: false,
      reason_message: 'TEST 진단', reason_type: 'TEST', fallback_available: false };
    else if (path.endsWith('/official-law-seeds/status')) body = { total_files: 0, total_articles: 0,
      confirmed_articles: 0, unconfirmed_articles: 0 };
    else throw new Error(`Unexpected fixture request: ${path}`);
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body),
      headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.route(sourceUrl, route => route.fulfill({ contentType: 'text/html', body: '<p>TEST stored source link</p>' }));

  async function noticeChecks() {
    const notice = page.locator('.referenceDisclaimer-global');
    await notice.waitFor({ state: 'visible' });
    assert.equal(await notice.count(), 1);
    const text = await notice.innerText();
    for (const word of ['참고용', '유권해석', '공식 판단을 대체하지 않습니다', '원문', '인허가권자', '전문가']) assert.ok(text.includes(word));
    assert.ok(await notice.evaluate(el => {
      const heading = document.getElementById(el.getAttribute('aria-labelledby'));
      const rect = el.getBoundingClientRect();
      return heading && el.contains(heading) && el.scrollWidth <= el.clientWidth + 1
        && rect.left >= 0 && rect.right <= innerWidth + 1
        && getComputedStyle(el).position !== 'fixed' && parseFloat(getComputedStyle(el).fontSize) >= 14;
    }));
    const overflow = await page.evaluate(() => {
      const width = document.documentElement.scrollWidth;
      if (width <= innerWidth + 1) return null;
      const offenders = [...document.querySelectorAll('main *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1)
        .slice(0, 10).map(el => ({ tag: el.tagName, className: el.className, right: el.getBoundingClientRect().right }));
      document.querySelectorAll('.referenceDisclaimer').forEach(el => el.style.display = 'none');
      const withoutNotices = document.documentElement.scrollWidth;
      document.querySelectorAll('.referenceDisclaimer').forEach(el => el.style.removeProperty('display'));
      return { width, withoutNotices, offenders };
    });
    assert.equal(overflow, null, JSON.stringify(overflow));
  }

  const routes = ['/', '/analyze', '/analyses', '/analyses/1', '/law-updates', '/analyses/invalid', '/missing'];
  for (const [size, width, height] of [['desktop', 1440, 1000], ['tablet', 768, 1024], ['mobile', 360, 800], ['small', 320, 800]]) {
    await page.setViewportSize({ width, height });
    for (const route of routes) {
      await page.goto(baseUrl + route);
      await noticeChecks();
      if (route === '/analyses/1') {
        await page.locator('.referenceDisclaimer-analysis').waitFor({ state: 'visible' });
        await page.locator('.caseSelectorItem').first().waitFor({ state: 'visible' });
        assert.ok(await page.locator('.procedureDetailCard').isVisible());
        assert.ok(await page.locator('.assessmentChecklistGrid').isVisible());
        await noticeChecks();
      }
      if (route === '/' || route === '/analyses/1') {
        await page.screenshot({ path: new URL(`${size}-${route === '/' ? 'main' : 'result'}.png`, output).pathname.replace(/^\/(\w:)/, '$1'), fullPage: true });
        if (route === '/analyses/1') {
          await page.screenshot({ path: new URL(`${size}-result-viewport.png`, output).pathname.replace(/^\/(\w:)/, '$1') });
        }
      }
      passed += 1;
      console.log(`PASS: ${size} ${route} shared notice, layout and semantics`);
    }
  }

  await page.goto(baseUrl + '/analyze');
  await page.getByRole('button', { name: '분석 실행', exact: true }).click();
  await page.locator('.referenceDisclaimer-analysis').waitFor({ state: 'visible' });
  await page.locator('.caseSelectorItem').first().waitFor();
  assert.equal(await page.locator('.caseComparison input:checked').count(), 2);
  await page.locator('.caseComparison input').first().uncheck();
  assert.equal(await page.locator('.caseComparison input:checked').count(), 1);
  await page.getByRole('button', { name: 'AI 근거 설명', exact: true }).click();
  await page.locator('.ragCitation').click();
  const anchor = page.getByRole('link', { name: '국가법령정보센터 원문 보기' });
  assert.equal(await anchor.getAttribute('href'), sourceUrl);
  await anchor.focus();
  const popupPromise = page.waitForEvent('popup');
  await page.keyboard.press('Enter');
  const popup = await popupPromise;
  await popup.waitForLoadState();
  assert.equal(popup.url(), sourceUrl);
  await popup.close();
  missingSource = true;
  await page.getByRole('button', { name: '다시 확인', exact: true }).click();
  await page.locator('.ragCitation').click();
  await page.getByText('공식 원문 링크가 등록되지 않음', { exact: true }).waitFor();
  assert.equal(await anchor.count(), 0);
  await page.emulateMedia({ media: 'print' });
  assert.ok(await page.locator('.referenceDisclaimer-report').isVisible());
  await page.emulateMedia({ media: 'screen' });
  passed += 1;
  console.log('PASS: analysis submit, comparison selection, RAG source/missing source, keyboard link and print notice');

  await page.goto(baseUrl + '/law-updates');
  const updateLink = page.getByRole('link', { name: '열기', exact: true });
  await updateLink.waitFor();
  assert.equal(await updateLink.getAttribute('href'), sourceUrl);
  passed += 1;
  console.log('PASS: existing law-update original link preserved');
  detailError = true;
  await page.goto(baseUrl + '/analyses/1');
  await page.getByText('분석 상세 정보를 불러오지 못했습니다.', { exact: true }).waitFor();
  await noticeChecks();
  passed += 1;
  console.log('PASS: shared notice persists through API error state');
  assert.deepEqual(errors, []);
  console.log(`Phase 61 browser validation: ${passed} passed, 0 failed (mocked API; no real DB writes)`);
} finally {
  await browser.close();
}
