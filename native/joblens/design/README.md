# Design provenance

- `web-tokens.css`: unchanged from job-lens/job-lens main 790e886, `apps/web/src/styles/tokens.css`.
- `brand-mark.svg`: unchanged source SVG. Converted path geometry lives in Android `res/drawable/brand_mark.xml`; night colors match the source SVG media query.
- Navigation icons reuse the Web `shared/ui/Icon.tsx` path geometry; the Android back arrow mirrors its directional path. Vector drawables retain 1.65px stroke, round caps and round joins.
- Compose uses native TextFields, buttons, dialogs, system inset handling, Storage Access Framework, Android Keystore, Bitmap/PdfRenderer and accessibility semantics. No HTML rendering or WebView.
- Page typography uses native serif headings with a CJK-friendly line height, native sans-serif controls, a 13sp metadata floor, 48dp minimum primary controls, 20dp cards and capsule inputs.
- System dark mode uses the exact corresponding neutral Web palette. Dynamic Material colors are intentionally not substituted for the product colors.

## 0.1.1 visual correction

Current Web baseline was rechecked at `e6a9c9fc9f6c45abe5ec94d65aff556505ca859e`. See `WEB-PARITY.md` for the page/state comparison and `web-reference/` for unchanged Buddy/Companions/WorkIllustration sources. Android uses their actual paths and animation timings in native Compose Canvas. The Web workspace overrides global serif headings with sans-serif; the native workspace now follows that rule. A small Noto Serif CJK SC font subset is bundled for the static authentication headings only, with its SIL Open Font License included.
