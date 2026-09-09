"use strict";

const TOKEN = window.RIGORA_SETUP_TOKEN;
const KEEP = "__RIGORA_KEEP__";
const SHARED = new Set(["plan_loop", "key_insight_check"]);
const THEME_KEY = "rigora-setup-theme";

const state = {
  step: 0,
  steps: [],
  catalog: null,
  current: null,
  selected: new Set(),
  slots: {},
  // 只放独占 Agent；方案生成与点睛之笔评分由 pairs 决定。
  assignments: {},
  pairs: [],
  highCross: "off",
  optional: {
    openalex_api_key: "",
    hf_token: "",
    hf_endpoint: "",
    database_url: "",
    reranker_backend: "auto",
  },
  saved: null,
  busy: false,
};

// --- dom helpers ---------------------------------------------------------

function el(tag, props, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props ?? {})) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Rigora-Setup-Token": TOKEN,
      ...(options.headers ?? {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error ?? `HTTP ${response.status}`);
  return payload;
}

function vendorFor(slot) {
  return state.catalog.vendors.find((item) => item.slot === slot);
}

function agentFor(name) {
  return state.catalog.agents.find((item) => item.name === name);
}

function exclusiveAgents() {
  return state.catalog.agent_order.filter((agent) => !SHARED.has(agent));
}

function slotLabel(slot) {
  const vendor = vendorFor(slot);
  const model = state.slots[slot]?.model?.trim();
  return model ? `${vendor.label} · ${model}` : vendor.label;
}

// --- step model ----------------------------------------------------------

function buildSteps() {
  state.steps = [
    { kind: "welcome" },
    ...state.catalog.agents.map((agent) => ({ kind: "agent", name: agent.name })),
    { kind: "providers" },
    { kind: "credentials" },
    { kind: "assign" },
    { kind: "pairs" },
    { kind: "optional" },
    { kind: "done" },
  ];
}

function seedFromCurrent() {
  for (const vendor of state.catalog.vendors) {
    const existing = state.current.slots.find((item) => item.slot === vendor.slot);
    state.slots[vendor.slot] = {
      api_key: "",
      keyStored: existing?.has_key ?? false,
      maskedKey: existing?.masked_key ?? "",
      base_url: existing?.base_url || vendor.default_base_url,
      model: existing?.model || vendor.default_model,
      api_style: existing?.api_style || vendor.default_api_style,
      probe: null,
    };
    if (existing && existing.agents.length > 0) state.selected.add(vendor.slot);
  }

  for (const agent of exclusiveAgents()) {
    const owner = state.current.slots.find((item) => item.agents.includes(agent));
    state.assignments[agent] = owner ? [owner.slot] : [];
  }

  state.pairs = (state.current.pairs ?? []).map((pair) => ({ ...pair }));
  state.highCross =
    state.current.high_cross === "ad" || state.current.high_cross === "bc"
      ? state.current.high_cross
      : "off";

  const option = state.current.optional;
  state.optional.hf_endpoint = option.hf_endpoint ?? "";
  state.optional.reranker_backend = option.reranker_backend ?? "auto";
  state.optional.openalex_api_key = option.openalex_has_key ? KEEP : "";
  state.optional.hf_token = option.hf_has_token ? KEEP : "";
  state.optional.database_url = option.database_has_url ? KEEP : "";
}

function pruneToSelected() {
  for (const agent of exclusiveAgents()) {
    state.assignments[agent] = (state.assignments[agent] ?? []).filter((slot) =>
      state.selected.has(slot),
    );
  }
  state.pairs = state.pairs.filter(
    (pair) => state.selected.has(pair.plan) && state.selected.has(pair.check),
  );
}

/** Seed one sensible pair so the step never opens empty. */
function ensurePairs() {
  if (state.pairs.length > 0 || state.selected.size === 0) return;
  const slots = [...state.selected];
  state.pairs = [{ plan: slots[0], check: slots[1] ?? slots[0] }];
}

/** Paths available at runtime; mirrors Settings.plan_check_pairs(). */
function pathCount() {
  if (state.pairs.length === 2 && (state.highCross === "ad" || state.highCross === "bc")) {
    return 3;
  }
  return state.pairs.length;
}

