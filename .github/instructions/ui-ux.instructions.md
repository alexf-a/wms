---
applyTo: "core/templates/**,core/static/**"
description: "UI/UX Design Guidelines for WMS"
---

# UI/UX Design Guidelines

## Design Principles

Less content is more. Pursue sleekness and simplicity.

- Keep all button text minimal
- Prefer icons to text
- Mobile-first layout: bottom tab nav (Home/Find/Add/See), card-based content, `max-w-sm` forms, `px-6` page padding

## CSS Framework: Tailwind CSS v4

New and migrated templates use **Tailwind CSS v4** with the standalone CLI (no Node.js). The design system is defined entirely in `core/tailwind/input.css` using `@theme` and CSS custom properties.

### Template Structure

- **New pages** extend `core/templates/core/base.html` and use Tailwind utility classes
- **Legacy pages** extend `core/templates/core/base.html` and use Material 3 classes from `styles.css`
- During migration, both base templates coexist. Do not mix them within a single page.

### Color Tokens

All components use semantic tokens (`bg-primary`, `text-muted-foreground`) — never raw color values. Colors are defined as CSS custom properties in `input.css` and swap automatically between light and dark mode via the `.dark` class on `<html>`.

| Token | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| `--background` | `hsl(30 20% 98%)` | `hsl(25 12% 10%)` | Page background (`bg-background`) |
| `--foreground` | `hsl(25 15% 12%)` | `hsl(30 15% 92%)` | Primary text (`text-foreground`) |
| `--primary` | `hsl(143 35% 48%)` | `hsl(143 35% 48%)` | Buttons, CTAs, active states, focus rings (`bg-primary`) |
| `--accent` | `hsl(192 40% 38%)` | `hsl(192 40% 38%)` | Links, badges, secondary actions (`bg-accent`) |
| `--card` | `hsl(30 15% 99%)` | `hsl(25 10% 13%)` | Card backgrounds (`bg-card`) |
| `--muted` | `hsl(30 10% 94%)` | `hsl(25 8% 18%)` | Muted backgrounds (`bg-muted`) |
| `--muted-foreground` | `hsl(25 8% 48%)` | `hsl(30 8% 55%)` | Captions/labels (`text-muted-foreground`) |
| `--border` | `hsl(30 12% 88%)` | `hsl(25 8% 20%)` | Borders (`border-border`) |
| `--destructive` | `hsl(0 72% 51%)` | `hsl(0 62% 40%)` | Delete buttons, error states (`bg-destructive`) |

### Component Patterns

- **Primary buttons**: `bg-primary text-primary-foreground`
- **Ghost buttons**: `hover:bg-accent`
- **Cards**: `bg-card border border-border rounded-lg`
- **Input borders**: `border-input`
- **Focus rings**: `ring-ring`
- **Destructive actions**: `bg-destructive text-destructive-foreground`

### Reusable Partials

- `core/templates/core/includes/bottom_nav.html` — bottom tab nav, pass `active_nav` context variable
- `core/templates/core/includes/toast.html` — toast/snackbar for Django messages
- `core/templates/core/includes/dialog_shell.html` — `<dialog>` wrapper with open/close animations

### JS Utilities

- `core/static/core/js/dialog_manager.js` — `openModal(id)`, `closeDialog(id)`, `openBottomSheet(id)`
- `core/static/core/js/fetch_utils.js` — `apiFetch(url, options)` with CSRF token injection

## CSS Coding Rules

- **DO NOT USE INLINE OR PAGE-SPECIFIC STYLES.** Use Tailwind utility classes for new pages, or `styles.css` for legacy M3 pages.
- Use and extend existing design tokens before adding new ones to `input.css`.
- Custom CSS (beyond Tailwind utilities) belongs in `input.css` inside an appropriate `@layer` block.

## Tailwind Development Workflow

- `make tw-build` — one-shot minified build
- `make tw-watch` — watch mode for development
- `make tw-install` — download the standalone CLI binary (auto-runs on first build)
- The Tailwind CLI auto-detects template and JS files from the project root
