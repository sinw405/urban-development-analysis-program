import { requestJson } from './client';
import type { RagAnswerRequest, RagAnswerResponse } from './types';

export function answerLegalQuestion(payload: RagAnswerRequest): Promise<RagAnswerResponse> {
  return requestJson<RagAnswerResponse>('/api/rag/answer', { method: 'POST', body: JSON.stringify(payload) });
}
