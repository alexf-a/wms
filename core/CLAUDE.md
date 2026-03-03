# Core Django App

## Models

Key models in `core/models.py`:

- **WMSUser** — Custom user model with `has_completed_onboarding` flag
- **Location** — Physical storage location (e.g., garage, closet) with optional address
- **Unit** — A storage container (bin, box, shelf) belonging to a Location, with optional dimensions. Has a unique QR code for direct access.
- **Item** — A stored object inside a Unit, with name, description, quantity, and optional image

Hierarchy: User → Location → Unit → Item (Units can also be standalone or nested via `parent_unit`)

## Views Architecture

- **Page views** — Render Django templates (all extend `base.html`)
- **API views** — JSON endpoints for AJAX operations (prefix: `/api/`), used by client-side JS for CRUD without full page reloads

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/browse/` | GET | Browse locations with unit counts |
| `/api/browse/location/<id>/` | GET | Units within a location |
| `/api/browse/unit/<uid>/<token>/` | GET | Items + child units within a unit |
| `/api/locations/create/` | POST | Create location |
| `/api/locations/<id>/update/` | POST | Update location |
| `/api/locations/<id>/delete/` | POST | Delete location |
| `/api/units/create/` | POST | Create unit |
| `/api/units/<uid>/<token>/update/` | POST | Update unit |
| `/api/units/<uid>/<token>/delete/` | POST | Delete unit |
| `/api/item/<id>/detail/` | GET | Item detail JSON |
| `/api/item/<id>/update/` | POST | Update item |
| `/api/item/<id>/delete/` | POST | Delete item |
| `/api/item/<id>/move/` | POST | Move item to different unit |
| `/api/item/<id>/quantity/` | POST | Update item quantity |
| `/api/extract-item-features/` | POST | AI-powered item feature extraction from image |
| `/api/onboarding/complete/` | POST | Mark onboarding as done |

## UI/UX Design System

### Design Principles

Less content is more. Pursue sleekness and simplicity. Keep button text minimal, prefer icons to text. Mobile-first layout with bottom tab nav (Home/Find/Add/See), card-based content, `max-w-sm` forms, `px-6` page padding.

### Tailwind CSS v4

All templates use Tailwind CSS v4 via standalone CLI. The design system is defined in `core/tailwind/input.css` using `@theme` and CSS custom properties. Dark mode uses `.dark` class on `<html>`.

### Color Tokens

Use semantic tokens (`bg-primary`, `text-muted-foreground`) — never raw color values.

| Token | Usage |
|-------|-------|
| `--background` | Page background (`bg-background`) |
| `--foreground` | Primary text (`text-foreground`) |
| `--primary` (Sage Green) | Buttons, CTAs, active states, focus rings (`bg-primary`) |
| `--accent` (Cool Teal) | Links, badges, secondary actions (`bg-accent`) |
| `--card` | Card backgrounds (`bg-card`) |
| `--muted` | Muted backgrounds (`bg-muted`) |
| `--muted-foreground` | Captions/labels (`text-muted-foreground`) |
| `--border` | Borders (`border-border`) |
| `--destructive` | Delete buttons, error states (`bg-destructive`) |

### Component Patterns

- **Primary buttons:** `bg-primary text-primary-foreground`
- **Ghost buttons:** `hover:bg-accent`
- **Cards:** `bg-card border border-border rounded-lg`
- **Input borders:** `border-input`
- **Focus rings:** `ring-ring`
- **Destructive actions:** `bg-destructive text-destructive-foreground`

### Reusable Partials

- `includes/bottom_nav.html` — Bottom tab nav; pass `active_nav` context variable
- `includes/toast.html` — Toast/snackbar for Django messages
- `includes/dialog_shell.html` — `<dialog>` wrapper with open/close animations

### JS Utilities

- `fetch_utils.js` — `apiFetch(url, options)` with CSRF token injection

### CSS Rules

- **No inline or page-specific styles.** Use Tailwind utility classes.
- Use and extend existing design tokens before adding new ones to `input.css`.
- Custom CSS beyond utilities belongs in `input.css` inside an appropriate `@layer` block.

## QR Code Flow

Each Unit has a unique QR code. Users download/print it and attach it to their physical storage container. Scanning the QR code with a phone:

1. Launches the WMS app
2. Prompts authentication
3. Navigates to the Unit's detail view

## AI-Enabled Workflows

### Item Addition

Users add items by uploading an image. An LLM generates text features (name, description) from the image. The user reviews and edits before confirming. Core logic: `llm/item_generation.py`, LLM call definitions: `core/llm_calls/item_generation.json`.

### Item Search

Users find items via natural language queries (e.g., "where is my red jacket?"). Two-step LLM process:

1. **Candidate search** — Text-based matching against all user items. Returns location if single high-confidence match.
2. **Location search** — Image-aware, resource-intensive disambiguation for ambiguous candidates.

Core logic: `llm/llm_search.py`, LLM call definitions: `core/llm_calls/item_candidates_search.json` and `core/llm_calls/item_location_search.json`.
