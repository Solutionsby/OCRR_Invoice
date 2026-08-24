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
// Leniwe ładowanie: każda zakładka dociąga swoje dane dopiero przy PIERWSZYM
// kliknięciu, nie przy starcie strony. Wcześniej wszystkie 7 zakładek
// (Przegląd sama w sobie robi 6 zapytań) odpytywały bazę równolegle od razu
// po otwarciu strony — kilkanaście zapytań naraz, część cross-database do
// Przychody, co realnie spowalniało pierwsze wejście. `TAB_LOADERS`
// odwołuje się do funkcji `load*` zdefiniowanych niżej w pliku — bezpieczne,
// bo to `async function` (hoisted) wołane dopiero przy kliknięciu, długo po
// tym jak cały skrypt się już wykonał. Przegląd nie ma tu wpisu — ładuje się
// eagerly w sekcji Start, bo to domyślna aktywna zakładka.
const TAB_LOADERS = {
  trend: () => loadTrend(),
  kontrahenci: () => loadDzialyOptionsInto(kontrahenciDzialSelect, kontrahenciFromEl, kontrahenciToEl).then(loadKontrahenci),
  dzialy: () => loadDzialyTrend(),
  kategorie: () => loadDzialyOptionsInto(kategorieDzialSelect, kategorieFromEl, kategorieToEl).then(loadKategorie),
  dochod: () => loadDochod(),
  "dochod-trend": () => loadDochodTrend(),
};
const loadedTabs = new Set();

