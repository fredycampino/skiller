# Taking Textual Screenshots

Textual exports the current terminal UI as an SVG. Use the CLI timer for
screenshots of the real Skiller interface, and `run_test` when the view must be
reproducible.

## Capture the CLI

Run this from the repository root. The terminal size keeps the resulting image
consistent across captures:

```bash
stty cols 140 rows 42
env -u NO_COLOR \
  TERM=xterm-256color \
  COLORTERM=truecolor \
  TEXTUAL_COLOR_SYSTEM=truecolor \
  TEXTUAL_SCREENSHOT=5 \
  TEXTUAL_SCREENSHOT_FILENAME=skiller.svg \
  TEXTUAL_SCREENSHOT_LOCATION=. \
  uv run skiller
```

`TEXTUAL_SCREENSHOT` is the delay in seconds. During that delay, prepare the
view you want to export:

`skiller` opens the last saved session, so its existing content is available
immediately.

- type `/` for command autocomplete;
- open `/runs` for run history;
- open `/auths` for configured providers.

Use `skiller` instead of `uv run skiller` when the command is installed. If the
SVG is monochrome, check that `NO_COLOR` is not set and that the terminal
reports a color-capable `TERM`.

## Capture from a test harness

For a deterministic state, drive the app with Textual's test API and save the
SVG after the UI settles:

```python
async with app.run_test(size=(140, 42)) as pilot:
    await pilot.pause()
    await pilot.press("/")
    await pilot.pause()
    app.save_screenshot(filename="skiller-autocomplete.svg", path=".")
```

`save_screenshot` writes the SVG. `app.export_screenshot()` can be used when
the SVG string is needed in memory instead.

See the [Textual screenshot constants](https://textual.textualize.io/api/constants/)
and [`App.save_screenshot`](https://textual.textualize.io/api/app/#save_screenshot)
for the complete option list.
