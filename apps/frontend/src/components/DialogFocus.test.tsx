// @vitest-environment jsdom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it } from 'vitest';
import { Dialog, TextField } from '@courtvision/design-system';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const mounted: Array<() => void> = [];

afterEach(() => {
  mounted.splice(0).forEach((cleanup) => cleanup());
  document.body.innerHTML = '';
});

describe('Dialog focus management', () => {
  it('keeps focus on the active field when controlled content rerenders', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    mounted.push(() => act(() => root.unmount()));

    const renderDialog = () => (
      <Dialog open title="Nueva cancha" onClose={() => undefined}>
        <TextField label="Nombre de la cámara" defaultValue="Cámara 1" />
        <TextField label="Host o IP" />
      </Dialog>
    );

    act(() => root.render(renderDialog()));
    const labels = Array.from(document.querySelectorAll<HTMLLabelElement>('.cv-field__label'));
    const nameInput = document.getElementById(labels[0].htmlFor);
    const hostInput = document.getElementById(labels[1].htmlFor) as HTMLInputElement;
    hostInput.focus();
    expect(document.activeElement).toBe(hostInput);

    act(() => root.render(renderDialog()));

    expect(document.activeElement).toBe(hostInput);
    expect(document.activeElement).not.toBe(nameInput);
  });
});