document.querySelectorAll(".mailer-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mailer-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".mailer-tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${btn.dataset.tab}`);
    });
    const tab = btn.dataset.tab;
    if (!loadedTabs.has(tab) && TAB_LOADERS[tab]) {
      loadedTabs.add(tab);
      TAB_LOADERS[tab]();
    }
  });
});

// --- Przegląd (dashboard — karty z najważniejszymi liczbami) ---
// Celowo bez nowych endpointów — reużywa te same zapytania co inne zakładki
// i podsumowuje w kartach. Zapytania kosztowe (Faktury) lecą równolegle,
// zapytania dotykające Przychody (cross-database) po kolei — patrz komentarz
// w loadPrzeglad().

const przegladStatus = document.getElementById("przeglad-status");
const przegladCardsEl = document.getElementById("przeglad-cards");

function shiftMonth(year, month, delta) {
  const idx = year * 12 + (month - 1) + delta;
  return { year: Math.floor(idx / 12), month: (idx % 12) + 1 };
}

function przegladCard(title, bodyHtml) {
  const card = document.createElement("div");
  card.className = "an-dochod-card";
  card.innerHTML = `<h4>${title}</h4>${bodyHtml}`;
  return card;
}

function statLine(label, value, cls) {
  return `<p><span>${label}</span><span class="an-dochod-value ${cls || ""}">${value}</span></p>`;
}

async function loadPrzeglad() {
  przegladStatus.textContent = "Ładowanie...";
  przegladCardsEl.innerHTML = "";
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth() + 1;
  const prev = shiftMonth(y, m, -1);
  const dzialyParam = DOCHOD_NAMED_DZIALY.join(",");

  try {
    // Zapytania czysto kosztowe (Faktury, bez cross-database) są bezpieczne
    // równolegle. Zapytania dotykające Przychody (cross-database, SQL Server
    // odpytuje przez to bazy źródłowe innych działów) NIE są — potwierdzone
    // na żywo: dwa jednoczesne zapytania cross-database dały connection
    // reset (10054) z serwera. Te trzy lecą więc po kolei, nie w Promise.all.
    const [trendMM, trendCyk, trendJed] = await Promise.all([
      fetch(`/api/analytics/trend?${qs({ year_from: prev.year, month_from: prev.month, year_to: y, month_to: m })}`).then((r) => r.json()),
      fetch(`/api/analytics/trend?${qs({ year_from: y, month_from: 1, year_to: y, month_to: m, cykliczna: "true" })}`).then((r) => r.json()),
      fetch(`/api/analytics/trend?${qs({ year_from: y, month_from: 1, year_to: y, month_to: m, cykliczna: "false" })}`).then((r) => r.json()),
    ]);
    const dochodMiesiac = await fetch(`/api/analytics/dochod?${qs({ year_from: y, month_from: m, year_to: y, month_to: m })}`).then((r) => r.json());
    const dochodYtd = await fetch(`/api/analytics/dochod?${qs({ year_from: y, month_from: 1, year_to: y, month_to: m })}`).then((r) => r.json());
    const fcTotal = await fetch(`/api/analytics/dochod-forecast-total?${qs({ dzialy: dzialyParam, months_ahead: 1 })}`).then((r) => r.json());

    przegladStatus.textContent = "";

    // 1) Ten miesiąc — cała firma (suma 6 brandów)
    const brandyMiesiac = dochodMiesiac.items.filter((i) => DOCHOD_NAMED_DZIALY.includes(i.dzial));
    const kosztM = brandyMiesiac.reduce((s, i) => s + i.koszt_netto, 0);
    const przychodM = brandyMiesiac.reduce((s, i) => s + (i.przychod_netto || 0), 0);
    const dochodM = brandyMiesiac.reduce((s, i) => s + i.dochod, 0);
    const marzaM = przychodM ? Math.round((dochodM / przychodM) * 1000) / 10 : null;
    przegladCardsEl.appendChild(przegladCard(
      `${MONTH_LABELS_PL[m - 1]} ${y} — cała firma`,
      statLine("Przychód netto", fmtMoney(przychodM)) +
      statLine("Koszt netto", fmtMoney(kosztM)) +
      statLine("Dochód", fmtDochod(dochodM), dochodM >= 0 ? "positive" : "negative") +
      (marzaM !== null ? statLine("Marża", `${marzaM >= 0 ? "+" : ""}${marzaM}%`, dochodM >= 0 ? "positive" : "negative") : "") +
      // Przychód bywa wpisywany zbiorczo na początku miesiąca, koszt spływa z
      // opóźnieniem (OCR faktur) — dochód bieżącego miesiąca może wyglądać
      // sztucznie dobrze, dopóki miesiąc się nie zamknie księgowo.
      `<p class="muted an-warning">Koszt bieżącego miesiąca bywa niekompletny (faktury spływają z opóźnieniem) — dochód może być zawyżony.</p>`,
    ));

    // 2) Prognoza na najbliższy miesiąc (baseline, nie ML — patrz zakładka Trend/Trend wg działu)
    const fcP = fcTotal.przychod.forecast[0];
    const fcD = fcTotal.dochod.forecast[0];
    if (fcP && fcD) {
      przegladCardsEl.appendChild(przegladCard(
        `Prognoza — ${MONTH_LABELS_PL[fcP.month - 1]} ${fcP.year}`,
        statLine("Przychód (prognoza)", fmtMoney(fcP.value)) +
        statLine("Dochód (prognoza)", fmtDochod(fcD.value), fcD.value >= 0 ? "positive" : "negative"),
      ));
    }

    // 3) Koszty — zmiana miesiąc do miesiąca
    const lastPt = trendMM.points[trendMM.points.length - 1];
    const prevPt = trendMM.points.find((p) => p.year === prev.year && p.month === prev.month);
    if (lastPt && prevPt) {
      const diffPct = prevPt.brutto ? Math.round(((lastPt.brutto - prevPt.brutto) / prevPt.brutto) * 1000) / 10 : null;
      const arrow = diffPct === null ? "" : diffPct >= 0 ? "▲ " : "▼ ";
      przegladCardsEl.appendChild(przegladCard(
        "Koszty — zmiana m/m",
        statLine(`${MONTH_LABELS_PL[lastPt.month - 1]} ${lastPt.year}`, fmtMoney(lastPt.brutto)) +
        statLine(`${MONTH_LABELS_PL[prevPt.month - 1]} ${prevPt.year}`, fmtMoney(prevPt.brutto)) +
        (diffPct !== null
          ? statLine("Zmiana", `${arrow}${diffPct >= 0 ? "+" : ""}${diffPct}%`, diffPct >= 0 ? "negative" : "positive")
          : ""),
      ));
    }

    // 4) Cykliczne vs jednorazowe (rok bieżący, od stycznia do dziś)
    const cyk = trendCyk.total_brutto, jed = trendJed.total_brutto;
    const suma = cyk + jed;
    const cykPct = suma ? Math.round((cyk / suma) * 1000) / 10 : null;
    przegladCardsEl.appendChild(przegladCard(
      `Cykliczne vs jednorazowe (${y}, od początku roku)`,
      statLine("Cykliczne", `${fmtMoney(cyk)}${cykPct !== null ? ` (${cykPct}%)` : ""}`) +
      statLine("Jednorazowe", fmtMoney(jed)),
    ));

    // 5) Ranking brandów (od początku roku do dziś)
    const brandyYtd = dochodYtd.items
      .filter((i) => DOCHOD_NAMED_DZIALY.includes(i.dzial))
      .sort((a, b) => b.dochod - a.dochod);
    const rankingHtml = brandyYtd
      .map((i) => statLine(i.dzial, fmtDochod(i.dochod), i.dochod >= 0 ? "positive" : "negative"))
      .join("");
    przegladCardsEl.appendChild(przegladCard(`Ranking brandów — dochód ${y} (od początku roku)`, rankingHtml));

    // 6) Uwagi — dynamiczne, tylko gdy jest o czym wspomnieć (niekompletność
    // bieżącego miesiąca jest już zaznaczona bezpośrednio przy karcie 1)
    const brakPrzychoduBrandy = dochodYtd.dzialy_bez_przychodu.filter((d) => DOCHOD_NAMED_DZIALY.includes(d));
    const uwagi = [];
    if (brakPrzychoduBrandy.length) uwagi.push(`Brak śledzonego przychodu: ${brakPrzychoduBrandy.join(", ")}.`);
    przegladCardsEl.appendChild(przegladCard(
      "Uwagi",
      uwagi.length ? uwagi.map((u) => `<p class="muted">${u}</p>`).join("") : `<p class="muted">Brak uwag.</p>`,
    ));
  } catch (e) {
    przegladStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać przeglądu.", true);
  }
}

document.getElementById("btn-przeglad-refresh").addEventListener("click", loadPrzeglad);

// --- Trend kosztów ---

const trendFromEl = document.getElementById("trend-month-from");
const trendToEl = document.getElementById("trend-month-to");
const trendCyklicznaEl = document.getElementById("trend-cykliczna-select");
const trendStatus = document.getElementById("trend-status");
const trendForecastStatus = document.getElementById("trend-forecast-status");
const trendShowForecastEl = document.getElementById("trend-show-forecast");
const trendForecastMonthsEl = document.getElementById("trend-forecast-months");
let trendChart = null;

async function loadTrend() {
  const range = parseMonthRange(trendFromEl, trendToEl);
  if (!range) return;
  const cykliczna = trendCyklicznaEl.value;
  trendStatus.textContent = "Ładowanie...";
  trendForecastStatus.textContent = "";
  try {
    const res = await fetch(`/api/analytics/trend?${qs({ ...range, cykliczna })}`);
    const data = await res.json();
    const rodzajLabel = cykliczna === "true" ? " (cykliczne)" : cykliczna === "false" ? " (jednorazowe)" : "";
    trendStatus.textContent =
      `Suma brutto${rodzajLabel}: ${fmtMoney(data.total_brutto)} · Faktur: ${data.total_count}`;

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
        const fcRes = await fetch(`/api/analytics/forecast?${qs({ months_ahead: monthsAhead, cykliczna })}`);
        const fc = await fcRes.json();
        if (fc.forecast && fc.forecast.length && brutto.length) {
          // Backend prognozuje na nowo bieżący (niedokończony) miesiąc jako
          // PIERWSZY punkt prognozy — to ta sama etykieta co ostatni realny
          // punkt (patrz core/analytics.get_spend_forecast), nie nowy słupek.
          // Bez tego rozróżnienia front dokładał duplikat etykiety miesiąca
          // i przesuwał całą resztę prognozy o jedną pozycję.
          const lastPoint = data.points[data.points.length - 1];
          let forecastPoints = fc.forecast;
          const forecastSeries = new Array(brutto.length - 1).fill(null);

          if (lastPoint && forecastPoints[0].year === lastPoint.year && forecastPoints[0].month === lastPoint.month) {
            forecastSeries.push(forecastPoints[0].brutto);
            forecastPoints = forecastPoints.slice(1);
          } else {
            // Normalny przypadek (ostatni widoczny miesiąc jest kompletny):
            // kropkowana linia zaczyna się od ostatniego realnego punktu,
            // żeby wizualnie łączyła się z linią rzeczywistych kosztów.
            forecastSeries.push(brutto[brutto.length - 1]);
          }

          forecastPoints.forEach((p) => {
            labels.push(monthLabel(p.year, p.month));
            forecastSeries.push(p.brutto);
            brutto.push(null);
          });

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
const kategorieCyklicznaSelect = document.getElementById("kategorie-cykliczna-select");
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
  const cykliczna = kategorieCyklicznaSelect.value;
  kategorieStatus.textContent = "Ładowanie...";
  podkategorieBlock.style.display = "none";
  try {
    const res = await fetch(`/api/analytics/kategorie?${qs({ ...range, dzial, cykliczna })}`);
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
  const cykliczna = kategorieCyklicznaSelect.value;
  podkategorieLabel.textContent = kategoria;
  podkategorieBlock.style.display = "";
  try {
    const res = await fetch(`/api/analytics/podkategorie?${qs({ ...range, dzial, cykliczna, kategoria })}`);
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

// --- Dochód (koszt vs przychód wg działu) ---

const dochodFromEl = document.getElementById("dochod-month-from");
const dochodToEl = document.getElementById("dochod-month-to");
const dochodStatus = document.getElementById("dochod-status");
const dochodWarning = document.getElementById("dochod-warning");
const dochodBrandsTotalEl = document.getElementById("dochod-brands-total");
const dochodCardsEl = document.getElementById("dochod-cards");
const dochodTableEl = document.getElementById("dochod-table");

// Te działy dostają własną, osobną kartę bilansu — reszta ląduje zbiorczo w
// tabeli "Pozostałe działy" poniżej. Kolejność jak podana przez użytkownika.
const DOCHOD_NAMED_DZIALY = ["CornerMarket", "Hotel", "RDS", "Gastronomia", "Automaty", "Wspólne"];

// Rzetelna, ciągła historia kosztów zaczyna się dopiero w 2024-01 (patrz
// prognoza — wcześniejsze lata mają tylko pojedyncze, odosobnione wpisy).
// Dochód liczony za lata sprzed tego progu zaniża koszty i sztucznie zawyża
// wynik, więc to jest domyślny "Od" dla tej zakładki (nie "ostatnie 24
// miesiące" jak gdzie indziej) — a ostrzeżenie w loadDochod() łapie ręczne
// cofnięcie zakresu przed tę datę.
const DOCHOD_MIN_YEAR = 2024, DOCHOD_MIN_MONTH = 1;

function fmtDochod(v) {
  const sign = v > 0 ? "+" : "";
  return `${sign}${fmtMoney(v)}`;
}

function dochodCardBodyHtml(kosztNetto, przychodNetto, dochod, marzaPct) {
  const przychod = przychodNetto === null ? "—" : fmtMoney(przychodNetto);
  const cls = dochod >= 0 ? "positive" : "negative";
  const marzaHtml = marzaPct === null || marzaPct === undefined
    ? ""
    : `<p><span>Marża</span><span class="an-dochod-value ${cls}">${marzaPct >= 0 ? "+" : ""}${marzaPct}%</span></p>`;
  return (
    `<p><span>Koszt netto</span><span class="an-dochod-value">${fmtMoney(kosztNetto)}</span></p>` +
    `<p><span>Przychód netto</span><span class="an-dochod-value">${przychod}</span></p>` +
    `<p><span>Dochód</span><span class="an-dochod-value ${cls}">${fmtDochod(dochod)}</span></p>` +
    marzaHtml
  );
}

function renderDochodCards(items) {
  dochodCardsEl.innerHTML = "";
  // Od najlepszego do najgorszego dochodu — brandy bez faktur w ogóle (brak
  // pozycji, nie 0 zł dochodu) lądują na końcu, bo nie da się ich porównać.
  const sorted = [...DOCHOD_NAMED_DZIALY].sort((a, b) => {
    const ia = items.find((i) => i.dzial === a);
    const ib = items.find((i) => i.dzial === b);
    if (!ia && !ib) return 0;
    if (!ia) return 1;
    if (!ib) return -1;
    return ib.dochod - ia.dochod;
  });

  sorted.forEach((dzial) => {
    const it = items.find((i) => i.dzial === dzial);
    const card = document.createElement("div");
    card.className = "an-dochod-card";
    if (!it) {
      card.innerHTML = `<h4>${dzial}</h4><p class="muted">Brak faktur w wybranym okresie.</p>`;
      dochodCardsEl.appendChild(card);
      return;
    }
    card.innerHTML = `<h4>${dzial}</h4>` + dochodCardBodyHtml(it.koszt_netto, it.przychod_netto, it.dochod, it.marza_pct);
    dochodCardsEl.appendChild(card);
  });
}

// Suma WSZYSTKICH 6 nazwanych brandów — brak śledzonego przychodu liczy się
// jako 0 (patrz core/analytics.get_dochod), więc dochod tu zawsze jest
// liczbą i sumuje się wprost, bez pomijania brandów bez przychodu.
function renderDochodBrandsTotal(items) {
  dochodBrandsTotalEl.innerHTML = "";
  const brandy = items.filter((i) => DOCHOD_NAMED_DZIALY.includes(i.dzial));
  if (!brandy.length) {
    dochodBrandsTotalEl.innerHTML = `<p class="muted">Brak danych dla 6 głównych brandów w wybranym okresie.</p>`;
    return;
  }
  const koszt = brandy.reduce((s, i) => s + i.koszt_netto, 0);
  const przychod = brandy.reduce((s, i) => s + (i.przychod_netto || 0), 0);
  const dochod = brandy.reduce((s, i) => s + i.dochod, 0);
  const zPrzychodem = brandy.filter((i) => i.przychod_netto !== null).length;
  const marzaPct = przychod ? Math.round((dochod / przychod) * 1000) / 10 : null;

  const card = document.createElement("div");
  card.className = "an-dochod-card an-dochod-card-total";
  card.innerHTML =
    `<h4>Brandy łącznie — wszystkie ${DOCHOD_NAMED_DZIALY.length} (przychód znany dla ${zPrzychodem}, reszta liczona z 0 zł przychodu)</h4>` +
    dochodCardBodyHtml(koszt, przychod, dochod, marzaPct);
  dochodBrandsTotalEl.appendChild(card);
}

function renderDochodTable(items) {
  dochodTableEl.innerHTML = "";
  if (!items.length) return;
  // Te działy nie generują (i nie będą generować) przychodu — pokazujemy
  // tylko koszt, posortowany malejąco (od największych do najmniejszych).
  const sorted = [...items].sort((a, b) => b.koszt_netto - a.koszt_netto);

  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Dział</th><th>Koszt netto</th></tr></thead>";
  const tbody = document.createElement("tbody");
  sorted.forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.dzial}</td><td>${fmtMoney(it.koszt_netto)}</td>`;
    tbody.appendChild(tr);
  });

  const totalKoszt = sorted.reduce((s, i) => s + i.koszt_netto, 0);
  const totalTr = document.createElement("tr");
  totalTr.innerHTML = `<td><strong>Suma (${sorted.length})</strong></td><td><strong>${fmtMoney(totalKoszt)}</strong></td>`;
  tbody.appendChild(totalTr);

  table.appendChild(tbody);
  dochodTableEl.appendChild(table);
}

