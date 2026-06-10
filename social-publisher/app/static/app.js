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

/* ---------- 账号设置 ---------- */

$("#btn-settings").addEventListener("click", openSettings);
$("#btn-settings-close").addEventListener("click", () =>
  $("#settings-modal").classList.add("hidden"));
$("#settings-modal").addEventListener("click", (e) => {
  if (e.target.id === "settings-modal") e.target.classList.add("hidden");
});

async function openSettings() {
  $("#settings-modal").classList.remove("hidden");
  const openIds = [...document.querySelectorAll(".acct.open")].map((d) => d.dataset.pid);
  const [res, authRes] = await Promise.all([
    fetch("/api/settings"), fetch("/api/auth/status"),
  ]);
  const data = await res.json();
  const authData = await authRes.json();
  renderSettings(data, openIds, authData.enabled);
}

function renderSettings(data, openIds = [], authEnabled = false) {
  const box = $("#settings-list");
  box.innerHTML = "";
  box.appendChild(buildAuthCard(authEnabled, openIds.includes("_auth")));
  data.platforms.forEach((p) => {
    const div = document.createElement("div");
    div.className = "acct" + (openIds.includes(p.id) ? " open" : "");
    div.dataset.pid = p.id;
    const chip = p.expired
      ? '<span class="chip exp">已过期，请重新登录</span>'
      : p.configured
        ? `<span class="chip on">已登录${p.keep_days ? `（剩 ${p.remaining_days} 天）` : "（永久）"}</span>`
        : p.has_api
          ? '<span class="chip off">未登录</span>'
          : '<span class="chip draft">草稿模式</span>';

    const fieldsHtml = p.fields.map((f) => `
      <label>${f.label}</label>
      <input type="${f.secret ? "password" : "text"}" data-key="${f.key}"
        value="${f.value || ""}" placeholder="${f.placeholder || ""}"
        autocomplete="off">`).join("");

    const keepHtml = data.keep_choices.map((c) =>
      `<option value="${c.days}" ${c.days === p.keep_days ? "selected" : ""}>${c.label}</option>`
    ).join("");

    div.innerHTML = `
      <div class="acct-head">
        <span>${p.icon}</span><span class="a-name">${p.name}</span>${chip}
      </div>
      <div class="acct-body">
        <p class="acct-help">${p.help}</p>
        ${p.has_api ? `
          ${fieldsHtml}
          <div class="acct-foot">
            <select data-keep>${keepHtml}</select>
            <button class="btn small" data-save>保存登录</button>
            ${p.configured || p.expired ? '<button class="btn small danger" data-logout>退出登录</button>' : ""}
            <span class="save-msg muted"></span>
          </div>` : ""}
      </div>`;

    div.querySelector(".acct-head").addEventListener("click", () =>
      div.classList.toggle("open"));

    const saveBtn = div.querySelector("[data-save]");
    if (saveBtn) saveBtn.addEventListener("click", async () => {
      const values = {};
      div.querySelectorAll("input[data-key]").forEach((inp) => {
        values[inp.dataset.key] = inp.value.trim();
      });
      const keep = Number(div.querySelector("[data-keep]").value);
      const msg = div.querySelector(".save-msg");
      msg.textContent = "保存中…";
      const res = await fetch(`/api/settings/${p.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values, keep_days: keep }),
      });
      const r = await res.json();
      msg.textContent = (r.ok ? "✅ " : "⚠️ ") + r.message;
      openSettings();
    });

    const logoutBtn = div.querySelector("[data-logout]");
    if (logoutBtn) logoutBtn.addEventListener("click", async () => {
      await fetch(`/api/settings/${p.id}`, { method: "DELETE" });
      openSettings();
    });

    box.appendChild(div);
  });
}

/* 手机访问/登录保护设置卡片 */
function buildAuthCard(enabled, open) {
  const div = document.createElement("div");
  div.className = "acct" + (open ? " open" : "");
  div.dataset.pid = "_auth";
  div.innerHTML = `
    <div class="acct-head">
      <span>📱</span><span class="a-name">手机访问 · 登录保护</span>
      ${enabled
        ? '<span class="chip on">已开启</span>'
        : '<span class="chip off">未开启</span>'}
    </div>
    <div class="acct-body">
      <p class="acct-help">手机连同一 Wi-Fi 后，用浏览器打开「http://电脑IP:8000」即可使用，
        并可通过浏览器菜单「添加到主屏幕」变成手机 App。
        开启访问密码后，其他设备需登录才能访问（可选保持登录时长）。</p>
      <label>访问密码（至少 4 位）</label>
      <input type="password" data-key="_pw" placeholder="${enabled ? "输入新密码可修改" : "设置访问密码"}"
        autocomplete="new-password">
      <div class="acct-foot">
        <button class="btn small" data-auth-save>${enabled ? "修改密码" : "开启保护"}</button>
        ${enabled ? '<button class="btn small danger" data-auth-off>关闭保护</button>' : ""}
        <span class="save-msg muted"></span>
      </div>
    </div>`;
  div.querySelector(".acct-head").addEventListener("click", () =>
    div.classList.toggle("open"));
  div.querySelector("[data-auth-save]").addEventListener("click", async () => {
    const pw = div.querySelector("[data-key='_pw']").value.trim();
    const msg = div.querySelector(".save-msg");
    const res = await fetch("/api/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    const r = await res.json();
    msg.textContent = (r.ok ? "✅ " : "⚠️ ") + r.message;
    if (r.ok) setTimeout(openSettings, 800);
  });
  const offBtn = div.querySelector("[data-auth-off]");
  if (offBtn) offBtn.addEventListener("click", async () => {
    await fetch("/api/auth/password", { method: "DELETE" });
    openSettings();
  });
  return div;
}

/* ---------- 数据看板 ---------- */

let statsData = null;

$("#btn-stats").addEventListener("click", openStats);
$("#btn-stats-close").addEventListener("click", () =>
  $("#stats-modal").classList.add("hidden"));
$("#btn-stats-back").addEventListener("click", showOverview);
$("#stats-modal").addEventListener("click", (e) => {
  if (e.target.id === "stats-modal") e.target.classList.add("hidden");
});
$("#btn-stats-refresh").addEventListener("click", async () => {
  const btn = $("#btn-stats-refresh");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 拉取中…';
  try {
    const res = await fetch("/api/stats/refresh", { method: "POST" });
    const data = await res.json();
    const fails = data.results.filter((r) => !r.ok);
    if (fails.length) alert(fails.map((f) => `${f.platform}: ${f.message}`).join("\n"));
    await openStats();
  } finally {
    btn.disabled = false;
    btn.textContent = "⟳ 刷新数据";
  }
});

async function openStats() {
  $("#stats-modal").classList.remove("hidden");
  const res = await fetch("/api/stats");
  statsData = await res.json();
  showOverview();
}

const fmt = (n) => n >= 10000 ? (n / 10000).toFixed(1) + "w" : String(n);
const deltaTag = (d) => !d ? "" :
  d > 0 ? `<span class="d-up">▲${fmt(d)}</span>` :
  d < 0 ? `<span class="d-down">▼${fmt(-d)}</span>` : "";

function showOverview() {
  $("#stats-title").textContent = "数据看板";
  $("#btn-stats-back").classList.add("hidden");
  $("#stats-detail").classList.add("hidden");
  const box = $("#stats-overview");
  box.classList.remove("hidden");
  box.innerHTML = "";
  statsData.platforms.forEach((p) => {
    const div = document.createElement("div");
    div.className = "stat-card";
    if (p.latest) {
      const m = p.latest, d = p.delta || {};
      div.innerHTML = `
        <div class="s-head">${p.icon} ${p.name}</div>
        <div class="s-followers">${fmt(m.followers)} ${deltaTag(d.followers)}
          <small>粉丝</small></div>
        <div class="stat-row">
          <span>❤ <b>${fmt(m.likes)}</b> ${deltaTag(d.likes)}</span>
          <span>💬 <b>${fmt(m.comments)}</b> ${deltaTag(d.comments)}</span>
          <span>⭐ <b>${fmt(m.favorites)}</b> ${deltaTag(d.favorites)}</span>
        </div>
        <div class="s-updated">更新于 ${new Date(p.updated * 1000).toLocaleString("zh-CN")}
          · ${p.source === "api" ? "API" : "手动"}</div>`;
    } else {
      div.innerHTML = `
        <div class="s-head">${p.icon} ${p.name}</div>
        <div class="s-empty">暂无数据，点击进入手动记录${
          statsData.refreshable.includes(p.id) ? "或刷新拉取" : ""}</div>`;
    }
    div.addEventListener("click", () => showDetail(p));
    box.appendChild(div);
  });
}

function showDetail(p) {
  $("#stats-title").textContent = `${p.icon} ${p.name} · 数据详情`;
  $("#btn-stats-back").classList.remove("hidden");
  $("#stats-overview").classList.add("hidden");
  const box = $("#stats-detail");
  box.classList.remove("hidden");

  const chart = p.series.length >= 2
    ? svgChart(p.series)
    : '<p class="muted">至少需要两次记录才能绘制趋势（用下方表单或「刷新数据」多记几次）</p>';

  const postsHtml = p.posts.length ? `
    <div class="chart-box">
      <h3>分条目数据（最近一次采集，共 ${p.posts.length} 条）</h3>
      <table class="posts-table">
        <tr><th>条目</th><th class="num">👁 浏览</th><th class="num">❤ 喜欢</th>
            <th class="num">💬 评论</th><th class="num">⭐ 收藏</th></tr>
        ${p.posts.map((t) => `
          <tr><td class="p-title">${t.title || "(无标题)"}</td>
              <td class="num">${fmt(t.views || 0)}</td>
              <td class="num">${fmt(t.likes || 0)}</td>
              <td class="num">${fmt(t.comments || 0)}</td>
              <td class="num">${fmt(t.favorites || 0)}</td></tr>`).join("")}
      </table>
    </div>` : "";

  box.innerHTML = `
    <div class="chart-box">
      <h3>数据趋势</h3>
      <div class="chart-legend">
        <span><i style="background:#3b6df0"></i>粉丝</span>
        <span><i style="background:#ec6a9c"></i>喜欢</span>
        <span><i style="background:#16a34a"></i>评论</span>
        <span><i style="background:#c2700a"></i>收藏</span>
      </div>
      ${chart}
    </div>
    ${postsHtml}
    <div class="chart-box">
      <h3>手动记录当前数据</h3>
      <div class="manual-form">
        ${["followers:粉丝", "likes:喜欢", "comments:评论", "favorites:收藏"].map((s) => {
          const [k, label] = s.split(":");
          return `<div class="mf"><label>${label}</label>
            <input type="number" min="0" data-mk="${k}"
              value="${p.latest ? p.latest[k] : ""}" placeholder="0"></div>`;
        }).join("")}
        <button class="btn small" id="btn-manual-save">记录</button>
      </div>
    </div>`;

  $("#btn-manual-save").addEventListener("click", async () => {
    const values = {};
    box.querySelectorAll("input[data-mk]").forEach((i) => {
      values[i.dataset.mk] = Number(i.value || 0);
    });
    await fetch(`/api/stats/manual/${p.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const res = await fetch("/api/stats");
    statsData = await res.json();
    showDetail(statsData.platforms.find((x) => x.id === p.id));
  });
}

/* 轻量 SVG 折线图：四个指标各一条线，按各自量级归一化 */
function svgChart(series) {
  const W = 640, H = 200, PAD = 34;
  const colors = { followers: "#3b6df0", likes: "#ec6a9c",
                   comments: "#16a34a", favorites: "#c2700a" };
  const ts = series.map((r) => r.ts);
  const tMin = Math.min(...ts), tMax = Math.max(...ts) || 1;
  const x = (t) => PAD + (W - 2 * PAD) * (tMax === tMin ? 0.5 : (t - tMin) / (tMax - tMin));

  let lines = "", labels = "";
  for (const [key, color] of Object.entries(colors)) {
    const vals = series.map((r) => r[key] || 0);
    const vMax = Math.max(...vals, 1);
    const y = (v) => H - PAD - (H - 2 * PAD) * (v / vMax);
    const pts = series.map((r) => `${x(r.ts).toFixed(1)},${y(r[key] || 0).toFixed(1)}`).join(" ");
    lines += `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round"/>`;
    lines += series.map((r) =>
      `<circle cx="${x(r.ts).toFixed(1)}" cy="${y(r[key] || 0).toFixed(1)}" r="2.5" fill="${color}"/>`
    ).join("");
    const last = series[series.length - 1];
    labels += `<text x="${W - PAD + 4}" y="${y(last[key] || 0) + 4}"
      font-size="10" fill="${color}">${fmt(last[key] || 0)}</text>`;
  }
  const dateFmt = (t) => new Date(t * 1000).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">
    <line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}"
      stroke="rgba(125,135,170,.35)"/>
    ${lines}${labels}
    <text x="${PAD}" y="${H - PAD + 16}" font-size="10" fill="#767c92">${dateFmt(tMin)}</text>
    <text x="${W - PAD}" y="${H - PAD + 16}" font-size="10" fill="#767c92" text-anchor="end">${dateFmt(tMax)}</text>
  </svg>`;
}

/* ---------- 事件绑定 ---------- */

$("#text").addEventListener("input", scheduleAnalyze);
$("#title").addEventListener("input", scheduleAnalyze);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
