import type { ProcedureStep } from "../api/types";
import { formatList } from "../utils/formatters";
import { normalizeProcedureSteps } from "../utils/analysisSummary";
import type { ChecklistStatus } from "./ProcedureChecklist";
import { ProcedureStepDetail } from "./ProcedureStepDetail";

interface ProcedureRoadmapProps {
  steps: ProcedureStep[];
  stepStatuses: Record<string, ChecklistStatus>;
  onStepStatusChange: (stepCode: string, status: ChecklistStatus) => void;
  asOf: string | null;
  persistenceScope: string;
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

export function ProcedureRoadmap({ steps, stepStatuses, onStepStatusChange, asOf, persistenceScope }: ProcedureRoadmapProps) {
  const normalizedSteps = normalizeProcedureSteps(steps, stepStatuses);

  if (normalizedSteps.length === 0) {
    return <p className="emptyState">표시할 절차 정보가 없습니다.</p>;
  }

  return (
    <section className="procedureRoadmap" aria-label="절차 로드맵">
      {normalizedSteps.map((step, index) => (
        <div className={`roadmapItem roadmap-${statusClass(step.checklistStatus)}`} key={step.stepCode}>
          <div className="roadmapMarker" aria-hidden="true">
            <span>{index + 1}</span>
          </div>
          <div className="roadmapContent">
            <div className="roadmapSummary">
              <div>
                <p className="eyebrow">{step.sequence}단계</p>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
              <div className="roadmapBadges">
                <span className="badge neutral">{step.stepCode}</span>
                <span className={`checkStatusBadge ${statusClass(step.checklistStatus)}`}>{step.checklistStatus}</span>
                <span className="badge">{step.legalReferenceState}</span>
              </div>
            </div>

            <div className="roadmapFacts">
              <span><strong>예상 소요기간</strong>{step.durationState}</span>
              <span><strong>필요 서류</strong>{step.requiredDocumentState}</span>
              <span><strong>협의/인허가 기관</strong>{step.relatedAgencyState}</span>
            </div>

            {step.hasMissingData && (
              <div className="missingDataNotice">
                <strong>확인 필요 항목</strong>
                <span>{formatList([
                  step.legalReferenceCount === 0 ? "근거 미연결" : "",
                  step.requiredDocumentCount === 0 ? "서류 확인 필요" : "",
                  step.relatedAgencyCount === 0 ? "기관 확인 필요" : "",
                  step.durationState === "기간 확인 필요" ? "기간 확인 필요" : ""
                ].filter(Boolean), "확인 필요 항목 없음")}</span>
              </div>
            )}

            <ProcedureStepDetail
              step={step.raw}
              normalizedStep={step}
              checklistStatus={step.checklistStatus}
              onChecklistStatusChange={(nextStatus) => onStepStatusChange(step.stepCode, nextStatus)}
              asOf={asOf}
              persistenceScope={persistenceScope}
            />
          </div>
        </div>
      ))}
    </section>
  );
}