async function loadDochod() {
  const range = parseMonthRange(dochodFromEl, dochodToEl);
  if (!range) return;
  dochodStatus.textContent = "Ładowanie...";
  dochodWarning.textContent = "";
  dochodWarning.className = "muted";
  try {
    const res = await fetch(`/api/analytics/dochod?${qs(range)}`);
    const data = await res.json();
    dochodStatus.textContent = "";

    if (range.year_from < DOCHOD_MIN_YEAR || (range.year_from === DOCHOD_MIN_YEAR && range.month_from < DOCHOD_MIN_MONTH)) {
      dochodWarning.textContent =
        `Uwaga: przed 01/${DOCHOD_MIN_YEAR} historia kosztów w bazie jest niekompletna (pojedyncze, odosobnione wpisy) — ` +
        `dochód za ten okres będzie zawyżony.`;
      dochodWarning.className = "muted an-warning";
    }

    renderDochodBrandsTotal(data.items);
    renderDochodCards(data.items);
    renderDochodTable(data.items.filter((it) => !DOCHOD_NAMED_DZIALY.includes(it.dzial)));
  } catch (e) {
    dochodStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać zestawienia dochodu.", true);
  }
}

document.getElementById("btn-dochod-refresh").addEventListener("click", loadDochod);

// --- Trend wg działu (porównanie lat) ---