/** The concrete (plan, check) slot pairs the runtime will use. */
function expandedPairs() {
  const pairs = state.pairs.map((pair) => [pair.plan, pair.check]);
  if (state.pairs.length === 2 && (state.highCross === "ad" || state.highCross === "bc")) {
    const [first, second] = state.pairs;
    pairs.push(
      state.highCross === "ad"
        ? [first.plan, second.check]
        : [second.plan, first.check],
    );
  }
  return pairs;
}

function slotReady(slot) {
  const config = state.slots[slot];
  if (!config) return false;
  if (!config.model.trim()) return false;
  if (!config.api_key.trim() && !config.keyStored) return false;
  if (config.api_style === "chat_completions" && !config.base_url.trim()) return false;
  return true;
}

function validate() {
  const step = state.steps[state.step];
  if (step.kind === "providers") {
    if (state.selected.size === 0) {
      return "至少选择一个供应商。正式运行必须有真实模型。";
    }
    return null;
  }
  if (step.kind === "credentials") {
    const bad = [...state.selected].filter((slot) => !slotReady(slot));
    if (bad.length > 0) {
      return `还缺少 key、模型名或地址：${bad.map(slotLabel).join("、")}`;
    }
    return null;
  }
  if (step.kind === "assign") {
    const missing = exclusiveAgents().filter(
      (agent) => (state.assignments[agent] ?? []).length !== 1,
    );
    if (missing.length > 0) {
      return `还有 Agent 没有分配模型：${missing.map((a) => agentFor(a).title).join("、")}`;
    }
    return null;
  }
  if (step.kind === "pairs") {
    if (state.pairs.length === 0) return "至少配一对：一个模型提方案，一个模型评分。";
    const seen = new Set();
    for (const pair of state.pairs) {
      const key = `${pair.plan}>${pair.check}`;
      if (seen.has(key)) {
        return `配对重复：${slotLabel(pair.plan)} 提 · ${slotLabel(pair.check)} 审。`;
      }
      seen.add(key);
    }
    return null;
  }
  return null;
}

// --- renderers -----------------------------------------------------------

function recId(item) {
  return typeof item === "string" ? item : item.id;
}

function recChip(item) {
  if (typeof item === "string") return item;
  return item.score != null ? `${item.label} · ${item.id}` : item.id;
}

function flowEdge(edge, fromLevel, toLevel) {
  const pulses = (count) =>
    Array.from({ length: count }, () => el("span", { class: "flow-pulse" }));
  return el(
    "div",
    {
      class: "flow-edge",
      "data-loop": edge?.loop ? "true" : "false",
      "data-from": fromLevel ?? "",
      "data-to": toLevel ?? "",
    },
    el("span", { class: "flow-edge-line", "aria-hidden": "true" }, pulses(3)),
    edge?.loop
      ? el(
          "span",
          { class: "flow-edge-line flow-edge-back", "aria-hidden": "true" },
          pulses(2),
        )
      : null,
    edge?.label ? el("span", { class: "flow-edge-label", text: edge.label }) : null,
  );
}

function flowNode(node, { focused } = {}) {
  return el(
    "button",
    {
      type: "button",
      class: "flow-node",
      "data-agent": node.id,
      "data-level": node.level,
      "data-on": String(Boolean(focused)),
      "aria-label": `${node.title}，思考${node.level}。${node.hover}`,
    },
    el("span", { class: "flow-dot", "aria-hidden": "true" }),
    el("span", { class: "flow-title", text: node.title }),
    el("span", { class: "flow-tip", text: node.hover }),
  );
}

function renderFlow(focus) {
  const flow = state.catalog.flow;
  const items = [];
  flow.nodes.forEach((node, index) => {
    if (index > 0) {
      const previous = flow.nodes[index - 1];
      const edge =
        (flow.edges ?? []).find(
          (item) => item.from === previous.id && item.to === node.id,
        ) ?? { from: previous.id, to: node.id, label: "" };
      items.push(flowEdge(edge, previous.level, node.level));
    }
    items.push(flowNode(node, { focused: focus === node.id }));
  });
  return el(
    "div",
    {
      class: "flow",
      "data-mode": focus ? "focus" : "overview",
      "data-focus": focus ?? "",
    },
    el("div", { class: "flow-track" }, items),
    el(
      "div",
      { class: "flow-legend", "aria-hidden": "true" },
      el("span", { "data-level": "低", text: "低" }),
      el("span", { "data-level": "中", text: "中" }),
      el("span", { "data-level": "高", text: "高" }),
    ),
    focus ? null : el("p", { class: "flow-caption", text: flow.caption }),
  );
}

