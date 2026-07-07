export const fieldLabels: Record<string, string> = {
  project_name: "사업명",
  location: "위치",
  area_m2: "사업면적",
  area_square_meters: "사업면적",
  method: "시행방식",
  implementation_method: "시행방식",
  operator_type: "시행자 유형",
  implementer_type: "시행자 유형",
  local_government: "관할 지자체",
  as_of: "기준일",
  procedures: "절차",
  steps: "절차",
  legal_references: "법령 근거",
  law_id: "법령 ID",
  article_id: "조문 ID",
  law_key: "법령 키",
  article_key: "조문 키",
  version_id: "버전 ID",
  version_status: "조문 상태",
  temporal_status: "조문 상태",
  effective_date: "시행일",
  source: "출처",
  analysis_id: "분석 ID",
  project_id: "사업 ID",
  step_code: "단계 코드",
  step_name: "단계명",
  description: "설명",
  estimated_duration: "예상 소요기간",
  change_type: "변경 유형",
  status: "상태",
  impacted_step_codes: "영향받는 절차 코드"
};

export const statusLabels: Record<string, string> = {
  current: "현재 유효",
  previous: "과거 버전",
  expired: "과거 버전",
  scheduled: "시행 예정",
  future: "시행 예정",
  unknown: "확인 필요",
  unknown_effective_date: "시행일 확인 필요",
  PENDING_MOLEG_API_MAPPING: "법제처 매핑 대기",
  TODO_MOLEG_API_ARTICLE_CHECK: "조문 확인 필요",
  EXPERT_REVIEW_REQUIRED: "전문가 검토 필요",
  NEW_VERSION: "신규 버전 감지",
  CONTENT_CHANGED: "내용 변경 감지",
  EFFECTIVE_DATE_CHANGED: "시행일 변경 감지",
  DETECTED: "감지됨",
  PENDING: "대기 중"
};

export const methodLabels: Record<string, string> = {
  mixed: "혼용 방식",
  expropriation_or_use: "수용 또는 사용 방식",
  replotting: "환지 방식"
};

export const operatorLabels: Record<string, string> = {
  public_private_spc: "민관 공동 SPC",
  public: "공공 시행자",
  private: "민간 시행자"
};

export function labelFor(key: string): string {
  return fieldLabels[key] ?? key;
}

export function statusLabel(value: string | null | undefined): string {
  if (!value) {
    return "확인 필요";
  }
  return statusLabels[value] ?? value;
}

export function methodLabel(value: string): string {
  return methodLabels[value] ?? value;
}

export function operatorLabel(value: string): string {
  return operatorLabels[value] ?? value;
}
