/* OnePost 前端逻辑：内容自动识别 → 平台匹配勾选 → 发布 */

const $ = (s) => document.querySelector(s);

const state = {
  files: [],        // [{name, original, kind, size, duration?, format?}]
  source: "",       // 转载来源链接
  platforms: [],    // 最近一次匹配结果
  checked: new Set(),
  userTouched: new Set(), // 用户手动改过的平台，不再被自动勾选覆盖
};

const CTYPE_LABEL = {
  text: "纯文字", image: "图片", "text+image": "图文",
  video: "视频", audio: "音频", link: "链接转载",
};

const URL_RE = /https?:\/\/[^\s<>"']+/;

/* ---------- 内容输入与自动分析 ---------- */

let analyzeTimer = null;
function scheduleAnalyze() {
  clearTimeout(analyzeTimer);
  analyzeTimer = setTimeout(analyze, 400);
}

async function analyze() {
  const text = $("#text").value.trim();
  detectLink(text);
  if (!text && state.files.length === 0) {
    $("#platforms").innerHTML = '<p class="muted">输入内容后自动匹配…</p>';
    $("#ctype-badge").classList.add("hidden");
    updatePublishBtn();
    return;
  }
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, title: $("#title").value, files: state.files }),
  });
  const data = await res.json();
  renderPlatforms(data.platforms, data.analysis.content_type);
}

function detectLink(text) {
  const m = text.match(URL_RE);
  const bar = $("#link-bar");
  if (m) {
    state.detectedUrl = m[0];
    $("#link-url").textContent = m[0];
    $("#link-url").href = m[0];
    bar.classList.remove("hidden");
  } else {
    bar.classList.add("hidden");
  }
}

/* ---------- 链接解析转载 ---------- */

$("#btn-extract").addEventListener("click", async () => {
  const url = state.detectedUrl;
  if (!url) return;
  const status = $("#extract-status");
  status.innerHTML = '<span class="spinner"></span> 解析中，视频会自动下载，请稍候…';
  $("#btn-extract").disabled = true;
  try {
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, download_video: true }),
    });
    const data = await res.json();
    const ex = data.extracted;
    if (ex.error) { status.textContent = "⚠️ " + ex.error; return; }

    if (ex.title) $("#title").value = ex.title;
    $("#text").value = (ex.text || "").trim();
    state.source = url;
    if (ex.video) {
      state.files = state.files.filter((f) => f.kind !== "video");
      state.files.push({ ...ex.video, kind: "video", original: ex.title || "video.mp4" });
      renderMedia();
    }
    status.textContent = "✅ 解析完成，请确认内容后选择发布平台";
    renderPlatforms(data.platforms, ex.kind === "video" ? "video" : "text+image");
  } catch (e) {
    status.textContent = "⚠️ 解析失败: " + e.message;
  } finally {
    $("#btn-extract").disabled = false;
  }
});

/* ---------- 文件上传 ---------- */

const dropzone = $("#dropzone");
dropzone.addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", (e) => uploadFiles(e.target.files));
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag");
  uploadFiles(e.dataTransfer.files);
});

async function uploadFiles(fileList) {
  for (const file of fileList) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const info = await res.json();
    state.files.push(info);
  }
  renderMedia();
  scheduleAnalyze();
}

function renderMedia() {
  const box = $("#media-list");
  box.innerHTML = "";
  state.files.forEach((f, i) => {
    const div = document.createElement("div");
    div.className = "media-item";
    const icon = { video: "🎬", audio: "🎵", other: "📄" }[f.kind] || "";
    div.innerHTML = f.kind === "image"
      ? `<img src="/uploads/${f.name}" alt="">`
      : `<span>${icon}</span>`;
    div.insertAdjacentHTML("beforeend",
      `<span class="tag">${f.original || f.name}</span>
       <button class="del" data-i="${i}">✕</button>`);
    box.appendChild(div);
  });
  box.querySelectorAll(".del").forEach((b) =>
    b.addEventListener("click", () => {
      state.files.splice(Number(b.dataset.i), 1);
      renderMedia();
      scheduleAnalyze();
    }));
}

/* ---------- 平台勾选 ---------- */

function renderPlatforms(list, ctype) {
  state.platforms = list;
  const badge = $("#ctype-badge");
  badge.textContent = "识别为：" + (CTYPE_LABEL[ctype] || ctype);
  badge.classList.remove("hidden");

  // 自动勾选推荐平台（用户手动操作过的除外）
  list.forEach((p) => {
    if (!state.userTouched.has(p.id)) {
      if (p.recommended) state.checked.add(p.id);
      else state.checked.delete(p.id);
    }
    if (!p.ok) state.checked.delete(p.id);
  });

  const box = $("#platforms");
  box.innerHTML = "";
  list.forEach((p) => {
    const label = document.createElement("label");
    const checked = state.checked.has(p.id);
    label.className = "platform" + (checked ? " checked" : "") + (p.ok ? "" : " disabled");
    label.innerHTML = `
      <input type="checkbox" ${checked ? "checked" : ""} ${p.ok ? "" : "disabled"}>
      <div>
        <div class="p-name">${p.icon} ${p.name}</div>
        ${p.issues.map((i) => `<div class="p-issues">⚠ ${i}</div>`).join("")}
        <div class="p-mode">${p.api_available ? "支持 API 直发" : "草稿包模式（无公开 API）"}</div>
      </div>`;
    label.querySelector("input").addEventListener("change", (e) => {
      state.userTouched.add(p.id);
      if (e.target.checked) state.checked.add(p.id);
      else state.checked.delete(p.id);
      label.classList.toggle("checked", e.target.checked);
      updatePublishBtn();
    });
    box.appendChild(label);
  });
  updatePublishBtn();
}

function updatePublishBtn() {
  const hasContent = $("#text").value.trim() || state.files.length;
  $("#btn-publish").disabled = !(hasContent && state.checked.size);
}

/* ---------- 发布 ---------- */

$("#btn-publish").addEventListener("click", async () => {
  const btn = $("#btn-publish");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 发布中…';
  try {
    const res = await fetch("/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: $("#title").value.trim(),
        text: $("#text").value.trim(),
        files: state.files,
        source: state.source,
        platforms: [...state.checked],
      }),
    });
    const data = await res.json();
    renderResults(data.results);
  } catch (e) {
    alert("发布失败: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "发 布";
  }
});

function renderResults(results) {
  $("#results").classList.remove("hidden");
  const box = $("#results-list");
  box.innerHTML = "";
  results.forEach((r) => {
    const div = document.createElement("div");
    div.className = "result-item";
    div.innerHTML = `
      <span class="status ${r.ok ? "ok" : "err"}">${r.ok ? "✅" : "❌"}</span>
      <div>
        <div><b>${r.icon || ""} ${r.name || r.platform}</b>
          ${r.mode === "draft" ? '<span class="muted">（草稿）</span>' : ""}</div>
        <div>${r.message} ${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">查看</a>` : ""}</div>
        ${(r.warnings || []).map((w) => `<div class="warn-line">⚠ ${w}</div>`).join("")}
      </div>`;
    box.appendChild(div);
  });
  $("#results").scrollIntoView({ behavior: "smooth" });
}

/* ---------- 事件绑定 ---------- */

$("#text").addEventListener("input", scheduleAnalyze);
$("#title").addEventListener("input", scheduleAnalyze);
