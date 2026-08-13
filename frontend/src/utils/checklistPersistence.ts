export type ChecklistItems = Record<string, boolean>;
export function checklistScope(result: { analysis_id: number | null; project_id: number | null; created_at: string | null; as_of: string | null }) {
  if (result.analysis_id) return 'analysis:' + result.analysis_id;
  return 'project:' + (result.project_id ?? 'unsaved') + ':' + (result.created_at ?? result.as_of ?? 'current');
}
export function checklistKey(scope: string, kind: 'step' | 'assessment', id: string, fingerprint: string) {
  return ['urban-dev:checklist:v1', scope, kind, id, fingerprint].join(':');
}
export function dataFingerprint(values: unknown[]) {
  let hash = 2166136261;
  for (const char of JSON.stringify(values)) { hash ^= char.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return (hash >>> 0).toString(36);
}
export function loadChecklist(key: string, defaults: ChecklistItems): ChecklistItems {
  try { const parsed = JSON.parse(localStorage.getItem(key) ?? '{}') as Record<string, unknown>; return Object.fromEntries(Object.keys(defaults).map(item => [item, parsed[item] === true])); } catch { return defaults; }
}
export function saveChecklist(key: string, value: ChecklistItems) { localStorage.setItem(key, JSON.stringify(value)); }
