import { describe, expect, it } from 'vitest';

import type { OwnerHighlight } from '../lib/api';
import { mergeOwnerHighlights } from './useOwnerConsole';

const highlight = (overrides: Partial<OwnerHighlight> = {}): OwnerHighlight => ({
  id: 'highlight-1',
  display_id: 'HIGHLIGHT-1',
  title: 'Momento',
  field_id: 'field-1',
  field_name: 'Cancha 1',
  session_id: 'session-1',
  session_code: 'ABC1',
  session_started_at: '2026-09-03T20:00:00Z',
  players: ['Jose'],
  occurred_at: '2026-09-03T20:10:00Z',
  duration_seconds: 30,
  confidence: 0.91,
  status: 'available',
  media_path: '/media?ticket=first',
  download_path: '/media?ticket=first&download=1',
  ...overrides,
});

describe('mergeOwnerHighlights', () => {
  it('keeps the same object and signed media URL when only the ticket rotates', () => {
    const current = [highlight()];
    const merged = mergeOwnerHighlights(current, [highlight({
      media_path: '/media?ticket=second',
      download_path: '/media?ticket=second&download=1',
    })]);

    expect(merged).toBe(current);
    expect(merged[0]).toBe(current[0]);
    expect(merged[0].media_path).toContain('ticket=first');
  });

  it('accepts the fresh media URL when processing completes', () => {
    const current = [highlight({ status: 'processing', media_path: null, download_path: null })];
    const merged = mergeOwnerHighlights(current, [highlight()]);

    expect(merged).not.toBe(current);
    expect(merged[0].status).toBe('available');
    expect(merged[0].media_path).toContain('ticket=first');
  });
});
