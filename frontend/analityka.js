// Analityka — osobna podstrona (patrz frontend/analityka.html). Wykresy przez
// Chart.js (CDN, patrz <head> analityka.html). Wzorowana na strukturze
// mailer.js (zakładki, <input type="month"> zakresy, self-contained JS bez
// buildu) — ale bez żadnej wysyłki, same odczyty z /api/analytics/*.

const toast = document.getElementById("toast");
let toastTimer = null;

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

const PALETTE = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
  "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4338ca",
  "#0d9488", "#be123c", "#a16207",
];

function fmtMoney(v) {
  return `${v.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} zł`;
}

function monthValue(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

// Domyślny zakres dla całej strony: ostatnie 24 miesiące (włącznie z bieżącym).
function defaultRange() {
  const now = new Date();
  const toYear = now.getFullYear();
  const toMonth = now.getMonth() + 1;
  const idx = toYear * 12 + (toMonth - 1) - 23;
  const fromYear = Math.floor(idx / 12);
  const fromMonth = (idx % 12) + 1;
  return { fromYear, fromMonth, toYear, toMonth };
}

function setDefaultRange(fromEl, toEl) {
  const r = defaultRange();
  fromEl.value = monthValue(r.fromYear, r.fromMonth);
  toEl.value = monthValue(r.toYear, r.toMonth);
}

function parseMonthInput(inputEl) {
  const value = inputEl.value;
  if (!value) return null;
  const [year, month] = value.split("-").map(Number);
  return { year, month };
}

function parseMonthRange(fromEl, toEl) {
  const from = parseMonthInput(fromEl);
  const to = parseMonthInput(toEl);
  if (!from || !to) return null;
  return { year_from: from.year, month_from: from.month, year_to: to.year, month_to: to.month };
}

function monthLabel(year, month) {
  return `${String(month).padStart(2, "0")}/${year}`;
}

function qs(params) {
  return Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

// --- Zakładki ---

document.querySelectorAll(".mailer-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mailer-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".mailer-tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${btn.dataset.tab}`);
    });
  });
});

// --- Trend kosztów ---

const trendFromEl = document.getElementById("trend-month-from");
const trendToEl = document.getElementById("trend-month-to");
const trendStatus = document.getElementById("trend-status");
const trendForecastStatus = document.getElementById("trend-forecast-status");
const trendShowForecastEl = document.getElementById("trend-show-forecast");
const trendForecastMonthsEl = document.getElementById("trend-forecast-months");
let trendChart = null;

async function loadTrend() {
  const range = parseMonthRange(trendFromEl, trendToEl);
  if (!range) return;
  trendStatus.textContent = "Ładowanie...";
  trendForecastStatus.textContent = "";
  try {
    const res = await fetch(`/api/analytics/trend?${qs(range)}`);
    const data = await res.json();
    trendStatus.textContent =
      `Suma brutto: ${fmtMoney(data.total_brutto)} · Faktur: ${data.total_count}`;

    const labels = data.points.map((p) => monthLabel(p.year, p.month));
    const brutto = data.points.map((p) => p.brutto);

    const datasets = [{
      label: "Koszty brutto",
      data: brutto,
      borderColor: PALETTE[0],
      backgroundColor: PALETTE[0] + "33",
      fill: true,
      tension: 0.2,
    }];

    if (trendShowForecastEl.checked) {
      const monthsAhead = parseInt(trendForecastMonthsEl.value, 10) || 6;
      try {
        const fcRes = await fetch(`/api/analytics/forecast?${qs({ months_ahead: monthsAhead })}`);
        const fc = await fcRes.json();
        if (fc.forecast && fc.forecast.length && brutto.length) {
          fc.forecast.forEach((p) => labels.push(monthLabel(p.year, p.month)));
          // Kropkowana linia zaczyna się od ostatniego realnego punktu, żeby
          // wizualnie łączyła się z linią rzeczywistych kosztów.
          const forecastSeries = new Array(brutto.length - 1).fill(null);
          forecastSeries.push(brutto[brutto.length - 1]);
          fc.forecast.forEach((p) => forecastSeries.push(p.brutto));
          brutto.push(...new Array(fc.forecast.length).fill(null));

          datasets[0].data = brutto;
          datasets.push({
            label: "Prognoza (baseline)",
            data: forecastSeries,
            borderColor: PALETTE[0],
            borderDash: [6, 4],
            backgroundColor: "transparent",
            fill: false,
            tension: 0.2,
            pointStyle: "triangle",
          });
          trendForecastStatus.textContent =
            `Prognoza to prosty baseline (mediana + sezonowość), nie model ML — oparty o ${fc.history_months} mies. ciągłej historii.`;
        }
      } catch (e) {
        // Prognoza to dodatek — brak prognozy nie blokuje wykresu rzeczywistych kosztów.
      }
    }

    if (trendChart) trendChart.destroy();
    trendChart = new Chart(document.getElementById("trend-chart"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: datasets.length > 1 } },
        scales: { y: { beginAtZero: true } },
      },
    });
  } catch (e) {
    trendStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać trendu kosztów.", true);
  }
}

document.getElementById("btn-trend-refresh").addEventListener("click", loadTrend);

// --- Ranking kontrahentów ---

const kontrahenciFromEl = document.getElementById("kontrahenci-month-from");
const kontrahenciToEl = document.getElementById("kontrahenci-month-to");
const kontrahenciLimitEl = document.getElementById("kontrahenci-limit");
const kontrahenciDzialSelect = document.getElementById("kontrahenci-dzial-select");
const kontrahenciStatus = document.getElementById("kontrahenci-status");
const kontrahenciTableEl = document.getElementById("kontrahenci-table");
let kontrahenciChart = null;

function renderKontrahenciTable(items) {
  kontrahenciTableEl.innerHTML = "";
  if (!items.length) return;
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Kontrahent</th><th>Faktur</th><th>Suma brutto</th><th>%</th></tr></thead>";
  const tbody = document.createElement("tbody");
  items.forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.kontrahent}</td><td>${it.count}</td><td>${fmtMoney(it.brutto)}</td><td>${it.pct}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  kontrahenciTableEl.appendChild(table);
}

async function loadKontrahenci() {
  const range = parseMonthRange(kontrahenciFromEl, kontrahenciToEl);
  if (!range) return;
  const limit = parseInt(kontrahenciLimitEl.value, 10) || 15;
  const dzial = kontrahenciDzialSelect.value || null;
  kontrahenciStatus.textContent = "Ładowanie...";
  try {
    const res = await fetch(`/api/analytics/kontrahenci?${qs({ ...range, limit, dzial })}`);
    const data = await res.json();
    const dzialLabel = dzial ? ` · dział: ${dzial}` : "";
    kontrahenciStatus.textContent =
      `Suma brutto (cały okres${dzialLabel}): ${fmtMoney(data.total_brutto)} · TOP ${data.items.length} pokazane na wykresie`;

    const labels = data.items.map((it) => it.kontrahent);
    const values = data.items.map((it) => it.brutto);

    if (kontrahenciChart) kontrahenciChart.destroy();
    kontrahenciChart = new Chart(document.getElementById("kontrahenci-chart"), {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Suma brutto", data: values, backgroundColor: PALETTE[1] }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });

    renderKontrahenciTable(data.items);
  } catch (e) {
    kontrahenciStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać rankingu kontrahentów.", true);
  }
}

document.getElementById("btn-kontrahenci-refresh").addEventListener("click", () => {
  loadDzialyOptionsInto(kontrahenciDzialSelect, kontrahenciFromEl, kontrahenciToEl);
  loadKontrahenci();
});

// --- Struktura wg działu ---

const dzialyFromEl = document.getElementById("dzialy-month-from");
const dzialyToEl = document.getElementById("dzialy-month-to");
const dzialyStatus = document.getElementById("dzialy-status");
const dzialyTableEl = document.getElementById("dzialy-table");
let dzialyChart = null;

function renderDzialyTable(series, totalBrutto) {
  dzialyTableEl.innerHTML = "";
  if (!series.length) return;
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Dział</th><th>Suma brutto (okres)</th><th>%</th></tr></thead>";
  const tbody = document.createElement("tbody");
  series.forEach((s) => {
    const pct = totalBrutto ? ((s.total / totalBrutto) * 100).toFixed(1) : "0.0";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.dzial}</td><td>${fmtMoney(s.total)}</td><td>${pct}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  dzialyTableEl.appendChild(table);
}

async function loadDzialyTrend() {
  const range = parseMonthRange(dzialyFromEl, dzialyToEl);
  if (!range) return;
  dzialyStatus.textContent = "Ładowanie...";
  try {
    const res = await fetch(`/api/analytics/dzialy-trend?${qs(range)}`);
    const data = await res.json();
    const totalBrutto = data.series.reduce((sum, s) => sum + s.total, 0);
    dzialyStatus.textContent = `Suma brutto (cały okres): ${fmtMoney(totalBrutto)} · Działów: ${data.series.length}`;

    const labels = data.months.map((m) => monthLabel(m.year, m.month));
    const datasets = data.series.map((s, i) => ({
      label: s.dzial,
      data: s.values,
      backgroundColor: PALETTE[i % PALETTE.length],
    }));

    if (dzialyChart) dzialyChart.destroy();
    dzialyChart = new Chart(document.getElementById("dzialy-chart"), {
      type: "bar",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true },
        },
      },
    });

    renderDzialyTable(data.series, totalBrutto);
  } catch (e) {
    dzialyStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać struktury wg działu.", true);
  }
}

document.getElementById("btn-dzialy-refresh").addEventListener("click", loadDzialyTrend);

// --- Kategorie (+ drill-down do podkategorii) ---

const kategorieFromEl = document.getElementById("kategorie-month-from");
const kategorieToEl = document.getElementById("kategorie-month-to");
const kategorieDzialSelect = document.getElementById("kategorie-dzial-select");
const kategorieStatus = document.getElementById("kategorie-status");
const kategorieTableEl = document.getElementById("kategorie-table");
const podkategorieBlock = document.getElementById("podkategorie-block");
const podkategorieLabel = document.getElementById("podkategorie-kategoria-label");
const podkategorieTableEl = document.getElementById("podkategorie-table");
let kategorieChart = null;
let podkategorieChart = null;

async function loadDzialyOptionsInto(selectEl, fromEl, toEl) {
  const range = parseMonthRange(fromEl, toEl);
  if (!range) return;
  try {
    const res = await fetch(`/api/mailer/monthly/dzialy?${qs(range)}`);
    const dzialy = await res.json();
    const current = selectEl.value;
    selectEl.innerHTML = '<option value="">— wszystkie —</option>';
    dzialy.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      selectEl.appendChild(opt);
    });
    selectEl.value = current;
  } catch (e) {
    // Lista działów to tylko wygoda filtrowania — brak listy nie blokuje reszty zakładki.
  }
}

function renderKategorieTable(items) {
  kategorieTableEl.innerHTML = "";
  if (!items.length) return;
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Kategoria</th><th>Faktur</th><th>Suma brutto</th><th>%</th><th></th></tr></thead>";
  const tbody = document.createElement("tbody");
  items.forEach((it) => {
    const tr = document.createElement("tr");
    const btnCell = it.kategoria === "(brak kategorii)"
      ? ""
      : `<button type="button" class="btn an-drill-btn" data-kategoria="${it.kategoria}">Podkategorie →</button>`;
    tr.innerHTML = `<td>${it.kategoria}</td><td>${it.count}</td><td>${fmtMoney(it.brutto)}</td><td>${it.pct}%</td><td>${btnCell}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  kategorieTableEl.appendChild(table);

  tbody.querySelectorAll(".an-drill-btn").forEach((btn) => {
    btn.addEventListener("click", () => loadPodkategorie(btn.dataset.kategoria));
  });
}

async function loadKategorie() {
  const range = parseMonthRange(kategorieFromEl, kategorieToEl);
  if (!range) return;
  const dzial = kategorieDzialSelect.value || null;
  kategorieStatus.textContent = "Ładowanie...";
  podkategorieBlock.style.display = "none";
  try {
    const res = await fetch(`/api/analytics/kategorie?${qs({ ...range, dzial })}`);
    const data = await res.json();

    // "(brak kategorii)" bywa największą pozycją i na wspólnej skali
    // spłaszcza wszystkie pozostałe słupki do zera — zostaje w tabeli, ale
    // nie wchodzi na wykres, żeby reszta kategorii była w ogóle czytelna.
    const brakKategorii = data.items.find((it) => it.kategoria === "(brak kategorii)");
    const chartItems = data.items.filter((it) => it.kategoria !== "(brak kategorii)");

    kategorieStatus.textContent = `Suma brutto: ${fmtMoney(data.total_brutto)}` +
      (brakKategorii ? ` · bez kategorii: ${brakKategorii.pct}%` : "");

    const labels = chartItems.map((it) => it.kategoria);
    const values = chartItems.map((it) => it.brutto);

    if (kategorieChart) kategorieChart.destroy();
    kategorieChart = new Chart(document.getElementById("kategorie-chart"), {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Suma brutto", data: values, backgroundColor: PALETTE[2] }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });

    renderKategorieTable(data.items);
  } catch (e) {
    kategorieStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać podziału na kategorie.", true);
  }
}

async function loadPodkategorie(kategoria) {
  const range = parseMonthRange(kategorieFromEl, kategorieToEl);
  if (!range) return;
  const dzial = kategorieDzialSelect.value || null;
  podkategorieLabel.textContent = kategoria;
  podkategorieBlock.style.display = "";
  try {
    const res = await fetch(`/api/analytics/podkategorie?${qs({ ...range, dzial, kategoria })}`);
    const data = await res.json();

    const labels = data.items.map((it) => it.podkategoria);
    const values = data.items.map((it) => it.brutto);

    if (podkategorieChart) podkategorieChart.destroy();
    podkategorieChart = new Chart(document.getElementById("podkategorie-chart"), {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Suma brutto", data: values, backgroundColor: PALETTE[3] }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });

    podkategorieTableEl.innerHTML = "";
    const table = document.createElement("table");
    table.className = "dzial-breakdown-table";
    table.innerHTML = "<thead><tr><th>Podkategoria</th><th>Faktur</th><th>Suma brutto</th><th>%</th></tr></thead>";
    const tbody = document.createElement("tbody");
    data.items.forEach((it) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${it.podkategoria}</td><td>${it.count}</td><td>${fmtMoney(it.brutto)}</td><td>${it.pct}%</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    podkategorieTableEl.appendChild(table);
    podkategorieBlock.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    showToast("Nie udało się pobrać podkategorii.", true);
  }
}

document.getElementById("btn-kategorie-refresh").addEventListener("click", () => {
  loadDzialyOptionsInto(kategorieDzialSelect, kategorieFromEl, kategorieToEl);
  loadKategorie();
});

// --- Start ---

setDefaultRange(trendFromEl, trendToEl);
setDefaultRange(kontrahenciFromEl, kontrahenciToEl);
setDefaultRange(dzialyFromEl, dzialyToEl);
setDefaultRange(kategorieFromEl, kategorieToEl);

loadTrend();
loadDzialyOptionsInto(kontrahenciDzialSelect, kontrahenciFromEl, kontrahenciToEl).then(loadKontrahenci);
loadDzialyTrend();
loadDzialyOptionsInto(kategorieDzialSelect, kategorieFromEl, kategorieToEl).then(loadKategorie);
