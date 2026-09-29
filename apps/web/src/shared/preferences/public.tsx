import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export type Preferences = components['schemas']['Preferences'];

/**
 * What a visitor gets before the server answers, and whenever it cannot.
 * Quiet by default: an unexpected sound or vibration costs this audience more
 * than a missing one, so silence is the safe direction to fail in.
 */
export const QUIET_DEFAULTS: Preferences = {
  font_scale: 1,
  volume: 0.5,
  quiet_mode: true,
  speech_enabled: false,
  vibration_enabled: false,
  version: 1,
};

const PreferencesContext = createContext<Preferences>(QUIET_DEFAULTS);

export function usePreferences(): Preferences {
  return useContext(PreferencesContext);
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const saved = useQuery({
    queryKey: ['preferences'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/me/preferences', { signal })),
    retry: false,
  });
  const preferences = saved.data ?? QUIET_DEFAULTS;
  useEffect(() => {
    // Font scale is a CSS variable so every page inherits it without opting in.
    document.documentElement.style.setProperty('--font-scale', String(preferences.font_scale));
  }, [preferences.font_scale]);
  return <PreferencesContext.Provider value={preferences}>{children}</PreferencesContext.Provider>;
}
