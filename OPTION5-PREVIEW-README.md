# ParentWise Ethiopia — Option 5 Bold Modern preview

**Status:** Visual implementation in isolated GitHub preview branch — NOT approved for QA deployment, production or payment enablement.

**Branch:** `preview/option5-bold-modern-20261011`

## Founder-selected visual reference (11 October 2026)

Option 5 ("Bold Modern") from the original five-option comparison. The reference is a mobile-first, dark forest-green page with an editorial white headline, large introductory video tile, three trust pillars, warm ivory purchase offer, burgundy call to action, and a small rail of actual product materials. The complete long-scroll website must keep all substantive original source sections.

## Implementation

- `index.html`: Loads optional Option 5 preview stylesheet and script, adds accessible mobile navigation and a video-ready preview component. Original source copy and product content remain in the page.
- `option5-preview.css`: Isolated brand-aligned mobile-first visual system, dark hero, value cards, method tiles, revised resource grids, integrated CTA rhythm, tablet/desktop support, focus and reduced-motion styles.
- `option5-preview.js`: Mobile navigation, keyboard close behavior and an honest video placeholder dialog.
- `styles.css`, `app.js`, `product-preview.js`, and all checkout/backend files remain **unchanged**.

### Preview-only limitations / required founder assets

1. **Real introduction video not provided**. Its button opens a clearly labeled informational dialog. It does not claim a video has played. When the approved HTTPS video URL is available, configure `data-video-src` on `#option5-intro-player` and verify playback, poster, captions, keyboard interaction and loading.
2. The intro card currently uses a **temporary external Pexels photograph** while waiting for a high-resolution founder-approved rendition of the selected mother-and-child art. Do not publish with unapproved imagery or hotlinked third-party dependencies.
3. The existing `assets/product-*.webp` and sample PDFs are retained. These are the **real original English-edition pages**, not invented final Amharic product packaging; final Amharic proofs and imagery must be approved separately.
4. Preview QA acceptance requires visual screenshots at 320, 360, 390, 430, 768 and 1440px, on both light and dark displays as appropriate; keyboard and touch testing, screen-reader checks, layout overflow, Core Web Vitals, image licenses, and no regression in the checkout journey.
5. Do not use the fictional QA-only expert-review cards as production endorsements. The production version must use verified independent reviews or omit these layouts.
6. Existing 5–10 minute manual payment review and 30-day practical-use refund promises are inherited unchanged for QA continuity. Validate the policies and operating capacity independently before production.

## Non-negotiable deployment protections

- Do not merge this branch or deploy it to `https://parentwise-ethiopia-qa.onrender.com/` without the founder's explicit visual sign-off.
- Do not modify backend/payment/admin code, environment variables, Render services, PostgreSQL, or product delivery.
- Maintain `APP_MODE=qa` and `PAYMENTS_ENABLED=false`.
- Preserve all accepted Task 05 Phases 1–6 evidence and behaviors.

## Review plan

1. Review this branch's visual changes in a **separate isolated preview**, not the current QA hostname.
2. Compare screenshots directly with the original Option 5 reference. Document any visual deviations; the source reference is generative artwork, so do not claim pixel-perfect source fidelity.
3. Attach the approved introduction video and rights-cleared brand imagery.
4. Run browser, accessibility and existing smoke/regression tests before requesting merge approval.

**Current sign-off:** Not requested; founder visual review pending. Production is NOT APPROVED.
