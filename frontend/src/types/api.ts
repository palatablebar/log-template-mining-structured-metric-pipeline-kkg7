export interface ApiErrorShape {
  code: string;
  message: string;
  detail?: string;
  trace_id?: string | null;
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;

  constructor(status: number, payload: ApiErrorShape) {
    super(payload.message || `HTTP ${status}`);
    this.status = status;
    this.code = payload.code || 'INTERNAL_ERROR';
    this.detail = payload.detail || '';
  }
}
