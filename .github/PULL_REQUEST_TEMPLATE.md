## What and why

<!-- What does this change, and why? Link the issue it closes. -->

Fixes #

## How I tested it

<!-- Commands you ran and screens you clicked through. -->

- [ ] `pytest` in `backend/` (backend changes)
- [ ] `pytest tests` in `desktop-sync-agent/` (agent changes)
- [ ] `npx tsc --noEmit` and `python3 ../.github/scripts/lint_changed_lines.py upstream/master` in `frontend-nextjs/` (frontend changes)
- [ ] Clicked through the changed screens at phone and desktop widths (UI changes)
- [ ] Tested against a real Tally Prime instance (sync changes, or say below that you couldn't)

## Screenshots

<!-- For UI changes: before and after. Use demo data, never real business data. -->

## Checklist

- [ ] Tests added or updated for backend and agent logic changes
- [ ] Docs updated if setup steps, environment variables or behaviour users see changed
- [ ] No secrets, `.env` files or real company data in the diff
- [ ] Tally XML changes follow the [Tally safety rules](https://github.com/Akashkansal065/tally-portal/blob/master/.agents/rules/tally-safety-rules.md)
