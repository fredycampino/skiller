# Skiller Website

The website lives in `website/` and uses Astro and Starlight. Run website npm commands from that directory. Documentation pages live in `website/src/content/docs/docs/`; documentation screenshots live in `website/public/images/docs/`.

## Start the local server

Requires Node.js 22.12 or newer. Use an installed compatible version through nvm; do not change the user's default Node version.

From the repository root:

```bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 22
cd website
npm run dev -- --host 127.0.0.1
```

Run `npm install` first if dependencies are missing. Astro normally serves at `http://127.0.0.1:4321/`; check its output for the actual port. Verify the server responds before reporting it as running. Use Ctrl+C to stop a foreground server.

Getting started begins at `http://127.0.0.1:4321/docs/getting-started/installation/`.

## Taking screenshots

Read `packages/skiller/docs/dev/taking-textual-screenshots.md` for Textual's screenshot APIs. Generate SVGs from the actual Stui interface; do not hand-edit terminal content to simulate behavior.

### Website dimensions

Match neighboring screenshots before capturing. Most existing documentation screenshots use a 90-column, 34-row terminal and produce an SVG viewBox of approximately `1116 × 880`. Prefer this size for consistency and readable text at the documentation column width. Increase height only when necessary to show the relevant content; avoid empty rows and oversized terminal widths that make the text shrink on the page.

The general development tutorial uses 140 × 42; do not copy those dimensions blindly for website images. Check the final image in the rendered page, including whether the menu is complete and text remains readable.

### Capture the real CLI

From the repository root, in an interactive terminal:

```bash
stty cols 90 rows 34
env -u NO_COLOR \
  TERM=xterm-256color \
  COLORTERM=truecolor \
  TEXTUAL_COLOR_SYSTEM=truecolor \
  TEXTUAL_SCREENSHOT=5 \
  TEXTUAL_SCREENSHOT_FILENAME=first-launch-provider-selection.svg \
  TEXTUAL_SCREENSHOT_LOCATION=website/public/images/docs \
  uv run skiller
```

The screenshot delay is in seconds. Prepare the desired view before it expires. `skiller` normally restores the last session; it does not necessarily show onboarding. Use `/` for autocomplete, `/auth` for providers, and `/runs` for run history.

For first-launch screenshots, use a temporary, isolated HOME and the real Runtime. Do not delete or reset the user's database, sessions, configuration, or credentials. Do not capture API keys or other secrets.

### Capture with Textual Pilot

For repeatable captures, construct the real app using `build_tui_container()` and `ConsoleScreen`, then drive it with `run_test`. Use a temporary HOME for first-launch captures and set it before constructing the container. Wait for the expected screen state, not only a fixed delay; fail if that state never appears.

Inside the capture harness:

```python
async with app.run_test(size=(90, 34)) as pilot:
    await pilot.pause()
    # Wait for the required state or use pilot.press(...) to prepare the view.
    app.save_screenshot(
        filename="first-launch-provider-selection.svg",
        path="website/public/images/docs",
    )
```

Pilot can use the real Runtime; do not describe a mock-backed capture as end-to-end verification. Stop after the required view is ready: provider authentication and model calls are not necessary for a provider-menu screenshot.

Reference images from Markdown using `/images/docs/<filename>.svg` and meaningful alt text.

## Validate changes

With the compatible Node version selected, run from `website/`:

```bash
npm run check
npm run build
npm run check:links
```

Also run `git diff --check` from the repository root. Inspect the modified page in the local server and verify screenshot dimensions, readability, complete content, and asset loading. Keep changes limited to the requested website documentation and assets; do not modify Runtime or Stui just to produce a screenshot.
