import { useState } from "react";
import type { ProcedureStep } from "../api/types";
import { formatList } from "../utils/formatters";
import type { ChecklistStatus } from "./ProcedureChecklist";
import { ProcedureStepDetail } from "./ProcedureStepDetail";

interface ProcedureRoadmapProps {
  steps: ProcedureStep[];
}

function statusClass(status: ChecklistStatus): string {
  if (status === "확인완료") {
    return "complete";
  }
  if (status === "확인중") {
    return "progress";
  }
  return "pending";
}

export function ProcedureRoadmap({ steps }: ProcedureRoadmapProps) {
  const [stepStatuses, setStepStatuses] = useState<Record<string, ChecklistStatus>>({});

  if (!steps || steps.length === 0) {
    return <p className="emptyState">표시할 절차 정보가 없습니다.</p>;
  }

  const orderedSteps = [...steps].sort((left, right) => left.sequence - right.sequence);

  function getStepStatus(stepCode: string): ChecklistStatus {
    return stepStatuses[stepCode] ?? "미확인";
  }

  function updateStepStatus(stepCode: string, status: ChecklistStatus) {
    setStepStatuses((current) => ({ ...current, [stepCode]: status }));
  }

  return (
    <section className="procedureRoadmap" aria-label="절차 로드맵">
      {orderedSteps.map((step, index) => {
        const status = getStepStatus(step.step_code);
        return (
          <div className={`roadmapItem roadmap-${statusClass(status)}`} key={step.step_code}>
            <div className="roadmapMarker" aria-hidden="true">
              <span>{index + 1}</span>
            </div>
            <div className="roadmapContent">
              <div className="roadmapSummary">
                <div>
                  <p className="eyebrow">{step.sequence}단계</p>
                  <h3>{step.step_name || "단계명 정보 없음"}</h3>
                  <p>{step.description || "단계 설명 정보가 없습니다."}</p>
                </div>
                <div className="roadmapBadges">
                  <span className="badge neutral">{step.step_code}</span>
                  <span className={`checkStatusBadge ${statusClass(status)}`}>{status}</span>
                  <span className="badge">법령 근거 {step.legal_references.length}개</span>
                </div>
              </div>

              <div className="roadmapFacts">
                <span><strong>예상 소요기간</strong>{step.estimated_duration || "정보 없음"}</span>
                <span><strong>필요 서류</strong>{formatList(step.required_documents, "정보 없음")}</span>
                <span><strong>협의기관</strong>{formatList(step.related_agencies, "정보 없음")}</span>
              </div>

              <ProcedureStepDetail
                step={step}
                checklistStatus={status}
                onChecklistStatusChange={(nextStatus) => updateStepStatus(step.step_code, nextStatus)}
              />
            </div>
          </div>
        );
      })}
    </section>
  );
}
