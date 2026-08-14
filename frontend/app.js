const listEl = document.getElementById("invoice-list");
const emptyState = document.getElementById("empty-state");
const review = document.getElementById("review");
const form = document.getElementById("review-form");
const pdfFrame = document.getElementById("pdf-frame");
const ambiguousBadge = document.getElementById("ambiguous-badge");
const statusMsg = document.getElementById("status-msg");
const toast = document.getElementById("toast");

let currentId = null;
let toastTimer = null;

function apiUrl(path) {
  return `/api/ksef${path}`;
}

// Osobny, chwilowy komunikat (a nie #status-msg) — bo status-msg jest
// czyszczony przy przełączeniu na kolejną fakturę (patrz selectInvoice),
// a wynik zapisu ma być widoczny nawet po tym przejściu.
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

async function loadList() {
  const res = await fetch(apiUrl("/invoices"));
  const items = await res.json();

  listEl.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item.file_name;
    li.dataset.id = item.id;
    li.className = item.id === currentId ? "active" : "";
    li.addEventListener("click", () => selectInvoice(item.id));
    listEl.appendChild(li);
  }

  if (items.length === 0) {
    currentId = null;
    review.classList.add("hidden");
    emptyState.textContent = "Brak faktur do przetworzenia w faktury_surowe/.";
    emptyState.classList.remove("hidden");
  }

  return items;
}

async function selectInvoice(id) {
  currentId = id;
  statusMsg.textContent = "";
  emptyState.classList.add("hidden");
  review.classList.remove("hidden");
  [...listEl.children].forEach((li) => li.classList.toggle("active", li.dataset.id === id));

  pdfFrame.src = apiUrl(`/invoices/${encodeURIComponent(id)}/file`);

  const res = await fetch(apiUrl(`/invoices/${encodeURIComponent(id)}`));

  // Odczyt OCR trwa różnie długo dla różnych faktur, więc odpowiedzi mogą
  // wrócić w innej kolejności niż kliknięcia na liście. Jeśli w międzyczasie
  // wybrano już inną fakturę, ta (nieaktualna) odpowiedź jest ignorowana —
  // inaczej formularz mógłby zostać nadpisany danymi ze starszego kliknięcia.
  if (currentId !== id) return;

  if (!res.ok) {
    statusMsg.textContent = "Błąd odczytu faktury: " + (await res.text());
    return;
  }
  const data = await res.json();
  if (currentId !== id) return;

  // form.elements.namedItem(...) zamiast "magicznej" form.firm_name — jawny
  // dostęp, żeby wykluczyć jakąkolwiek interferencję z natywnymi
  // właściwościami HTMLFormElement albo autouzupełnianiem przeglądarki.
  field("firm_name").value = data.firm_name;
  field("invoice_number").value = data.invoice_number;
  field("invoice_date").value = data.invoice_date;
  field("payment_date").value = data.payment_date;
  field("payment_status").value = data.payment_status;
  field("payment_form").value = data.payment_form;
  field("brutto").value = data.brutto;
  field("kategoria").value = data.kategoria || "";
  field("scanned_firm").value = data.scanned_firm;
  ambiguousBadge.classList.toggle("hidden", !data.payment_status_ambiguous);
}

function field(name) {
  return form.elements.namedItem(name);
}

function collectFormData(action) {
  return {
    firm_name: field("firm_name").value.trim(),
    invoice_number: field("invoice_number").value.trim(),
    invoice_date: field("invoice_date").value.trim(),
    payment_date: field("payment_date").value.trim() || "brak",
    payment_status: field("payment_status").value.trim(),
    payment_form: field("payment_form").value.trim(),
    brutto: parseFloat(String(field("brutto").value).replace(",", ".")) || 0,
    kategoria: field("kategoria").value.trim(),
    scanned_firm: field("scanned_firm").value,
    action,
  };
}

async function selectNextAfter(processedId) {
  const items = await loadList();
  const next = items.find((i) => i.id !== processedId) || items[0];
  if (next) {
    await selectInvoice(next.id);
  }
}

async function finalizeInvoice(action) {
  if (!currentId) return;
  const processedId = currentId;
  statusMsg.textContent = "Zapisywanie...";

  const res = await fetch(apiUrl(`/invoices/${encodeURIComponent(processedId)}/finalize`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectFormData(action)),
  });

  if (!res.ok) {
    const detail = await res.text();
    statusMsg.textContent = "Błąd: " + detail;
    showToast("Błąd zapisu: " + detail, true);
    return;
  }

  const result = await res.json();
  const suffix = result.saved_to_payments
    ? " — dodano do bazy płatności SQL"
    : " — bez zapisu do bazy płatności (opłacona albo brak terminu)";
  showToast(`Zapisano: ${result.target_path}${suffix}`);

  await selectNextAfter(processedId);
}

function skipInvoice() {
  if (!currentId) return;
  const items = [...listEl.children];
  const idx = items.findIndex((li) => li.dataset.id === currentId);
  const next = items[idx + 1] || items[idx - 1];
  if (next) {
    selectInvoice(next.dataset.id);
  } else {
    currentId = null;
    review.classList.add("hidden");
    emptyState.textContent = "Brak faktur do przetworzenia w faktury_surowe/.";
    emptyState.classList.remove("hidden");
  }
}

document.getElementById("btn-skip").addEventListener("click", skipInvoice);
document.getElementById("btn-queue").addEventListener("click", () => finalizeInvoice("k"));
form.addEventListener("submit", (e) => {
  e.preventDefault();
  finalizeInvoice("t");
});

loadList().then((items) => {
  if (items.length > 0) selectInvoice(items[0].id);
});
