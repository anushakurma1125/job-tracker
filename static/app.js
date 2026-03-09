let allJobs = [];
let activeFilter = "";
let sortCol = "";
let sortAsc = true;
let searchQuery = "";

document.addEventListener("DOMContentLoaded", () => {
    // Clean up any stale modal backdrops
    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");

    loadJobs();

    // Stat card filters
    document.querySelectorAll(".stat-card").forEach(card => {
        card.style.cursor = "pointer";
        card.addEventListener("click", () => {
            const filter = card.dataset.filter;
            activeFilter = activeFilter === filter ? "" : filter;
            document.querySelectorAll(".stat-card").forEach(c => c.classList.remove("border-primary"));
            if (activeFilter) card.classList.add("border-primary");
            renderJobs();
        });
    });

    // Search input
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            searchQuery = e.target.value.toLowerCase();
            renderJobs();
        });
    }

    // Sortable headers
    document.querySelectorAll("th[data-sort]").forEach(th => {
        th.style.cursor = "pointer";
        th.addEventListener("click", () => {
            const col = th.dataset.sort;
            if (sortCol === col) {
                sortAsc = !sortAsc;
            } else {
                sortCol = col;
                sortAsc = true;
            }
            updateSortIcons();
            renderJobs();
        });
    });
});

function updateSortIcons() {
    document.querySelectorAll("th[data-sort]").forEach(th => {
        const icon = th.querySelector(".sort-icon");
        if (!icon) return;
        if (th.dataset.sort === sortCol) {
            icon.className = sortAsc ? "bi bi-caret-up-fill sort-icon ms-1" : "bi bi-caret-down-fill sort-icon ms-1";
        } else {
            icon.className = "bi bi-caret-up-fill sort-icon ms-1 text-muted opacity-25";
        }
    });
}

async function loadJobs() {
    const res = await fetch("/api/jobs");
    allJobs = await res.json();
    updateStats();
    renderJobs();
}

function updateStats() {
    document.getElementById("statTotal").textContent = allJobs.length;
    const counts = { Applied: 0, Interviewing: 0, Offer: 0, Rejected: 0 };
    allJobs.forEach(j => { if (counts[j.status] !== undefined) counts[j.status]++; });
    document.getElementById("statApplied").textContent = counts.Applied;
    document.getElementById("statInterviewing").textContent = counts.Interviewing;
    document.getElementById("statOffer").textContent = counts.Offer;
    document.getElementById("statRejected").textContent = counts.Rejected;
}

function formatDate(d) {
    if (!d) return "";
    // Strip time portion like "2026-01-03 00:00:00" → "2026-01-03"
    return d.split(" ")[0];
}

function getFilteredSortedJobs() {
    let jobs = allJobs;

    // Status filter (stat cards)
    if (activeFilter) {
        jobs = jobs.filter(j => j.status === activeFilter);
    }

    // Search filter
    if (searchQuery) {
        jobs = jobs.filter(j => {
            const text = [
                j.applied_date, j.company, j.role, j.posted_on,
                j.status, j.comment, j.visa_answer, j.link
            ].filter(Boolean).join(" ").toLowerCase();
            return text.includes(searchQuery);
        });
    }

    // Sort
    if (sortCol) {
        jobs = [...jobs].sort((a, b) => {
            let va = (a[sortCol] || "").toString().toLowerCase();
            let vb = (b[sortCol] || "").toString().toLowerCase();
            if (va < vb) return sortAsc ? -1 : 1;
            if (va > vb) return sortAsc ? 1 : -1;
            return 0;
        });
    }

    return jobs;
}

