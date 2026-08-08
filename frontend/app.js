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
  loadProfile();
  Object.keys(collections).forEach(loadCollection);
}

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
    const delBtn = document.createElement("button");
    delBtn.textContent = "Supprimer";
    delBtn.addEventListener("click", async () => {
      await fetch(`${API}${endpoint}/${item.id}`, { method: "DELETE" });
      loadCollection(name);
    });
    card.appendChild(delBtn);
    list.appendChild(card);
  });
}

Object.keys(collections).forEach((name) => {
  const form = document.getElementById(`form-${name}`);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    // dates vides -> null
    for (const key of ["start_date", "end_date"]) {
      if (key in payload && payload[key] === "") payload[key] = null;
    }
    await fetch(`${API}${collections[name].endpoint}/?profile_id=${currentProfileId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
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
