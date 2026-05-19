---
name: NUSConfessIT Dashboard
description: A public dashboard for browsing and exploring the NUSConfessIT Telegram channel.
colors:
  midnight-tutorial: "#003D7C"
  midnight-tutorial-mid: "#00509E"
  hot-take-orange: "#EF7C00"
  page-bg: "#F4F6F9"
  card-bg: "#FFFFFF"
  surface-bg: "#F8F9FB"
  text-primary: "#222222"
  text-secondary: "#666666"
  text-muted: "#999999"
  border-subtle: "#EEEEEE"
  cat-tag-bg: "#E8F0FE"
  rank-gold: "#FFD700"
  rank-silver: "#C0C0C0"
  rank-bronze: "#CD7F32"
typography:
  title:
    fontFamily: "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  section-label:
    fontFamily: "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.05em"
  body:
    fontFamily: "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.05em"
rounded:
  pill: "20px"
  card: "10px"
  element: "8px"
  tag: "10px"
  circle: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "36px"
  container-max: "960px"
components:
  button-primary:
    backgroundColor: "{colors.midnight-tutorial}"
    textColor: "{colors.card-bg}"
    rounded: "{rounded.element}"
    padding: "10px 22px"
  button-primary-hover:
    backgroundColor: "{colors.midnight-tutorial-mid}"
    textColor: "{colors.card-bg}"
    rounded: "{rounded.element}"
    padding: "10px 22px"
  range-tab-active:
    backgroundColor: "{colors.midnight-tutorial}"
    textColor: "{colors.card-bg}"
    rounded: "{rounded.pill}"
    padding: "10px 18px"
  range-tab-default:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.pill}"
    padding: "10px 18px"
  score-tag:
    backgroundColor: "{colors.hot-take-orange}"
    textColor: "{colors.card-bg}"
    rounded: "{rounded.tag}"
    padding: "2px 8px"
  cat-tag:
    backgroundColor: "{colors.cat-tag-bg}"
    textColor: "{colors.midnight-tutorial}"
    rounded: "{rounded.tag}"
    padding: "2px 8px"
---

# Design System: NUSConfessIT Dashboard

## 1. Overview

**Creative North Star: "The Campus Bulletin Board"**

This is not an analytics product. It's a pinboard. The NUSConfessIT Telegram channel is where NUS students say things they can't say anywhere else: confessions about crushes, rants about modules, anxious questions about careers, dark-humoured commentary on campus life. The dashboard's job is to make that archive browsable without flattening it into a data product.

The visual system reflects this. Surfaces are light and open, like blank corkboard. The primary color is institutional but human: a deep navy that every NUS student recognizes from lecture hall seats, at midnight, grinding through tutorials. The accent is orange, the color of a hot take: rare, emphatic, used only where something actually deserves attention. Shadows are near-invisible. The text does the work.

This system explicitly rejects: enterprise dashboard sterility (Metabase, Grafana); social-media analytics optimisation theater (Sprout Social); and the institutional color-by-committee of nus.edu.sg. If it looks like it belongs in a university IT portal, something has gone wrong.

**Key Characteristics:**
- Content-first: confession text is always the largest, most prominent element on screen
- Browse-native: cards are skimmable at speed; every metadata row is compressed to one line
- Controlled color: orange appears in four places only (score tags, section label underlines, active nav indicator, primary button hover)
- Flat surface: depth is tonal (background layers), not shadow-heavy
- Student-scale: max-width 960px; this is a reading interface, not a data warehouse

## 2. Colors: The Midnight Tutorial Palette

Two intentional colors against a neutral field. Everything else is a shade of the wall.

### Primary
- **Midnight Tutorial** (`#003D7C`): The dominant chromatic surface. Nav bar background, page-header gradient, stat values, section heading text, primary buttons, and the active state of all interactive elements. Named for the blue of a lecture hall monitor at 2am.

### Secondary
- **Midnight Tutorial Mid** (`#00509E`): Lighter shift used in gradients (page-header), primary button hover, and bar fill hover states. Never appears on its own as a standalone color.

### Tertiary
- **Hot Take Orange** (`#EF7C00`): The accent. Score tags, section-label underlines, active nav underline, focus ring, score badge backgrounds. Restricted to functional emphasis only. Its rarity is its authority.

### Neutral
- **Page Background** (`#F4F6F9`): The corkboard. Slightly blue-tinted off-white, not pure white. The surface everything sits on.
- **Card Background** (`#FFFFFF`): Cards and confession containers. Clean separation from the page bg.
- **Surface Background** (`#F8F9FB`): Stat card backgrounds and secondary surfaces. One step above card-bg.
- **Text Primary** (`#222222`): Confession text, headings, primary body copy. Near-black, slightly warm.
- **Text Secondary** (`#666666`): Metadata, labels, supporting text.
- **Text Muted** (`#999999`): Timestamps, low-priority counts, disabled labels.
- **Border Subtle** (`#EEEEEE`): Confession card borders, input default stroke, dividers.
- **Category Tag Background** (`#E8F0FE`): Light blue tint for category chips. Keeps the chip family cohesive with the primary without competing.