function renderJobs() {
    const tbody = document.getElementById("jobsTableBody");
    const filtered = getFilteredSortedJobs();

    // Update count badge
    const countEl = document.getElementById("filteredCount");
    if (countEl) {
        countEl.textContent = (searchQuery || activeFilter)
            ? `Showing ${filtered.length} of ${allJobs.length}`
            : `${allJobs.length} jobs`;
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-5 text-muted">
                    <i class="bi bi-briefcase" style="font-size: 2rem;"></i>
                    <p class="mt-2 mb-0">${(activeFilter || searchQuery) ? 'No matching jobs found.' : 'No jobs tracked yet. Click "Add Job" to get started.'}</p>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(job => `
        <tr>
            <td class="editable-cell" data-id="${job.id}" data-field="applied_date" data-type="date">${formatDate(job.applied_date) || "—"}</td>
            <td class="editable-cell fw-semibold" data-id="${job.id}" data-field="company">${escapeHtml(job.company) || "—"}</td>
            <td class="editable-cell" data-id="${job.id}" data-field="role">${escapeHtml(job.role) || "—"}</td>
            <td class="editable-cell" data-id="${job.id}" data-field="posted_on" data-type="date">${formatDate(job.posted_on) || "—"}</td>
            <td>
                <select class="form-select form-select-sm status-select ${statusClass(job.status)}"
                        onchange="updateStatus(${job.id}, this.value)">
                    ${["Applied", "Waiting for Referral", "Interviewing", "Offer", "Rejected", "Withdrawn", "Saved"]
                        .map(s => `<option value="${s}" ${s === job.status ? "selected" : ""}>${s}</option>`)
                        .join("")}
                </select>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm comment-input"
                       value="${escapeHtml(job.comment || '')}"
                       placeholder="Add comment..."
                       onchange="updateField(${job.id}, 'comment', this.value)">
            </td>
            <td>
                <select class="form-select form-select-sm visa-select"
                        onchange="updateField(${job.id}, 'visa_answer', this.value)">
                    ${["", "Yes", "No", "Other"]
                        .map(v => `<option value="${v}" ${v === (job.visa_answer || '') ? "selected" : ""}>${v || "—"}</option>`)
                        .join("")}
                </select>
            </td>
            <td>
                ${job.link ? `<a href="${escapeHtml(job.link)}" target="_blank" rel="noopener" class="text-decoration-none small">
                    <i class="bi bi-box-arrow-up-right me-1"></i>View
                </a>` : "—"}
            </td>
            <td class="text-end text-nowrap">
                <button class="btn btn-sm btn-outline-secondary me-1" onclick="showDetails(${job.id})" title="Details">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteJob(${job.id})" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join("");

    // Attach click-to-edit handlers
    tbody.querySelectorAll(".editable-cell").forEach(cell => {
        cell.addEventListener("click", startEditing);
    });
}

function startEditing(e) {
    const cell = e.currentTarget;
    if (cell.querySelector("input")) return; // Already editing

    const id = cell.dataset.id;
    const field = cell.dataset.field;
    const type = cell.dataset.type || "text";
    const currentVal = cell.textContent.trim() === "—" ? "" : cell.textContent.trim();

    const input = document.createElement("input");
    input.type = type;
    input.value = currentVal;
    input.className = "form-control form-control-sm edit-inline";

    cell.textContent = "";
    cell.appendChild(input);
    input.focus();
    input.select();

    const save = async () => {
        const newVal = input.value.trim();
        await updateField(id, field, newVal);
        // Update local data so we don't refetch
        const job = allJobs.find(j => j.id == id);
        if (job) job[field] = newVal;
        cell.textContent = (field === "applied_date" || field === "posted_on") ? (formatDate(newVal) || "—") : (newVal || "—");
    };

    input.addEventListener("blur", save);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { input.blur(); }
        if (e.key === "Escape") {
            cell.textContent = currentVal || "—";
        }
    });
}

function statusClass(status) {
    const map = {
        Applied: "status-applied",
        Interviewing: "status-interviewing",
        Offer: "status-offer",
        Rejected: "status-rejected",
        "Waiting for Referral": "status-referral",
        Withdrawn: "status-withdrawn",
        Saved: "status-saved",
    };
    return map[status] || "";
}

async function addJob() {
    const linkInput = document.getElementById("jobLink");
    const link = linkInput.value.trim();
    if (!link) return;

    const btn = document.getElementById("submitJobBtn");
    const statusEl = document.getElementById("extractionStatus");
    const errorEl = document.getElementById("extractionError");

    btn.disabled = true;
    statusEl.classList.remove("d-none");
    errorEl.classList.add("d-none");

    try {
        const res = await fetch("/api/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ link }),
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.error || "Failed to extract job details");
        }

        linkInput.value = "";
        bootstrap.Modal.getInstance(document.getElementById("addJobModal")).hide();
        loadJobs();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        statusEl.classList.add("d-none");
    }
}

async function updateStatus(id, status) {
    await fetch(`/api/jobs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
    });
    loadJobs();
}

async function updateField(id, field, value) {
    await fetch(`/api/jobs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
    });
}

async function deleteJob(id) {
    if (!confirm("Delete this job application?")) return;
    await fetch(`/api/jobs/${id}`, { method: "DELETE" });
    loadJobs();
}

async function showDetails(id) {
    const res = await fetch(`/api/jobs/${id}`);
    const job = await res.json();

    document.getElementById("detailsTitle").textContent = `${job.company} — ${job.role}`;
    document.getElementById("detailCompany").textContent = job.company || "—";
    document.getElementById("detailRole").textContent = job.role || "—";
    document.getElementById("detailAppliedDate").textContent = formatDate(job.applied_date) || "—";
    document.getElementById("detailPostedOn").textContent = formatDate(job.posted_on) || "—";
    document.getElementById("detailStatus").innerHTML = `<span class="badge ${statusBadge(job.status)}">${job.status}</span>`;
    document.getElementById("detailComment").textContent = job.comment || "—";
    document.getElementById("detailVisaAnswer").textContent = job.visa_answer || "—";
    document.getElementById("detailLink").innerHTML = job.link
        ? `<a href="${escapeHtml(job.link)}" target="_blank" rel="noopener">${escapeHtml(job.link)}</a>`
        : "—";
    document.getElementById("detailDescription").textContent = job.job_description || "No description available.";

    new bootstrap.Modal(document.getElementById("detailsModal")).show();
}

function statusBadge(status) {
    const map = {
        Applied: "bg-primary",
        Interviewing: "bg-warning text-dark",
        Offer: "bg-success",
        Rejected: "bg-danger",
        "Waiting for Referral": "bg-purple",
        Withdrawn: "bg-secondary",
        Saved: "bg-info",
    };
    return map[status] || "bg-secondary";
}

async function bulkUpload() {
    const fileInput = document.getElementById("bulkFile");
    const file = fileInput.files[0];
    if (!file) return;

    const btn = document.getElementById("bulkSubmitBtn");
    const statusEl = document.getElementById("bulkStatus");
    const resultEl = document.getElementById("bulkResult");
    const errorEl = document.getElementById("bulkError");

    btn.disabled = true;
    statusEl.classList.remove("d-none");
    resultEl.classList.add("d-none");
    errorEl.classList.add("d-none");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/api/jobs/bulk", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.error || "Upload failed");
        }

        let html = `<div class="alert alert-success py-2">
            <strong>${data.added}</strong> jobs imported`;
        if (data.skipped > 0) html += `, <strong>${data.skipped}</strong> duplicates skipped`;
        html += `.</div>`;
        if (data.errors && data.errors.length > 0) {
            html += `<div class="alert alert-warning py-2 small">${data.errors.join("<br>")}</div>`;
        }
        resultEl.innerHTML = html;
        resultEl.classList.remove("d-none");
        fileInput.value = "";
        loadJobs();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        statusEl.classList.add("d-none");
    }
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