function renderWelcome() {
  const product = state.catalog.product;
  return [
    el("h1", { text: `${product.name}：${product.tagline}` }),
    el("p", { class: "lede", text: product.idea }),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "它是什么" }),
      (product.story ?? []).map((item) => el("p", { class: "story", text: item })),
      el("p", { class: "hint", text: product.scope }),
    ),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "核心流程" }),
      el(
        "p",
        {
          class: "pick-note",
          text: "五个环节横着走。圆点颜色是思考强度，线上的光点是数据在往下流。悬停圆点看细节。",
        },
      ),
      renderFlow(null),
    ),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "怎么保证结论可核对" }),
      el(
        "ul",
        { class: "bullets" },
        product.boundaries.map((item) => el("li", { text: item })),
      ),
    ),
    el("p", { class: "hint", text: "接下来按流程逐个介绍五个环节，然后填写模型配置。" }),
  ];
}

function renderAgent(name) {
  const agent = agentFor(name);
  const asOf = agent.ranking_as_of ?? state.catalog.ranking_as_of;
  return [
    el("p", { class: "eyebrow", text: `环节 ${agent.step} / 5 · 思考 ${agent.thinking_level}` }),
    el("h1", { text: agent.title }),
    el("p", { class: "lede", text: agent.role }),
    el(
      "section",
      { class: "card flow-card" },
      renderFlow(name),
      el(
        "p",
        {
          class: "flow-guide",
          text: `当前放大的是「${agent.title}」。思考强度：${agent.thinking_level}。${agent.role}。`,
        },
      ),
    ),
    el(
      "section",
      { class: "card" },
      el("p", { text: agent.text }),
      el(
        "ul",
        { class: "bullets" },
        agent.highlights.map((item) => el("li", { text: item })),
      ),
    ),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "选模型时注意" }),
      el("p", { text: agent.needs }),
      el(
        "ul",
        { class: "chips" },
        agent.recommended.map((item) =>
          el("li", { class: "chip", "data-tone": "accent", text: recChip(item) }),
        ),
      ),
      el("p", {
        class: "hint",
        text: asOf
          ? `参考型号按 ${asOf} 的智能指数名单挑选，填进下一页时用芯片里的英文 id。同能力可以替换。`
          : "这只是参考。同能力的模型都可以替换。",
      }),
    ),
  ];
}

function renderProviders() {
  const cards = state.catalog.vendors.map((vendor) => {
    const on = state.selected.has(vendor.slot);
    const stored = state.slots[vendor.slot]?.keyStored;
    return el(
      "button",
      {
        type: "button",
        class: "pick",
        "data-on": String(on),
        "aria-pressed": String(on),
        onclick: () => {
          if (on) state.selected.delete(vendor.slot);
          else state.selected.add(vendor.slot);
          pruneToSelected();
          render();
        },
      },
      el("span", { class: "pick-box", text: on ? "✓" : "" }),
      el(
        "span",
        {},
        el("span", { class: "pick-title", text: vendor.label }),
        el(
          "span",
          { class: "pick-note" },
          el("br"),
          `默认模型 ${vendor.default_model}`,
          stored ? el("br") : null,
          stored ? ".env 中已有 key" : null,
        ),
      ),
    );
  });

  return [
    el("h1", { text: "选择你有 key 的供应商" }),
    el("p", { class: "lede", text: "可以多选。一家的 key 只填一次，后面分配时可以复用给多个 Agent。" }),
    el("div", { class: "picker" }, cards),
    el("p", {
      class: "hint",
      text: "填两家或以上，方案生成与评分就能交叉互审：一家提方案、另一家审。",
    }),
  ];
}

