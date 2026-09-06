export type SportCode = 'padel' | 'football';
export type HighlightStatus = 'processing' | 'ready' | 'failed' | 'expired';
export type DeliveryStatus = 'queued' | 'sent' | 'delivered' | 'failed' | 'revoked';

export interface HighlightSummary {
  id: string;
  fieldName: string;
  createdAt: string;
  status: HighlightStatus;
  durationSeconds: number;
}
