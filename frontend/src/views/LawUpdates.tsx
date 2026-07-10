import { useEffect, useState } from "react";
import { getMolegDiagnostic, listLawUpdates } from "../api/lawUpdates";
import type { LawUpdateEvent, MolegSafeDiagnosticResponse } from "../api/types";
import { formatDate, formatList, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";

function UpdateStatusBadge({ value }: { value: string }) {
  return <span className={`statusBadge status-${value}`}>{formatStatus(value)}</span>;
}

function MolegStatusBadge({ diagnostic }: { diagnostic: MolegSafeDiagnosticResponse | null }) {
  const label = diagnostic?.transport_ok ? "정상" : diagnostic?.live_enabled ? "확인 필요" : "비활성";
  const className = diagnostic?.transport_ok ? "statusBadge moleg-ok" : diagnostic?.live_enabled ? "statusBadge moleg-warn" : "statusBadge moleg-muted";
  return <span className={className}>{label}</span>;
}

export function LawUpdates() {
  const [items, setItems] = useState<LawUpdateEvent[]>([]);
  const [diagnostic, setDiagnostic] = useState<MolegSafeDiagnosticResponse | null>(null);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    setDiagnosticError(null);
    try {
      const [updates, moleg] = await Promise.allSettled([listLawUpdates(), getMolegDiagnostic()]);
      if (updates.status === "fulfilled") {
        setItems(updates.value.items);
      } else {
        setError(updates.reason instanceof Error ? updates.reason.message : "법령 개정 감지 내역을 불러오지 못했습니다.");
      }
      if (moleg.status === "fulfilled") {
        setDiagnostic(moleg.value);
      } else {
        setDiagnostic(null);
        setDiagnosticError(moleg.reason instanceof Error ? moleg.reason.message : "법제처 API 진단 상태를 불러오지 못했습니다.");
      }
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
          <p className="eyebrow">법령 개정 감지</p>
          <h1>법령 개정 감지 내역</h1>
          <p className="muted">TEST 데이터 기준으로 감지된 법령 변경 이벤트와 영향받는 절차 코드를 확인합니다.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={isLoading}>새로고침</button>
      </div>

      <div className="noticeBox compactNotice">
        실제 법령명, 조문번호, 기준값은 표시하지 않습니다. 이 화면은 저장된 이벤트 메타데이터만 보여줍니다.
      </div>

      <div className="noticeBox compactNotice">
        <div className="inlineStatusRow">
          <strong>법제처 API 연결</strong>
          <MolegStatusBadge diagnostic={diagnostic} />
        </div>
        {diagnostic ? (
          <p>
            사유: {diagnostic.reason_message} ({diagnostic.reason_type}) · fallback {diagnostic.fallback_available ? "사용 가능" : "확인 필요"} · secret 노출 없음 · raw payload 저장 없음
          </p>
        ) : (
          <p>{diagnosticError ?? "법제처 API 진단 상태를 확인 중입니다."}</p>
        )}
      </div>

      {error && (
        <div className="errorBox">
          <strong>법령 개정 감지 내역을 불러오지 못했습니다.</strong>
          <p>백엔드 서버가 실행 중인지 확인해 주세요.</p>
          <details>
            <summary>개발자용 오류 상세</summary>
            <pre>{error}</pre>
          </details>
        </div>
      )}

      {isLoading ? <div className="loadingBox">불러오는 중입니다.</div> : null}
      {!isLoading && items.length === 0 ? <p className="emptyState">감지된 법령 개정 이벤트가 없습니다.</p> : null}

      {items.length > 0 && (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>이벤트 ID</th>
                <th>{labelFor("change_type")}</th>
                <th>{labelFor("effective_date")}</th>
                <th>{labelFor("status")}</th>
                <th>{labelFor("source")}</th>
                <th>{labelFor("impacted_step_codes")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event) => (
                <tr key={event.event_id}>
                  <td>{event.event_id}</td>
                  <td>{formatStatus(event.change_type)}</td>
                  <td>{formatDate(event.effective_date)}</td>
                  <td><UpdateStatusBadge value={event.status} /></td>
                  <td>{event.source}</td>
                  <td>{formatList(event.impacted_step_codes, "영향받는 절차 없음")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
