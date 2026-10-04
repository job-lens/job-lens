# Native Android work

- Keep production strictly native Kotlin/Compose, with no WebView or fake production data.
- Never add credentials, test fixtures or signing keys to the main APK or source archive.
- Keep origin fixed to the verified JobLens API. Roles/ownership come from the service.
- Preserve CSRF, optimistic resource versions, idempotency keys and unknown outcomes.
- Run core tests, model regressions, Android build and lint after modifications. Distinguish device tests that ran from tests only compiled.
- Device tests and synthetic screenshots must be explicitly labeled and isolated in androidTest.
- Respect upstream Issue → branch → draft PR workflow for any future repository submission. No merge or deploy is implied by this local implementation.
- Cloud software emulators are resource-heavy: coordinate ownership; do not overlap emulator with Gradle or another emulator.
