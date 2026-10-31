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

## Form Validation

One shared validation rule set applies across frontend (`src/utils/validators.ts`) and backend (`apps/core/validators.py`). The server enforces authoritative validation; the frontend provides instant feedback.

| Field Type / Field                                             | Allowed Characters / Format                                                             | Length / Range                                                     | Normalization / Storage                                                                                                              | Error Message                                                          |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **Phone** (`phone`, `contact_phone`, `emergency_contact`)      | Digits, optional leading `+`, spaces, hyphens. Letters blocked on input.                | 9–15 digits total. Ethiopian: 9 digits after +251 (prefix 9 or 7). | Ethiopian numbers (`+2519...`, `09...`, `07...`, `+2517...`, `251...`) normalized to `+251XXXXXXXXX`. International stored in E.164. | "Enter a valid phone number (e.g. +251911223344 or 0911223344)."       |
| **Names** (`full_name`, `gym_name`, `contact_name`)            | Letters of any script (Amharic `\p{L}` included), spaces, `'`, `-`, `.`. No digits.     | 2 to 100 characters (trimmed).                                     | Trimmed, collapse excess whitespace.                                                                                                 | "Name must be 2–100 characters and cannot contain digits or symbols."  |
| **Email** (`email`)                                            | Standard email format (`local@domain`).                                                 | Max 254 characters.                                                | Stored lowercase, trimmed.                                                                                                           | "Enter a valid email address."                                         |
| **Password** (`password`, `new_password`)                      | Live checklist: >=10 chars, not only digits, not common, matches confirmation.          | Min 10 characters.                                                 | Hashed (Argon2 / PBKDF2).                                                                                                            | "Password must meet all checklist requirements."                       |
| **Weight** (`weight_kg`)                                       | Decimal number (max 2 decimals).                                                        | 20.00 to 400.00 kg.                                                | Decimal                                                                                                                              | "Weight must be between 20 and 400 kg."                                |
| **Height** (`height_cm`)                                       | Decimal number (max 2 decimals).                                                        | 50.00 to 260.00 cm.                                                | Decimal                                                                                                                              | "Height must be between 50 and 260 cm."                                |
| **Waist** (`waist_cm`)                                         | Decimal number (max 2 decimals).                                                        | 40.00 to 200.00 cm.                                                | Decimal                                                                                                                              | "Waist circumference must be between 40 and 200 cm."                   |
| **Neck** (`neck_cm`)                                           | Decimal number (max 2 decimals).                                                        | 20.00 to 80.00 cm.                                                 | Decimal                                                                                                                              | "Neck circumference must be between 20 and 80 cm."                     |
| **Hip** (`hip_cm`)                                             | Decimal number (max 2 decimals).                                                        | 40.00 to 220.00 cm.                                                | Decimal                                                                                                                              | "Hip circumference must be between 40 and 220 cm."                     |
| **Chest** (`chest_cm`)                                         | Decimal number (max 2 decimals).                                                        | 50.00 to 200.00 cm.                                                | Decimal                                                                                                                              | "Chest circumference must be between 50 and 200 cm."                   |
| **Bicep** (`bicep_left_cm`, `bicep_right_cm`)                  | Decimal number (max 2 decimals).                                                        | 15.00 to 80.00 cm.                                                 | Decimal                                                                                                                              | "Bicep circumference must be between 15 and 80 cm."                    |
| **Thigh** (`thigh_left_cm`, `thigh_right_cm`)                  | Decimal number (max 2 decimals).                                                        | 30.00 to 120.00 cm.                                                | Decimal                                                                                                                              | "Thigh circumference must be between 30 and 120 cm."                   |
| **Calf** (`calf_left_cm`, `calf_right_cm`)                     | Decimal number (max 2 decimals).                                                        | 20.00 to 80.00 cm.                                                 | Decimal                                                                                                                              | "Calf circumference must be between 20 and 80 cm."                     |
| **Resting Heart Rate** (`resting_heart_rate_bpm`)              | Whole number (integer).                                                                 | 30 to 220 bpm.                                                     | Clamped integer                                                                                                                      | "Resting heart rate must be an integer between 30 and 220 bpm."        |
| **Body Fat %** (`body_fat_percentage`)                         | Decimal number (max 2 decimals).                                                        | 2.00 to 70.00 %.                                                   | Decimal                                                                                                                              | "Body fat percentage must be between 2 and 70%."                       |
| **Payment Amount** (`amount`)                                  | Decimal number (max 2 decimals).                                                        | > 0 to 10,000,000 ETB.                                             | Decimal                                                                                                                              | "Payment amount must be greater than 0 and at most 10,000,000 ETB."    |
| **Page Size** (`page_size`)                                    | Integer                                                                                 | 1 to 100                                                           | Clamped integer                                                                                                                      | "Page size must be between 1 and 100."                                 |
| **Date of Birth** (`date_of_birth`)                            | Valid date (YYYY-MM-DD)                                                                 | Not in future; <= 120 years ago.                                   | ISO Date                                                                                                                             | "Date of birth cannot be in the future or older than 120 years."       |
| **Date Filter Range** (`date_from`, `date_to`)                 | Valid dates (YYYY-MM-DD)                                                                | `date_from` <= `date_to`.                                          | ISO Date                                                                                                                             | "From date cannot be after to date."                                   |
| **Override Reason** (`reason`)                                 | Text                                                                                    | 5 to 500 characters.                                               | Trimmed                                                                                                                              | "Reason must be between 5 and 500 characters."                         |
| **Search Query** (`search`, `q`)                               | Text                                                                                    | Max 100 characters.                                                | Trimmed                                                                                                                              | "Search query cannot exceed 100 characters."                           |
| **Notes / Free Text** (`notes`)                                | Text                                                                                    | Max 1000 characters.                                               | Trimmed                                                                                                                              | "Notes cannot exceed 1000 characters."                                 |
| **Subdomain** (`subdomain`)                                    | DNS label: lowercase alphanumeric and hyphens (`^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`). | 1 to 63 characters.                                                | Lowercase, not reserved.                                                                                                             | "Subdomain must be 1–63 lowercase alphanumeric characters or hyphens." |
| **Brand Color** (`brand_color`)                                | Hex color: `^#[0-9a-fA-F]{6}$`.                                                         | 7 characters (`#RRGGBB`).                                          | Uppercase/lowercase hex.                                                                                                             | "Brand color must be a valid 6-character hex code (e.g. #2563EB)."     |
| **Payment Reference** (`bank_reference`)                       | Alphanumeric, hyphens, slashes.                                                         | 3 to 100 characters.                                               | Trimmed                                                                                                                              | "Payment reference must be 3–100 characters."                          |
| **Manual Code** (`code`, `token`)                              | String                                                                                  | Max 500 characters.                                                | Trimmed                                                                                                                              | "Code cannot exceed 500 characters."                                   |
| **Goal** (`goal`)                                              | Goal selection (`fat_loss`, `muscle_gain`, `strength`, `endurance`, `general_fitness`). | Required.                                                          | Stored lowercase enum                                                                                                                | "Goal is required."                                                    |
| **Fitness Level** (`fitness_level`)                            | Level selection (`beginner`, `intermediate`, `advanced`).                               | Required.                                                          | Stored lowercase enum                                                                                                                | "Fitness level is required."                                           |
| **Training Days** (`training_days_per_week`)                   | Whole number (integer).                                                                 | 2 to 6 days.                                                       | Clamped integer                                                                                                                      | "Training days must be a whole number between 2 and 6."                |
| **Session Length** (`session_length_minutes`)                  | Integer selection (30, 45, 60, 90 minutes).                                             | 30, 45, 60, or 90 minutes.                                         | Integer                                                                                                                              | "Session length must be 30, 45, 60, or 90 minutes."                    |
| **Dietary Notes** (`dietary_notes`)                            | Free text (restrictions, allergies, fasting periods).                                   | Optional, max 1000 characters.                                     | Trimmed                                                                                                                              | "Dietary notes cannot exceed 1000 characters."                         |
| **Weekly Trainer Note** (`trainer_note_for_week`)              | Free text.                                                                              | Optional, max 500 characters.                                      | Trimmed                                                                                                                              | "Trainer note cannot exceed 500 characters."                           |
| **Plan Rejection Reason** (`rejection_reason`)                 | Text.                                                                                   | 5 to 500 characters.                                               | Trimmed                                                                                                                              | "Reason must be between 5 and 500 characters."                         |
| **Weekly Check-in Score** (`energy`, `recovery`, `motivation`) | Whole number (integer).                                                                 | 1 to 5.                                                            | Clamped integer                                                                                                                      | "Score must be an integer between 1 and 5."                            |

### Form Behavior & Accessibility

- **Required fields**: Marked with a visible asterisk `*` and `required` attribute.
- **Messages under the field**: Displayed directly below the field with an alert icon + descriptive text (never color alone).
- **ARIA bindings**: Fields with errors set `aria-invalid="true"` and `aria-describedby="{fieldId}-error"`.
- **Focus on submit**: When form submission fails validation, focus is automatically moved to the first invalid field.
- **Submit button disabled**: Submit buttons show a loading state and are disabled while sending.
- **Server field errors**: Backend validation error payloads are mapped to display directly under the matching form field.
- **Input modes and types**: Use `type="email"`, `inputMode="tel"`, `inputMode="decimal"`, `autoComplete`, and `maxLength`.
