import type { OwnerSession } from './api';

const AUTH_KEY = 'courtvision.owner.session';
const ADMIN_AUTH_KEY = 'tveo.admin.session';

export function readOwnerSession(): OwnerSession | null {
  try {
    const value = localStorage.getItem(AUTH_KEY);
    return value ? JSON.parse(value) as OwnerSession : null;
  } catch {
    return null;
  }
}

export function saveOwnerSession(session: OwnerSession) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(session));
}

export function clearOwnerSession() {
  localStorage.removeItem(AUTH_KEY);
}

export function readAdminSession(): OwnerSession | null {
  try {
    const value = localStorage.getItem(ADMIN_AUTH_KEY);
    return value ? JSON.parse(value) as OwnerSession : null;
  } catch {
    return null;
  }
}

export function saveAdminSession(session: OwnerSession) {
  localStorage.setItem(ADMIN_AUTH_KEY, JSON.stringify(session));
}

export function clearAdminSession() {
  localStorage.removeItem(ADMIN_AUTH_KEY);
}
