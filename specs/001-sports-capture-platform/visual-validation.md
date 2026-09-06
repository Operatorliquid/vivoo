# Visual validation — first frontend slice

Date: 2026-08-11

Typography review: 2026-08-10. Replaced the previous expressive display face with
Manrope 700–800 for a more professional broadcast/editorial tone. IBM Plex Sans
remains the interface face and IBM Plex Mono remains the data face. The display
rules now live in `packages/design-system/src/typography.css`.

The CourtVision prototype was checked with Playwright against the local Vite
server at desktop 1440px and mobile 390px viewports.

| Surface | Viewport | Result |
|---|---:|---|
| Owner login `/` | 1440px | PASS — demo owner can sign in and reaches the protected command center |
| Owner command center `/` | 1440px | PASS — authenticated API data, media-led layout, camera strip, activity, highlights and metrics render without horizontal overflow |
| Field operations section `/fields` | 1440px | PASS — navigable dashboard section with custom field selector, create/delete flow, club identity, field names, camera state, camera load/edit/unlink, recording mode, gesture/manual detection, QR copy and field selection |
| Field detail `/fields/:fieldId` | 1440px | PASS — opening a field leads to its clips, camera resource, capture settings, player QR and destructive actions in a dedicated view |
| Owner settings `/settings` | 1440px | PASS — club identity and owner account data save through the protected API in separate full-width sections |
| Notifications `/notifications` | 1440px | PASS — camera/session/highlight alerts load from the API and can be marked as read without a modal |
| QR landing `/qr` | 390px | PASS — single primary action, high-contrast form card, touch-sized controls |
| Player media page `/player` | 390px | PASS — honest empty state and club CTA render without invented matches, dates or highlights |
| QR registration flow | 390px | PASS — welcome → form → registered state, field validation and confirmation copy |

Screenshots captured during validation:

- `/tmp/courtvision-owner.png`
- `/tmp/courtvision-fields.png`
- `/tmp/courtvision-qr-mobile.png`
- `/tmp/courtvision-player-mobile.png`

The owner summary and infrastructure surfaces use API-backed values only. When the
local store has no club identity, highlights or delivery records, the interface
shows an explicit empty state or `—` instead of a fabricated title, date or metric.

Known follow-up: replace the deterministic CSS court artwork with real signed media
fixtures once the capture-agent and S3 media contracts are implemented.
