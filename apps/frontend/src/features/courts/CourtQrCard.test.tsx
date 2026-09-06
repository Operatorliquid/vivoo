import { describe, expect, it } from 'vitest';
import { qrDownloadName } from './CourtQrCard';

describe('qrDownloadName', () => {
  it('creates a safe, identifiable filename for each court', () => {
    expect(qrDownloadName('Cancha Pádel 01')).toBe('vivoo-qr-cancha-padel-01.png');
  });

  it('falls back when the court name has no filename characters', () => {
    expect(qrDownloadName('***')).toBe('vivoo-qr-cancha.png');
  });
});
