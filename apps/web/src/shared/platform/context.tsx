import { createContext, useContext } from 'react';
import { usePreferences } from '@/shared/preferences/public';
import type { Platform } from './types';
export const PlatformContext = createContext<Platform | null>(null);
export function usePlatform(): Platform {
  const platform = useContext(PlatformContext);
  if (!platform) throw new Error('Platform provider is required');
  return platform;
}

/**
 * Device prompts already bound to the viewer's settings. Pages use this rather than
 * `usePlatform`, so nobody has to remember to pass preferences and nobody can forget.
 */
export function usePrompt() {
  const platform = usePlatform();
  const preferences = usePreferences();
  return {
    speak: (text: string) => platform.speak(text, preferences),
    vibrate: () => platform.vibrate(preferences),
    cancelSpeech: () => platform.cancelSpeech(),
  };
}