const dochodTrendDzialSelect = document.getElementById("dochod-trend-dzial-select");
const dochodTrendFromEl = document.getElementById("dochod-trend-month-from");
const dochodTrendToEl = document.getElementById("dochod-trend-month-to");
const dochodTrendStatus = document.getElementById("dochod-trend-status");
const dochodTrendWarning = document.getElementById("dochod-trend-warning");
const dochodTrendForecastStatus = document.getElementById("dochod-trend-forecast-status");
const dochodTrendShowForecastEl = document.getElementById("dochod-trend-show-forecast");
const dochodTrendForecastMonthsEl = document.getElementById("dochod-trend-forecast-months");
let dochodTrendPrzychodChart = null;
let dochodTrendDochodChart = null;

const MONTH_LABELS_PL = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];
const DOCHOD_TREND_ALL_SENTINEL = "__ALL__";

(() => {
  const optAll = document.createElement("option");
  optAll.value = DOCHOD_TREND_ALL_SENTINEL;
  optAll.textContent = "— Wszystkie brandy (suma) —";
  dochodTrendDzialSelect.appendChild(optAll);
})();
DOCHOD_NAMED_DZIALY.forEach((dzial) => {
  const opt = document.createElement("option");
  opt.value = dzial;
  opt.textContent = dzial;
  dochodTrendDzialSelect.appendChild(opt);
});

