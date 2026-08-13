import { useState } from 'react';
import { answerLegalQuestion } from '../api/rag';
import type { RagAnswerResponse, RagCitation, RagEvidence } from '../api/types';

interface Props { stepName: string; asOf: string | null; }

const labels = {
  title: '법령 근거 설명', article: '법령 조문', table: '별표/별첨 근거',
  loading: '법령 근거와 설명을 확인하는 중입니다.', open: 'AI 근거 설명', retry: '다시 확인'
};
const sourceLabel = (value: string) => value === 'attached_table' ? labels.table : labels.article;

export function officialSourceUrl(provenance: Record<string, unknown>) {
  const value = provenance.official_source_url;
  if (typeof value !== 'string') return null;
  try { const url = new URL(value); return url.protocol === 'https:' && (url.hostname === 'law.go.kr' || url.hostname === 'www.law.go.kr') ? url.href : null; } catch { return null; }
}

export function ragStateMessage(status: string) {
  const messages: Record<string, string> = {
    insufficient_evidence: '현재 확보된 법령 근거만으로는 이 내용을 확정하기 어렵습니다.',
    validation_failed: '생성된 설명이 법령 근거 검증을 통과하지 못해 표시하지 않았습니다.',
    generation_unavailable: '법령 근거는 확인되었지만 설명 생성 기능을 현재 사용할 수 없습니다.',
    grounded_with_conflicts: '관련 근거 사이에 추가 검토가 필요한 내용이 있습니다.'
  };
  return messages[status] ?? null;
}

function EvidenceDetail({ item }: { item: RagCitation | RagEvidence }) {
  const excerpt = 'excerpt' in item ? item.excerpt : item.text_excerpt;
  const source = typeof item.provenance.source === 'string' ? item.provenance.source : '저장된 법령 근거';
  const officialUrl = officialSourceUrl(item.provenance);
  return <dl className='definitionGrid ragEvidenceDetail'>
    <dt>근거 구분</dt><dd>{sourceLabel(item.source_type)}</dd><dt>법령</dt><dd>{item.law_name}</dd>
    <dt>조문/별표</dt><dd>{item.title}</dd><dt>시행일</dt><dd>{item.effective_date}</dd>
    <dt>출처</dt><dd>{source}</dd>{item.mst ? <><dt>법령 버전 식별값</dt><dd>{item.mst}</dd></> : null}
    <dt>공식 원문</dt><dd>{officialUrl ? <a href={officialUrl} target='_blank' rel='noopener noreferrer'>국가법령정보센터 원문 보기</a> : '공식 원문 링크가 등록되지 않음'}</dd>
    <dt>근거 내용</dt><dd className='ragExcerpt'>{excerpt}</dd>
  </dl>;
}


export function GroundedLegalExplanation({ stepName, asOf }: Props) {
  const [result, setResult] = useState<RagAnswerResponse | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  async function load() {
    if (!asOf || loading) return;
    setLoading(true); setError(false); setSelectedCitation(null);
    try {
      setResult(await answerLegalQuestion({
        question: `도시개발사업에서 ${stepName}와 관련된 법령 근거와 현재 확보된 근거가 의미하는 내용을 설명해 주세요.`,
        as_of: asOf, retrieval_mode: 'lexical', top_k: 5, source_types: ['article', 'attached_table']
      }));
    } catch { setError(true); } finally { setLoading(false); }
  }
  const items = result?.citations.length ? result.citations : result?.evidence ?? [];
  return <section className='legalReferenceSection ragPanel'>
    <div className='ragPanelHeader'><h4>{labels.title}</h4><button type='button' className='smallButton' onClick={() => void load()} disabled={loading || !asOf}>{loading ? labels.loading : result || error ? labels.retry : labels.open}</button></div>
    {!asOf ? <p className='missingDataNotice'>분석 기준일을 확인해 주세요.</p> : null}
    {loading ? <div className='loadingBox' role='status'>{labels.loading}</div> : null}
    {error ? <div className='errorBox' role='alert'><strong>법령 근거 설명을 불러오지 못했습니다.</strong><p>기존 분석 결과는 유지됩니다.</p></div> : null}
    {result ? <div className='ragResult'>
      <p><strong>법령 기준일</strong> {result.as_of}</p>
      {ragStateMessage(result.status) ? <div className='missingDataNotice'>{ragStateMessage(result.status)}</div> : null}
      {result.answer ? <div className='ragAnswer'>{result.answer}</div> : null}
      {result.warnings.length ? <ul className='checkList'>{result.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul> : null}
      <div className='ragEvidenceList'>{items.map(item => <button type='button' className='ragCitation' key={item.citation_id} onClick={() => setSelectedCitation(item.citation_id)}><span>{sourceLabel(item.source_type)}</span><strong>{item.law_name}</strong><span>{item.title}</span></button>)}</div>
      {selectedCitation ? <EvidenceDetail item={items.find(item => item.citation_id === selectedCitation)!} /> : null}
      <p className='ragDisclaimer'>{result.disclaimer}</p>
    </div> : null}
  </section>;
}
