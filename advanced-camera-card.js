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
    this._renderingKey = null;
    this._muted = true;
    this._cameraCards = {};
    this._preloadStarted = false;
    this._lingerTimer = null;
    this._lingerCameraKey = null;
    this._lingerDone = new Set();
    this._lastOverlayKey = null;
    this._templateSubs = {};
    this._templateValues = {};
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
      show_title: true,
      show_mode_pill: true,
      show_controls: true,
      compact: false,
      preload_cameras: false,
      card_height: null,
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

    this._muted = this._config.webrtc_defaults?.muted ?? true;
    this._cameraCards = {};
    this._preloadStarted = false;
    this._clearTemplateSubs();
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
          display: flex;
          align-items: baseline;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;
        }

        .title {
          font-size: 15px;
          font-weight: 600;
          line-height: 1.2;
          color: var(--primary-text-color);
          white-space: nowrap;
        }

        .reason {
          font-size: 12px;
          color: var(--secondary-text-color);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          flex: 1;
          min-width: 0;
        }

        .mode-pill {
          font-size: 11px;
          padding: 4px 8px;
          border-radius: 999px;
          background: rgba(var(--rgb-primary-color), 0.14);
          color: var(--primary-color);
          white-space: nowrap;
        }

        .camera-wrap {
          position: relative;
          padding: 8px 10px 6px;
          overflow: hidden;
        }

        .camera-wrap.compact {
          padding: 6px 8px 4px;
        }

        .camera-host {
          overflow: hidden;
          height: 100%;
        }

        .camera-host > *,
        .camera-host > * > * {
          display: block;
          height: 100%;
        }

        .overlays-host {
          position: absolute;
          inset: 0;
          pointer-events: none;
          overflow: hidden;
        }

        .entity-overlay {
          position: absolute;
          transform: translate(-50%, -50%);
          background: rgba(0, 0, 0, 0.55);
          color: #fff;
          padding: 4px 8px;
          border-radius: 6px;
          line-height: 1.4;
          white-space: nowrap;
          text-align: center;
        }

        .overlay-name {
          display: inline;
          font-size: inherit;
          color: #fff;
        }

        .overlay-value {
          display: inline;
          font-size: inherit;
          color: #fff;
        }

        .controls-bar {
          display: flex;
          align-items: center;
        }

        .controls-bar.hidden {
          display: none;
        }

        .chips {
          flex: 1;
          min-width: 0;
          display: flex;
          gap: 7px;
          padding: 6px 10px 12px;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .chips::-webkit-scrollbar {
          display: none;
        }

        .mute-wrap {
          flex-shrink: 0;
          padding: 6px 10px 12px;
          padding-left: 0;
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
        <div class="camera-wrap">
          <div class="camera-host"></div>
          <div class="overlays-host"></div>
        </div>
        <div class="controls-bar">
          <div class="chips"></div>
          <div class="mute-wrap">
            <button class="chip mute-btn" type="button" aria-label="Toggle mute">
              <ha-icon icon="mdi:volume-off"></ha-icon>
            </button>
          </div>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector(".mute-btn").addEventListener("click", () => this._toggleMute());
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

    const titleEl = this.shadowRoot.querySelector(".title");
    titleEl.textContent = this._config.title || "Cameras";
    titleEl.style.display = this._config.show_title === false ? "none" : "";

    const reasonEl = this.shadowRoot.querySelector(".reason");
    if (this._config.show_reason === false) {
      reasonEl.style.display = "none";
    } else {
      reasonEl.style.display = "";
      reasonEl.textContent = decision.reason;
    }

    const modePill = this.shadowRoot.querySelector(".mode-pill");
    modePill.textContent = this._manualCamera ? "Manual" : "Auto";
    modePill.style.display = this._config.show_mode_pill === false ? "none" : "";
    const cameraWrap = this.shadowRoot.querySelector(".camera-wrap");
    cameraWrap.classList.toggle("compact", !!this._config.compact);
    cameraWrap.style.height = this._config.card_height ? `${this._config.card_height}px` : "";
    this.shadowRoot.querySelector(".controls-bar").classList.toggle("hidden", this._config.show_controls === false);

    await this._renderCamera(activeKey, activeCamera);
    this._renderOverlays(activeCamera);
    this._renderChips(activeKey);
    this._updateMuteButton();
  }

  _clearLinger() {
    if (this._lingerTimer) clearTimeout(this._lingerTimer);
    this._lingerTimer = null;
    this._lingerCameraKey = null;
  }

  _isEntityCondition(condition) {
    if (!condition) return false;
    if (Array.isArray(condition.conditions)) {
      return condition.conditions.some((c) => this._isEntityCondition(c));
    }
    return condition.type !== "time" && !!condition.entity;
  }

  _chooseCamera() {
    if (this._manualCamera && this._config.cameras[this._manualCamera]) {
      const cam = this._config.cameras[this._manualCamera];
      return {
        key: this._manualCamera,
        reason: `Showing ${cam.name || this._manualCamera} manually`,
      };
    }

    // Two-pass evaluation: entity/state conditions take priority over time conditions.
    // Pass 1: cameras with at least one entity-based condition.
    // Pass 2: cameras with only time-based conditions.
    for (const pass of ["entity", "time"]) {
      for (const [key, camera] of Object.entries(this._config.cameras)) {
        if (!Array.isArray(camera.show_when) || camera.show_when.length === 0) continue;

        const hasEntity = camera.show_when.some((c) => this._isEntityCondition(c));
        if (pass === "entity" && !hasEntity) continue;
        if (pass === "time" && hasEntity) continue;

        const matchMode = camera.operator || camera.match || "all";
        const isOr = matchMode === "any" || matchMode === "or";
        const matched = isOr
          ? camera.show_when.some((condition) => this._conditionMatches(condition))
          : camera.show_when.every((condition) => this._conditionMatches(condition));

        if (matched) {
          if (this._lingerCameraKey && this._lingerCameraKey !== key) {
            this._clearLinger();
          }
          this._lingerDone.delete(key);
          return {
            key,
            reason: camera.reason || this._reasonFor(camera, key),
          };
        }
      }
    }

    // No condition matched — hold the current camera if a linger is running
    if (this._lingerTimer && this._lingerCameraKey) {
      const cam = this._config.cameras[this._lingerCameraKey];
      if (cam) {
        return {
          key: this._lingerCameraKey,
          reason: cam.linger_reason || cam.reason || this._reasonFor(cam, this._lingerCameraKey),
        };
      }
    }

    // Start a linger if the camera we're leaving had linger_seconds configured
    const prevKey = this._activeCameraKey;
    if (
      prevKey &&
      prevKey !== this._config.default_camera &&
      !this._lingerTimer &&
      !this._lingerDone.has(prevKey)
    ) {
      const prevCam = this._config.cameras[prevKey];
      const secs = Number(prevCam?.linger_seconds ?? this._config.default_linger_seconds ?? 0);
      if (secs > 0) {
        this._lingerCameraKey = prevKey;
        this._lingerTimer = setTimeout(() => {
          this._lingerDone.add(prevKey);
          this._clearLinger();
          this._update();
        }, secs * 1000);
        return {
          key: prevKey,
          reason: prevCam.linger_reason || prevCam.reason || this._reasonFor(prevCam, prevKey),
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

    // Nested group: { operator: "or"/"and", conditions: [...] }
    if (Array.isArray(condition.conditions)) {
      const op = condition.operator || "and";
      const isOr = op === "or" || op === "any";
      return isOr
        ? condition.conditions.some((c) => this._conditionMatches(c))
        : condition.conditions.every((c) => this._conditionMatches(c));
    }

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
    if (this._config.preload_cameras) {
      return this._renderCameraPreloaded(activeKey);
    }

    if (this._activeCameraKey === activeKey && this._childCard) {
      this._childCard.hass = this._hass;
      return;
    }

    // Guard against concurrent renders for the same key while awaiting card helpers
    if (this._renderingKey === activeKey) return;
    this._renderingKey = activeKey;

    this._activeCameraKey = activeKey;
    this._childCard = null;
    const host = this.shadowRoot.querySelector(".camera-host");
    host.innerHTML = "";

    const defaults = this._config.webrtc_defaults || {};
    const baseStyle = camera.style || defaults.style || ".mode {display: none}";
    const fitStyle = !camera.style && this._config.card_height
      ? " video { height: 100%; max-height: 100%; width: 100%; object-fit: contain; }"
      : "";
    const cardConfig = {
      type: camera.card_type || "custom:webrtc-camera",
      entity: camera.entity,
      muted: this._muted,
      mode: camera.mode || defaults.mode || "webrtc",
      ui: camera.ui ?? defaults.ui ?? false,
      style: baseStyle + fitStyle,
      ...(camera.card_options || {}),
    };

    try {
      const helpers = await window.loadCardHelpers();
      if (this._renderingKey !== activeKey) return;
      const card = await helpers.createCardElement(cardConfig);
      if (this._renderingKey !== activeKey) return;
      card.hass = this._hass;
      this._childCard = card;
      host.appendChild(card);
    } catch (err) {
      this._showEmpty(`Could not load camera card: ${err.message}`);
    } finally {
      if (this._renderingKey === activeKey) this._renderingKey = null;
    }
  }

  _renderCameraPreloaded(activeKey) {
    // Pass hass updates to all already-loaded background cards
    for (const card of Object.values(this._cameraCards)) {
      card.hass = this._hass;
    }

    // No switch needed if already on this camera
    if (this._activeCameraKey === activeKey && this._childCard) return;

    // First call: create a hidden slot per camera and kick off async loading
    if (!this._preloadStarted) {
      this._preloadStarted = true;
      const host = this.shadowRoot.querySelector(".camera-host");
      host.innerHTML = "";
      for (const key of Object.keys(this._config.cameras)) {
        const slot = document.createElement("div");
        slot.dataset.cameraKey = key;
        slot.style.display = "none";
        host.appendChild(slot);
      }
      this._loadAllCameraCards();
    }

    // Show the active slot, hide the rest
    const host = this.shadowRoot.querySelector(".camera-host");
    host.querySelectorAll("[data-camera-key]").forEach(slot => {
      slot.style.display = slot.dataset.cameraKey === activeKey ? "" : "none";
    });

    this._activeCameraKey = activeKey;
    this._childCard = this._cameraCards[activeKey] || null;

    // Sync current mute state to the newly visible camera
    if (this._childCard) {
      const video = this._childCard.querySelector("video") ||
                    this._childCard.shadowRoot?.querySelector("video");
      if (video) video.muted = this._muted;
    }
  }

  async _loadAllCameraCards() {
    const defaults = this._config.webrtc_defaults || {};
    const host = this.shadowRoot?.querySelector(".camera-host");
    if (!host) return;

    try {
      const helpers = await window.loadCardHelpers();
      for (const [key, camera] of Object.entries(this._config.cameras)) {
        if (this._cameraCards[key]) continue;
        const slot = host.querySelector(`[data-camera-key="${key}"]`);
        if (!slot) continue;

        const baseStyle = camera.style || defaults.style || ".mode {display: none}";
        const fitStyle = !camera.style && this._config.card_height
          ? " video { height: 100%; max-height: 100%; width: 100%; object-fit: contain; }"
          : "";
        const cardConfig = {
          type: camera.card_type || "custom:webrtc-camera",
          entity: camera.entity,
          muted: this._muted,
          mode: camera.mode || defaults.mode || "webrtc",
          ui: camera.ui ?? defaults.ui ?? false,
          style: baseStyle + fitStyle,
          ...(camera.card_options || {}),
        };

        try {
          const card = await helpers.createCardElement(cardConfig);
          card.hass = this._hass;
          this._cameraCards[key] = card;
          slot.appendChild(card);

          // If this camera just finished loading and it's already the active one, wire it up
          if (key === this._activeCameraKey) {
            this._childCard = card;
            const video = card.querySelector("video") || card.shadowRoot?.querySelector("video");
            if (video) video.muted = this._muted;
          }
        } catch (err) {
          console.warn(`advanced-camera-card: failed to preload camera "${key}":`, err);
        }
      }
    } catch (err) {
      console.warn("advanced-camera-card: preload init failed:", err);
    }
  }

  _renderOverlays(camera) {
    const host = this.shadowRoot?.querySelector(".overlays-host");
    if (!host) return;

    const overlays = camera?.overlays;
    if (!Array.isArray(overlays) || overlays.length === 0) {
      if (host.childElementCount > 0) host.innerHTML = "";
      this._lastOverlayKey = null;
      return;
    }

    const displayValues = overlays.map((o) => {
      if (o.template) {
        if (o.template.includes("{%") || o.template.includes("{{")) {
          this._subscribeJinjaTemplate(o.template);
          return this._templateValues[o.template] ?? "";
        }
        return this._resolveTemplate(o.template);
      }
      if (!o.entity) return "";
      const es = this._hass?.states[o.entity];
      if (!es) return "";
      const raw = o.attribute != null ? (es.attributes[o.attribute] ?? es.state) : es.state;
      return this._formatOverlayValue(raw, o.format);
    });

    const renderKey = JSON.stringify({ overlays, displayValues });
    if (renderKey === this._lastOverlayKey) return;
    this._lastOverlayKey = renderKey;

    host.innerHTML = "";
    for (let i = 0; i < overlays.length; i++) {
      const overlay = overlays[i];
      if (!overlay.entity && !overlay.name && !overlay.template) continue;

      const value = displayValues[i];

      const x = typeof overlay.x === "number" ? overlay.x : 50;
      const y = typeof overlay.y === "number" ? overlay.y : 50;
      const size = typeof overlay.size === "number" ? overlay.size : 14;

      const el = document.createElement("div");
      el.className = "entity-overlay";
      el.style.left = `${x}%`;
      el.style.top = `${y}%`;
      el.style.fontSize = `${size}px`;

      const display = overlay.display || (overlay.name ? "name_state" : "state");

      if (overlay.name && (display === "name_state" || display === "name")) {
        const nameEl = document.createElement("span");
        nameEl.className = "overlay-name";
        nameEl.textContent = overlay.name;
        if (overlay.name_size) nameEl.style.fontSize = `${overlay.name_size}px`;
        el.appendChild(nameEl);
      }

      if (display === "name_state" && overlay.name) {
        el.appendChild(document.createTextNode(" "));
      }

      if (display === "name_state" || display === "state") {
        const valueEl = document.createElement("span");
        valueEl.className = "overlay-value";
        valueEl.textContent = value;
        if (overlay.state_size) valueEl.style.fontSize = `${overlay.state_size}px`;
        el.appendChild(valueEl);
      }

      host.appendChild(el);
    }
  }

  _subscribeJinjaTemplate(template) {
    if (template in this._templateSubs) return;
    if (!this._hass?.connection) return;
    this._templateSubs[template] = null;
    this._hass.connection.subscribeMessage(
      (msg) => {
        const val = (msg.result ?? "").toString().trim();
        if (this._templateValues[template] === val) return;
        this._templateValues[template] = val;
        this._lastOverlayKey = null;
        const activeCamera = this._config?.cameras[this._activeCameraKey];
        if (activeCamera) this._renderOverlays(activeCamera);
      },
      { type: "render_template", template }
    ).then((unsub) => {
      this._templateSubs[template] = unsub;
    }).catch(() => {
      delete this._templateSubs[template];
    });
  }

  _clearTemplateSubs() {
    for (const unsub of Object.values(this._templateSubs)) {
      if (typeof unsub === "function") unsub();
    }
    this._templateSubs = {};
    this._templateValues = {};
  }

  disconnectedCallback() {
    this._clearTemplateSubs();
  }

  _resolveTemplate(template) {
    if (!template) return "";
    return template.replace(/\{\{\s*(.*?)\s*\}\}/g, (match, expr) => {
      expr = expr.trim();
      const statesMatch = expr.match(/^states\(\s*['"]([^'"]+)['"]\s*\)$/);
      if (statesMatch) return this._hass?.states[statesMatch[1]]?.state ?? "";
      const attrMatch = expr.match(/^state_attr\(\s*['"]([^'"]+)['"],\s*['"]([^'"]+)['"]\s*\)$/);
      if (attrMatch) return this._hass?.states[attrMatch[1]]?.attributes[attrMatch[2]] ?? "";
      return match;
    });
  }

  _formatOverlayValue(value, format) {
    if (!format || value === "" || value == null) return value;
    const num = Number(value);
    if (Number.isNaN(num)) return value;
    let totalMinutes;
    if (format === "duration_minutes") totalMinutes = Math.round(num);
    else if (format === "duration_seconds") totalMinutes = Math.round(num / 60);
    else return value;
    if (totalMinutes <= 0) return "0m";
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    if (h > 0 && m > 0) return `${h}h ${m}m`;
    if (h > 0) return `${h}h`;
    return `${m}m`;
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
        active: !!this._manualCamera && this._manualCamera === key,
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

  _updateMuteButton() {
    const btn = this.shadowRoot?.querySelector(".mute-btn");
    if (!btn) return;
    btn.querySelector("ha-icon")?.setAttribute("icon", this._muted ? "mdi:volume-off" : "mdi:volume-high");
    btn.classList.toggle("active", !this._muted);
  }

  _toggleMute() {
    this._muted = !this._muted;
    const video = this._getVideoElement();
    if (video) video.muted = this._muted;
    this._updateMuteButton();
  }

  _getVideoElement() {
    if (!this._childCard) return null;
    let video = this._childCard.querySelector("video");
    if (video) return video;
    if (this._childCard.shadowRoot) {
      video = this._childCard.shadowRoot.querySelector("video");
      if (video) return video;
    }
    return null;
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
  documentationURL: "https://github.com/petergCA/advanced-camera-card",
});
