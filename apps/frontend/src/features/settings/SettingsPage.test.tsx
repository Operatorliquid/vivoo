import { describe, expect, it } from 'vitest';
import type { WhatsAppConnection } from '../../lib/api';
import { mergeWhatsAppPairing } from './SettingsPage';

const pairing: WhatsAppConnection = {
  status: 'connecting',
  instance_name: 'tveo-test',
  phone: null,
  profile_name: null,
  qr_base64: 'data:image/png;base64,qr',
  pairing_code: '12345678',
};

describe('mergeWhatsAppPairing', () => {
  it('keeps the QR while a status poll still reports connecting', () => {
    const statusOnly = { ...pairing, qr_base64: null, pairing_code: null };
    expect(mergeWhatsAppPairing(pairing, statusOnly)).toEqual(pairing);
  });

  it('uses a refreshed QR when Evolution returns one', () => {
    const refreshed = { ...pairing, qr_base64: 'data:image/png;base64,new' };
    expect(mergeWhatsAppPairing(pairing, refreshed)).toEqual(refreshed);
  });

  it('removes pairing data after WhatsApp connects', () => {
    const connected: WhatsAppConnection = { ...pairing, status: 'connected', qr_base64: null, pairing_code: null };
    expect(mergeWhatsAppPairing(pairing, connected)).toEqual(connected);
  });
});
