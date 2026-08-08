const API = ""; // même origine

// ---------- Profil courant (multi-profils) ----------
let currentProfileId = localStorage.getItem("cvtailor_profile_id");

async function loadProfiles() {
  const res = await fetch(`${API}/api/profiles`);
  let profiles = await res.json();

  if (profiles.length === 0) {
    const created = await fetch(`${API}/api/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: "Profil 1" }),
    }).then((r) => r.json());
    profiles = [created];
  }

  if (!currentProfileId || !profiles.some((p) => String(p.id) === String(currentProfileId))) {
    currentProfileId = String(profiles[0].id);
  }
  localStorage.setItem("cvtailor_profile_id", currentProfileId);

  const select = document.getElementById("profile-select");
  select.innerHTML = "";
  profiles.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.full_name || `Profil ${p.id}`;
    if (String(p.id) === String(currentProfileId)) opt.selected = true;
    select.appendChild(opt);
  });
}

document.getElementById("profile-select").addEventListener("change", (e) => {
  currentProfileId = e.target.value;
  localStorage.setItem("cvtailor_profile_id", currentProfileId);
  refreshAll();
});

document.getElementById("btn-new-profile").addEventListener("click", async () => {
  const name = prompt("Nom du nouveau profil (ex: prénom) :");
  if (name === null) return;
  const created = await fetch(`${API}/api/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: name }),
  }).then((r) => r.json());
  currentProfileId = String(created.id);
  localStorage.setItem("cvtailor_profile_id", currentProfileId);
  await loadProfiles();
  refreshAll();
});

function refreshAll() {
  Object.keys(collections).forEach(exitEditMode);
  loadProfile();
  Object.keys(collections).forEach(loadCollection);
}

document.getElementById("btn-delete-profile").addEventListener("click", async () => {
  const select = document.getElementById("profile-select");
  const label = select.options[select.selectedIndex]?.textContent || "ce profil";
  const confirmed = confirm(
    `Supprimer définitivement le profil "${label}" et toutes ses données ` +
    `(expériences, formations, compétences, projets, langues) ?\n\nCette action est irréversible.`
  );
  if (!confirmed) return;

  const res = await fetch(`${API}/api/profile/${currentProfileId}`, { method: "DELETE" });
  if (!res.ok) {
    alert("Erreur lors de la suppression du profil.");
    return;
  }
  localStorage.removeItem("cvtailor_profile_id");
  currentProfileId = null;
  await loadProfiles();
  refreshAll();
});

// ---------- Navigation entre onglets ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// ---------- Profil ----------
async function loadProfile() {
  const res = await fetch(`${API}/api/profile/${currentProfileId}`);
  const data = await res.json();
  const form = document.getElementById("form-profile");
  for (const key in data) {
    if (form.elements[key]) form.elements[key].value = data[key] || "";
  }
}

document.getElementById("form-profile").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  await fetch(`${API}/api/profile/${currentProfileId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadProfiles(); // le nom affiché dans le sélecteur peut avoir changé
  const status = document.getElementById("status-profile");
  status.textContent = "Enregistré ✓";
  setTimeout(() => (status.textContent = ""), 2000);
});

// ---------- Import LinkedIn ----------
document.getElementById("form-linkedin-import").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("linkedin-file");
  const status = document.getElementById("status-linkedin-import");
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  status.style.color = "#374151";
  status.textContent = "Import en cours...";

  try {
    const res = await fetch(`${API}/api/import/linkedin?profile_id=${currentProfileId}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Échec de l'import");
    }
    const counts = await res.json();
    status.style.color = "#059669";
    status.textContent =
      `Importé : ${counts.experiences} expérience(s), ${counts.educations} formation(s), ` +
      `${counts.skills} compétence(s), ${counts.languages} langue(s)` +
      (counts.profile_updated ? ", profil complété." : ".");
    fileInput.value = "";
    refreshAll();
  } catch (err) {
    status.style.color = "#b91c1c";
    status.textContent = "Erreur : " + err.message;
  }
});

