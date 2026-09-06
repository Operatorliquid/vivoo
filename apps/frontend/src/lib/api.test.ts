import { describe, expect, it } from 'vitest';

import { ApiRequestError, formatApiError, isInvalidSessionError } from './api';

describe('formatApiError', () => {
  it('preserves a clear API message', () => {
    expect(formatApiError('Email o contraseña incorrectos', 'fallback')).toBe('Email o contraseña incorrectos');
  });

  it('turns validation objects into readable text', () => {
    expect(formatApiError([
      { loc: ['body', 'password'], msg: 'La contraseña es demasiado corta' },
      { loc: ['body', 'email'], msg: 'Ingresá un email válido' },
    ], 'fallback')).toBe('La contraseña es demasiado corta. Ingresá un email válido');
  });

  it('never serializes unknown objects into the UI', () => {
    expect(formatApiError([{ unexpected: true }], 'No pudimos completar la operación.')).toBe('No pudimos completar la operación.');
  });
});

describe('isInvalidSessionError', () => {
  it('only clears stored access when the server rejects the session', () => {
    expect(isInvalidSessionError(new ApiRequestError('Venció', 401))).toBe(true);
    expect(isInvalidSessionError(new ApiRequestError('Sin permiso', 403))).toBe(true);
    expect(isInvalidSessionError(new ApiRequestError('Servidor caído', 503))).toBe(false);
    expect(isInvalidSessionError(new Error('No hay conexión'))).toBe(false);
  });
});
