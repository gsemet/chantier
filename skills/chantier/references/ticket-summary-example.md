# Ticket summary: a reference

Modelled on a real ticket summary of 2026-11-10; its text is not kept here. The shape and the size
are the point: [chief-of-staff](chief-of-staff.md), "Ticket summary", says how it is made and posted.

## The comment

Thanks for the report. Accepted.

What will be done:
- The editor gets a dark theme, chosen in Settings > Appearance.
- The choice is kept between sessions.
- Code blocks and the schema tree follow the theme.

Left out: a theme per document, and custom colours.

The plan and a mock-up of the result are attached to this issue: <plan link>, <demo link>.
No date yet; the pull request will be linked here.

## The plan (plan.md)

# Dark theme: the plan
- What changes for you: a "Theme" choice (Light, Dark, System) in Settings > Appearance.
- Limits: one theme for the whole app; printing stays light.
- Safety: no data changes; the choice is stored with the other settings.
- Docs: the Settings page gains a "Theme" paragraph.

## The demo (demo.html), its first lines

```html
<!-- Mock-up: imitates the planned result; not the product. -->
<!doctype html>
<html><head><meta charset="utf-8"><title>Dark theme, mock-up</title>
<style>body{background:#1e1f22;color:#e6e6e6;font-family:system-ui}</style></head>
<body><p><em>Mock-up of the planned result, not the product.</em></p>
...
```

## The PR's section

```markdown
## Issues References

Closes #336
```
