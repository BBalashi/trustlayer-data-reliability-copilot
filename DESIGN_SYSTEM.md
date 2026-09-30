# Measured Field

Measured Field is the reusable interface identity used by TrustLayer. It is intended for
analytical tools, dashboards, operational views, and small internal products where clarity
matters more than decoration.

The style is understated, tactile, and precise. Its signature is not a dashboard layout. It is
the combination of warm neutral surfaces, a short teal rule beside major headings, compact
metadata, disciplined spacing, and restrained geometry.

## Principles

1. **Put the work first.** Keep headers compact and bring data or actions into the first screen.
2. **Use hierarchy, not ornament.** Separate content with spacing, thin rules, and small surface
   changes before adding a container.
3. **Keep geometry quiet.** Controls use 4–6px corners; larger panels use 6–8px corners.
4. **Use one signature deliberately.** The short teal heading rule identifies major sections.
   Do not repeat it on every card or control.
5. **State facts plainly.** Labels describe what is shown or what an action does.
6. **Design both themes together.** Light and dark modes use the same hierarchy, not inverted
   afterthoughts.

## Design tokens

The source of truth for the web implementation is `assets/trustlayer.css`. Streamlit's native
widget theme is defined in `.streamlit/config.toml`.

### Colour

| Role | Light | Dark | Use |
|---|---|---|---|
| Canvas | `#F3F0E9` | `#1C1C1A` | Page background |
| Sidebar | `#EAE6DE` | `#20201D` | Navigation rail |
| Surface | `#FBFAF6` | `#262622` | Panels that need a boundary |
| Muted surface | `#ECE8E0` | `#2D2D29` | Expanders and quiet controls |
| Text | `#2A2B28` | `#E9E7E1` | Primary copy and values |
| Muted text | `#686A64` | `#AAA8A1` | Descriptions and metadata |
| Border | `#D5D0C6` | `#3E3E39` | Standard one-pixel rule |
| Strong border | `#BDB8AE` | `#56564F` | Selected or emphasized boundary |
| Teal | `#4F7772` | `#7DA39E` | Signature rule, focus, active state |
| Teal tint | `#DDE8E5` | `#293936` | Selected navigation background |
| Success | `#4C755F` | `#83AA91` | Healthy or passed state |
| Warning | `#8F673B` | `#C39A6B` | Review-needed state |
| Failure | `#9B4F55` | `#CF858A` | Failed or high-severity state |

Use status colour with a written label. Never use colour as the only status cue.

### Spacing

The spacing scale uses a four-pixel base:

| Token | Value |
|---|---:|
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 24px |
| `space-6` | 32px |

Use 16px inside standard panels, 24–32px between sections, and 8–12px between a label and its
related value. Prefer removing a container before reducing its internal spacing.

### Shape and depth

- Small elements: `4px` radius.
- Inputs and buttons: `5px` radius.
- Panels: `8px` radius maximum.
- Standard border: `1px solid` using the border token.
- Emphasized status edge: `3px solid` using the appropriate status token.
- Standard shadow: `0 1px 2px rgba(40, 37, 31, 0.06)`.

Do not use pills for navigation, large rounded cards, gradients, glows, glass effects, background
patterns, or stacked decorative shadows.

## Typography

Use a humanist system stack so the interface remains fast and local:

```css
font-family: "Segoe UI Variable Text", "Aptos", "Segoe UI",
             ui-sans-serif, system-ui, sans-serif;
```

- Page title: 32–42px, weight 700, compact line height.
- Section title: 21–25px, weight 680.
- Panel title: 16px, weight 660.
- Body: 16px.
- Descriptions: 14–15px, muted.
- Metadata: 12–13px, muted label with a slightly stronger value.
- Metrics: use tabular numerals and make only the primary measure oversized.

Sentence case is the default. Avoid all-caps labels and wide letter spacing.

## Signature elements

### Ruled section heading

Major sections begin with a short, three-pixel teal rule beside the heading. The rule is about
28px high and is paired with a direct one-sentence description. Use it once per major section,
not inside panels.

### Compact metadata

