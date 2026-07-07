import type { ProcedureStep } from "../api/types";
import { formatList } from "../utils/formatters";
import { ProcedureStepDetail } from "./ProcedureStepDetail";

interface ProcedureRoadmapProps {
  steps: ProcedureStep[];
}

export function ProcedureRoadmap({ steps }: ProcedureRoadmapProps) {
  if (!steps || steps.length === 0) {
    return <p className="emptyState">표시할 절차 정보가 없습니다.</p>;
  }

  const orderedSteps = [...steps].sort((left, right) => left.sequence - right.sequence);

  return (
    <section className="procedureRoadmap" aria-label="절차 로드맵">
      {orderedSteps.map((step, index) => (
        <div className="roadmapItem" key={step.step_code}>
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
                <span className="badge">법령 근거 {step.legal_references.length}개</span>
              </div>
            </div>

            <div className="roadmapFacts">
              <span><strong>예상 소요기간</strong>{step.estimated_duration || "정보 없음"}</span>
              <span><strong>필요 서류</strong>{formatList(step.required_documents, "정보 없음")}</span>
              <span><strong>협의기관</strong>{formatList(step.related_agencies, "정보 없음")}</span>
            </div>

            <ProcedureStepDetail step={step} />
          </div>
        </div>
      ))}
    </section>
  );
}
