import { describe, expect, it } from 'vitest';
import { TAPO_STREAM_PATH } from './NewCourtDialog';

describe('Tapo camera defaults', () => {
  it('uses the native Tapo RTSP stream path', () => {
    expect(TAPO_STREAM_PATH).toBe('/stream1');
  });
});