### Rank Neutrals
- **Rank Gold** (`#FFD700`), **Rank Silver** (`#C0C0C0`), **Rank Bronze** (`#CD7F32`): Used exclusively on the rank badge circles for top-3 posts. Conventional, universally understood. Don't repurpose these for anything else.

### Named Rules

**The Hot Take Rule.** Hot Take Orange appears on at most four elements per screen: score tags, section-label underlines, active nav underline, and focus rings. If a fifth orange element appears, one of the others has to go. Scarcity is the point.

**The Two-Blue Rule.** Midnight Tutorial (`#003D7C`) and its mid-shift (`#00509E`) are the only two blues in this system. If a third blue is needed, revisit the layout instead.

## 3. Typography

**Body Font:** DM Sans (Google Fonts, weights 400/500/600/700/800), with `-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif` as fallback.

**Character:** DM Sans is a geometric humanist: friendlier than Inter, more grounded than Poppins, unpretentious. At 800 weight it reads confident without feeling corporate. That weight range (400 for confessions, 800 for nav brand and stat numbers) is where this typeface earns its place.

### Hierarchy

- **Title** (700, 1.6rem, line-height 1.25): Page-level headings only (the H1 in the gradient page-header). One per page.
- **Section Label** (700, 0.85rem, uppercase, letter-spacing 0.05em): Card section headers, marked with an orange underline. Not headings in the semantic scale; they're labels for content areas.
- **Brand Display** (800, 1rem, letter-spacing -0.02em): Nav brand text only. The highest weight in the system, reserved for the one identifier that never changes.
- **Body** (400, 0.88rem, line-height 1.55): Confession excerpts and post text. DM Sans at this size is comfortable to read at speed, which is how people actually browse this site.
- **Label** (700, 0.72rem, uppercase, letter-spacing 0.05em): Stat card labels ("TOTAL POSTS", "AVG REACTIONS"), tag text, metadata counts. Small and compressed, never used for running text.
- **Stat Value** (800, 1.6rem): The numeric values in the stats section. Heavy enough to read at a glance while scrolling.

### Named Rules

**The Single Family Rule.** DM Sans is the only typeface. No display serifs, no monospace counters, no icon fonts. The weight range (400–800) provides all the hierarchy this system needs.

**The Label Cap Rule.** Uppercase is reserved for two element types: section-label cards headers and stat card labels. Lowercase elsewhere, including buttons, navigation, and tags.

## 4. Elevation

This system is flat by default. Depth is tonal, not shadow-heavy. The three background values (page `#F4F6F9`, card `#FFFFFF`, surface `#F8F9FB`) create a natural layer without shadows. Confession cards have a 1px `#EEEEEE` border at rest, no shadow. A shadow appears only in response to interaction.

### Shadow Vocabulary

- **Ambient card** (`0 1px 4px rgba(0,0,0,0.07)`): Applied to `.card` containers (stat block, chart, posts-of-week wrapper). Barely perceptible; establishes the card as slightly lifted from the page without drama.
- **Hover lift** (`0 2px 10px rgba(0,0,0,0.09)`): Applied to `.confession-card:hover`. The only place shadows meaningfully increase. Signals clickability on the card without requiring a color change.
- **Nav drop** (`0 2px 8px rgba(0,0,0,0.2)`): The sticky navigation shadow. Slightly heavier to reinforce the nav as a fixed layer above scrolling content.

### Named Rules

**The Flat-by-Default Rule.** Surfaces are flat at rest. Shadows appear only in response to state (hover) or to establish a persistent chrome layer (nav). No resting shadow on confession cards, no multi-layer shadow stacks.

## 5. Components

### Buttons

Solid and direct. No outlines, no ghosts. When something is interactive, it looks like a button.

- **Shape:** Gently rounded (8px radius). Rounded enough to feel friendly, square enough to read as a control.
- **Primary** (`#003D7C` background, white text, `10px 22px` padding): Used for the Search button. Full fill, full weight.
- **Hover:** Background shifts to `#00509E`. No scale, no shadow added. Color change only, transition 0.15s ease.
- **Focus:** `outline: 2px solid #EF7C00; outline-offset: 2px` — the orange focus ring. Never `outline: none` without this replacement.

### Range Tabs (filter pills)

- **Active:** `#003D7C` background, white text, 20px radius, `10px 18px` padding. Full pill shape.
- **Default:** transparent background, `#555` text, 1.5px `#ddd` border. Quiet until activated.
- **Hover (default state):** Border shifts to `#003D7C`, text to `#003D7C`. Signals primary activation.
- **Touch target:** minimum 44px height enforced by the 10px top/bottom padding.

### Cards

The primary container. Two variants:

- **Section card** (`.card`): `#FFFFFF` background, 10px radius, ambient shadow (`0 1px 4px rgba(0,0,0,0.07)`), `22px 24px` internal padding. Used for all major content blocks.
- **Stat card** (`.stat`): `#F8F9FB` background, 8px radius, `border-top: 3px solid #003D7C`. No shadow; the top border provides structural emphasis without a side-stripe.

Do not nest cards. Never put a `.card` inside another `.card`.

### Confession Card

