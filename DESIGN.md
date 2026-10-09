# Design and Accessibility

## Reference boundaries

Both reference sites were visually inspected using browser screenshots before the screens were built. [SheKunj](https://www.shekunj.com/) showed a spacious pale entrance composition, a large centred headline and illustration-led hierarchy. Only the welcome screen adopts those compositional ideas. Its green/cream palette, abstract source-network drawing, words and NULLVERSE mark are original. No branding, proprietary imagery or text was copied.

[Justin Lerner's site](https://jlern.com/) showed a measured tiled grid with clear borders, oversized typographic elements and individual illustrated cells. The main workspace adapts its modular composition and restrained entrances to investigation tasks. It does not reproduce the site's assets or infer unobserved motion. The graph sketch on the dashboard is explicitly decorative; real graph entities and statistics come from database endpoints.

## Tokens

| Token | Value / Use |
|---|---|
| Canvas | `#09151e` dark navy |
| Panel | `#0d1d28` |
| Border | `#20323d` |
| Text | `#dce8ec` |
| Muted | `#90a6b3` |
| Accent | `#7ed7bf` teal |
| Warning | Warm amber, with textual review-state labels |
| Typography | Locally bundled variable DM Sans and Manrope |
| Corners | 4–8 px workspace surfaces; softer welcome framing |

The desktop workspace uses a narrow navigation column, full-width heading, an asymmetric overview composition and compact data tables. On small screens, navigation becomes a horizontally scrollable row, cards stack, source review becomes vertical, tables scroll within their container and drawers fill the viewport. Native page scrolling and pinch zoom remain available.

## Interaction and motion

Welcome/workspace entrance uses Framer Motion with operating-system reduced-motion preferences. Panels and drawers animate opacity and transform only. Import progress uses transform on a fixed track. The graph canvas uses a brief entrance, while layout geometry updates immediately to avoid animation callbacks surviving a view switch. Reduced motion disables the canvas entrance. Nothing loops continuously. Every major state has a loading, empty or error presentation; service errors are announced instead of displaying mock data.

Buttons operate in-page views at the unchanged `/` URL. The user's single-page instruction intentionally overrides Web Design Guidelines recommendations to synchronise tabs with query parameters. Original-file links open the separate backend source endpoint in a new tab; browser application navigation stays unchanged. Skip to Content focuses the main landmark without adding a URL hash.

Forms have accessible names; upload, mapping, search, review, dates, source corrections and path endpoints have native labels. Icon-only buttons have explicit names. Keyboard focus is visible. Native modal dialogs trap focus and support Escape. Graph controls expose buttons and a keyboard-accessible entity/relationship list, rather than requiring pointer gestures. Facts and conflicts use text labels as well as colour. Counts use tabular numbers; display numbers/dates use Intl formatting.

Uploaded content uses escaped React text. Long filenames, identifiers and prose wrap or scroll inside bounded containers. Large records/evidence lists use content-visibility. Nonessential graph code loads on demand. Fonts ship locally, so the application UI does not need a font CDN.

The mandatory local Web Design Guidelines skill and its [current guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) were read and applied. Browser tests cover keyboard skip link, dialogs, mobile overflow and reduced motion; automated WCAG scans complement source review. These checks do not substitute for a full assistive-technology usability assessment.
