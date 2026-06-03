class AdvancedCameraCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._manualCamera = null;
    this._manualTimer = null;
    this._activeCameraKey = null;
    this._childCard = null;
    this._lastRenderKey = null;
  }

  setConfig(config) {
    if (!config || !config.cameras || typeof config.cameras !== "object") {
      throw new Error("advanced-camera-card requires a cameras object");
    }

    const cameraKeys = Object.keys(config.cameras);
    if (cameraKeys.length === 0) {
      throw new Error("advanced-camera-card requires at least one camera");
    }

    this._config = {
      title: "Cameras",
      default_camera: cameraKeys[0],
      auto_reset_minutes: 0,
      show_reason: true,
      show_header: true,
      show_controls: true,
      compact: false,
      webrtc_defaults: {
        muted: true,
        mode: "webrtc",
        ui: false,
        style: ".mode {display: none}",
      },
      ...config,
    };

    if (!this._config.cameras[this._config.default_camera]) {
      throw new Error(`default_camera "${this._config.default_camera}" is not defined in cameras`);
    }

    this._renderBase();
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return this._config?.compact ? 3 : 4;
  }

  getGridOptions() {
    return {
      columns: 12,
      min_columns: 6,
      rows: this._config?.compact ? 5 : 6,
      min_rows: 4,
    };
  }

  static getStubConfig() {
    return {
      title: "Smart Cameras",
      default_camera: "main",
      auto_reset_minutes: 10,
      show_reason: true,
      cameras: {
        main: {
          name: "Main",
          icon: "mdi:cctv",
          entity: "camera.example_camera",
        },
      },
    };
  }

  _renderBase() {
    if (!this.shadowRoot) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          overflow: hidden;
          background: var(--ha-card-background, var(--card-background-color));
          border-radius: var(--ha-card-border-radius, 12px);
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 14px 4px;
        }

        .header.hidden {
          display: none;
        }

        .title-wrap {
          min-width: 0;
        }

        .title {
          font-size: 15px;
          font-weight: 600;
          line-height: 1.2;
          color: var(--primary-text-color);
        }

        .reason {
          margin-top: 2px;
          font-size: 12px;
          color: var(--secondary-text-color);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .mode-pill {
          font-size: 11px;
          padding: 4px 8px;
          border-radius: 999px;
          background: rgba(var(--rgb-primary-color), 0.14);
          color: var(--primary-color);
          white-space: nowrap;
        }

        .camera-host {
          padding: 8px 10px 6px;
        }

        .camera-host.compact {
          padding: 6px 8px 4px;
        }

        .chips {
          display: flex;
          gap: 7px;
          padding: 6px 10px 12px;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .chips.hidden {
          display: none;
        }

        .chips::-webkit-scrollbar {
          display: none;
        }

        button.chip {
          border: 0;
          outline: 0;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 7px 10px;
          border-radius: 999px;
          font-size: 12px;
          font-family: inherit;
          color: var(--primary-text-color);
          background: rgba(255, 255, 255, 0.06);
          transition: background 120ms ease, transform 120ms ease;
          white-space: nowrap;
        }

        button.chip:hover {
          background: rgba(var(--rgb-primary-color), 0.16);
        }

        button.chip.active {
          background: rgba(var(--rgb-primary-color), 0.28);
          color: var(--primary-text-color);
        }

        button.chip ha-icon {
          --mdc-icon-size: 17px;
        }

        .empty {
          padding: 16px;
          color: var(--secondary-text-color);
          font-size: 13px;
        }
      </style>

      <ha-card>
        <div class="header">
          <div class="title-wrap">
            <div class="title"></div>
            <div class="reason"></div>
          </div>
          <div class="mode-pill"></div>
        </div>
        <div class="camera-host"></div>
        <div class="chips"></div>
      </ha-card>
    `;
  }

  async _update() {
    if (!this._config || !this._hass || !this.shadowRoot) return;

    const decision = this._chooseCamera();
    const activeKey = decision.key;
    const activeCamera = this._config.cameras[activeKey];

    if (!activeCamera) {
      this._showEmpty(`Camera "${activeKey}" not found`);
      return;
    }

    const header = this.shadowRoot.querySelector(".header");
    header.classList.toggle("hidden", this._config.show_header === false);

    this.shadowRoot.querySelector(".title").textContent = this._config.title || "Cameras";

    const reasonEl = this.shadowRoot.querySelector(".reason");
    if (this._config.show_reason === false) {
      reasonEl.style.display = "none";
    } else {
      reasonEl.style.display = "";
      reasonEl.textContent = decision.reason;
    }

    this.shadowRoot.querySelector(".mode-pill").textContent = this._manualCamera ? "Manual" : "Auto";
    this.shadowRoot.querySelector(".camera-host").classList.toggle("compact", !!this._config.compact);
    this.shadowRoot.querySelector(".chips").classList.toggle("hidden", this._config.show_controls === false);

    await this._renderCamera(activeKey, activeCamera);
    this._renderChips(activeKey);
  }

  _chooseCamera() {
    if (this._manualCamera && this._config.cameras[this._manualCamera]) {
      const cam = this._config.cameras[this._manualCamera];
      return {
        key: this._manualCamera,
        reason: `Showing ${cam.name || this._manualCamera} manually`,
      };
    }

    for (const [key, camera] of Object.entries(this._config.cameras)) {
      if (!Array.isArray(camera.show_when) || camera.show_when.length === 0) continue;

      const matchMode = camera.match || "all";
      const matched = matchMode === "any"
        ? camera.show_when.some((condition) => this._conditionMatches(condition))
        : camera.show_when.every((condition) => this._conditionMatches(condition));

      if (matched) {
        return {
          key,
          reason: camera.reason || this._reasonFor(camera, key),
        };
      }
    }

    return {
      key: this._config.default_camera,
      reason: "Default view",
    };
  }

  _conditionMatches(condition) {
    if (!condition) return false;

    if (condition.type === "time") {
      return this._timeMatches(condition);
    }

    const entityId = condition.entity;
    if (!entityId) return false;

    const entity = this._hass.states[entityId];
    if (!entity) return false;

    const current = String(entity.state);

    if (condition.state !== undefined) {
      const allowed = Array.isArray(condition.state) ? condition.state.map(String) : [String(condition.state)];
      return allowed.includes(current);
    }

    if (condition.not_state !== undefined) {
      const blocked = Array.isArray(condition.not_state) ? condition.not_state.map(String) : [String(condition.not_state)];
      return !blocked.includes(current);
    }

    if (condition.above !== undefined || condition.below !== undefined) {
      const numeric = Number(current);
      if (Number.isNaN(numeric)) return false;
      if (condition.above !== undefined && !(numeric > Number(condition.above))) return false;
      if (condition.below !== undefined && !(numeric < Number(condition.below))) return false;
      return true;
    }

    return false;
  }

  _timeMatches(condition) {
    const now = new Date();
    const after = this._parseTime(condition.after);
    const before = this._parseTime(condition.before);
    if (!after || !before) return false;

    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    const afterMinutes = after.hours * 60 + after.minutes;
    const beforeMinutes = before.hours * 60 + before.minutes;

    if (afterMinutes <= beforeMinutes) {
      return currentMinutes >= afterMinutes && currentMinutes < beforeMinutes;
    }

    return currentMinutes >= afterMinutes || currentMinutes < beforeMinutes;
  }

  _parseTime(value) {
    if (!value || typeof value !== "string") return null;
    const [h, m] = value.split(":").map(Number);
    if (Number.isNaN(h) || Number.isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) return null;
    return { hours: h, minutes: m };
  }

  _reasonFor(camera, key) {
    const condition = camera.show_when?.[0];
    if (!condition) return `Showing ${camera.name || key}`;
    if (condition.type === "time") return `Scheduled view ${condition.after}-${condition.before}`;
    if (condition.entity && condition.state !== undefined) return `${condition.entity} is ${Array.isArray(condition.state) ? condition.state.join(" or ") : condition.state}`;
    if (condition.entity && condition.not_state !== undefined) return `${condition.entity} is active`;
    if (condition.entity && (condition.above !== undefined || condition.below !== undefined)) return `${condition.entity} matched threshold`;
    return `Showing ${camera.name || key}`;
  }

  async _renderCamera(activeKey, camera) {
    if (this._activeCameraKey === activeKey && this._childCard) {
      this._childCard.hass = this._hass;
      return;
    }

    this._activeCameraKey = activeKey;
    const host = this.shadowRoot.querySelector(".camera-host");
    host.innerHTML = "";

    const defaults = this._config.webrtc_defaults || {};
    const cardConfig = {
      type: camera.card_type || "custom:webrtc-camera",
      entity: camera.entity,
      muted: camera.muted ?? defaults.muted ?? true,
      mode: camera.mode || defaults.mode || "webrtc",
      ui: camera.ui ?? defaults.ui ?? false,
      style: camera.style || defaults.style || ".mode {display: none}",
      ...(camera.card_options || {}),
    };

    try {
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement(cardConfig);
      card.hass = this._hass;
      this._childCard = card;
      host.appendChild(card);
    } catch (err) {
      this._showEmpty(`Could not load camera card: ${err.message}`);
    }
  }

  _renderChips(activeKey) {
    const chips = this.shadowRoot.querySelector(".chips");
    if (!chips || this._config.show_controls === false) return;

    const renderKey = JSON.stringify({ activeKey, manual: this._manualCamera, cameras: Object.keys(this._config.cameras) });
    if (renderKey === this._lastRenderKey) return;
    this._lastRenderKey = renderKey;

    chips.innerHTML = "";
    chips.appendChild(this._makeChip({
      name: "Auto",
      icon: "mdi:auto-mode",
      active: !this._manualCamera,
      onClick: () => this._clearManualCamera(),
    }));

    for (const [key, camera] of Object.entries(this._config.cameras)) {
      chips.appendChild(this._makeChip({
        name: camera.name || key,
        icon: camera.icon || "mdi:cctv",
        active: this._manualCamera ? this._manualCamera === key : activeKey === key,
        onClick: () => this._setManualCamera(key),
      }));
    }
  }

  _makeChip({ name, icon, active, onClick }) {
    const button = document.createElement("button");
    button.className = `chip ${active ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `<ha-icon icon="${icon}"></ha-icon><span>${name}</span>`;
    button.addEventListener("click", onClick);
    return button;
  }

  _setManualCamera(key) {
    this._manualCamera = key;
    this._lastRenderKey = null;

    if (this._manualTimer) clearTimeout(this._manualTimer);
    this._manualTimer = null;

    const minutes = Number(this._config.auto_reset_minutes || 0);
    if (minutes > 0) {
      this._manualTimer = setTimeout(() => this._clearManualCamera(), minutes * 60 * 1000);
    }

    this._update();
  }

  _clearManualCamera() {
    this._manualCamera = null;
    this._lastRenderKey = null;
    if (this._manualTimer) clearTimeout(this._manualTimer);
    this._manualTimer = null;
    this._update();
  }

  _showEmpty(message) {
    const host = this.shadowRoot?.querySelector(".camera-host");
    if (host) host.innerHTML = `<div class="empty">${message}</div>`;
  }
}

if (!customElements.get("advanced-camera-card")) {
  customElements.define("advanced-camera-card", AdvancedCameraCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "advanced-camera-card",
  name: "Advanced Camera Card",
  preview: false,
  description: "Smart camera switching card with manual override controls",
  documentationURL: "https://github.com/YOUR_GITHUB_USERNAME/advanced-camera-card",
});
