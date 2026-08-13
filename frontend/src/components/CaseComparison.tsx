import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchComparisonCases } from "../api/cases";
import type { AnalyzeResponse, CaseComparisonItem, CaseHistoryItem } from "../api/types";

interface CaseComparisonProps {
  currentProject: AnalyzeResponse;
}

const NO_DATA = "정보 없음";
const MAX_SELECTED_CASES = 2;

function displayValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return NO_DATA;
  return String(value);
}

function displayArea(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_DATA;
  return `${value.toLocaleString("ko-KR")}㎡`;
}

function orderedHistory(item: CaseComparisonItem): CaseHistoryItem[] {
  return [...item.timeline, ...item.history].sort((left, right) => {
    if (!left.date && !right.date) return 0;
    if (!left.date) return 1;
    if (!right.date) return -1;
    return left.date.localeCompare(right.date);
  });
}

export function CaseComparison({ currentProject }: CaseComparisonProps) {
  const [cases, setCases] = useState<CaseComparisonItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");

  const loadCases = useCallback(async () => {
    if (currentProject.project_id === null) {
      setCases([]);
      setSelectedIds([]);
      setStatus("empty");
      return;
    }
    setStatus("loading");
    try {
      const response = await fetchComparisonCases(currentProject.project_id);
      setCases(response.items);
      setSelectedIds(response.items.slice(0, MAX_SELECTED_CASES).map((item) => item.id));
      setStatus(response.items.length === 0 ? "empty" : "ready");
    } catch {
      setStatus("error");
    }
  }, [currentProject.project_id]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const selectedCases = useMemo(
    () => selectedIds.map((id) => cases.find((item) => item.id === id)).filter((item): item is CaseComparisonItem => Boolean(item)),
    [cases, selectedIds]
  );

  function toggleCase(id: number) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= MAX_SELECTED_CASES) return current;
      return [...current, id];
    });
  }

  return (
    <section className="panel caseComparison" aria-labelledby="case-comparison-title">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">사례 비교</p>
          <h2 id="case-comparison-title">현재 사업과 등록 사례 비교</h2>
          <p className="muted">비교 사례는 최대 2개까지 선택할 수 있습니다.</p>
        </div>
        {status === "ready" && <span className="badge neutral">등록 사례 {cases.length}개</span>}
      </div>

      <p className="noticeBox compactNotice">
        사례 비교 정보는 참고용이며, 개별 사업의 법적·행정적 적용 여부는 해당 사업의 분석 결과와 관계기관 확인이 필요합니다.
      </p>

      {status === "loading" && <div className="loadingBox">비교 사례를 불러오는 중입니다.</div>}
      {status === "empty" && <div className="emptyPanel"><p>등록된 비교 사례가 없습니다.</p></div>}
      {status === "error" && (
        <div className="errorBox">
          <p>사례 정보를 불러오지 못했습니다.</p>
          <button type="button" className="secondaryButton smallButton" onClick={() => void loadCases()}>다시 시도</button>
        </div>
      )}

      {status === "ready" && (
        <>
          <div className="caseSelector" aria-label="비교 사례 선택">
            {cases.map((item) => {
              const checked = selectedIds.includes(item.id);
              return (
                <label key={item.id} className="caseSelectorItem">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!checked && selectedIds.length >= MAX_SELECTED_CASES}
                    onChange={() => toggleCase(item.id)}
                  />
                  <span><strong>{item.name}</strong><small>비교 사례</small></span>
                </label>
              );
            })}
          </div>

          <div className="tableWrap caseComparisonTable">
            <table>
              <thead>
                <tr>
                  <th>비교 항목</th>
                  <th><span className="badge">현재 분석 사업</span><br />{currentProject.project_name}</th>
                  {selectedCases.map((item) => <th key={item.id}><span className="badge neutral">비교 사례</span><br />{item.name}</th>)}
                </tr>
              </thead>
              <tbody>
                <tr><th>사업명</th><td>{displayValue(currentProject.project_name)}</td>{selectedCases.map((item) => <td key={item.id}>{displayValue(item.name)}</td>)}</tr>
                <tr><th>위치·지역</th><td>{displayValue(currentProject.location)}</td>{selectedCases.map((item) => <td key={item.id}>{displayValue(item.location)}</td>)}</tr>
                <tr><th>면적</th><td>{displayArea(currentProject.area_square_meters)}</td>{selectedCases.map((item) => <td key={item.id}>{displayArea(item.area_m2)}</td>)}</tr>
                <tr><th>시행방식</th><td>{displayValue(currentProject.implementation_method)}</td>{selectedCases.map((item) => <td key={item.id}>{displayValue(item.method)}</td>)}</tr>
                <tr><th>시행자 유형</th><td>{displayValue(currentProject.implementer_type)}</td>{selectedCases.map((item) => <td key={item.id}>{displayValue(item.operator_type)}</td>)}</tr>
              </tbody>
            </table>
          </div>

          {selectedCases.length === 0 && <p className="emptyState">비교할 사례를 선택해 주세요.</p>}
          {selectedCases.map((item) => {
            const entries = orderedHistory(item);
            return (
              <section key={item.id} className="caseHistoryCard">
                <h3>{item.name} 진행 이력</h3>
                {entries.length === 0 ? (
                  <p className="emptyState">등록된 진행 이력이 없습니다.</p>
                ) : (
                  <ol className="caseHistoryList">
                    {entries.map((entry, index) => (
                      <li key={`${entry.date ?? "undated"}-${entry.stage ?? "stage"}-${index}`}>
                        <strong>{displayValue(entry.stage)}</strong>
                        <span>{displayValue(entry.date)} · {displayValue(entry.status)}</span>
                        {entry.description ? <p>{entry.description}</p> : null}
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            );
          })}
        </>
      )}
    </section>
  );
}