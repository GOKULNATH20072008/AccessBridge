# AccessBridge Web Widget (v2)

Switch access for any web page. A person using a single switch key (Space by
default) can navigate and activate every interactive element, with an
adjustable scan speed and a high-contrast highlight. v1.1 adds a two-switch
**Step** mode, one-press select handling, screen-reader announcements, and a
live status pill.

Vanilla JS, no dependencies, no build step. All logic runs client-side in a
Shadow DOM, so the widget's styles never clash with the host page.

## Quick start

```bash
cd accessbridge/web_widget
python3 -m http.server 8000
```

Open http://localhost:8000/demo/index.html

The demo page embeds the widget with:

```html
<script src="../access-widget.js" async></script>
```

## Features

- **Auto mode** — highlight auto-advances at Slow (1.5 s) / Medium (0.8 s) /
  Fast (0.4 s); the switch key activates the highlighted item.
- **Step mode** (two switches) — Space moves the highlight, Enter activates;
  no timer runs.
- **Selects** open their native dropdown on activation; scanning pauses until
  you pick an option or press Esc.
- **Text fields** enter a paused editing state on activation (switch key is
  released to the field); Esc returns to scanning.
- **Esc** while scanning stops scanning.
- **Screen-reader support** — `aria-live` announcements for start/stop,
  editing, select open, and activations; the target receives real focus with
  the native ring suppressed so only one indicator shows.
- **Status pill** — current mode, speed, and position
  (e.g. `Scanning · medium · 5/24`).
- **Key-mash proof** — presses within 250 ms and OS repeat keys are ignored.
- Settings persist in a cookie (`accessbridge_settings`); a debounced
  `MutationObserver` rebuilds the scan list when the page changes;
  `prefers-reduced-motion` is respected.

## Files

- `access-widget.js` — the entire widget (single file).
- `demo/index.html` — host page used to exercise the widget, with a self-test
  checklist you can tick with the switch alone.
