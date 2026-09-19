/**
 * ThermoGuard — Investigation Priority Dashboard
 * Vanilla JavaScript frontend for the 100-event pilot cohort API.
 *
 * Author: Riya (frontend/GIS contribution)
 * Branch: feature/riya-frontend-gis
 *
 * Architecture:
 *   - API module     : fetchEvents(), fetchEvent()
 *   - State module   : centralised application state
 *   - Map module     : Leaflet GIS map with custom markers
 *   - List module    : event list + filters + sorting
 *   - Detail module  : right-panel event detail view
 *   - App init       : bootstrap sequence
 *
 * Scientific note:
 *   All risk scores are READ from the deterministic backend API.
 *   No risk calculation is performed in JavaScript.
 *   All outputs represent investigation priority — NOT fire confirmation.
 */

'use strict';

// ── Configuration ─────────────────────────────────────────────────────────────

// API origin: configurable via window.THERMOGUARD_API_BASE or window.__ENV__?.API_BASE_URL
const API_BASE_URL = (typeof window !== 'undefined' && (window.THERMOGUARD_API_BASE || window.__ENV__?.API_BASE_URL))
  || 'http://localhost:8000';
const API_EVENTS   = `${API_BASE_URL}/api/events`;

// Risk dimension metadata (weights are display-only; computation is backend)
const DIMENSIONS = [
  { key: 'thermal',     label: 'Thermal Intensity',          weight: 30 },
  { key: 'persistence', label: 'Persistence',                weight: 25 },
  { key: 'industrial',  label: 'Industrial Association',     weight: 20 },
  { key: 'spectral',    label: 'Spectral / Surface Evidence',weight: 15 },
  { key: 'spatial',     label: 'Spatial Scale',              weight: 10 },
];

const TIER_ORDER = ['CRITICAL', 'HIGH', 'MODERATE', 'LOW'];

// ── Application state ─────────────────────────────────────────────────────────

const State = {
  allEvents:      [],   // all EventSummary objects from GET /events
  filteredEvents: [],   // after filter + search
  selectedId:     null, // currently selected event_id
  tierFilter:     null, // active tier chip filter (or null for all)
  searchQuery:    '',
  sortMode:       'risk_score_desc',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Return value if non-null/undefined/NaN, else fallback string.
 */
function display(val, fallback = 'Not available', decimals = null) {
  if (val === null || val === undefined) return fallback;
  if (typeof val === 'number' && !isFinite(val)) return fallback;
  if (typeof val === 'string' && val.trim() === '') return fallback;
  if (decimals !== null && typeof val === 'number') return val.toFixed(decimals);
  return val;
}

function fmtScore(score) {
  if (score === null || score === undefined) return '—';
  return Number(score).toFixed(1);
}

function fmtDatetime(iso) {
  if (!iso) return 'Not available';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return iso; }
}

function tierClass(tier) {
  if (!tier) return '';
  return `tier-${tier.toLowerCase()}`;
}

function tierBadgeClass(tier) {
  if (!tier) return '';
  return `badge-${tier.toLowerCase()}`;
}

function scoreBarColor(tier) {
  switch (tier) {
    case 'CRITICAL': return '#ef4444';
    case 'HIGH':     return '#f97316';
    case 'MODERATE': return '#eab308';
    case 'LOW':      return '#22c55e';
    default:         return '#8b95b0';
  }
}

function scoreRingColor(tier) {
  switch (tier) {
    case 'CRITICAL': return '#ef4444';
    case 'HIGH':     return '#f97316';
    case 'MODERATE': return '#eab308';
    case 'LOW':      return '#22c55e';
    default:         return '#ff6b35';
  }
}

function markerRadius(score) {
  if (score === null || score === undefined) return 8;
  return 6 + (score / 100) * 8;
}

// ── Toast notifications ───────────────────────────────────────────────────────

function showToast(message, type = 'info', durationMs = 4500) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => container.removeChild(toast), 320);
  }, durationMs);
}

// ── API module ────────────────────────────────────────────────────────────────