function renderCredentials() {
  if (state.selected.size === 0) {
    return [el("p", { class: "lede", text: "先回到上一步选择供应商。" })];
  }

  const cards = [...state.selected].map((slot) => {
    const vendor = vendorFor(slot);
    const config = state.slots[slot];

    const probeLine = el("span", {
      class: "probe-msg",
      "data-tone": config.probe ? (config.probe.ok ? "ok" : "bad") : "",
      text: config.probe ? config.probe.message : "",
    });

    return el(
      "section",
      { class: "card" },
      el("h2", { text: vendor.label }),
      el(
        "label",
        { class: "field" },
        el("span", { text: "API key" }),
        el("input", {
          type: "password",
          autocomplete: "off",
          spellcheck: "false",
          placeholder: config.keyStored
            ? `已保存 ${config.maskedKey}，留空表示不修改`
            : "粘贴你的 key",
          value: config.api_key,
          oninput: (event) => {
            config.api_key = event.target.value;
            config.probe = null;
            refreshFoot();
          },
        }),
      ),
      el(
        "div",
        { class: "field-row" },
        el(
          "label",
          { class: "field" },
          el("span", { text: "模型名" }),
          el("input", {
            type: "text",
            spellcheck: "false",
            placeholder: vendor.default_model,
            value: config.model,
            oninput: (event) => {
              config.model = event.target.value;
              config.probe = null;
              refreshFoot();
            },
          }),
        ),
        el(
          "label",
          { class: "field" },
          el("span", { text: "接口风格" }),
          el(
            "select",
            {
              onchange: (event) => {
                config.api_style = event.target.value;
                config.probe = null;
                render();
              },
            },
            ["chat_completions", "responses"].map((option) =>
              el("option", {
                value: option,
                text: option,
                ...(config.api_style === option ? { selected: "selected" } : {}),
              }),
            ),
          ),
        ),
      ),
      el(
        "label",
        { class: "field" },
        el("span", { text: "base_url（已填好官方地址；用中转服务时改这里，填到 /v1 一级）" }),
        el("input", {
          type: "text",
          spellcheck: "false",
          placeholder: vendor.default_base_url,
          value: config.base_url,
          oninput: (event) => {
            config.base_url = event.target.value;
            config.probe = null;
            refreshFoot();
          },
        }),
      ),
      el(
        "div",
        { class: "probe-row" },
        el("button", {
          type: "button",
          class: "quiet",
          text: "测试连接",
          onclick: (event) => probe(slot, event.target, probeLine),
        }),
        probeLine,
      ),
    );
  });

  return [
    el("h1", { text: "填入 key 与模型" }),
    el("p", {
      class: "lede",
      text: "key 只写入本机仓库根目录的 .env，不会进数据库、日志或前端页面。",
    }),
    cards,
  ];
}

async function probe(slot, button, line) {
  const config = state.slots[slot];
  button.disabled = true;
  line.textContent = "正在测试…";
  line.setAttribute("data-tone", "");
  try {
    const result = await api("/api/probe", {
      method: "POST",
      body: JSON.stringify({
        slot,
        api_key: config.api_key.trim() || (config.keyStored ? KEEP : ""),
        base_url: config.base_url.trim(),
        model: config.model.trim(),
        api_style: config.api_style,
      }),
    });
    config.probe = result;
    line.textContent = result.message;
    line.setAttribute("data-tone", result.ok ? "ok" : "bad");
  } catch (error) {
    config.probe = { ok: false, message: String(error.message ?? error) };
    line.textContent = config.probe.message;
    line.setAttribute("data-tone", "bad");
  } finally {
    button.disabled = false;
  }
}

