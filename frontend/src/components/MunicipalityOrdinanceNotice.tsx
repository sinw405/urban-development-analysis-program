import { useId } from "react";

// No municipality ordinance integration or verified coverage exists in this repository.
// This is current system capability, not a claim about a municipality's ordinances.
export const ORDINANCE_AVAILABILITY = "not_linked" as const;

const NOTICE = {
  variance: "지자체별 조례·위원회 운영기준에 따라 절차·심의·서류·처리 방식이 달라질 수 있습니다.",
  status: "현재 시스템에는 지자체 조례·운영기준이 연동되어 있지 않아 선택 지역의 조례 반영 여부를 확인할 수 없습니다.",
  standard: "현재 등록된 공통 법령 근거와 표준 절차 기준으로 안내하며, 해당 지자체에서 확정된 절차를 의미하지 않습니다. 근거 미확인·후보·검토 필요 항목은 그대로 유지됩니다.",
  verification: "실제 적용 전 해당 지자체 자치법규 원문과 인허가권자에게 최종 적용 여부를 확인하세요."
};

interface MunicipalityOrdinanceNoticeProps {
  municipality?: string | null;
  variant?: "global" | "input" | "result" | "report";
}

export function MunicipalityOrdinanceNotice({ municipality, variant = "global" }: MunicipalityOrdinanceNoticeProps) {
  const headingId = useId();
  const Heading = variant === "report" ? "h3" : "h2";
  const region = municipality?.trim();

  return (
    <aside className={`ordinanceNotice ordinanceNotice-${variant}`} aria-labelledby={headingId}>
      <Heading id={headingId}>지자체 조례 안내 · 표준 절차 기준</Heading>
      {variant === "global" ? (
        <p>조례·운영기준 미연동으로 표준 절차를 안내합니다. {NOTICE.variance} {NOTICE.verification}</p>
      ) : (
        <>
          <p><strong>관할 지자체:</strong> {region || "관할 지자체 입력·확인 필요"} <span className="badge neutral">조례 미연동</span></p>
          <p>{NOTICE.status}</p>
          <p>{variant === "input" ? "분석은 기존 공통·표준 절차 기준으로 계속 진행됩니다. " : "표준 절차 기준으로 분석 결과를 표시합니다. "}{NOTICE.standard}</p>
          <p>{NOTICE.variance} {NOTICE.verification}</p>
        </>
      )}
    </aside>
  );
}
