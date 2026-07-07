import { statusLabel } from "./labels";

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "확인 필요";
  }
  return value;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toLocaleString("ko-KR");
}

export function formatArea(value: number | null | undefined): string {
  const formatted = formatNumber(value);
  return formatted === "-" ? formatted : `${formatted}㎡`;
}

export function formatList(values: string[] | null | undefined, emptyText = "표시할 데이터가 없습니다."): string {
  if (!values || values.length === 0) {
    return emptyText;
  }
  return values.join(", ");
}

export function formatStatus(value: string | null | undefined): string {
  return statusLabel(value);
}

export function countLegalReferences<T extends { legal_references?: unknown[] }>(steps: T[]): number {
  return steps.reduce((total, step) => total + (step.legal_references?.length ?? 0), 0);
}