function renderAssign() {
  const slots = [...state.selected];
  const cards = exclusiveAgents().map((name) => {
    const agent = agentFor(name);
    const chosen = state.assignments[name] ?? [];

    const options = slots.map((slot) => {
      const on = chosen.includes(slot);
      return el(
        "button",
        {
          type: "button",
          class: "pick",
          "data-on": String(on),
          "aria-pressed": String(on),
          onclick: () => {
            state.assignments[name] = on ? [] : [slot];
            render();
          },
        },
        el("span", { class: "pick-box", "data-round": "true", text: on ? "✓" : "" }),
        el("span", { class: "pick-title", text: slotLabel(slot) }),
      );
    });

    return el(
      "section",
      { class: "card" },
      el("p", { class: "eyebrow", text: `Agent ${agent.step} · 单选` }),
      el("h2", { text: agent.title }),
      el("p", { class: "pick-note", text: agent.role }),
      el("div", { class: "picker" }, options),
      el("p", {
        class: "hint",
        text: `${agent.needs} 参考：${agent.recommended.map(recId).join(" / ")}`,
      }),
    );
  });

  return [
    el("h1", { text: "把模型分配给每个 Agent" }),
    el("p", {
      class: "lede",
      text: "这三个环节各由一个模型承担。同一个模型可以被选多次，分配给不同的 Agent。",
    }),
    cards,
    el("p", {
      class: "hint",
      text: "方案生成与点睛之笔评分要成对配置，放在下一步单独设置。",
    }),
  ];
}

function slotSelect(label, value, onchange) {
  return el(
    "label",
    { class: "field" },
    el("span", { text: label }),
    el(
      "select",
      { onchange },
      [...state.selected].map((slot) =>
        el("option", {
          value: slot,
          text: slotLabel(slot),
          ...(value === slot ? { selected: "selected" } : {}),
        }),
      ),
    ),
  );
}

function renderModes() {
  const paths = pathCount();
  return el(
    "div",
    { class: "modes" },
    state.catalog.plan_modes.map((mode) => {
      const on = mode.paths <= paths;
      return el(
        "div",
        { class: "mode", "data-on": String(on) },
        el(
          "div",
          { class: "mode-name" },
          el("span", { text: mode.title }),
          el("span", {
            class: "mode-paths",
            text: on ? `${mode.paths} 条` : `需 ${mode.paths} 条`,
          }),
        ),
        el("p", { class: "mode-text", text: mode.text }),
      );
    }),
  );
}

function renderCrossChoice() {
  const [first, second] = state.pairs;
  const choices = [
    ["off", null, null, "保持双方案，不补第三条路"],
    ["ad", first.plan, second.check, null],
    ["bc", second.plan, first.check, null],
  ];
  return el(
    "section",
    { class: "card" },
    el("h2", { text: "要不要打开三方案" }),
    el("p", {
      class: "pick-note",
      text: "配了 2 对时默认是双方案。只有你主动选一个交错组合，才会补第三条路。",
    }),
    el(
      "div",
      { class: "picker" },
      choices.map(([value, plan, check, label]) => {
        const on = state.highCross === value;
        const title =
          label ?? `${slotLabel(plan)} 提 · ${slotLabel(check)} 审`;
        return el(
          "button",
          {
            type: "button",
            class: "pick",
            "data-on": String(on),
            "aria-pressed": String(on),
            onclick: () => {
              state.highCross = value;
              render();
            },
          },
          el("span", { class: "pick-box", "data-round": "true", text: on ? "✓" : "" }),
          el(
            "span",
            {},
            el("span", { class: "pick-title", text: title }),
            plan && plan === check
              ? el(
                  "span",
                  { class: "pick-note" },
                  el("br"),
                  "同一个模型自己写自己审",
                )
              : null,
          ),
        );
      }),
    ),
    selfReviewCross()
      ? el("p", {
          class: "hint",
          "data-tone": "warn",
          text: "这个组合里提方案和评分是同一个模型，第三条路等于自己给自己打分。换另一个组合，或者改一下上面某一对。",
        })
      : null,
  );
}

/** True when the chosen crossed pair has the same model on both sides. */
function selfReviewCross() {
  if (state.pairs.length !== 2) return false;
  if (state.highCross !== "ad" && state.highCross !== "bc") return false;
  const [first, second] = state.pairs;
  return state.highCross === "ad"
    ? first.plan === second.check
    : second.plan === first.check;
}

/** Providers that hold a key but never get called. */
function idleSlots() {
  const busy = new Set();
  for (const slots of Object.values(state.assignments)) {
    for (const slot of slots) busy.add(slot);
  }
  for (const pair of state.pairs) {
    busy.add(pair.plan);
    busy.add(pair.check);
  }
  return [...state.selected].filter((slot) => !busy.has(slot));
}