async function fetchEvents() {
  const response = await fetch(`${API_EVENTS}?limit=200`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json().then(data => data.events);
}

async function fetchEvent(eventId) {
  const response = await fetch(`${API_EVENTS}/${encodeURIComponent(eventId)}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

// ── GIS Map module ────────────────────────────────────────────────────────────

const MapModule = (() => {
  let map = null;
  let markerLayer = null;
  const markerIndex = {}; // event_id -> Leaflet marker

  function init() {
    map = L.map('map', {
      center: [22.5, 80.0],  // Central India
      zoom: 5,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map);

    markerLayer = L.layerGroup().addTo(map);

    // Inject SVG gradient defs for score ring
    const svgDefs = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgDefs.setAttribute('style', 'position:absolute;width:0;height:0');
    svgDefs.innerHTML = `<defs>
      <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#ff6b35"/>
        <stop offset="100%" stop-color="#f7931e"/>
      </linearGradient>
    </defs>`;
    document.body.appendChild(svgDefs);
  }

  function renderMarkers(events) {
    markerLayer.clearLayers();
    Object.keys(markerIndex).forEach(k => delete markerIndex[k]);

    events.forEach(ev => {
      if (ev.lat === null || ev.lon === null) return;

      const r = markerRadius(ev.risk_score);
      const tierCls = tierClass(ev.risk_tier);

      const icon = L.divIcon({
        className: `thermo-marker ${tierCls}`,
        iconSize: [r * 2, r * 2],
        iconAnchor: [r, r],
        popupAnchor: [0, -r - 4],
        html: '',
      });

      const marker = L.marker([ev.lat, ev.lon], { icon, title: ev.event_id })
        .bindPopup(() => buildPopupElement(ev), { maxWidth: 220, className: '' });

      marker.on('click', () => {
        selectEvent(ev.event_id);
      });

      marker.addTo(markerLayer);
      markerIndex[ev.event_id] = marker;
    });
  }

  function buildPopupElement(ev) {
    const tierCls = tierClass(ev.risk_tier);
    const color = scoreBarColor(ev.risk_tier);

    const popup = document.createElement('div');
    popup.className = 'map-popup';

    const idEl = document.createElement('div');
    idEl.className = 'map-popup-id';
    idEl.textContent = ev.event_id;
    popup.appendChild(idEl);

    const scoreEl = document.createElement('div');
    scoreEl.className = 'map-popup-score';
    scoreEl.style.color = color;
    scoreEl.textContent = fmtScore(ev.risk_score);
    popup.appendChild(scoreEl);

    const tierEl = document.createElement('div');
    tierEl.className = `map-popup-tier ${tierCls}`;
    tierEl.style.color = color;
    tierEl.textContent = display(ev.risk_tier);
    popup.appendChild(tierEl);

    const driverEl = document.createElement('div');
    driverEl.className = 'map-popup-driver';
    driverEl.textContent = `▲ ${display(ev.primary_driver)}`;
    popup.appendChild(driverEl);

    const btn = document.createElement('button');
    btn.className = 'map-popup-btn';
    btn.type = 'button';
    btn.textContent = 'View full assessment';
    btn.addEventListener('click', () => {
      selectEvent(ev.event_id);
    });
    popup.appendChild(btn);

    return popup;
  }

  function flyTo(lat, lon, zoom = 9) {
    if (lat !== null && lon !== null) {
      map.flyTo([lat, lon], zoom, { duration: 0.8 });
    }
  }

  function highlightMarker(eventId) {
    const marker = markerIndex[eventId];
    if (marker) {
      marker.openPopup();
    }
  }

  function closeAllPopups() {
    map.closePopup();
  }

  return { init, renderMarkers, flyTo, highlightMarker, closeAllPopups };
})();

// ── Event List module ─────────────────────────────────────────────────────────

const ListModule = (() => {

  function render(events) {
    const container = document.getElementById('event-list');
    container.innerHTML = '';

    // Update filtered count (always set before empty-state check so '0 events' displays)
    const countEl = document.getElementById('filtered-count');
    if (countEl) {
      countEl.textContent = `${events.length} event${events.length !== 1 ? 's' : ''}`;
    }

    if (events.length === 0) {
      container.innerHTML = `
        <div class="list-loading" role="status">
          <span style="font-size:1.4rem;">🔍</span>
          <span>No events match the current filters.</span>
        </div>`;
      return;
    }

    const frag = document.createDocumentFragment();
    events.forEach(ev => {
      const card = buildCard(ev);
      frag.appendChild(card);
    });
    container.appendChild(frag);

    // Highlight selected
    if (State.selectedId) {
      const sel = container.querySelector(`[data-id="${State.selectedId}"]`);
      if (sel) sel.classList.add('selected');
    }
  }

  function buildCard(ev) {
    const card = document.createElement('div');
    card.className = 'event-card';
    card.setAttribute('data-id', ev.event_id);
    card.setAttribute('role', 'listitem');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `Event ${ev.event_id}, risk score ${fmtScore(ev.risk_score)}, tier ${ev.risk_tier}`);

    const color   = scoreBarColor(ev.risk_tier);
    const barPct  = ev.risk_score !== null ? Math.min(100, ev.risk_score) : 0;
    const driver  = display(ev.primary_driver, '—');
    const landuse = display(ev.osm_primary_category, '');
    const meta    = [driver, landuse].filter(Boolean).join(' · ');

    card.innerHTML = `
      <div class="card-top">
        <code class="card-event-id"></code>
        <span class="card-tier-badge"></span>
      </div>
      <div class="card-score-row">
        <div class="card-score-bar-wrap">
          <div class="card-score-bar"></div>
        </div>
        <span class="card-score-text"></span>
      </div>
      <div class="card-meta">
        <span class="card-driver">
          <span class="card-driver-dot"></span>
        </span>
      </div>`;

    card.querySelector('.card-event-id').textContent = ev.event_id;

    const badge = card.querySelector('.card-tier-badge');
    badge.className = `card-tier-badge ${tierBadgeClass(ev.risk_tier)}`;
    badge.textContent = display(ev.risk_tier, '—');

    const bar = card.querySelector('.card-score-bar');
    bar.style.width = `${barPct}%`;
    bar.style.background = color;

    const scoreText = card.querySelector('.card-score-text');
    scoreText.style.color = color;
    scoreText.textContent = fmtScore(ev.risk_score);

    const driverEl = card.querySelector('.card-driver');
    driverEl.appendChild(document.createTextNode(meta || 'Not available'));

    card.addEventListener('click',   () => selectEvent(ev.event_id));
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') selectEvent(ev.event_id); });

    return card;
  }

  function setSelectedCard(eventId) {
    document.querySelectorAll('.event-card').forEach(c => c.classList.remove('selected'));
    if (eventId) {
      const card = document.querySelector(`.event-card[data-id="${eventId}"]`);
      if (card) {
        card.classList.add('selected');
        card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }

  return { render, setSelectedCard };
})();

// ── Detail panel module ───────────────────────────────────────────────────────

const DetailModule = (() => {

  function setLoading() {
    document.getElementById('detail-empty').removeAttribute('hidden');
    document.getElementById('detail-content').setAttribute('hidden', '');
    document.getElementById('detail-empty').innerHTML = `
      <div class="spinner" aria-label="Loading event detail"></div>
      <span>Loading assessment…</span>`;
  }

  function setEmpty() {
    document.getElementById('detail-empty').removeAttribute('hidden');
    document.getElementById('detail-content').setAttribute('hidden', '');
    document.getElementById('detail-empty').innerHTML = `
      <div class="detail-empty-icon" aria-hidden="true">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="22" stroke="url(#emptyGrad)" stroke-width="2" stroke-dasharray="5 3"/>
          <path d="M24 14 L24 26 M24 30 v2" stroke="url(#emptyGrad)" stroke-width="2.5" stroke-linecap="round"/>
          <defs>
            <linearGradient id="emptyGrad" x1="0" y1="0" x2="48" y2="48">
              <stop offset="0%" stop-color="#ff6b35" stop-opacity="0.5"/>
              <stop offset="100%" stop-color="#f7931e" stop-opacity="0.5"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <p>Select an event on the map or list to view its full scientific assessment.</p>`;
  }

  function render(ev) {
    document.getElementById('detail-empty').setAttribute('hidden', '');
    const content = document.getElementById('detail-content');
    content.removeAttribute('hidden');

    // Header
    document.getElementById('det-event-id').textContent    = ev.event_id;
    document.getElementById('det-methodology').textContent = display(ev.methodology_version);
    const spatialExtent = ev.dimensions?.spatial?.raw?.spatial_extent_km2 ?? ev.spatial_extent_km2;
    document.getElementById('det-spatial-extent').textContent =
      spatialExtent != null ? `${Number(spatialExtent).toFixed(2)} km²` : 'Not available';

    // Tier badge
    const tierBadge = document.getElementById('det-tier-badge');
    tierBadge.textContent  = display(ev.risk_tier, '—');
    tierBadge.className    = `detail-tier-badge ${tierBadgeClass(ev.risk_tier)}`;

    // Score ring
    const score       = ev.risk_score !== null ? Number(ev.risk_score) : 0;
    const circumf     = 2 * Math.PI * 34; // r=34
    const offset      = circumf - (score / 100) * circumf;
    const ringFill    = document.getElementById('det-ring-fill');
    ringFill.style.stroke            = scoreRingColor(ev.risk_tier);
    ringFill.style.strokeDashoffset  = circumf; // reset first
    setTimeout(() => { ringFill.style.strokeDashoffset = offset; }, 30);

    document.getElementById('det-score-value').textContent = fmtScore(ev.risk_score);

    // Confidence
    const confTier = ev.confidence_tier ? ` (${ev.confidence_tier})` : '';
    document.getElementById('det-confidence').textContent =
      ev.evidence_confidence !== null
        ? `${Number(ev.evidence_confidence).toFixed(1)}%${confTier}`
        : 'Not available';

    // Drivers
    document.getElementById('det-primary').textContent   = display(ev.ranking?.primary_driver);
    document.getElementById('det-secondary').textContent = display(ev.ranking?.secondary_driver);
    document.getElementById('det-weakest').textContent   = display(ev.ranking?.weakest_dimension);
    document.getElementById('det-recommendation').textContent = display(ev.explanation?.recommendation);

    // Risk dimensions
    renderDimensions(ev);

    // Thermal evidence
    setText('det-frp-mean',   fmtNum(ev.thermal?.frp_mean,   2));
    setText('det-frp-max',    fmtNum(ev.thermal?.frp_max,    2));
    setText('det-brightness', fmtNum(ev.thermal?.brightness_mean, 2));
    setText('det-swir',       fmtNum(ev.spectral?.swir2_anomaly_ratio, 4));
    setText('det-ndvi',       fmtNum(ev.spectral?.ndvi,        4));
    setText('det-bsi',        fmtNum(ev.spectral?.bsi,         4));

    // Timeline / persistence
    setText('det-first-detect',  fmtDatetime(ev.temporal?.first_detection));
    setText('det-last-detect',   fmtDatetime(ev.temporal?.last_detection));
    setText('det-duration',      fmtNum(ev.temporal?.duration_days, 1));
    setText('det-detect-days',   display(ev.temporal?.distinct_detection_days));
    setText('det-detect-count',  display(ev.temporal?.detection_count));
    setText('det-satellites',    display(ev.context?.distinct_satellites));

    // Land cover
    setText('det-worldcover',   display(ev.context?.worldcover_class_name));
    setText('det-osm-cat',      display(ev.context?.osm_primary_category));
    setText('det-osm-sub',      display(ev.context?.osm_sub_category));
    const distInd = ev.dimensions?.industrial?.raw?.min_distance_m ?? ev.context?.distance_to_industrial_m;
    setText('det-dist-ind',
      distInd != null
        ? `${Number(distInd).toFixed(0)} m`
        : 'Not available');
    const osmMatched = ev.dimensions?.industrial?.raw?.osm_matched_fraction;
    setText('det-osm-matched',
      osmMatched != null
        ? `${(osmMatched * 100).toFixed(1)}%`
        : 'Not available');

    // Explanation narrative
    const expSection = document.getElementById('explanation-section');
    const expSummary = ev.explanation?.analyst_synthesis;
    const expDrivers = ev.explanation?.task28_explanation?.contribution_ranking?.primary_driver_text;
    const expRec     = ev.explanation?.recommendation;
    const hasSummary = expSummary || expDrivers || expRec;
    if (hasSummary) {
      expSection.removeAttribute('hidden');
      setHtml('det-explanation-summary', expSummary || '');
      setHtml('det-explanation-drivers', expDrivers || '');
      setHtml('det-explanation-rec',     expRec || '');
    } else {
      expSection.setAttribute('hidden', '');
    }

    // Missing evidence
    const missingBox = document.getElementById('det-missing-box');
    const limitations = ev.explanation?.limitations;
    if (limitations) {
      missingBox.removeAttribute('hidden');
      setText('det-missing-evidence', limitations);
    } else {
      missingBox.setAttribute('hidden', '');
    }
  }

  function renderDimensions(ev) {
    const dims = ev.dimensions || {};
    const chart = document.getElementById('dims-chart');
    chart.innerHTML = '';

    DIMENSIONS.forEach(d => {
      const dim = dims?.[d.key];
      const scoreVal =
        dim?.normalized_score !== undefined && dim?.normalized_score !== null
          ? dim.normalized_score
          : null;
      const pct        = scoreVal !== null ? Math.round(scoreVal * 100) : null;
      const barW       = scoreVal !== null ? (scoreVal * 100).toFixed(1) : 0;

      const row = document.createElement('div');
      row.className = 'dim-row';
      row.setAttribute('role', 'listitem');
      row.setAttribute('aria-label', `${d.label}: ${pct !== null ? pct + '%' : 'not available'}`);
      row.innerHTML = `
        <span class="dim-label">${d.label} <span style="color:var(--text-muted);font-size:0.6rem">(${d.weight}%)</span></span>
        <div class="dim-bar-wrap">
          <div class="dim-bar" style="width:${barW}%"></div>
        </div>
        <span class="dim-pct">${pct !== null ? pct + '%' : '—'}</span>`;
      chart.appendChild(row);
    });
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function setHtml(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val; // textContent to avoid XSS
  }

  function fmtNum(val, decimals) {
    if (val === null || val === undefined) return 'Not available';
    const n = Number(val);
    if (!isFinite(n)) return 'Not available';
    return n.toFixed(decimals);
  }

  return { render, setLoading, setEmpty };
})();

// ── Filter & sort logic ───────────────────────────────────────────────────────

function applyFilters() {
  let events = [...State.allEvents];

  // Tier chip filter
  if (State.tierFilter) {
    events = events.filter(e => e.risk_tier === State.tierFilter);
  }

  // Dropdown tier filter (takes precedence if both set)
  const ddTier = document.getElementById('tier-filter').value;
  if (ddTier && !State.tierFilter) {
    events = events.filter(e => e.risk_tier === ddTier);
  }

  // Search
  const q = State.searchQuery.toLowerCase().trim();
  if (q) {
    events = events.filter(e =>
      e.event_id.toLowerCase().includes(q)
      || (e.osm_primary_category || '').toLowerCase().includes(q)
      || (e.osm_sub_category     || '').toLowerCase().includes(q)
      || (e.primary_driver       || '').toLowerCase().includes(q)
    );
  }

  // Sort
  events.sort((a, b) => {
    switch (State.sortMode) {
      case 'risk_score_desc': return (b.risk_score || 0) - (a.risk_score || 0);
      case 'risk_score_asc':  return (a.risk_score || 0) - (b.risk_score || 0);
      case 'duration_desc':   return (b.duration_days || 0) - (a.duration_days || 0);
      case 'confidence_desc': return (b.evidence_confidence || 0) - (a.evidence_confidence || 0);
      default: return 0;
    }
  });

  State.filteredEvents = events;
  return events;
}

function refreshList() {
  const events = applyFilters();
  ListModule.render(events);
  MapModule.renderMarkers(events);
}

// ── Event selection ───────────────────────────────────────────────────────────

/**
 * Exposed globally so Leaflet popup button can call it.
 */
window.selectEvent = async function selectEvent(eventId) {
  if (State.selectedId === eventId) return;
  State.selectedId = eventId;

  // Immediately highlight list card and fly map
  ListModule.setSelectedCard(eventId);
  const summary = State.allEvents.find(e => e.event_id === eventId);
  if (summary) {
    MapModule.flyTo(summary.lat, summary.lon);
    MapModule.highlightMarker(eventId);
  }

  // Load full detail from API
  DetailModule.setLoading();
  try {
    const detail = await fetchEvent(eventId);
    // Race guard: verify selection has not changed while waiting for network
    if (State.selectedId !== eventId) return;
    DetailModule.render(detail);
  } catch (err) {
    console.error('Failed to load event detail:', err);
    // Race guard: do not disturb a newer selection
    if (State.selectedId !== eventId) return;
    showToast(`Could not load detail for ${eventId}. Is the backend running?`, 'error');
    DetailModule.setEmpty();
    ListModule.setSelectedCard(null);
    MapModule.closeAllPopups();
    State.selectedId = null;
  }
};

// ── Tier summary chips ────────────────────────────────────────────────────────

function updateTierCounts(allEvents) {
  const counts = { CRITICAL: 0, HIGH: 0, MODERATE: 0, LOW: 0 };
  allEvents.forEach(e => { if (e.risk_tier && counts[e.risk_tier] !== undefined) counts[e.risk_tier]++; });
  document.getElementById('count-critical').textContent = counts.CRITICAL;
  document.getElementById('count-high').textContent     = counts.HIGH;
  document.getElementById('count-moderate').textContent = counts.MODERATE;
  document.getElementById('count-low').textContent      = counts.LOW;

  // Header count
  document.getElementById('hdr-event-count').textContent = `${allEvents.length} events`;
}

function setupTierChips() {
  document.querySelectorAll('.tier-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const tier = chip.dataset.tier;
      if (State.tierFilter === tier) {
        // Deselect
        State.tierFilter = null;
        document.getElementById('tier-filter').value = '';
        chip.setAttribute('aria-pressed', 'false');
      } else {
        State.tierFilter = tier;
        document.getElementById('tier-filter').value = '';
        document.querySelectorAll('.tier-chip').forEach(c => c.setAttribute('aria-pressed', 'false'));
        chip.setAttribute('aria-pressed', 'true');
      }
      refreshList();
    });
  });
}

// ── Controls setup ────────────────────────────────────────────────────────────

function setupControls() {
  // Search input (debounced)
  let searchTimer;
  document.getElementById('search-input').addEventListener('input', e => {
    clearTimeout(searchTimer);
    State.searchQuery = e.target.value;
    searchTimer = setTimeout(refreshList, 200);
  });

  // Tier dropdown
  document.getElementById('tier-filter').addEventListener('change', () => {
    // Clear chip selection when dropdown is used
    State.tierFilter = null;
    document.querySelectorAll('.tier-chip').forEach(c => c.setAttribute('aria-pressed', 'false'));
    refreshList();
  });

  // Sort
  document.getElementById('sort-select').addEventListener('change', e => {
    State.sortMode = e.target.value;
    refreshList();
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function init() {
  MapModule.init();
  setupTierChips();
  setupControls();

  try {
    const events = await fetchEvents();
    State.allEvents = events;

    // Derive authoritative methodology version from API response
    if (events.length > 0 && events[0].methodology_version) {
      const hdrMethodology = document.getElementById('hdr-methodology');
      if (hdrMethodology) {
        hdrMethodology.textContent = events[0].methodology_version;
      }
    }

    updateTierCounts(events);
    refreshList();

  } catch (err) {
    console.error('Failed to load events:', err);
    document.getElementById('list-loading').innerHTML = `
      <span style="font-size:1.4rem">⚠️</span>
      <span style="color:#ef4444;text-align:center">
        Could not reach ThermoGuard API.<br>
        <span style="color:var(--text-muted);font-size:0.75rem">Make sure the backend is running on <code style="font-family:monospace">localhost:8000</code>.</span>
      </span>`;
    showToast('Backend unreachable — start the FastAPI server on port 8000.', 'error', 8000);
    document.getElementById('hdr-event-count').textContent = 'API offline';
  }
}

document.addEventListener('DOMContentLoaded', init);