// Ostatni realny punkt bieżącego roku + wartości z prognozy (tylko te
// mieszczące się w bieżącym roku — miesiące przyszłego roku pomijamy, żeby
// nie komplikować wykresu osobną, przyszłoroczną serią) → 12-elementowa
// tablica do doklejenia jako kropkowana linia, wizualnie łącząca się z
// ciągłą linią bieżącego roku.
function buildForecastOverlay(currentYearValues, forecastPoints, currentYear) {
  const overlay = new Array(12).fill(null);
  let lastIdx = -1;
  for (let i = 0; i < 12; i++) {
    if (currentYearValues[i] !== null && currentYearValues[i] !== undefined) lastIdx = i;
  }
  if (lastIdx >= 0) overlay[lastIdx] = currentYearValues[lastIdx];
  forecastPoints.forEach((p) => {
    if (p.year === currentYear) overlay[p.month - 1] = p.value;
  });
  return overlay;
}

// Lata przeszłe jako słupki (łatwo porównać poziomy obok siebie), bieżący
// rok jako linia na wierzchu (widać "gdzie jesteśmy" na tle historii),
// opcjonalnie doklejona kropkowana prognoza tego samego koloru.
function renderYearComparisonChart(canvasId, existingChart, years, seriesByYear, forecastOverlay) {
  const currentYear = new Date().getFullYear();
  const datasets = seriesByYear.map((s, i) => {
    const isCurrent = s.year === currentYear;
    const color = PALETTE[i % PALETTE.length];
    return {
      type: isCurrent ? "line" : "bar",
      label: String(s.year),
      data: s.values,
      borderColor: color,
      backgroundColor: isCurrent ? "transparent" : color + "aa",
      borderWidth: isCurrent ? 3 : 1,
      spanGaps: true,
      tension: 0.2,
      order: isCurrent ? 0 : 1,
    };
  });

  if (forecastOverlay) {
    const currentColorIdx = seriesByYear.findIndex((s) => s.year === currentYear);
    const color = PALETTE[(currentColorIdx >= 0 ? currentColorIdx : 0) % PALETTE.length];
    datasets.push({
      type: "line",
      label: `${currentYear} (prognoza)`,
      data: forecastOverlay,
      borderColor: color,
      borderDash: [6, 4],
      backgroundColor: "transparent",
      borderWidth: 2,
      spanGaps: true,
      tension: 0.2,
      pointStyle: "triangle",
      order: -1,
    });
  }

  if (existingChart) existingChart.destroy();
  return new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels: MONTH_LABELS_PL, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

async function loadDochodTrend() {
  const range = parseMonthRange(dochodTrendFromEl, dochodTrendToEl);
  if (!range) return;
  const dzial = dochodTrendDzialSelect.value;
  const isAll = dzial === DOCHOD_TREND_ALL_SENTINEL;
  const dzialyParam = DOCHOD_NAMED_DZIALY.join(",");
  const currentYear = new Date().getFullYear();
  dochodTrendStatus.textContent = "Ładowanie...";
  dochodTrendWarning.textContent = "";
  dochodTrendWarning.className = "muted";
  dochodTrendForecastStatus.textContent = "";
  try {
    const trendUrl = isAll
      ? `/api/analytics/dochod-trend-total?${qs({ ...range, dzialy: dzialyParam })}`
      : `/api/analytics/dochod-trend?${qs({ ...range, dzial })}`;
    const res = await fetch(trendUrl);
    const data = await res.json();
    dochodTrendStatus.textContent = data.years.length
      ? `Lata w danych: ${data.years.join(", ")}`
      : "Brak danych dla wybranego działu i okresu.";

    if (range.year_from < DOCHOD_MIN_YEAR || (range.year_from === DOCHOD_MIN_YEAR && range.month_from < DOCHOD_MIN_MONTH)) {
      dochodTrendWarning.textContent =
        `Uwaga: przed 01/${DOCHOD_MIN_YEAR} historia kosztów w bazie jest niekompletna — dochód za wcześniejsze ` +
        `lata będzie zawyżony (przychód netto powyżej nie jest tym dotknięty, liczony jest niezależnie od kosztów).`;
      dochodTrendWarning.className = "muted an-warning";
    }

    let przychodOverlay = null;
    let dochodOverlay = null;
    if (dochodTrendShowForecastEl.checked) {
      const monthsAhead = parseInt(dochodTrendForecastMonthsEl.value, 10) || 4;
      try {
        const fcUrl = isAll
          ? `/api/analytics/dochod-forecast-total?${qs({ dzialy: dzialyParam, months_ahead: monthsAhead })}`
          : `/api/analytics/dochod-forecast?${qs({ dzial, months_ahead: monthsAhead })}`;
        const fcRes = await fetch(fcUrl);
        const fc = await fcRes.json();
        const przychodCurrent = data.przychod_by_year.find((s) => s.year === currentYear);
        const dochodCurrent = data.dochod_by_year.find((s) => s.year === currentYear);
        if (przychodCurrent) przychodOverlay = buildForecastOverlay(przychodCurrent.values, fc.przychod.forecast, currentYear);
        if (dochodCurrent) dochodOverlay = buildForecastOverlay(dochodCurrent.values, fc.dochod.forecast, currentYear);
        dochodTrendForecastStatus.textContent =
          `Prognoza to prosty baseline (mediana + sezonowość), nie model ML — przychód oparty o ` +
          `${fc.przychod.history_months} mies. historii, dochód o ${fc.dochod.history_months} mies.`;
      } catch (e) {
        // Prognoza to dodatek — brak prognozy nie blokuje wykresów rzeczywistych danych.
      }
    }

    dochodTrendPrzychodChart = renderYearComparisonChart(
      "dochod-trend-przychod-chart", dochodTrendPrzychodChart, data.years, data.przychod_by_year, przychodOverlay,
    );
    dochodTrendDochodChart = renderYearComparisonChart(
      "dochod-trend-dochod-chart", dochodTrendDochodChart, data.years, data.dochod_by_year, dochodOverlay,
    );
  } catch (e) {
    dochodTrendStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać trendu wg działu.", true);
  }
}

document.getElementById("btn-dochod-trend-refresh").addEventListener("click", loadDochodTrend);

// --- Trafność prognozy (backtest): co model przewidziałby dla miesięcy, ---
// --- które już mamy w danych, zestawione z tym co faktycznie wyszło.    ---

const dochodBacktestMonthsEl = document.getElementById("dochod-backtest-months");
const dochodBacktestPrzychodTableEl = document.getElementById("dochod-backtest-przychod-table");
const dochodBacktestDochodTableEl = document.getElementById("dochod-backtest-dochod-table");

function renderBacktestTable(el, title, items) {
  el.innerHTML = "";
  const heading = document.createElement("h5");
  heading.textContent = title;
  heading.style.margin = "8px 0 4px";
  el.appendChild(heading);
  if (!items.length) {
    el.innerHTML += `<p class="muted">Za mało historii do backtestu.</p>`;
    return;
  }
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML =
    "<thead><tr><th>Miesiąc</th><th>Rzeczywiste</th><th>Prognoza (bez znajomości tego miesiąca)</th><th>Różnica</th></tr></thead>";
  const tbody = document.createElement("tbody");
  items.forEach((it) => {
    const cls = it.diff >= 0 ? "positive" : "negative";
    const pct = it.diff_pct === null ? "" : ` (${it.diff_pct >= 0 ? "+" : ""}${it.diff_pct}%)`;
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${MONTH_LABELS_PL[it.month - 1]} ${it.year}</td><td>${fmtMoney(it.actual)}</td><td>${fmtMoney(it.forecast)}</td>` +
      `<td><span class="an-dochod-value ${cls}">${it.diff >= 0 ? "+" : ""}${fmtMoney(it.diff)}${pct}</span></td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

async function loadDochodBacktest() {
  const dzial = dochodTrendDzialSelect.value;
  const isAll = dzial === DOCHOD_TREND_ALL_SENTINEL;
  const monthsBack = parseInt(dochodBacktestMonthsEl.value, 10) || 6;
  dochodBacktestPrzychodTableEl.innerHTML = `<p class="muted">Ładowanie...</p>`;
  dochodBacktestDochodTableEl.innerHTML = "";
  try {
    const url = isAll
      ? `/api/analytics/dochod-backtest-total?${qs({ dzialy: DOCHOD_NAMED_DZIALY.join(","), months_back: monthsBack })}`
      : `/api/analytics/dochod-backtest?${qs({ dzial, months_back: monthsBack })}`;
    const data = await fetch(url).then((r) => r.json());
    renderBacktestTable(dochodBacktestPrzychodTableEl, "Przychód netto", data.przychod);
    renderBacktestTable(dochodBacktestDochodTableEl, "Dochód netto", data.dochod);
  } catch (e) {
    dochodBacktestPrzychodTableEl.innerHTML = "";
    showToast("Nie udało się pobrać trafności prognozy.", true);
  }
}

document.getElementById("btn-dochod-backtest-refresh").addEventListener("click", loadDochodBacktest);

// --- Start ---

setDefaultRange(trendFromEl, trendToEl);
setDefaultRange(kontrahenciFromEl, kontrahenciToEl);
setDefaultRange(dzialyFromEl, dzialyToEl);
setDefaultRange(kategorieFromEl, kategorieToEl);
dochodFromEl.value = monthValue(DOCHOD_MIN_YEAR, DOCHOD_MIN_MONTH);
dochodToEl.value = monthValue(defaultRange().toYear, defaultRange().toMonth);
// Domyślnie tylko 2025+ (na życzenie użytkownika — mniejszy zakres, mniej
// danych do przeliczenia). Pełną historię (Hotel ma sensowny przychód już od
// 2019) nadal widać, jeśli ktoś ręcznie cofnie "Od".
dochodTrendFromEl.value = monthValue(2025, 1);
dochodTrendToEl.value = monthValue(defaultRange().toYear, defaultRange().toMonth);

// Tylko Przegląd (domyślna aktywna zakładka) ładuje się od razu — reszta
// leniwie, przy pierwszym kliknięciu (patrz TAB_LOADERS wyżej).
loadPrzeglad();