function renderPairs() {
  ensurePairs();
  if (state.selected.size === 0) {
    return [el("p", { class: "lede", text: "先回到上一步选择供应商。" })];
  }

  const max = state.catalog.max_pairs;
  const rule =
    state.catalog.pairing.by_count.find((item) => item.pairs === state.pairs.length) ??
    null;

  const rows = state.pairs.map((pair, index) =>
    el(
      "section",
      { class: "card" },
      el(
        "div",
        { class: "pair-head" },
        el("p", { class: "eyebrow", text: `第 ${index + 1} 条路径` }),
        state.pairs.length > 1
          ? el("button", {
              type: "button",
              class: "quiet",
              text: "移除",
              onclick: () => {
                state.pairs.splice(index, 1);
                if (state.pairs.length !== 2) state.highCross = "off";
                render();
              },
            })
          : null,
      ),
      el(
        "div",
        { class: "pair-body" },
        slotSelect("谁来想方案", pair.plan, (event) => {
          pair.plan = event.target.value;
          render();
        }),
        el("span", { class: "pair-arrow", text: "→" }),
        slotSelect("谁来评分", pair.check, (event) => {
          pair.check = event.target.value;
          render();
        }),
      ),
      pair.plan === pair.check
        ? el("p", {
            class: "hint",
            "data-tone": "warn",
            text: "这条路是同一个模型自己写、自己审，容易给自己放水。建议换成另一家。",
          })
        : null,
    ),
  );

  return [
    el("h1", { text: "方案生成与评分，成对配置" }),
    el("p", {
      class: "lede",
      text: "每一对是一条候选路径：一个模型出方案，另一个模型给它打分。配几对，就决定了你能用哪些模式。",
    }),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "三种模式" }),
      renderModes(),
      rule ? el("p", { class: "hint", text: rule.text }) : null,
    ),
    rows,
    el(
      "div",
      { class: "pair-add" },
      el("button", {
        type: "button",
        class: "quiet",
        text: state.pairs.length >= max ? `最多 ${max} 对` : "再加一对",
        disabled: state.pairs.length >= max ? "disabled" : null,
        onclick: () => {
          const slots = [...state.selected];
          const used = state.pairs.length;
          state.pairs.push({
            plan: slots[used % slots.length],
            check: slots[(used + 1) % slots.length],
          });
          // 加到 2 对时不要沿用旧 .env 里的 ad/bc，否则会直接跳进三方案。
          state.highCross = "off";
          render();
        },
      }),
    ),
    state.pairs.length === 2 ? renderCrossChoice() : null,
    el("p", { class: "hint", text: state.catalog.pairing.advice }),
  ];
}

function secretField(label, key, stored, masked, placeholder) {
  return el(
    "label",
    { class: "field" },
    el("span", { text: label }),
    el("input", {
      type: "password",
      autocomplete: "off",
      spellcheck: "false",
      placeholder: stored ? `已保存 ${masked}，留空表示不修改` : placeholder,
      value: state.optional[key] === KEEP ? "" : state.optional[key],
      oninput: (event) => {
        const text = event.target.value;
        state.optional[key] = text.trim() === "" && stored ? KEEP : text;
      },
    }),
  );
}

