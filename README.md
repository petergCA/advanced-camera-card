# Advanced Camera Card

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

A smart Home Assistant Lovelace camera card that automatically switches between camera feeds based on motion, time windows, entity states, or manual override controls.

This card is designed to wrap `custom:webrtc-camera`, but you can override the child card type per camera if needed.

## Features

- Automatic camera switching based on entity state, numeric threshold, or time window
- Priority-ordered rules — cameras are evaluated top-to-bottom
- Configurable linger delay keeps a triggered camera visible for N seconds after its condition clears
- Manual override with per-camera chip buttons
- Mute / unmute button for the active feed
- Optional auto-reset back to Auto mode after a configurable timeout
- Inline reason text next to the title to save vertical space
- Fine-grained show/hide controls for every header element
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

Copy `advanced-camera-card.js` to:

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

### Card options

| Option | Type | Default | Description |
|---|---|---|---|
| `title` | string | `Cameras` | Header title text. |
| `default_camera` | string | first camera key | Camera shown when no rules match. |
| `auto_reset_minutes` | number | `0` | Minutes before a manual override resets to Auto. `0` disables the timer. |
| `default_linger_seconds` | number | `0` | Seconds any triggered camera stays visible after its `show_when` condition clears. Applied to cameras that do not set their own `linger_seconds`. `0` disables the delay. |
| `compact` | boolean | `false` | Slightly tighter padding and reduced grid row count. |
| `preload_cameras` | boolean | `false` | Load all camera cards at startup in hidden slots so switching is instant. Trades memory for zero-latency camera changes. |
| `card_height` | number | — | Fix the camera host to this height in pixels. Useful when cameras have different aspect ratios and you want a stable layout. |
| `webrtc_defaults` | object | see below | Default options passed to `custom:webrtc-camera` for every camera. |
| `cameras` | object | **required** | Camera definitions keyed by a unique camera id. |

### Visibility options

These can be set independently to show or hide each part of the card.

| Option | Type | Default | Description |
|---|---|---|---|
| `show_header` | boolean | `true` | Show or hide the entire header row (title, reason, and mode pill). |
| `show_title` | boolean | `true` | Show or hide the title text. |
| `show_reason` | boolean | `true` | Show or hide the reason text shown next to the title. |
| `show_mode_pill` | boolean | `true` | Show or hide the Auto / Manual pill. |
| `show_controls` | boolean | `true` | Show or hide the camera chip buttons and mute button. |

### `webrtc_defaults`

Default values applied to every camera unless overridden at the camera level.

```yaml
webrtc_defaults:
  muted: true   # also controls the initial state of the mute button
  mode: webrtc
  ui: false
  style: ".mode {display: none}"
```

## Camera options

| Option | Type | Description |
|---|---|---|
| `name` | string | Friendly name shown on the camera chip button. |
| `icon` | string | Material Design Icon for the chip (e.g. `mdi:cctv`). |
| `entity` | string | Camera entity id. |
| `reason` | string | Custom reason text shown next to the title when this camera is active. |
| `linger_seconds` | number | Seconds this camera stays visible after its `show_when` condition clears. Overrides `default_linger_seconds`. |
| `linger_reason` | string | Reason text shown during the linger delay. Falls back to `reason` if not set. |
| `show_when` | array | List of conditions that trigger this camera. Evaluated top-to-bottom across all cameras. |
| `operator` | string | `and` (default) or `or` — how multiple `show_when` conditions are combined. `match` is accepted as an alias for backward compatibility. |
| `card_type` | string | Child card type. Defaults to `custom:webrtc-camera`. |
| `mode` | string | WebRTC mode for this camera. Overrides `webrtc_defaults.mode`. |
| `ui` | boolean | Show the WebRTC UI for this camera. Overrides `webrtc_defaults.ui`. |
| `style` | string | CSS injected into the WebRTC card for this camera. Overrides `webrtc_defaults.style`. |
| `card_options` | object | Any extra options merged into the child card config. Takes highest precedence. |

## Conditions

### Entity equals state

```yaml
show_when:
  - entity: binary_sensor.example_motion
    state: "on"
```

`state` can also be a list — the condition matches if the entity is in any of the listed states:

```yaml
show_when:
  - entity: alarm_control_panel.home
    state:
      - armed_home
      - armed_away
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

`above` and `below` can be used together for a range. Both are exclusive (`>` / `<`).

### Time window

```yaml
show_when:
  - type: time
    after: "13:30"
    before: "16:15"
```

Time windows that cross midnight are supported (e.g. `after: "22:00"`, `before: "06:00"`).

### Multiple conditions (AND / OR)

Use `operator` at the camera level to control how the conditions in `show_when` are combined.

**OR — show when any condition is true:**

```yaml
cameras:
  porch:
    name: Porch
    icon: mdi:cctv
    entity: camera.porch
    operator: or
    show_when:
      - entity: binary_sensor.doorbell_motion
        state: "on"
      - entity: binary_sensor.porch_person
        state: "on"
```

**AND — show only when all conditions are true (default):**

```yaml
cameras:
  entry:
    name: Entry
    icon: mdi:cctv
    entity: camera.entry
    operator: and   # default, can be omitted
    show_when:
      - entity: binary_sensor.entry_motion
        state: "on"
      - entity: input_boolean.security_armed
        state: "on"
```

### Nested condition groups

For more complex logic, a `show_when` entry can itself be a condition group with its own `operator` and `conditions` list. This lets you mix AND and OR in a single rule.

**Show when security is armed AND (doorbell has motion OR porch has a person):**

```yaml
cameras:
  porch:
    name: Porch
    entity: camera.porch
    operator: and
    show_when:
      - entity: input_boolean.security_armed
        state: "on"
      - operator: or
        conditions:
          - entity: binary_sensor.doorbell_motion
            state: "on"
          - entity: binary_sensor.porch_person
            state: "on"
```

Nesting works to any depth — each group can contain plain conditions or further nested groups.

## Linger delay

By default a camera switches away the moment its `show_when` condition clears. `linger_seconds` holds the feed for that many seconds before reverting to the default camera. If the condition becomes active again before the delay expires the countdown is cancelled and the camera stays live.

Set a per-camera value:

```yaml
cameras:
  entry:
    entity: camera.entry
    linger_seconds: 30
    show_when:
      - entity: binary_sensor.entry_motion
        state: "on"
```

Or set a global default that applies to every camera without its own `linger_seconds`:

```yaml
type: custom:advanced-camera-card
default_linger_seconds: 20
cameras:
  ...
```

`linger_seconds: 0` (or omitting both options) restores the instant-switch behaviour.

The `linger_reason` option customises the status text shown in the header during the delay:

```yaml
entry:
  entity: camera.entry
  linger_seconds: 30
  reason: Entry motion detected
  linger_reason: Entry — motion cleared, holding
```

The linger works with **any** `show_when` condition type — entity state, numeric threshold, or time window. No special entity naming or device class is required.

## Runtime controls

The bottom bar contains two sets of controls.

**Camera chips** (left) — an Auto chip resets to automatic switching; one chip per configured camera selects a manual override. A manual override stays active until the `auto_reset_minutes` timer expires or the user taps Auto.

**Mute button** (right) — toggles audio on the active feed. The initial state comes from `webrtc_defaults.muted` (default `true`). The chosen state persists across camera switches within the same session but resets on page reload.

## Notes

Manual override state is stored in the card instance only. It does not persist across page refreshes or devices. A future version could optionally back this with a Home Assistant `input_select` for shared persistent state.
