import { describe, expect, it } from 'vitest';

import { courtIdFromPath, pathToSection, pathToView } from './routes';

describe('console routing', () => {
  it('separates owner, QR and player experiences', () => {
    expect(pathToView('/')).toBe('owner');
    expect(pathToView('/qr?field=field-01')).toBe('qr');
    expect(pathToView('/player?access=private')).toBe('player');
  });

  it('resolves every dashboard section without ambiguous prefixes', () => {
    expect(pathToSection('/')).toBe('overview');
    expect(pathToSection('/fields')).toBe('courts');
    expect(pathToSection('/fields/field-01')).toBe('court');
    expect(pathToSection('/library')).toBe('library');
    expect(pathToSection('/activity')).toBe('activity');
    expect(pathToSection('/notifications')).toBe('notifications');
    expect(pathToSection('/settings')).toBe('settings');
  });

  it('extracts a safe court identifier from the URL', () => {
    expect(courtIdFromPath('/fields/field-01?tab=camera')).toBe('field-01');
    expect(courtIdFromPath('/fields')).toBeNull();
  });
});
