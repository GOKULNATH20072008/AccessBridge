(function () {
  'use strict';

  var SPEEDS = { slow: 1500, medium: 800, fast: 400 };
  var COOLDOWN_MS = 250;
  var MUTATION_DEBOUNCE_MS = 150;
  var COOKIE_NAME = 'accessbridge_settings';
  var SELECT_WATCHDOG_MS = 8000;

  var SELECTOR = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    '[tabindex]:not([tabindex="-1"])',
    '[contenteditable]',
    '[role="button"]',
    '[role="textbox"]',
    '[role="combobox"]',
    '[role="searchbox"]',
    '[role="spinbutton"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '[role="switch"]',
    '[role="slider"]',
    '[role="tab"]'
  ].join(',');

  var CSS = [
    ':host { all: initial; }',
    '.ab-fab { position: fixed; top: 14px; right: 14px; z-index: 2147483647; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }',
    '.ab-actions { display: flex; gap: 8px; }',
    '.ab-toggle, .ab-gear { font-family: inherit; font-size: 15px; font-weight: 700; line-height: 1; padding: 12px 16px; border: 2px solid #000; border-radius: 6px; background: #111827; color: #fff; cursor: pointer; box-shadow: 0 4px 14px rgba(0,0,0,.35); }',
    '.ab-gear { padding: 12px 14px; font-size: 16px; }',
    '.ab-toggle:hover, .ab-gear:hover { background: #1f2937; }',
    '.ab-toggle:focus-visible, .ab-gear:focus-visible { outline: 3px solid #fde047; outline-offset: 2px; }',
    '.ab-status { margin-top: 2px; padding: 5px 11px; border-radius: 999px; background: #111827; color: #fff; font-size: 12px; font-weight: 600; max-width: 250px; line-height: 1.45; }',
    '.ab-status[hidden] { display: none; }',
    '.ab-panel { background: #fff; color: #111827; border: 2px solid #111827; border-radius: 8px; padding: 14px; min-width: 250px; box-shadow: 0 8px 24px rgba(0,0,0,.25); font-size: 14px; }',
    '.ab-panel[hidden] { display: none; }',
    '.ab-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }',
    '.ab-label { font-weight: 600; }',
    '.ab-seg { display: flex; border: 1px solid #9ca3af; border-radius: 6px; overflow: hidden; }',
    '.ab-segbtn { font: inherit; padding: 6px 10px; border: 0; background: #f3f4f6; color: #111827; cursor: pointer; }',
    '.ab-segbtn[aria-pressed="true"] { background: #111827; color: #fff; }',
    '.ab-segbtn:focus-visible { outline: 3px solid #f59e0b; outline-offset: -1px; }',
    '.ab-select { font: inherit; padding: 5px 8px; border: 1px solid #9ca3af; border-radius: 6px; background: #fff; color: #111827; }',
    '.ab-hint { margin-top: 6px; color: #4b5563; line-height: 1.45; }',
    '.ab-highlight { position: fixed; z-index: 2147483646; pointer-events: none; display: none; border: 4px solid #000; outline: 3px solid #fde047; outline-offset: 1px; border-radius: 6px; box-shadow: 0 0 0 8px rgba(0,0,0,.28); }',
    '.ab-sr-only { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }'
  ].join('\n');

  var state = {
    enabled: false,
    mode: 'OFF',
    index: 0,
    timer: null,
    candidates: [],
    currentEl: null,
    lastActivation: 0,
    keydowns: 0,
    activations: 0,
    settings: { speed: 'medium', key: ' ', mode: 'auto' }
  };

  var host, shadow, toggleBtn, panel, overlay, statusEl, liveEl;
  var ringStack = [];
  var observer = null;
  var mutationTimer = null;
  var rafPending = false;
  var selectPending = null;

  function init() {
    if (document.getElementById('accessbridge-host')) return;
    host = document.createElement('div');
    host.id = 'accessbridge-host';
    shadow = host.attachShadow({ mode: 'open' });
    shadow.innerHTML = buildMarkup();
    document.body.appendChild(host);
    toggleBtn = shadow.getElementById('ab-toggle');
    panel = shadow.getElementById('ab-panel');
    overlay = shadow.getElementById('ab-highlight');
    statusEl = shadow.getElementById('ab-status');
    liveEl = shadow.getElementById('ab-live');
    wireUI();
    loadSettings();
    applySettingsUI();
    window.addEventListener('keydown', onKeydown, true);
    window.addEventListener('scroll', schedulePosition, true);
    window.addEventListener('resize', schedulePosition);
    window.__AccessBridge = {
      get state() {
        return {
          enabled: state.enabled,
          mode: state.mode,
          index: state.index,
          total: state.candidates.length,
          speed: state.settings.speed,
          key: state.settings.key,
          scanMode: state.settings.mode
        };
      },
      get counters() {
        return { keydowns: state.keydowns, activations: state.activations };
      },
      get status() {
        return statusEl ? statusEl.textContent : '';
      },
      get currentEl() {
        return state.currentEl ? { tag: state.currentEl.tagName, id: state.currentEl.id, cls: state.currentEl.className } : null;
      },
      list: function () {
        return state.candidates.map(function (el) {
          return el.id || el.tagName.toLowerCase() + (el.getAttribute && el.getAttribute('href') ? '[href]' : '');
        });
      },
      indexOf: function (id) {
        for (var i = 0; i < state.candidates.length; i++) {
          if (state.candidates[i].id === id) return i;
        }
        return -1;
      },
      overlayRect: function () {
        var r = overlay.getBoundingClientRect();
        return { display: overlay.style.display, x: r.x, y: r.y, w: r.width, h: r.height };
      },
      freeze: function () {
        if (state.mode === 'SCANNING') stopTimer();
      },
      resume: function () {
        if (state.mode === 'SCANNING') startTimer();
      }
    };
  }

  function buildMarkup() {
    return '<style>' + CSS + '</style>' +
      '<div class="ab-fab">' +
        '<div class="ab-actions">' +
          '<button id="ab-toggle" type="button" aria-pressed="false" class="ab-toggle">Start scanning</button>' +
          '<button id="ab-gear" type="button" aria-expanded="false" aria-label="Settings" class="ab-gear">&#9881;</button>' +
        '</div>' +
        '<div id="ab-status" class="ab-status" hidden></div>' +
        '<div id="ab-panel" class="ab-panel" hidden>' +
          '<div class="ab-row">' +
            '<span class="ab-label">Scan speed</span>' +
            '<div class="ab-seg" role="group" aria-label="Scan speed">' +
              '<button type="button" class="ab-segbtn" data-speed="slow">Slow</button>' +
              '<button type="button" class="ab-segbtn" data-speed="medium">Medium</button>' +
              '<button type="button" class="ab-segbtn" data-speed="fast">Fast</button>' +
            '</div>' +
          '</div>' +
          '<div class="ab-row">' +
            '<span class="ab-label">Scan mode</span>' +
            '<div class="ab-seg" role="group" aria-label="Scan mode">' +
              '<button type="button" class="ab-segbtn" data-mode="auto">Auto</button>' +
              '<button type="button" class="ab-segbtn" data-mode="step">Step</button>' +
            '</div>' +
          '</div>' +
          '<div class="ab-row">' +
            '<span class="ab-label">Switch key</span>' +
            '<select id="ab-key" class="ab-select" aria-label="Switch key">' +
              '<option value=" ">Space</option>' +
              '<option value="Enter">Enter</option>' +
            '</select>' +
          '</div>' +
          '<div class="ab-hint">' +
            '<span id="ab-hint-auto">Press <b id="ab-keyname">Space</b> to activate the highlighted item. Esc returns from a field, or stops scanning.</span>' +
            '<span id="ab-hint-step" hidden>Two-switch step scan: <b>Space</b> moves to the next item, <b>Enter</b> activates it. Esc stops scanning.</span>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div id="ab-highlight" class="ab-highlight" aria-hidden="true"></div>' +
      '<div id="ab-live" class="ab-sr-only" role="status" aria-live="polite"></div>';
  }

  function wireUI() {
    toggleBtn.addEventListener('click', function () {
      toggleScan();
    });
    shadow.getElementById('ab-gear').addEventListener('click', function () {
      var hidden = panel.hasAttribute('hidden');
      panel.hidden = !hidden;
      this.setAttribute('aria-expanded', hidden ? 'true' : 'false');
    });
    var speedBtns = panel.querySelectorAll('[data-speed]');
    for (var i = 0; i < speedBtns.length; i++) {
      speedBtns[i].addEventListener('click', function () {
        state.settings.speed = this.getAttribute('data-speed');
        saveSettings();
        applySettingsUI();
        if (state.mode === 'SCANNING') {
          restartTimer();
          setStatus(currentStatus());
        }
      });
    }
    var modeBtns = panel.querySelectorAll('[data-mode]');
    for (var j = 0; j < modeBtns.length; j++) {
      modeBtns[j].addEventListener('click', function () {
        state.settings.mode = this.getAttribute('data-mode');
        saveSettings();
        applySettingsUI();
        if (state.mode === 'SCANNING') {
          if (state.settings.mode === 'auto') startTimer(); else stopTimer();
          setStatus(currentStatus());
        }
      });
    }
    shadow.getElementById('ab-key').addEventListener('change', function () {
      state.settings.key = this.value;
      saveSettings();
      applySettingsUI();
    });
  }

  function toggleScan() {
    if (state.enabled) {
      disableScan();
    } else {
      enableScan();
    }
  }

  function enableScan() {
    state.enabled = true;
    state.mode = 'SCANNING';
    state.lastActivation = 0;
    state.index = 0;
    toggleBtn.textContent = 'Stop scanning';
    toggleBtn.setAttribute('aria-pressed', 'true');
    observe();
    refreshCandidates();
    if (!state.candidates.length) {
      hideOverlay();
      setStatus('Nothing to scan on this page');
      announce('Scanning started. Nothing to scan.');
      return;
    }
    step();
    restartTimer();
    announce('Scanning started');
  }

  function disableScan() {
    stopTimer();
    disconnect();
    clearSelectPending();
    state.enabled = false;
    state.mode = 'OFF';
    state.currentEl = null;
    state.index = 0;
    toggleBtn.textContent = 'Start scanning';
    toggleBtn.setAttribute('aria-pressed', 'false');
    restoreRing();
    hideOverlay();
    setStatus('');
    announce('Scanning stopped');
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  }

  function startTimer() {
    stopTimer();
    state.timer = setInterval(tick, SPEEDS[state.settings.speed]);
  }

  function stopTimer() {
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
    }
  }

  function restartTimer() {
    if (state.mode !== 'SCANNING') return;
    if (state.settings.mode === 'auto') startTimer(); else stopTimer();
  }

  function tick() {
    if (!state.candidates.length) return;
    state.index = (state.index + 1) % state.candidates.length;
    step();
  }

  function step() {
    var el = state.candidates[state.index];
    if (!el) return;
    state.currentEl = el;
    focusTarget(el);
    positionOverlay(el);
    setStatus(currentStatus());
  }

  function stepNext() {
    if (!state.candidates.length) return;
    state.index = (state.index + 1) % state.candidates.length;
    step();
  }

  function focusTarget(el) {
    suppressRing(el);
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      try { el.focus(); } catch (e2) {}
    }
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    try {
      el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest', inline: 'nearest' });
    } catch (e) {}
  }

  function refreshCandidates() {
    var prev = state.currentEl;
    state.candidates = collectCandidates();
    if (state.mode === 'EDITING' || state.mode === 'SELECTING') return;
    if (!state.candidates.length) {
      state.currentEl = null;
      state.index = 0;
      hideOverlay();
      return;
    }
    var idx = prev ? state.candidates.indexOf(prev) : -1;
    state.index = idx >= 0 ? idx : Math.min(state.index, state.candidates.length - 1);
    if (state.mode === 'SCANNING') {
      step();
    }
  }

  function collectCandidates() {
    var out = [];
    var nodes = document.querySelectorAll(SELECTOR);
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!eligible(el)) continue;
      if (out.indexOf(el) >= 0) continue;
      out.push(el);
    }
    out.push(toggleBtn);
    return out;
  }

  function eligible(el) {
    if (el.disabled) return false;
    if (el.matches && el.matches('[hidden], [aria-hidden="true"], [inert]')) return false;
    var type = el.getAttribute && el.getAttribute('type');
    if (type === 'hidden') return false;
    return isVisible(el);
  }

  function isVisible(el) {
    var r;
    try {
      r = el.getBoundingClientRect();
    } catch (e) {
      return false;
    }
    if (!r.width && !r.height) return false;
    var cs;
    try {
      cs = window.getComputedStyle(el);
    } catch (e) {
      return true;
    }
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    return true;
  }

  function activate() {
    var el = state.currentEl;
    if (!el) return;
    if (el.tagName === 'SELECT') {
      openSelect(el);
      return;
    }
    if (isTextEntry(el)) {
      enterEditing(el);
      return;
    }
    try {
      el.click();
    } catch (e) {}
    announce('Activated ' + describe(el));
  }

  function isTextEntry(el) {
    if (el.isContentEditable) return true;
    var tag = el.tagName;
    if (tag === 'SELECT') return true;
    if (tag === 'TEXTAREA') return !el.disabled && !el.readOnly;
    if (tag === 'INPUT') {
      if (el.disabled || el.readOnly) return false;
      var t = (el.getAttribute('type') || 'text').toLowerCase();
      return t !== 'checkbox' && t !== 'radio' && t !== 'button' && t !== 'submit' && t !== 'reset' && t !== 'image' && t !== 'range' && t !== 'color' && t !== 'file';
    }
    var role = (el.getAttribute('role') || '').toLowerCase();
    if (el.getAttribute('aria-readonly') === 'true') return false;
    return role === 'textbox' || role === 'combobox' || role === 'searchbox' || role === 'spinbutton';
  }

  function enterEditing(el) {
    stopTimer();
    state.mode = 'EDITING';
    state.currentEl = el;
    positionOverlay(el);
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      try { el.focus(); } catch (e2) {}
    }
    if (typeof el.select === 'function') {
      try { el.select(); } catch (e) {}
    }
    setStatus(currentStatus());
    announce('Editing ' + describe(el));
  }

  function openSelect(el) {
    stopTimer();
    state.currentEl = el;
    positionOverlay(el);
    if (typeof el.showPicker === 'function') {
      try {
        el.showPicker();
      } catch (err) {
        enterEditing(el);
        return;
      }
      state.mode = 'SELECTING';
      setStatus('Select open — pick an option');
      announce('Select open');
      var done = false;
      var watchdog = null;
      function cleanup() {
        el.removeEventListener('change', once);
        el.removeEventListener('blur', once);
        if (watchdog) clearTimeout(watchdog);
      }
      function once() {
        if (done) return;
        done = true;
        cleanup();
        selectPending = null;
        resumeScan();
      }
      el.addEventListener('change', once);
      el.addEventListener('blur', once);
      watchdog = setTimeout(once, SELECT_WATCHDOG_MS);
      selectPending = { resume: once };
      return;
    }
    enterEditing(el);
  }

  function resumeScan() {
    if (state.mode === 'SCANNING') return;
    state.mode = 'SCANNING';
    refreshCandidates();
    restartTimer();
    setStatus(currentStatus());
    announce('Scanning resumed');
  }

  function exitEditing() {
    resumeScan();
  }

  function clearSelectPending() {
    if (selectPending) {
      var pending = selectPending;
      selectPending = null;
      pending.resume();
    }
  }

  function onKeydown(e) {
    state.keydowns += 1;
    try {
      if (!state.enabled) return;
      if (isWidgetEvent(e)) return;
      if (state.mode === 'EDITING') {
        if (e.key === 'Escape') {
          e.preventDefault();
          exitEditing();
        }
        return;
      }
      if (state.mode === 'SELECTING') {
        if (e.key === 'Escape') {
          var pending = selectPending;
          if (pending) setTimeout(pending.resume, 0);
        }
        return;
      }
      if (state.mode !== 'SCANNING') return;
      if (e.key === 'Escape') {
        e.preventDefault();
        disableScan();
        return;
      }
      var isSpace = e.code === 'Space' || e.key === ' ';
      var isEnter = e.key === 'Enter' || e.code === 'Enter';
      if (state.settings.mode === 'step') {
        if (isSpace) {
          if (e.repeat) return;
          e.preventDefault();
          stepNext();
          return;
        }
        if (isEnter) {
          if (e.repeat) return;
          var now = Date.now();
          if (now - state.lastActivation < COOLDOWN_MS) return;
          state.lastActivation = now;
          state.activations += 1;
          e.preventDefault();
          activate();
          return;
        }
        return;
      }
      if (!keyMatches(e)) return;
      if (e.repeat) return;
      var now2 = Date.now();
      if (now2 - state.lastActivation < COOLDOWN_MS) return;
      state.lastActivation = now2;
      state.activations += 1;
      e.preventDefault();
      activate();
    } catch (err) {}
  }

  function keyMatches(e) {
    if (state.settings.key === ' ') {
      return e.key === ' ' || e.code === 'Space';
    }
    return e.key === 'Enter' || e.code === 'Enter';
  }

  function isWidgetEvent(e) {
    var path = e.composedPath && e.composedPath();
    if (!path || !path.length) return false;
    var first = path[0];
    if (!first || typeof first !== 'object' || !first.nodeType) return false;
    return host.contains(first);
  }

  function positionOverlay(el) {
    var r = el.getBoundingClientRect();
    if (!r.width && !r.height) {
      hideOverlay();
      return;
    }
    var pad = 2;
    overlay.style.display = 'block';
    overlay.style.left = (r.left - pad) + 'px';
    overlay.style.top = (r.top - pad) + 'px';
    overlay.style.width = (r.width + pad * 2) + 'px';
    overlay.style.height = (r.height + pad * 2) + 'px';
  }

  function hideOverlay() {
    overlay.style.display = 'none';
  }

  function schedulePosition() {
    if (!state.currentEl) return;
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(function () {
      rafPending = false;
      if (state.currentEl) {
        positionOverlay(state.currentEl);
      }
    });
  }

  function observe() {
    if (!window.MutationObserver || observer) return;
    observer = new MutationObserver(function () {
      if (mutationTimer) clearTimeout(mutationTimer);
      mutationTimer = setTimeout(function () {
        if (state.mode === 'SCANNING') refreshCandidates();
      }, MUTATION_DEBOUNCE_MS);
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style', 'disabled', 'hidden', 'href']
    });
  }

  function disconnect() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    if (mutationTimer) {
      clearTimeout(mutationTimer);
      mutationTimer = null;
    }
  }

  function suppressRing(el) {
    restoreRing();
    if (!el) return;
    ringStack = [{
      el: el,
      outline: el.style.getPropertyValue('outline'),
      outlinePriority: el.style.getPropertyPriority('outline'),
      boxShadow: el.style.getPropertyValue('box-shadow'),
      boxShadowPriority: el.style.getPropertyPriority('box-shadow')
    }];
    el.style.setProperty('outline', 'none', 'important');
    el.style.setProperty('box-shadow', 'none', 'important');
  }

  function restoreRing() {
    for (var i = 0; i < ringStack.length; i++) {
      var rec = ringStack[i];
      if (rec.outline) {
        rec.el.style.setProperty('outline', rec.outline, rec.outlinePriority);
      } else {
        rec.el.style.removeProperty('outline');
      }
      if (rec.boxShadow) {
        rec.el.style.setProperty('box-shadow', rec.boxShadow, rec.boxShadowPriority);
      } else {
        rec.el.style.removeProperty('box-shadow');
      }
    }
    ringStack = [];
  }

  function setStatus(text) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.hidden = !text;
  }

  function currentStatus() {
    var total = state.candidates.length;
    var pos = total ? (state.index + 1) + '/' + total : '0/0';
    if (state.mode === 'OFF') return '';
    if (state.mode === 'EDITING') {
      return 'Editing ' + (state.currentEl ? elName(state.currentEl) || 'field' : 'field') + ' — Esc to return';
    }
    if (state.mode === 'SELECTING') return 'Select open — pick an option';
    if (state.settings.mode === 'step') return 'Step scan · ' + pos;
    return 'Scanning · ' + state.settings.speed + ' · ' + pos;
  }

  function announce(msg) {
    if (!liveEl) return;
    liveEl.textContent = '';
    var span = document.createElement('span');
    span.textContent = msg;
    liveEl.appendChild(span);
  }

  function describe(el) {
    var kind = elKind(el);
    var name = elName(el);
    return kind + (name ? ' ' + name : '');
  }

  function elKind(el) {
    var tag = el.tagName;
    if (tag === 'BUTTON') return 'button';
    if (tag === 'A') return 'link';
    if (tag === 'SELECT') return 'select';
    if (tag === 'TEXTAREA') return 'text field';
    if (tag === 'INPUT') {
      var t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'range') return 'slider';
      return 'text field';
    }
    if (el.isContentEditable) return 'editable text';
    var role = (el.getAttribute('role') || '').toLowerCase();
    if (role) return role;
    return tag.toLowerCase();
  }

  function elName(el) {
    var s = el.getAttribute && el.getAttribute('aria-label');
    if (s && s.trim()) return s.trim();
    var lb = el.getAttribute && el.getAttribute('aria-labelledby');
    if (lb) {
      var ref = document.getElementById(lb);
      if (ref && ref.textContent && ref.textContent.trim()) return ref.textContent.trim();
    }
    if (el.id) {
      try {
        var label = document.querySelector('label[for="' + cssEscape(el.id) + '"]');
        if (label && label.textContent && label.textContent.trim()) return label.textContent.trim();
      } catch (e) {}
    }
    var txt = el.textContent;
    if (txt && txt.trim()) return txt.trim().slice(0, 60);
    var ph = el.getAttribute && el.getAttribute('placeholder');
    if (ph) return ph;
    var t = el.getAttribute && el.getAttribute('type');
    return el.tagName.toLowerCase() + (t && t !== 'text' ? ' ' + t : '');
  }

  function cssEscape(id) {
    if (window.CSS && CSS.escape) return CSS.escape(id);
    return String(id).replace(/[\\"]/g, '\\$&');
  }

  function loadSettings() {
    try {
      var parts = document.cookie.split(';');
      for (var i = 0; i < parts.length; i++) {
        var part = parts[i].trim();
        if (part.indexOf(COOKIE_NAME + '=') !== 0) continue;
        var data = JSON.parse(decodeURIComponent(part.slice(COOKIE_NAME.length + 1)));
        if (data.speed && SPEEDS[data.speed]) state.settings.speed = data.speed;
        if (data.key === ' ' || data.key === 'Enter') state.settings.key = data.key;
        if (data.mode === 'auto' || data.mode === 'step') state.settings.mode = data.mode;
      }
    } catch (e) {}
  }

  function saveSettings() {
    var value = encodeURIComponent(JSON.stringify(state.settings));
    var expires = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toUTCString();
    document.cookie = COOKIE_NAME + '=' + value + '; expires=' + expires + '; path=/; SameSite=Lax';
  }

  function applySettingsUI() {
    var speedBtns = panel.querySelectorAll('[data-speed]');
    for (var i = 0; i < speedBtns.length; i++) {
      speedBtns[i].setAttribute('aria-pressed', speedBtns[i].getAttribute('data-speed') === state.settings.speed ? 'true' : 'false');
    }
    var modeBtns = panel.querySelectorAll('[data-mode]');
    for (var j = 0; j < modeBtns.length; j++) {
      modeBtns[j].setAttribute('aria-pressed', modeBtns[j].getAttribute('data-mode') === state.settings.mode ? 'true' : 'false');
    }
    shadow.getElementById('ab-key').value = state.settings.key;
    shadow.getElementById('ab-keyname').textContent = state.settings.key === 'Enter' ? 'Enter' : 'Space';
    shadow.getElementById('ab-hint-auto').hidden = state.settings.mode !== 'auto';
    shadow.getElementById('ab-hint-step').hidden = state.settings.mode !== 'step';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
