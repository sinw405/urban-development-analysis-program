import { useEffect, useState } from "react";
import { getMolegDiagnostic, getOfficialLawSeedStatus, listLawUpdates } from "../api/lawUpdates";
import type { LawUpdateEvent, MolegSafeDiagnosticResponse, OfficialLawSeedStatusResponse } from "../api/types";
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
        setError(updates.reason instanceof Error ? updates.reason.message : "법령 개정 감지 내역을 불러오지 못했습니다.");
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
          <>
            <p>
              사유: {diagnostic.reason_message_ko ?? diagnostic.reason_message} ({diagnostic.final_reason_type ?? diagnostic.reason_type}) · fallback {diagnostic.fallback_available ? "사용 가능" : "확인 필요"} · secret 노출 없음 · raw payload 저장 없음
            </p>
            <p>
              조치: {diagnostic.suggested_fix ?? diagnostic.next_action} · 검색 {diagnostic.search_probe?.status ?? "대기"} · 상세조회 {diagnostic.detail_probe?.status ?? "대기"} · 파싱 {diagnostic.parse_probe?.status ?? "대기"}
            </p>
            <p>
              브라우저 성공 기준 {diagnostic.browser_success_metadata_present ? "반영" : "미반영"} · 선택 endpoint {diagnostic.selected_endpoint ?? "미선택"} · live ingest {diagnostic.ready_for_live_ingest ? "가능" : "대기"}
            </p>
          </>
        ) : (
          <p>{diagnosticError ?? "법제처 API 진단 상태를 확인 중입니다."}</p>
        )}
        <div className="inlineStatusRow seedStatusLine">
          <strong>공식 seed 파일</strong>
          <span>{seedStatus ? `${seedStatus.total_files}개` : "확인 중"}</span>
          <span>적재된 공식 조문 {seedStatus?.total_articles ?? 0}개</span>
          <span>확정 조문 {seedStatus?.confirmed_articles ?? 0}개</span>
          <span>미확정 조문 {seedStatus?.unconfirmed_articles ?? 0}개</span>
        </div>
        <p>{seedStatus && seedStatus.total_articles === 0 ? "상태: seed 파일 준비됨 / 아직 공식 조문 미입력" : `상태: ${seedStatus?.validation_status ?? "확인 중"}`} · 수동 작성 {seedStatus?.ready_for_manual_authoring ? "준비됨" : "확인 필요"} · dry-run {seedStatus?.dry_run_supported ? "지원" : "확인 필요"} · 체크리스트 {seedStatus?.authoring_checklist_exists ? "있음" : "없음"} · raw payload 저장 없음 · secret 노출 없음</p>
        <div className="inlineStatusRow seedStatusLine">
          <strong>Batch 1 source</strong>
          <span>자료 폴더 {seedStatus?.source_material_directory_exists ? "있음" : "없음"}</span>
          <span>intake {seedStatus?.source_intake_status ?? "확인 중"}</span>
          <span>row {seedStatus?.source_intake_rows ?? 0}개</span>
          <span>seed 생성 {seedStatus?.ready_for_seed_generation ? "준비됨" : "대기"}</span>
          <span>정책 문서 {seedStatus?.batch1_policy_exists ? "있음" : "없음"}</span>
        </div>
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