Metadata is presented as aligned label/value pairs separated by thin vertical rules on wide
screens. On small screens, pairs stack and the dividers disappear. Good metadata includes run
time, status, mode, owner, environment, or source—not promotional claims.

### Primary measure

Each analytical view may identify one primary measure. Give it a bounded surface and a larger
value. Supporting measures remain on the canvas with thin rules. If every metric is emphasized,
none of them is.

## Components

### Page header

- Left aligned.
- One product or page name.
- One straightforward explanatory sentence.
- Up to three useful metadata pairs.
- A bottom divider, not a surrounding card.

### Sidebar

- Wordmark with a single teal rule.
- Plain navigation rows with a subtle tinted active state and a two-pixel active edge.
- One latest-run reference when useful.
- Resources and secondary actions remain visually quiet.
- Theme choice uses the host application's native control.

### Panels

Use a panel only when content needs a boundary: charts, filter groups, data tables, incident
explanations, or setup instructions. A panel has one-pixel border, eight-pixel radius, 16px
padding, and at most the standard one-pixel shadow.

### Controls

- Minimum target height: 42px.
- Five-pixel radius.
- Clear labels above fields.
- Visible three-pixel focus outline using teal.
- Predictable native behavior takes priority over custom decoration.

### Charts

- Transparent plot and paper backgrounds.
- Use the host theme for text, axes, gridlines, and tooltips.
- Use a restrained teal for the main series and neutral stone for supporting series.
- Status charts use success, warning, and failure colours plus patterns or text labels.
- Include a short written readout and an expandable data table.

### Tables

- Use the native data table theme.
- Five-pixel outer radius and a one-pixel border.
- Prefer readable column names over abbreviations.
- Keep download, search, column, and fullscreen controls available.

### Status and incidents

- Pair the label with a small dot; do not add a decorative badge background by default.
- High-severity incident panels use a three-pixel failure edge.
- Medium-severity incident panels use a three-pixel warning edge.
- Keep “what changed,” “why it matters,” and “recommended action” distinct.

## Writing

- Say what the user can inspect: “Choose a run and status,” not “Focus the evidence.”
- Prefer “Latest run,” “Records in snapshot,” and “Checks evaluated” over branded phrases.
- Keep descriptions to one sentence.
- Use action labels that describe the result: “Refresh data,” “View chart data.”
- Reserve “healthy,” “warning,” and “failed” for actual system states.

## Accessibility and responsive behavior

- Meet WCAG AA contrast for text and controls in both themes.
- Preserve a visible keyboard focus outline.
- Maintain at least 42px interactive targets.
- Pair status colour with text and chart patterns where practical.
- Provide text readouts and table alternatives for charts.
- Respect `prefers-reduced-motion`.
- Support forced-colour mode with solid surfaces and system colours.
- Wrap metadata and columns before text becomes cramped; stack at narrow widths.
- Do not hide Streamlit's sidebar collapse control, menu, dataframe controls, or labels needed by
  assistive technology.

## Streamlit implementation rules

1. Use native widgets for behavior, keyboard support, and AppTest coverage.
2. Give intentional layout containers stable keys such as `tl-panel-quality-table`.
3. Style stable `.st-key-*` hooks and documented `data-testid` attributes only.
4. Do not target generated `.st-emotion-cache-*` classes or positional page children.
5. Keep static CSS in `assets/trustlayer.css`; keep semantic HTML helpers in `src/ui.py`.
6. Define light and dark widget palettes in `.streamlit/config.toml`.
7. Leave Plotly backgrounds transparent and render with `theme="streamlit"`.

## Reuse checklist

For a future project, keep the tokens and rules, then adapt the information architecture:

- Use the warm canvas, surface, border, type, and teal tokens.
- Keep the compact page header and ruled major headings.
- Select one primary measure per view.
- Use plain sidebar navigation.
- Add panels only around content that needs a boundary.
- Keep status text redundant with colour.
- Test light, dark, keyboard focus, and a narrow viewport.

The identity should still be recognizable even when the future product has no dashboard, no
sidebar, and no charts.
