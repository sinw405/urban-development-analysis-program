import { useMemo, useState } from "react";
import type { ProcedureStep } from "../api/types";
import { formatList } from "../utils/formatters";

export type ChecklistStatus = "미확인" | "확인중" | "확인완료";

type ChecklistItemKey = "legal" | "documents" | "agencies" | "duration" | "notes";

interface ChecklistItem {
  key: ChecklistItemKey;
  label: string;
  detail: string;
}

interface ProcedureChecklistProps {
  step: ProcedureStep;
  status: ChecklistStatus;
  onStatusChange: (status: ChecklistStatus) => void;
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

function buildChecklistItems(step: ProcedureStep): ChecklistItem[] {
  return [
    {
      key: "legal",
      label: "법령 근거 확인",
      detail: step.legal_references.length > 0 ? `연결된 법령 근거 ${step.legal_references.length}개` : "연결된 법령 근거가 없습니다."
    },
    {
      key: "documents",
      label: "필요 서류 확인",
      detail: formatList(step.required_documents, "등록된 필요 서류가 없습니다.")
    },
    {
      key: "agencies",
      label: "협의기관 확인",
      detail: formatList(step.related_agencies, "등록된 협의기관 정보가 없습니다.")
    },
    {
      key: "duration",
      label: "예상 소요기간 확인",
      detail: step.estimated_duration || "예상 소요기간 정보가 없습니다."
    },
    {
      key: "notes",
      label: "비고/주의사항 확인",
      detail: formatList(step.notes, "등록된 비고가 없습니다.")
    }
  ];
}

export function ProcedureChecklist({ step, status, onStatusChange }: ProcedureChecklistProps) {
  const items = useMemo(() => buildChecklistItems(step), [step]);
  const [checkedItems, setCheckedItems] = useState<Record<ChecklistItemKey, boolean>>({
    legal: false,
    documents: false,
    agencies: false,
    duration: false,
    notes: false
  });

  function updateCheckedItem(key: ChecklistItemKey, checked: boolean) {
    const next = { ...checkedItems, [key]: checked };
    setCheckedItems(next);

    const checkedCount = Object.values(next).filter(Boolean).length;
    if (checkedCount === 0) {
      onStatusChange("미확인");
    } else if (checkedCount === items.length) {
      onStatusChange("확인완료");
    } else {
      onStatusChange("확인중");
    }
  }

  return (
    <section className="procedureChecklist">
      <div className="checklistHeader">
        <div>
          <h4>실무 확인 체크리스트</h4>
          <p className="muted">체크 상태는 현재 화면에서만 관리되며 서버에 저장되지 않습니다.</p>
        </div>
        <span className={`checkStatusBadge ${statusClass(status)}`}>{status}</span>
      </div>

      <div className="checklistItems">
        {items.map((item) => (
          <label className="checklistItem" key={item.key}>
            <input
              type="checkbox"
              checked={checkedItems[item.key]}
              onChange={(event) => updateCheckedItem(item.key, event.target.checked)}
            />
            <span>
              <strong>{item.label}</strong>
              <small>{item.detail}</small>
            </span>
          </label>
        ))}
      </div>
    </section>
  );
}
