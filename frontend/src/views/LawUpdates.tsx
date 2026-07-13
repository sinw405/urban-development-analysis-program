import { useEffect, useState } from "react";
import { getMolegDiagnostic, getOfficialLawSeedStatus, listLawUpdates } from "../api/lawUpdates";
import type { LawUpdateEvent, MolegSafeDiagnosticResponse, OfficialLawSeedStatusResponse } from "../api/types";
import { formatDate, formatList, formatStatus } from "../utils/formatters";

function UpdateStatusBadge({ value }: { value: string }) {
  return <span className={`statusBadge status-${value}`}>{formatStatus(value)}</span>;
}

function MolegStatusBadge({ diagnostic }: { diagnostic: MolegSafeDiagnosticResponse | null }) {
  const label = diagnostic?.transport_ok ? "정상" : diagnostic?.live_enabled ? "확인 필요" : "비활성";
  const className = diagnostic?.transport_ok ? "statusBadge moleg-ok" : diagnostic?.live_enabled ? "statusBadge moleg-warn" : "statusBadge moleg-muted";
  return <span className={className}>{label}</span>;
}

function impactLabel(event: LawUpdateEvent) {
  if (event.mapping_status === "confirmed") return "confirmed mapping impact";
  if (event.mapping_status === "unconfirmed" || event.mapping_status === "new_unconfirmed_candidate") return "unconfirmed candidate impact";
  return "unmapped law change";
}

export function LawUpdates() {
  const [items, setItems] = useState<LawUpdateEvent[]>([]);
  const [diagnostic, setDiagnostic] = useState<MolegSafeDiagnosticResponse | null>(null);
  const [seedStatus, setSeedStatus] = useState<OfficialLawSeedStatusResponse | null>(null);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    setDiagnosticError(null);
    try {
      const [updates, moleg, seeds] = await Promise.allSettled([listLawUpdates(), getMolegDiagnostic(), getOfficialLawSeedStatus()]);
      if (updates.status === "fulfilled") {
        setItems(updates.value.items);
      } else {
        setError(updates.reason instanceof Error ? updates.reason.message : "법령 개정 영향 목록을 불러오지 못했습니다.");
      }
      if (moleg.status === "fulfilled") {
        setDiagnostic(moleg.value);
      } else {
        setDiagnostic(null);
        setDiagnosticError(moleg.reason instanceof Error ? moleg.reason.message : "법제처 API 진단 상태를 불러오지 못했습니다.");
      }
      setSeedStatus(seeds.status === "fulfilled" ? seeds.value : null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">법령 개정 알림</p>
          <h1>법령 개정 영향 목록</h1>
          <p className="muted">구조적 조문 변경과 절차 후보 연결 상태만 표시합니다. 법적 의미는 사람이 검토해야 합니다.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={isLoading}>새로고침</button>
      </div>

      <div className="noticeBox compactNotice">
        <div className="inlineStatusRow">
          <strong>법제처 API 연결</strong>
          <MolegStatusBadge diagnostic={diagnostic} />
        </div>
        {diagnostic ? (
          <p>
            사유: {diagnostic.reason_message_ko ?? diagnostic.reason_message} ({diagnostic.final_reason_type ?? diagnostic.reason_type}) · fallback {diagnostic.fallback_available ? "사용 가능" : "확인 필요"} · secret 노출 없음 · raw payload 저장 없음
          </p>
        ) : (
          <p>{diagnosticError ?? "법제처 API 진단 상태를 확인 중입니다."}</p>
        )}
        <div className="inlineStatusRow seedStatusLine">
          <strong>공식 seed 파일</strong>
          <span>{seedStatus ? `${seedStatus.total_files}개` : "확인 중"}</span>
          <span>공식 조문 {seedStatus?.total_articles ?? 0}개</span>
          <span>확정 조문 {seedStatus?.confirmed_articles ?? 0}개</span>
          <span>미확정 조문 {seedStatus?.unconfirmed_articles ?? 0}개</span>
        </div>
      </div>

      {error && (
        <div className="errorBox">
          <strong>법령 개정 영향 목록을 불러오지 못했습니다.</strong>
          <p>백엔드 서버가 실행 중인지 확인해 주세요.</p>
          <details>
            <summary>개발자용 오류 상세</summary>
            <pre>{error}</pre>
          </details>
        </div>
      )}

      {isLoading ? <div className="loadingBox">불러오는 중입니다.</div> : null}
      {!isLoading && items.length === 0 ? <p className="emptyState">현재 확인된 법령 개정 영향이 없습니다.</p> : null}

      {items.length > 0 && (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>법령명</th>
                <th>변경 조문</th>
                <th>변경 유형</th>
                <th>버전</th>
                <th>영향받는 절차</th>
                <th>영향 수준</th>
                <th>검토 상태</th>
                <th>구분</th>
                <th>감지일시</th>
                <th>원문</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event) => (
                <tr key={`${event.event_kind}-${event.event_id}`}>
                  <td>{event.law_name ?? `법령 ID ${event.law_id ?? "-"}`}</td>
                  <td>{event.article_no ? `${event.article_no}${event.article_title ? ` ${event.article_title}` : ""}` : `article ${event.article_id ?? "-"}`}</td>
                  <td>{formatStatus(event.change_type)}</td>
                  <td>{event.from_mst || event.to_mst ? `${event.from_effective_date ?? event.from_mst ?? "-"} -> ${event.to_effective_date ?? event.to_mst ?? "-"}` : formatDate(event.effective_date)}</td>
                  <td>{event.affected_procedure_name ?? formatList(event.impacted_step_codes, "영향받는 절차 없음")}</td>
                  <td>{event.impact_level ?? "-"}</td>
                  <td><UpdateStatusBadge value={event.review_status ?? event.status} /></td>
                  <td>{impactLabel(event)}</td>
                  <td>{formatDate(event.detected_at)}</td>
                  <td>{event.official_url && event.official_url_status === "available" ? <a href={event.official_url} target="_blank" rel="noreferrer">열기</a> : "unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
