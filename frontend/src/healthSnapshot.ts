import type { SystemHealth } from './types';

export interface HealthSnapshot {
  accountId: number | null;
  health: SystemHealth;
}

// Health includes private library counts. A new account must not inherit them,
// including during a slow or failed refresh; keep a neutral pending state.
export function healthForAccount(snapshot: HealthSnapshot | null, accountId: number | null): SystemHealth | null {
  return snapshot?.accountId === accountId ? snapshot.health : null;
}