document.getElementById("form-linkedin-api-import").addEventListener("submit", async (e) => {
  e.preventDefault();
  const tokenInput = document.getElementById("linkedin-token");
  const status = document.getElementById("status-linkedin-api-import");
  const access_token = tokenInput.value.trim();
  if (!access_token) return;

  status.style.color = "#374151";
  status.textContent = "Import en cours...";

  try {
    const res = await fetch(`${API}/api/import/linkedin-api?profile_id=${currentProfileId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Échec de l'import");
    }
    const counts = await res.json();
    status.style.color = "#059669";
    status.textContent =
      `Importé : ${counts.experiences} expérience(s), ${counts.educations} formation(s), ` +
      `${counts.skills} compétence(s), ${counts.languages} langue(s)` +
      (counts.profile_updated ? ", profil complété." : ".");
    tokenInput.value = "";
    refreshAll();
  } catch (err) {
    status.style.color = "#b91c1c";
    status.textContent = "Erreur : " + err.message;
  }
});

// ---------- Collections génériques (expériences, formations, compétences, projets, langues) ----------
const collections = {
  experiences: {
    endpoint: "/api/experiences",
    render: (item) => `
      <strong>${item.role} — ${item.company}</strong>
      <div class="item-sub">${item.location || ""} ${fmtRange(item.start_date, item.end_date)}</div>
    `,
  },
  educations: {
    endpoint: "/api/educations",
    render: (item) => `
      <strong>${item.degree || ""} ${item.field ? "— " + item.field : ""}</strong>
      <div class="item-sub">${item.school} ${fmtRange(item.start_date, item.end_date, true)}</div>
    `,
  },
  skills: {
    endpoint: "/api/skills",
    render: (item) => `
      <strong>${item.name}</strong>
      <div class="item-sub">${item.category || ""} ${item.level ? "· " + item.level : ""}</div>
    `,
  },
  projects: {
    endpoint: "/api/projects",
    render: (item) => `
      <strong>${item.name}</strong>
      <div class="item-sub">${(item.tags || "").split(",").filter(Boolean).join(", ")}</div>
    `,
  },
  languages: {
    endpoint: "/api/languages",
    render: (item) => `<strong>${item.name}</strong><div class="item-sub">${item.level || ""}</div>`,
  },
};

function fmtRange(start, end, yearOnly) {
  const f = (d) => (d ? (yearOnly ? d.slice(0, 4) : d.slice(0, 7)) : "");
  if (!start && !end) return "";
  return `(${f(start)} – ${end ? f(end) : "en cours"})`;
}

async function loadCollection(name) {
  const { endpoint, render } = collections[name];
  const res = await fetch(`${API}${endpoint}/?profile_id=${currentProfileId}`);
  const items = await res.json();
  const list = document.getElementById(`list-${name}`);
  list.innerHTML = "";
  if (items.length === 0) {
    list.innerHTML = `<p class="hint">Rien pour l'instant.</p>`;
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `<div class="item-main">${render(item)}</div>`;

    const actions = document.createElement("div");
    actions.className = "item-actions";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn-edit";
    editBtn.textContent = "Modifier";
    editBtn.addEventListener("click", () => enterEditMode(name, item));
    actions.appendChild(editBtn);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn-delete";
    delBtn.textContent = "Supprimer";
    delBtn.addEventListener("click", async () => {
      await fetch(`${API}${endpoint}/${item.id}`, { method: "DELETE" });
      loadCollection(name);
    });
    actions.appendChild(delBtn);

    card.appendChild(actions);
    list.appendChild(card);
  });
}

function buildPayload(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  // dates vides -> null
  for (const key of ["start_date", "end_date"]) {
    if (key in payload && payload[key] === "") payload[key] = null;
  }
  return payload;
}

function enterEditMode(name, item) {
  const form = document.getElementById(`form-${name}`);
  for (const key in item) {
    if (form.elements[key]) form.elements[key].value = item[key] ?? "";
  }
  form.dataset.editingId = item.id;
  form.querySelector("button[type=submit]").textContent = "Enregistrer les modifications";
  form.querySelector(".btn-cancel-edit").style.display = "";
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function exitEditMode(name) {
  const form = document.getElementById(`form-${name}`);
  form.reset();
  delete form.dataset.editingId;
  form.querySelector("button[type=submit]").textContent = "Ajouter";
  form.querySelector(".btn-cancel-edit").style.display = "none";
}

Object.keys(collections).forEach((name) => {
  const form = document.getElementById(`form-${name}`);

  form.querySelector(".btn-cancel-edit").addEventListener("click", () => exitEditMode(name));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = buildPayload(form);
    const editingId = form.dataset.editingId;
    const url = editingId
      ? `${API}${collections[name].endpoint}/${editingId}`
      : `${API}${collections[name].endpoint}/?profile_id=${currentProfileId}`;
    await fetch(url, {
      method: editingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    exitEditMode(name);
    loadCollection(name);
  });
});

// ---------- Génération de CV ----------
document.getElementById("btn-preview").addEventListener("click", async () => {
  const offer_text = document.getElementById("offer-text").value;
  const res = await fetch(`${API}/api/generate-cv/html`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offer_text, profile_id: currentProfileId }),
  });
  const html = await res.text();
  const iframe = document.getElementById("cv-preview");
  iframe.srcdoc = html;
});

document.getElementById("btn-download-docx").addEventListener("click", async () => {
  const offer_text = document.getElementById("offer-text").value;
  const res = await fetch(`${API}/api/generate-cv/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offer_text, profile_id: currentProfileId }),
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "CV.docx";
  a.click();
  URL.revokeObjectURL(url);
});

// ---------- Init ----------
loadProfiles().then(refreshAll);
