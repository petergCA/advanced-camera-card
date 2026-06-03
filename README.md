# Advanced Camera Card

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

A smart Home Assistant Lovelace camera card that automatically switches between camera feeds based on motion, time windows, entity states, or manual override controls.

This card is designed to wrap `custom:webrtc-camera`, but you can override the child card type per camera if needed.

## Features

- Automatic camera switching based on entity state
- Time-window based camera switching
- Manual override camera buttons
- Optional auto-reset back to Auto mode
- Priority based on camera order in YAML
- Works well with `custom:webrtc-camera`
- HACS-ready repository structure

## Requirements

- Home Assistant
- HACS, optional but recommended
- `custom:webrtc-camera` if you use the default child card type

## Installation with HACS custom repository

1. Push this repository to GitHub as a public repository.
2. In Home Assistant, open HACS.
3. Open the three-dot menu.
4. Choose **Custom repositories**.
5. Add your GitHub repository URL.
6. Select category **Dashboard** or **Lovelace**, depending on your HACS UI wording.
7. Install **Advanced Camera Card**.
8. Reload the browser cache or restart Home Assistant if needed.

HACS should load the card from:

```yaml
url: /hacsfiles/advanced-camera-card/advanced-camera-card.js
type: module
```

If you manage resources manually, add the resource under **Settings > Dashboards > Resources**.

## Manual installation

Copy this file:

```text
dist/advanced-camera-card.js
```

to:

```text
/config/www/advanced-camera-card.js
```

Then add this dashboard resource:

```yaml
url: /local/advanced-camera-card.js?v=0.1.0
type: module
```

## Example

Defaults to the primary camera. Switches to the entry camera while motion is detected, and switches to an alternate camera during a configured time window.

```yaml
type: custom:advanced-camera-card
title: Cameras
default_camera: primary
auto_reset_minutes: 10
show_reason: true
cameras:
  entry:
    name: Entry
    icon: mdi:cctv
    entity: camera.entry
    reason: Entry motion detected
    show_when:
      - entity: binary_sensor.entry_motion
        state: "on"

  alternate:
    name: Alternate
    icon: mdi:cctv
    entity: camera.alternate
    reason: Scheduled camera window
    show_when:
      - type: time
        after: "13:30"
        before: "16:15"

  primary:
    name: Primary
    icon: mdi:video
    entity: camera.primary
```

## Configuration

| Option | Type | Default | Description |
|---|---:|---:|---|
| `title` | string | `Cameras` | Header title. |
| `default_camera` | string | first camera | Camera key used when no rules match. |
| `auto_reset_minutes` | number | `0` | Minutes before manual override resets to Auto. `0` disables reset. |
| `show_reason` | boolean | `true` | Shows the reason under the title. |
| `show_header` | boolean | `true` | Shows or hides the header. |
| `show_controls` | boolean | `true` | Shows or hides the Auto/camera chips. |
| `compact` | boolean | `false` | Slightly tighter padding and grid sizing. |
| `webrtc_defaults` | object | see below | Default options passed to `custom:webrtc-camera`. |
| `cameras` | object | required | Camera definitions keyed by camera id. |

Default `webrtc_defaults`:

```yaml
webrtc_defaults:
  muted: true
  mode: webrtc
  ui: false
  style: ".mode {display: none}"
```

## Camera options

| Option | Type | Description |
|---|---:|---|
| `name` | string | Friendly name shown on the button. |
| `icon` | string | Material Design Icon name. |
| `entity` | string | Camera entity id. |
| `reason` | string | Optional custom reason text when this camera is auto-selected. |
| `show_when` | array | List of conditions. |
| `match` | string | `all` or `any` for multiple `show_when` conditions. Defaults to `all`. |
| `card_type` | string | Child card type. Defaults to `custom:webrtc-camera`. |
| `card_options` | object | Extra options merged into the child card config. |

## Conditions

### Entity equals state

```yaml
show_when:
  - entity: binary_sensor.example_motion
    state: "on"
```

### Entity not in state list

```yaml
show_when:
  - entity: sensor.example_status
    not_state:
      - idle
      - offline
      - unavailable
      - unknown
```

### Numeric threshold

```yaml
show_when:
  - entity: sensor.example_motion_count
    above: 0
```

### Time window

```yaml
show_when:
  - type: time
    after: "13:30"
    before: "16:15"
```

Time windows that cross midnight are supported.

## Development

The HACS distributable file is:

```text
dist/advanced-camera-card.js
```

The editable source copy is:

```text
src/advanced-camera-card.js
```

For this first version, there is no bundler. The build script simply copies `src/advanced-camera-card.js` to `dist/advanced-camera-card.js`.

```bash
npm run build
```

## Releasing

For a clean HACS version number, create a GitHub release. Tags alone are not enough for HACS to use a version number.

Suggested first release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Then create a GitHub release from that tag.

## Notes

Manual override state is stored in the browser/card instance. It does not persist across page refreshes or across devices. A future version could optionally support a Home Assistant `input_select` for shared persistent override state.
