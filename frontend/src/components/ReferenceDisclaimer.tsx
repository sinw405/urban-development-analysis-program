import { useId } from "react";

const NOTICE = {
  reference: "본 분석 결과는 참고용 자료이며 법적 유권해석 또는 인허가권자의 공식 판단을 대체하지 않습니다.",
  verification: "실제 사업 적용 시 관련 법령·조문 원문을 확인하고, 최종 적용 여부는 해당 인허가권자 및 필요한 경우 도시개발·법무 등 관련 전문가에게 확인해야 합니다.",
  scope: "절차, 근거 조문, 심의·평가, 필요 서류, 협의기관, 기간, 규칙 기반 판정 및 AI 근거 설명을 포함한 분석 결과에 적용되는 안내입니다.",
  source: "근거 조문 원문은 법령 근거 설명의 출처·인용 항목에서 제공되는 원문 링크로 확인하세요. 원문 링크가 없는 항목은 관련 법령·조문 원문을 별도로 확인해야 합니다."
};

interface ReferenceDisclaimerProps {
  variant?: "global" | "analysis" | "report";
}

export function ReferenceDisclaimer({ variant = "global" }: ReferenceDisclaimerProps) {
  const headingId = useId();
  const title = variant === "global" ? "참고용 · 적용 전 확인 안내" : "분석 결과 이용 안내 · 참고용";
  const Heading = variant === "report" ? "h3" : "h2";

  return (
    <aside className={`referenceDisclaimer referenceDisclaimer-${variant}`} aria-labelledby={headingId}>
      <Heading id={headingId}>{title}</Heading>
      <p>{NOTICE.reference}</p>
      <p>{NOTICE.verification}</p>
      {variant !== "global" && (
        <>
          <p>{NOTICE.scope}</p>
          <p>{NOTICE.source}</p>
        </>
      )}
    </aside>
  );
}
