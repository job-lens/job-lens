export type PlatformFailure = 'unsupported' | 'permission_denied' | 'cancelled' | 'failed';
export type PlatformResult<T> = { ok: true; value: T } | { ok: false; reason: PlatformFailure };
export interface PromptPreferences {
  quiet_mode: boolean; volume: number; speech_enabled: boolean; vibration_enabled: boolean;
}
export interface Platform {
  pickImage(camera: boolean, signal?: AbortSignal): Promise<PlatformResult<File>>;
  speak(text: string, preferences: PromptPreferences): PlatformResult<void>;
  vibrate(preferences: PromptPreferences): PlatformResult<void>;
  cancelSpeech(): void;
}
