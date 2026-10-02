import type { AnalyzeResponse } from "../api/types";
import type { ChecklistStatus } from "./ProcedureChecklist";
import { ReferenceDisclaimer } from "./ReferenceDisclaimer";
import { MunicipalityOrdinanceNotice } from "./MunicipalityOrdinanceNotice";
import { CANDIDATE_LEGAL_REFERENCE_NOTICE, normalizeAnalysisSummary } from "../utils/analysisSummary";

interface AnalysisReportProps {
  result: AnalyzeResponse;
  checklistStatuses: Record<string, ChecklistStatus>;
}

export function AnalysisReport({ result, checklistStatuses }: AnalysisReportProps) {
  const summary = normalizeAnalysisSummary(result, checklistStatuses);

  return (
    <section className="analysisReport" aria-label="보고서형 분석 결과">
      <div className="reportHeader">
        <div>
          <p className="eyebrow">보고서형 요약</p>
          <h2>도시개발사업 절차 분석 보고서</h2>
          <p className="muted">브라우저 인쇄 기능으로 PDF 저장이 가능합니다. 서버 PDF 생성 기능은 아직 구현하지 않았습니다.</p>
        </div>
        <button type="button" className="printButton" onClick={() => window.print()}>인쇄하기</button>
      </div>

      <div className="noticeBox compactNotice reportNotice">
        이 보고서는 개발 검증용 화면입니다. 실제 법령 조문, 조문번호, 기준값은 아직 연동되지 않았으며 TEST_*_DO_NOT_USE 데이터는 화면 검증용입니다.
      </div>

      {summary.hasCandidateLegalReferences && (
        <div className="noticeBox compactNotice reportNotice">
          {CANDIDATE_LEGAL_REFERENCE_NOTICE}
        </div>
      )}

      <dl className="reportSummaryGrid">
        <div><dt>사업명</dt><dd>{summary.projectName}</dd></div>
        <div><dt>분석 ID</dt><dd>{summary.analysisId ?? "-"}</dd></div>
        <div><dt>사업 ID</dt><dd>{summary.projectId ?? "-"}</dd></div>
        <div><dt>기준일</dt><dd>{summary.asOf}</dd></div>
        <div><dt>생성일</dt><dd>{summary.createdAt}</dd></div>
        <div><dt>사업면적</dt><dd>{summary.area}</dd></div>
        <div><dt>전체 절차 수</dt><dd>{summary.procedureCount}개</dd></div>
        <div><dt>법령 근거 연결 수</dt><dd>{summary.legalReferenceCount}개</dd></div>
        <div><dt>검증완료 근거</dt><dd>{summary.verifiedLegalReferenceCount}개</dd></div>
        <div><dt>후보근거</dt><dd>{summary.candidateLegalReferenceCount}개</dd></div>
        <div><dt>근거미확인 단계</dt><dd>{summary.missingLegalReferenceCount}개</dd></div>
        <div><dt>서류 확인 필요</dt><dd>{summary.missingDocumentCount}개 단계</dd></div>
        <div><dt>기관 확인 필요</dt><dd>{summary.missingAgencyCount}개 단계</dd></div>
        <div><dt>기간 확인 필요</dt><dd>{summary.missingDurationCount}개 단계</dd></div>
        <div><dt>체크 완료</dt><dd>{summary.checklistCompleteCount}개 단계</dd></div>
        <div><dt>체크 확인중</dt><dd>{summary.checklistProgressCount}개 단계</dd></div>
        <div><dt>체크 미확인</dt><dd>{summary.checklistPendingCount}개 단계</dd></div>
      </dl>

      <section className="reportSection">
        <h3>사업 개요</h3>
        <dl className="definitionGrid">
          <dt>위치</dt><dd>{summary.location}</dd>
          <dt>시행방식</dt><dd>{summary.implementationMethod}</dd>
          <dt>시행자 유형</dt><dd>{summary.implementerType}</dd>
          <dt>관할 지자체</dt><dd>{summary.localGovernment}</dd>
        </dl>
      </section>

      <section className="reportSection">
        <h3>확인 필요 항목 요약</h3>
        {summary.missingItems.length === 0 ? (
          <p>현재 표시 가능한 범위에서는 별도 확인 필요 항목이 없습니다.</p>
        ) : (
          <ul className="missingSummaryList">
            {summary.missingItems.map((item) => <li key={item}>{item}</li>)}
          </ul>
        )}
      </section>

      <section className="reportSection">
        <h3>단계별 요약 테이블</h3>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>단계</th>
                <th>근거 법령</th>
                <th>근거 상태</th>
                <th>필요 서류</th>
                <th>협의/인허가 기관</th>
                <th>예상 기간</th>
                <th>확인상태</th>
              </tr>
            </thead>
            <tbody>
              {summary.steps.map((step) => (
                <tr key={step.stepCode}>
                  <td>{step.sequence}. {step.title}</td>
                  <td>{step.legalReferenceCount}개</td>
                  <td>{step.legalReferenceState}</td>
                  <td>{step.requiredDocumentState}</td>
                  <td>{step.relatedAgencyState}</td>
                  <td>{step.durationState}</td>
                  <td>{step.checklistStatus}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="reportSection">
        <h3>단계별 상세 요약</h3>
        <div className="reportStepCards">
          {summary.steps.map((step) => (
            <article className="reportStepCard" key={step.stepCode}>
              <div className="cardTitle compactTitle">
                <h4>{step.sequence}. {step.title}</h4>
                <span className="badge neutral">{step.checklistStatus}</span>
              </div>
              <p>{step.description}</p>
              <dl className="definitionGrid">
                <dt>예상 소요기간</dt><dd>{step.durationState}</dd>
                <dt>필요 서류</dt><dd>{step.requiredDocumentState}</dd>
                <dt>협의/인허가 기관</dt><dd>{step.relatedAgencyState}</dd>
                <dt>근거 법령</dt><dd>{step.legalReferenceCount}개</dd>
                <dt>근거 상태</dt><dd>{step.legalReferenceState}</dd>
                <dt>데이터 누락</dt><dd>{step.hasMissingData ? "확인 필요" : "기본 데이터 연결됨"}</dd>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <ReferenceDisclaimer variant="report" />
      <MunicipalityOrdinanceNotice municipality={result.local_government} variant="report" />
    </section>
  );
}
