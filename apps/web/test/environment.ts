import { builtinEnvironments, type Environment } from 'vitest/environments';

export default {
  name: 'jsdom-native-fetch',
  transformMode: 'web',
  async setup(global, options) {
    const { AbortController, AbortSignal } = global;
    const environment = await builtinEnvironments.jsdom.setup(global, options);
    // Node supplies fetch/Request; cancellation must use the same realm, not jsdom's signal.
    Object.assign(global, { AbortController, AbortSignal });
    return environment;
  },
} satisfies Environment;