function renderOptional() {
  const option = state.current.optional;
  const cards = state.catalog.optional.map((item) => {
    const body = [
      el(
        "p",
        { class: "eyebrow" },
        item.advanced ? "进阶，一般不用管" : item.recommended ? "推荐配上" : "可以跳过",
      ),
      el("h2", { text: item.title }),
      el("p", { text: item.why }),
      el("p", { class: "pick-note", text: `不配置：${item.without}` }),
      el("p", { class: "hint", text: item.how }),
      item.url
        ? el(
            "p",
            {},
            el("a", { href: item.url, target: "_blank", rel: "noreferrer", text: item.url }),
          )
        : null,
      item.command
        ? el("pre", { class: "hint", text: item.command })
        : null,
    ];

    if (item.key === "openalex") {
      body.push(
        secretField(
          "OpenAlex key",
          "openalex_api_key",
          option.openalex_has_key,
          option.openalex_masked,
          "留空则和其他人共用通道",
        ),
      );
    } else if (item.key === "hf_token") {
      body.push(
        secretField(
          "Hugging Face 访问令牌",
          "hf_token",
          option.hf_has_token,
          option.hf_masked,
          "留空即走镜像",
        ),
        el(
          "label",
          { class: "field" },
          el("span", { text: "下载来源" }),
          el(
            "select",
            {
              onchange: (event) => {
                state.optional.hf_endpoint = event.target.value;
              },
            },
            [
              ["", "不指定"],
              ["mirror", "ModelScope（国内推荐）"],
              ["hf-mirror", "hf-mirror.com"],
              ["official", "Hugging Face 官方"],
            ].map(([value, text]) =>
              el("option", {
                value,
                text,
                ...(state.optional.hf_endpoint === value ? { selected: "selected" } : {}),
              }),
            ),
          ),
        ),
      );
    } else if (item.key === "database") {
      body.push(
        secretField(
          "数据库地址",
          "database_url",
          option.database_has_url,
          option.database_masked,
          "留空则存成本机文件",
        ),
      );
    } else if (item.key === "reranker") {
      body.push(
        el(
          "label",
          { class: "field" },
          el("span", { text: "排序方式" }),
          el(
            "select",
            {
              onchange: (event) => {
                state.optional.reranker_backend = event.target.value;
              },
            },
            [
              ["auto", "自动：下载好了就按意思排，没下就明确告诉你"],
              ["lexical", "只按字面找词"],
              ["unavailable", "关掉这个功能"],
            ].map(([value, text]) =>
              el("option", {
                value,
                text,
                ...(state.optional.reranker_backend === value
                  ? { selected: "selected" }
                  : {}),
              }),
            ),
          ),
        ),
      );
    }

    return el("section", { class: "card" }, body);
  });

  return [
    el("h1", { text: "还有几个可选项" }),
    el("p", {
      class: "lede",
      text: "全部跳过也能正常用，之后重跑一次 rigora-setup 就能补上。建议至少把第一项配好。",
    }),
    cards,
  ];
}

function renderDone() {
  if (state.saved === null) {
    const rows = exclusiveAgents().map((agent) =>
      el(
        "div",
        {},
        el("span", { text: agentFor(agent).title }),
        el("span", { text: (state.assignments[agent] ?? []).map(slotLabel).join("、") || "—" }),
      ),
    );
    const pathRows = expandedPairs().map(([plan, check], index) =>
      el(
        "div",
        {},
        el("span", { text: `路径 ${index + 1}` }),
        el("span", { text: `${slotLabel(plan)} 提 · ${slotLabel(check)} 审` }),
      ),
    );

    const idle = idleSlots();
    return [
      el("h1", { text: "写入配置" }),
      el("p", { class: "lede", text: "确认无误后点右下角「写入 .env」。" }),
      el(
        "section",
        { class: "card" },
        el("h2", { text: "即将写入" }),
        el("div", { class: "summary" }, rows, pathRows),
        el("p", {
          class: "hint",
          text:
            `可用模式：${state.catalog.plan_modes
              .filter((mode) => mode.paths <= pathCount())
              .map((mode) => mode.title)
              .join(" / ")}。` +
            `文件写入 ${state.current.env_path}，权限 600。`,
        }),
        idle.length > 0
          ? el("p", {
              class: "hint",
              "data-tone": "warn",
              text:
                `这些供应商填了 key 但没被用到，不会产生任何调用：${idle
                  .map(slotLabel)
                  .join("、")}。` + "key 仍会写进 .env，之后重跑就能直接分配。",
            })
          : null,
      ),
    ];
  }

  return [
    el("h1", { text: "配置完成" }),
    el("p", { class: "lede", text: `已写入 ${state.saved.env_path}` }),
    el(
      "section",
      { class: "card" },
      el("h2", { text: "接下来" }),
      el(
        "ol",
        { class: "bullets" },
        el("li", { text: "uv run alembic upgrade head" }),
        el("li", {
          text: "uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000",
        }),
        el("li", { text: "另一个终端：cd frontend && npm install && npm run dev" }),
      ),
      el("p", {
        class: "hint",
        text: "服务已在运行的话需要重启才会读到新配置。这个引导页可以关掉了。",
      }),
    ),
  ];
}

