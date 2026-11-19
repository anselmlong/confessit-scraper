## Design Context

### Users
NUS students browsing anonymously submitted confessions — on their phone between classes, late at night in their hall room, or slouched in a kopitiam. Also the creator, using it as a personal data tool to explore sentiment trends and channel analytics. Both audiences want to find interesting content fast; neither wants friction.

### Brand Personality
Campus-casual and honest, presented like a well-made modern product. The voice stays student-built (plain, a little irreverent); the interface is clean and calm so the confessions carry the personality.

### Aesthetic Direction
**Clean modern product** (chosen Nov 2026, replacing the earlier dark zine look). Bar: Linear / Vercel dashboard craft.

- Neutral zinc surfaces, one indigo accent (`--blue` token, kept for historical reasons). Accent marks links, data and focus; active controls invert to ink (`--ink` / `--on-ink`) rather than turning purple.
- Light and dark are both first-class; default follows the system.
- Geist for UI and headings, Geist Mono for numerals and axis labels.
- One container: `.panel` (hairline border, 14px radius, near-invisible shadow). No nested cards, no uppercase tracked kickers.
- Icons are inline SVG (`components/Icons.tsx`), not emoji.
- Charts are hand-drawn SVG in `components/charts/`, single hue, hover + table view, no chart library.

**No NUS blue/orange.**

### Design Principles
1. **Text is the hero**: confession excerpts dominate; metadata is secondary.
2. **Compression over decoration**: every element removed is a confession better read.
3. **Honest data**: state time zones, flag partial/provisional periods, never imply precision the data lacks.
4. **Ruthless hierarchy**: one primary signal per card (the confession), one secondary (engagement), everything else tertiary.