The primary reading unit. Every confession is one of these.

- **Shape:** 8px radius, 1px `#EEEEEE` border at rest, `16px` internal padding.
- **Layout:** flex row, rank badge on the left (36px circle), body text on the right.
- **Hover:** Box shadow lifts to `0 2px 10px rgba(0,0,0,0.09)`. Cursor pointer via the wrapping anchor.
- **Body:** title in `#003D7C` 0.92rem 700, excerpt in `#444` 0.88rem 400, metadata row in `#999` 0.75rem with emoji metrics and tags.

### Tags (Chips)

Two variants, both using 10px radius and `2px 8px` padding. Tags are informational, not interactive.

- **Score Tag:** `#EF7C00` background, white text, 700 weight, 0.72rem. The hot-take orange in its most concentrated form. Appears once per confession card.
- **Category Tag:** `#E8F0FE` background (blue tint), `#003D7C` text, 600 weight, uppercase, letter-spacing 0.3px. Quieter than the score tag; provides classification context without competing.

### Inputs / Fields

- **Style:** `1.5px solid #ddd` border, 8px radius, transparent background, `10px 16px` padding.
- **Focus:** Border shifts to `#003D7C`. No glow, no shadow. The color shift is sufficient.
- **Placeholder:** Gray placeholder text. The search field uses a concrete example query as placeholder copy ("Search confessions... e.g. 'relationship', 'CS2030', 'internship'") — functional, not decorative.
- **outline: none** is set but compensated by the border-color focus shift. Always pair `outline: none` with a visible border-state change.

### Navigation

- **Background:** `#003D7C`, sticky at top, `0 2px 8px rgba(0,0,0,0.2)` drop shadow.
- **Brand text:** white, 800 weight, 1rem, letter-spacing -0.3px. "Dashboard" word in Hot Take Orange.
- **Nav links:** `rgba(255,255,255,0.75)` at rest, white on hover and active. 0.88rem, 500 weight, `14px 16px` padding.
- **Active indicator:** `border-bottom: 3px solid #EF7C00`. Orange underline only — no background change, no pill.
- **Mobile:** Nav brand shrinks to 0.88rem at 500px. All links remain visible; no hamburger menu currently implemented.

### Rank Badges

- **Shape:** 36px circle (border-radius: 50%), flex-centered number, 0.9rem 800 weight.
- **Colors:** Gold (`#FFD700`) for rank 1, silver (`#C0C0C0`) for rank 2, bronze (`#CD7F32`) for rank 3, Midnight Tutorial (`#003D7C`) for rank 4+. Text color `#333` on light badges, white on blue.
- **Rule:** Only used on the posts leaderboard. Never repurpose rank colors for other numeric indicators.

## 6. Do's and Don'ts

### Do

- **Do** make confession text the largest, most prominent element on any page. If a UI element is bigger than the post text, it's the wrong size.
- **Do** use Hot Take Orange only for score tags, section-label underlines, the active nav indicator, and focus rings. Four uses maximum.
- **Do** respect WCAG AA: minimum 4.5:1 contrast for body text, 3:1 for large text and UI components.
- **Do** add `aria-label` to all emoji metric spans so screen readers say "29 reactions", not "red heart 29".
- **Do** keep the layout max-width at 960px. This is a reading interface; 1440px full-bleed layouts are wrong for it.
- **Do** use `border-top: 3px solid #003D7C` on stat cards. The top accent is structural emphasis. Side-stripes are prohibited.
- **Do** use DM Sans at 800 weight for the nav brand and stat values. The weight contrast is what makes the hierarchy work.
- **Do** respect `prefers-reduced-motion: reduce`: all transitions disabled, bar-fill animation disabled.
- **Do** keep all touch targets at 44px minimum height on mobile — enforced by the range tabs' `10px 18px` padding rule.

### Don't

- **Don't** make this look like a generic SaaS dashboard (Metabase, Grafana, Datadog). No grey config panels, no sidebar full of chart types, no enterprise data-warehouse density.
- **Don't** make this look like a social media analytics tool (Sprout Social, Hootsuite). No "engagement rate" framing, no growth charts, no conversion language.
- **Don't** make this look like an NUS official website (nus.edu.sg, LumiNUS). Institutional rigidity and committee-approved color schemes are the opposite of what this channel stands for.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on any card, list item, or callout. Rewrite with background tints, full borders, or remove entirely.
- **Don't** use gradient text (`background-clip: text`). Single solid color only; emphasis via weight or size.
- **Don't** introduce a second typeface. DM Sans at 400–800 is the whole system.
- **Don't** add a third blue. If you need more blue, reconsider the layout.
- **Don't** use the hero-metric template: big number center-aligned, small label below, gradient accent behind it. The stats section is below the fold, in a card, subsidiary to the posts feed.
- **Don't** nest cards. A `.card` inside a `.card` is always wrong.
- **Don't** put `outline: none` without a visible replacement focus state. The orange focus ring (`2px solid #EF7C00`) must be present on all interactive elements.
- **Don't** use orange for decorative purposes. If it's not a score tag, a section-label underline, an active state, or a focus ring, it should not be orange.
