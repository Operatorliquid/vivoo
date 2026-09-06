import { describe, expect, it } from 'vitest';

import { normalizeWhatsAppPhone } from './phone';

describe('normalizeWhatsAppPhone', () => {
  it('adds the Argentine mobile prefix to a local number', () => {
    expect(normalizeWhatsAppPhone('2227 462048')).toBe('+5492227462048');
  });

  it('normalizes an Argentine country prefix without the mobile 9', () => {
    expect(normalizeWhatsAppPhone('+54 2227 462048')).toBe('+5492227462048');
  });

  it('preserves an explicit non-Argentine international number', () => {
    expect(normalizeWhatsAppPhone('+598 99 123 456')).toBe('+59899123456');
  });
});