// --- shell ---------------------------------------------------------------

function refreshFoot() {
  const step = state.steps[state.step];
  const problem = validate();
  const note = document.getElementById("footNote");
  const next = document.getElementById("nextButton");
  const back = document.getElementById("backButton");

  back.disabled = state.step === 0 || state.saved !== null;
  next.disabled = state.busy || problem !== null || state.saved !== null;
  next.textContent =
    step.kind === "done" ? "写入 .env" : step.kind === "optional" ? "确认配置" : "下一步";
  if (state.saved !== null) next.textContent = "已完成";
  note.textContent = state.busy ? "正在写入…" : (problem ?? "");
  note.setAttribute("data-tone", problem === null ? "" : "bad");
}

function render() {
  const stage = document.getElementById("stage");
  stage.replaceChildren();
  const step = state.steps[state.step];
  const byKind = {
    welcome: renderWelcome,
    agent: () => renderAgent(step.name),
    providers: renderProviders,
    credentials: renderCredentials,
    assign: renderAssign,
    pairs: renderPairs,
    optional: renderOptional,
    done: renderDone,
  };
  for (const node of byKind[step.kind]().flat()) if (node) stage.append(node);

  const rail = document.getElementById("rail");
  rail.replaceChildren();
  state.steps.forEach((_, index) => {
    rail.append(el("span", { "data-on": String(index <= state.step) }));
  });

  refreshFoot();
}

async function save() {
  state.busy = true;
  refreshFoot();
  try {
    state.saved = await api("/api/save", {
      method: "POST",
      body: JSON.stringify({
        slots: [...state.selected].map((slot) => {
          const config = state.slots[slot];
          return {
            slot,
            api_key: config.api_key.trim() || (config.keyStored ? KEEP : ""),
            base_url: config.base_url.trim(),
            model: config.model.trim(),
            api_style: config.api_style,
          };
        }),
        assignments: Object.fromEntries(
          exclusiveAgents().map((agent) => [agent, state.assignments[agent] ?? []]),
        ),
        pairs: state.pairs,
        high_cross: state.highCross,
        optional: state.optional,
      }),
    });
  } catch (error) {
    state.busy = false;
    const note = document.getElementById("footNote");
    note.textContent = String(error.message ?? error);
    note.setAttribute("data-tone", "bad");
    return;
  }
  state.busy = false;
  render();
}

function goNext() {
  if (validate() !== null) return;
  const step = state.steps[state.step];
  if (step.kind === "done") {
    void save();
    return;
  }
  state.step = Math.min(state.step + 1, state.steps.length - 1);
  render();
  document.getElementById("stage").focus();
  window.scrollTo({ top: 0 });
}

function goBack() {
  state.step = Math.max(state.step - 1, 0);
  render();
  window.scrollTo({ top: 0 });
}

// --- theme ---------------------------------------------------------------

/** Light unless the user picked dark here before. System preference is ignored. */
function readTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  const button = document.getElementById("themeToggle");
  if (button) button.textContent = theme === "dark" ? "深色" : "浅色";
}

function toggleTheme() {
  const next = readTheme() === "dark" ? "light" : "dark";
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* 隐私模式下写不进去也不影响当前会话 */
  }
  applyTheme(next);
}

async function boot() {
  applyTheme(readTheme());
  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
  document.getElementById("nextButton").addEventListener("click", goNext);
  document.getElementById("backButton").addEventListener("click", goBack);

  try {
    const [catalogPayload, currentPayload] = await Promise.all([
      api("/api/catalog"),
      api("/api/current"),
    ]);
    state.catalog = catalogPayload;
    state.current = currentPayload;
    buildSteps();
    seedFromCurrent();
    render();
  } catch (error) {
    document.getElementById("stage").replaceChildren(
      el("p", { class: "lede", text: `载入失败：${error.message ?? error}` }),
    );
  }
}

void boot();
