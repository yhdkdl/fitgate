# FitGate — Design System

Single source of UI rules.

## Theme

- Dark only (no light theme this version). Modern, calm, high contrast.

## Tokens (CSS variables in the Tailwind theme)

- `--bg`: `#070B14`
- `--surface`: `#0E1626`
- `--surface-2`: `#141F33`
- `--border`: `#1F2C45`
- `--primary`: `#2563EB`
- `--primary-hover`: `#1D4ED8`
- `--ring`: `#60A5FA`
- `--text`: `#F8FAFC`
- `--text-muted`: `#9AA7BD`
- `--success`: `#22C55E`
- `--warning`: `#F59E0B`
- `--danger`: `#EF4444`
- Text on primary is white.

## Typography

- Inter with system-ui fallback; base 16px; headings semibold; no text smaller than 14px.

## Shape and Spacing

- 4px spacing scale, 12px radius on cards and inputs, subtle borders instead of heavy shadows.

## Accessibility

- Contrast at least 4.5:1 for text; visible focus ring; touch targets at least 44px; respect prefers-reduced-motion; no information by color alone.

## Responsive

- Mobile first; usable at 320px with no sideways scroll; sidebar on desktop, bottom navigation on mobile; navigation items come from the role's dashboard config.

## Gym Brand Color

- Gym brand color (`GymConfig.brand_color`) is used only as an accent on that gym's pages (logo area, small highlights); it never replaces background or text colors; if it fails contrast against the surface, fall back to `--primary`.

## Components (`src/components/ui`)

- Components in `src/components/ui`: `Button`, `Input`, `Select`, `Card`, `Alert`, `Badge`, `Table`, `Modal`, `Spinner`, `EmptyState`, `FormField`.
- Every data view has loading, empty and error states; server error messages are shown to the user; forms disable the submit button while sending.
