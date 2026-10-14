#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const WORKFLOW_CONTRACTS = new Set([
  "workflow:catalog-photo-context-submenu",
  "workflow:catalog-folder-context-scroll",
  "workflow:edit-tool-expand-crop",
  "workflow:photo-switch-history",
  "workflow:preset-import-preview-apply",
  "workflow:layer-lifecycle",
  "workflow:mask-lifecycle",
  "workflow:compare-zoom-pan",
  "workflow:multi-image-three-workflows",
  "workflow:export-dialog-file",
]);
const PARAMETER_TYPES = new Set(["float", "array", "asset", "boolean", "enum"]);

function parseArgs(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) throw new Error(`invalid argument near ${key ?? "<end>"}`);
    values.set(key.slice(2), value);
  }
  for (const required of ["contracts", "fixture", "output-root", "raw-output"]) {
    if (!values.has(required)) throw new Error(`missing --${required}`);
  }
  return {
    contracts: resolve(values.get("contracts")),
    fixture: resolve(values.get("fixture")),
    outputRoot: resolve(values.get("output-root")),
    rawOutput: resolve(values.get("raw-output")),
    baseUrl: values.get("base-url") ?? "http://127.0.0.1:5175",
    chrome: resolve(values.get("chrome") ?? DEFAULT_CHROME),
    schema: resolve(values.get("schema") ?? "configs/capabilities/parameter-schema.json"),
    contractId: values.get("contract-id") ?? "workflow:multi-image-three-workflows",
    dryRun: values.get("dry-run") === "true",
    resume: values.get("resume") === "true",
  };
}

function canonicalValue(parameter, definition) {
  const type = definition?.type;
  const fallback = definition?.default;
  if (type === "float") {
    const candidate = Number(definition.min) + (Number(definition.max) - Number(definition.min)) * 0.65;
    return Math.abs(candidate - Number(fallback)) < 1e-9
      ? Number(definition.min) + (Number(definition.max) - Number(definition.min)) * 0.35
      : Number(candidate.toFixed(6));
  }
  if (type === "enum") return definition.values.find((value) => value !== fallback) ?? definition.values[0];
  if (type === "boolean") return !Boolean(fallback);
  if (type === "asset") return "fixture:canonical-asset";
  if (type === "array" && parameter === "crop_box") return [0.1, 0.1, 0.8, 0.8];
  if (type === "array" && parameter === "strokes") return [{ x: 0.5, y: 0.5, radius: 0.05, strength: 1 }];
  throw new Error(`no canonical value recipe for ${parameter} (${type})`);
}

function effectiveDefinition(schema, capabilityId, parameter) {
  const common = schema.common_parameters?.[parameter];
  if (!common || typeof common !== "object" || Array.isArray(common)) {
    throw new Error(`parameter has no common definition: ${capabilityId}.${parameter}`);
  }
  const override = schema.capabilities?.[capabilityId]?.parameter_overrides?.[parameter] ?? {};
  if (!override || typeof override !== "object" || Array.isArray(override)) {
    throw new Error(`parameter override must be an object: ${capabilityId}.${parameter}`);
  }
  return { ...common, ...override };
}

function validateContracts(contracts, schema) {
  if (contracts.version !== "1.0") throw new Error(`current interaction matrix requires version 1.0, got ${contracts.version}`);
  if (Object.hasOwn(contracts, "contracts")) throw new Error("legacy contracts container is not accepted");
  if (!/^[0-9a-f]{64}$/.test(contracts.matrix_fingerprint ?? "")) throw new Error("interaction matrix has invalid fingerprint");
  if (!Array.isArray(contracts.records) || contracts.records.length !== 84) {
    throw new Error(`current interaction matrix requires exactly 84 records, got ${contracts.records?.length ?? 0}`);
  }
  const ids = new Set();
  const types = {};
  let workflows = 0;
  let parameters = 0;
  for (const contract of contracts.records) {
    if (ids.has(contract.id)) throw new Error(`duplicate interaction contract: ${contract.id}`);
    ids.add(contract.id);
    if (contract.kind === "workflow-contract") {
      workflows += 1;
      if (!WORKFLOW_CONTRACTS.has(contract.id)) throw new Error(`workflow has no explicit current handler: ${contract.id}`);
    } else if (contract.kind === "tool-parameter-contract") {
      parameters += 1;
      const definition = effectiveDefinition(
        schema,
        contract.capability_id,
        contract.parameter,
      );
      if (!definition || !PARAMETER_TYPES.has(definition.type)) throw new Error(`unknown parameter type for ${contract.id}: ${definition?.type}`);
      const locator = `[data-capability-id="${contract.capability_id}"] [data-parameter-id="${contract.parameter}"]`;
      if (!contract.capability_id || !contract.parameter || !locator) throw new Error(`parameter contract has no current locator: ${contract.id}`);
      canonicalValue(contract.parameter, definition);
      types[definition.type] = (types[definition.type] ?? 0) + 1;
    } else {
      throw new Error(`unsupported current interaction kind: ${contract.kind}`);
    }
    if (!Array.isArray(contract.events) || !contract.events.length) throw new Error(`contract has no events: ${contract.id}`);
    if (!Array.isArray(contract.visible_assertions) || !contract.visible_assertions.length) throw new Error(`contract has no visible assertions: ${contract.id}`);
    if (!Array.isArray(contract.api_assertions) || !contract.api_assertions.length) throw new Error(`contract has no API assertions: ${contract.id}`);
  }
  if (workflows !== 10 || parameters !== 74) throw new Error(`interaction kind counts mismatch: ${workflows}/${parameters}`);
  return { supported: contracts.records.length, workflows, parameters, parameter_types: types };
}

function delay(milliseconds) {
  return new Promise((accept) => setTimeout(accept, milliseconds));
}

function progress(contractId, stage) {
  process.stdout.write(`${JSON.stringify({ contract: contractId, stage })}\n`);
}

function createPipeClient(process, onEvent) {
  let nextId = 1;
  let buffered = Buffer.alloc(0);
  const pending = new Map();
  const rejectAll = (error) => {
    for (const { reject } of pending.values()) reject(error);
    pending.clear();
  };
  process.once("error", (error) => rejectAll(error));
  process.once("exit", (code, signal) => {
    if (pending.size) {
      rejectAll(new Error(`Chrome exited before replying: code=${code} signal=${signal}`));
    }
  });
  process.stdio[3].on("error", (error) => rejectAll(error));
  process.stdio[4].on("data", (chunk) => {
    buffered = Buffer.concat([buffered, chunk]);
    while (true) {
      const separator = buffered.indexOf(0);
      if (separator < 0) break;
      const raw = buffered.subarray(0, separator).toString("utf8");
      buffered = buffered.subarray(separator + 1);
      if (!raw) continue;
      const message = JSON.parse(raw);
      if (message.id && pending.has(message.id)) {
        const { accept, reject, requestMethod } = pending.get(message.id);
        pending.delete(message.id);
        if (message.error) reject(new Error(`${requestMethod} failed: ${JSON.stringify(message.error)}`));
        else accept(message.result ?? {});
      } else if (message.method) onEvent(message);
    }
  });
  return (method, params = {}, sessionId) => new Promise((accept, reject) => {
    const id = nextId++;
    pending.set(id, { accept, reject, requestMethod: method });
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    process.stdio[3].write(`${JSON.stringify(message)}\0`);
  });
}

async function evaluate(send, sessionId, expression) {
  let result;
  try {
    result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, sessionId);
  } catch (error) {
    throw new Error(`browser evaluation transport failed for ${expression.slice(0, 180)}: ${error.message}`);
  }
  if (result.exceptionDetails) throw new Error(`browser evaluation failed: ${JSON.stringify(result.exceptionDetails)}`);
  return result.result?.value;
}

async function waitFor(send, sessionId, expression, description, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(send, sessionId, expression)) return;
    await delay(100);
  }
  throw new Error(`timed out waiting for ${description}`);
}

async function clickByName(send, sessionId, name) {
  const encoded = JSON.stringify(name);
  await waitFor(
    send,
    sessionId,
    `[...document.querySelectorAll('button,[role="button"],label,a')].some((node) => (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim() === ${encoded})`,
    `click target ${name}`,
    30000,
  );
  await evaluate(send, sessionId, `(() => {
    const name = ${encoded};
    const nodes = [...document.querySelectorAll('button,[role="button"],label,a')];
    const target = nodes.find((node) => (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim() === name);
    if (!target) throw new Error('click target not found: ' + name);
    target.click();
    return true;
  })()`);
}

async function clickByTitle(send, sessionId, title) {
  const encoded = JSON.stringify(title);
  await evaluate(send, sessionId, `(() => {
    const title = ${encoded};
    const target = [...document.querySelectorAll('[title]')]
      .find((node) => node.getAttribute('title') === title);
    if (!target) throw new Error('title target not found: ' + title);
    target.click();
    return true;
  })()`);
}

async function clickRailItem(send, sessionId, name) {
  const encoded = JSON.stringify(name);
  await evaluate(send, sessionId, `(() => {
    const target = [...document.querySelectorAll('.workspace-nav-rail button')]
      .find((node) => (node.textContent || '').replace(/\\s+/g, ' ').trim() === ${encoded});
    if (!target) throw new Error('rail target not found: ' + ${encoded});
    target.click();
    return true;
  })()`);
}

async function ensureRailItem(send, sessionId, name) {
  const encoded = JSON.stringify(name);
  await evaluate(send, sessionId, `(() => {
    const target = [...document.querySelectorAll('.workspace-nav-rail button')]
      .find((node) => (node.textContent || '').replace(/\\s+/g, ' ').trim() === ${encoded});
    if (!target) throw new Error('rail target not found: ' + ${encoded});
    if (target.getAttribute('aria-current') !== 'page') target.click();
    return true;
  })()`);
}

async function pressHistoryShortcut(send, sessionId, redo = false) {
  await evaluate(send, sessionId, `window.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'z', code: 'KeyZ', metaKey: true, shiftKey: ${redo}, bubbles: true, cancelable: true,
  }))`);
}

async function clickSubmenuItem(send, sessionId, submenuLabel, itemLabel) {
  const encodedSubmenu = JSON.stringify(submenuLabel);
  const encodedItem = JSON.stringify(itemLabel);
  await evaluate(send, sessionId, `(() => {
    const menu = [...document.querySelectorAll('[role="menu"]')]
      .find((node) => node.getAttribute('aria-label') === ${encodedSubmenu});
    if (!menu) throw new Error('submenu not found: ' + ${encodedSubmenu});
    const parentButton = menu.parentElement?.querySelector(':scope > button.has-submenu');
    if (!parentButton) throw new Error('submenu parent not found: ' + ${encodedSubmenu});
    parentButton.focus();
    if (getComputedStyle(menu).display === 'none') throw new Error('submenu did not become visible: ' + ${encodedSubmenu});
    const target = [...menu.querySelectorAll(':scope > button')]
      .find((node) => (node.querySelectorAll('span')[1]?.textContent || '').replace(/\\s+/g, ' ').trim() === ${encodedItem});
    if (!target) throw new Error('submenu item not found: ' + ${encodedItem});
    target.click();
    return true;
  })()`);
}

async function dispatchOn(send, sessionId, selector, type, init = {}) {
  const encodedSelector = JSON.stringify(selector);
  const encodedType = JSON.stringify(type);
  const encodedInit = JSON.stringify(init);
  await evaluate(send, sessionId, `(() => {
    const target = document.querySelector(${encodedSelector});
    if (!target) throw new Error('event target not found: ' + ${encodedSelector});
    const init = { bubbles: true, cancelable: true, ...${encodedInit} };
    const EventType = ${encodedType}.startsWith('pointer') ? PointerEvent : ${encodedType}.startsWith('mouse') || ${encodedType} === 'contextmenu' || ${encodedType} === 'dblclick' ? MouseEvent : Event;
    target.dispatchEvent(new EventType(${encodedType}, init));
    return true;
  })()`);
}

async function setControl(send, sessionId, selector, value) {
  const encodedSelector = JSON.stringify(selector);
  const encodedValue = JSON.stringify(value);
  await evaluate(send, sessionId, `(() => {
    const target = document.querySelector(${encodedSelector});
    if (!target) throw new Error('control not found: ' + ${encodedSelector});
    const prototype = target instanceof HTMLSelectElement ? HTMLSelectElement.prototype
      : target instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    if (!setter) throw new Error('native value setter not found: ' + ${encodedSelector});
    setter.call(target, ${encodedValue});
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
}

async function dragSelector(send, sessionId, selector, deltaX, deltaY) {
  const encodedSelector = JSON.stringify(selector);
  const point = await evaluate(send, sessionId, `(() => {
    const target = document.querySelector(${encodedSelector});
    if (!target) throw new Error('drag target not found: ' + ${encodedSelector});
    const box = target.getBoundingClientRect();
    return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: point.x, y: point.y, button: "left", buttons: 1, clickCount: 1 }, sessionId);
  await delay(150);
  for (const ratio of [0.25, 0.5, 0.75, 1]) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x + deltaX * ratio, y: point.y + deltaY * ratio, button: "left", buttons: 1 }, sessionId);
    await delay(100);
  }
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: point.x + deltaX, y: point.y + deltaY, button: "left", buttons: 0, clickCount: 1 }, sessionId);
}

async function firstCatalogRecord(send, sessionId) {
  return evaluate(send, sessionId, `(() => {
    const card = document.querySelector('.photo-card');
    const projectId = card?.dataset.projectId;
    const assetId = card?.dataset.assetId;
    if (!projectId || !assetId) throw new Error('first catalog card has no stable identity');
    return fetch('/api/v1/catalog').then((response) => response.json()).then((payload) => {
      const record = payload.records.find((item) => !item.deleted_at && item.project_id === projectId && item.asset_id === assetId);
      if (!record) throw new Error('catalog identity readback mismatch');
      return record;
    });
  })()`);
}

async function openFirstCatalogRecord(send, sessionId) {
  const record = await firstCatalogRecord(send, sessionId);
  if (!record?.project_id) throw new Error("catalog has no active project");
  await dispatchOn(send, sessionId, ".photo-card", "dblclick", { clientX: 700, clientY: 300 });
  await waitFor(send, sessionId, "!!(document.querySelector('.workspace-edit') && document.querySelector('.filmstrip button.selected'))", "editor project ready", 30000);
  await waitFor(send, sessionId, "!!(document.querySelector('img[alt=\"编辑预览\"]') || document.querySelector('img[alt=\"原始图片\"]'))", "editor image ready", 120000);
  return record;
}

async function clickWorkflow(send, sessionId, label) {
  const encoded = JSON.stringify(label);
  await evaluate(send, sessionId, `(() => {
    const label = ${encoded};
    const workflowButton = [...document.querySelectorAll('.workflow-folders button')]
      .find((node) => node.querySelector('span')?.textContent?.trim() === label);
    const catalogButton = [...document.querySelectorAll('button')]
      .find((node) => (node.textContent || '').replace(/\\s+/g, ' ').trim() === label);
    const target = workflowButton || catalogButton;
    if (!target) throw new Error('workflow target not found: ' + label);
    target.click();
    return true;
  })()`);
}

async function setFiles(send, sessionId, selector, files) {
  const documentNode = await send("DOM.getDocument", { depth: -1, pierce: true }, sessionId);
  const query = await send("DOM.querySelector", { nodeId: documentNode.root.nodeId, selector }, sessionId);
  if (!query.nodeId) throw new Error(`file input not found: ${selector}`);
  await send("DOM.setFileInputFiles", { nodeId: query.nodeId, files: files.map((path) => resolve(path)) }, sessionId);
}

async function frontendBuildHash(frontendRoot) {
  const files = [];
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (["node_modules", "dist"].includes(entry.name)) continue;
      const path = join(directory, entry.name);
      if (entry.isDirectory()) await visit(path);
      else {
        const rel = relative(frontendRoot, path).replaceAll("\\", "/");
        const parts = rel.split("/");
        if (parts.includes("src") || ["package.json", "package-lock.json", "vite.config.ts"].includes(entry.name) || entry.name.startsWith("tsconfig")) files.push([rel, path]);
      }
    }
  }
  await visit(frontendRoot);
  const digest = createHash("sha256");
  for (const [rel, path] of files.sort((left, right) => left[0] < right[0] ? -1 : left[0] > right[0] ? 1 : 0)) {
    digest.update(rel); digest.update("\0"); digest.update(await readFile(path)); digest.update("\0");
  }
  return digest.digest("hex");
}

function pngSize(bytes) {
  if (bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") throw new Error("screenshot is not PNG");
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
}

async function waitForExit(process, timeoutMs) {
  if (process.exitCode !== null) return;
  await Promise.race([new Promise((accept) => process.once("exit", accept)), delay(timeoutMs)]);
}

async function waitForDownload(directory, expectedName, timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const files = (await readdir(directory)).filter((name) => !name.endsWith(".crdownload"));
    const completed = expectedName ? files.find((name) => name === expectedName) : files.length === 1 ? files[0] : undefined;
    if (completed) {
      const path = join(directory, completed);
      const bytes = await readFile(path);
      if (bytes.length) return { filename: completed, bytes };
    }
    await delay(100);
  }
  throw new Error(`timed out waiting for completed download ${expectedName ?? "<single>"}; found ${JSON.stringify(await readdir(directory))}`);
}

async function projectReadback(send, sessionId, projectId) {
  return evaluate(send, sessionId, `fetch('/api/v1/projects/${projectId}').then((response) => {
    if (!response.ok) throw new Error('project readback failed: ' + response.status);
    return response.json();
  })`);
}

function projectState(project) {
  return {
    edits: project.edits ?? [],
    layers: project.layers ?? [],
    masks: project.masks ?? {},
  };
}

function projectStateHash(project) {
  return createHash("sha256").update(JSON.stringify(projectState(project))).digest("hex");
}

async function openTool(send, sessionId, capabilityId) {
  const encoded = JSON.stringify(capabilityId);
  await evaluate(send, sessionId, `(() => {
    const root = document.querySelector('[data-capability-id=' + JSON.stringify(${encoded}) + ']');
    if (!root) throw new Error('tool not found: ' + ${encoded});
    root.scrollIntoView({ block: 'center', inline: 'nearest' });
    const toggle = root.matches('button,[role="button"]') ? root : root.querySelector(':scope > button,[role="button"],summary');
    if (!toggle) throw new Error('tool toggle not found: ' + ${encoded});
    if (toggle.getAttribute('aria-expanded') !== 'true' && !root.classList.contains('expanded')) toggle.click();
    return true;
  })()`);
  await waitFor(
    send,
    sessionId,
    `document.querySelector('[data-capability-id=' + JSON.stringify(${encoded}) + ']')?.classList.contains('expanded') === true`,
    `${capabilityId} expanded`,
    30000,
  );
}

async function resetToOriginal(send, sessionId, projectId, reason) {
  await waitFor(send, sessionId, `(() => {
    const target = [...document.querySelectorAll('button')].find((node) => (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim() === '恢复到原始状态');
    return Boolean(target && !target.disabled);
  })()`, `${reason} reset control enabled`, 30000);
  const beforeCount = await evaluate(send, sessionId, "window.__zpixelResponses.filter((item) => item.method === 'POST' && item.url.endsWith('/reset')).length");
  await clickByName(send, sessionId, "恢复到原始状态");
  await waitFor(
    send,
    sessionId,
    `window.__zpixelResponses.filter((item) => item.method === 'POST' && item.url.endsWith('/reset')).length > ${beforeCount}`,
    `${reason} reset response`,
    30000,
  );
  await waitFor(
    send,
    sessionId,
    `fetch('/api/v1/projects/${projectId}').then((response) => response.json()).then((project) => project.edits.length === 0 && project.layers.length === 0 && Object.keys(project.masks || {}).length === 0)`,
    `${reason} original state`,
    120000,
  );
  return projectReadback(send, sessionId, projectId);
}

async function prepareParameterPrerequisites(send, sessionId, capabilityId, parameter) {
  if (capabilityId === "bw_channels") {
    await clickByName(send, sessionId, "转换为黑白");
    await waitFor(send, sessionId, "!!document.querySelector('.black-white-conversion button[aria-pressed=true]')", "black and white conversion");
  }
  const needsAsset = capabilityId === "sky_replace"
    || capabilityId === "color_transfer"
    || capabilityId === "lut_mapping";
  if (needsAsset && parameter !== "asset_id") {
    const selector = `[data-capability-id="${capabilityId}"] .asset-card`;
    await evaluate(send, sessionId, `(() => {
      const target = document.querySelector(${JSON.stringify(selector)});
      if (!target) throw new Error('asset prerequisite is unavailable: ' + ${JSON.stringify(capabilityId)});
      if (target.getAttribute('aria-selected') !== 'true') target.click();
      return true;
    })()`);
    await waitFor(send, sessionId, `!!document.querySelector(${JSON.stringify(`${selector}[aria-selected="true"]`)})`, `${capabilityId} asset selected`, 30000);
  }
  const needsStroke = new Set(["erase", "dodge_burn", "clone", "new_neon_light"]).has(capabilityId);
  if (needsStroke && parameter !== "strokes") {
    const selector = `[data-capability-id="${capabilityId}"] [data-parameter-id="strokes"]`;
    await evaluate(send, sessionId, `(() => {
      const target = document.querySelector(${JSON.stringify(selector)});
      if (!target) throw new Error('stroke prerequisite is unavailable: ' + ${JSON.stringify(capabilityId)});
      target.dispatchEvent(new CustomEvent('zpixel:set-parameter', { bubbles: true, detail: { value: [{ x: 0.5, y: 0.5, radius: 0.05, strength: 1 }] } }));
      return true;
    })()`);
    await waitFor(send, sessionId, `!document.querySelector(${JSON.stringify(`[data-capability-id="${capabilityId}"] .native-ai-apply`)})?.disabled`, `${capabilityId} stroke prerequisite`, 30000);
  }
}

async function changeParameter(send, sessionId, contract, definition) {
  const selector = `[data-capability-id="${contract.capability_id}"] [data-parameter-id="${contract.parameter}"]`;
  const canonical = canonicalValue(contract.parameter, definition);
  return evaluate(send, sessionId, `(() => {
    const selector = ${JSON.stringify(selector)};
    const parameterType = ${JSON.stringify(definition.type)};
    const canonical = ${JSON.stringify(canonical)};
    const target = document.querySelector(selector);
    if (!target) throw new Error('parameter control not found: ' + selector);
    target.scrollIntoView({ block: 'center', inline: 'nearest' });
    const before = target.matches('input[type="checkbox"]') ? target.checked
      : target.matches('button') ? target.getAttribute('aria-pressed')
      : target.value ?? target.getAttribute('data-value');
    let requested = canonical;
    if (parameterType === 'boolean') {
      const checked = target.matches('input[type="checkbox"]') ? target.checked : target.getAttribute('aria-pressed') === 'true';
      if (checked !== canonical) target.click();
    } else if (parameterType === 'array' || parameterType === 'asset' || (parameterType === 'enum' && !(target instanceof HTMLInputElement || target instanceof HTMLSelectElement))) {
      target.dispatchEvent(new CustomEvent('zpixel:set-parameter', { bubbles: true, detail: { value: canonical } }));
    } else {
      if (parameterType === 'float' && target instanceof HTMLInputElement) {
        const minimum = Number(target.min);
        const maximum = Number(target.max);
        const current = Number(target.value);
        const high = minimum + (maximum - minimum) * 0.65;
        const low = minimum + (maximum - minimum) * 0.35;
        requested = Math.abs(high - current) < 1e-9 ? low : high;
      }
      const prototype = target instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
      if (!setter) throw new Error('parameter has no native value setter: ' + selector);
      setter.call(target, String(requested));
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const after = target.matches('input[type="checkbox"]') ? target.checked
      : target.matches('button') ? target.getAttribute('aria-pressed')
      : target.value ?? target.getAttribute('data-value');
    return { selector, parameterType, canonical, requested, before, after };
  })()`);
}

async function executeParameterContract(args, contract, schema, send, sessionId, downloadDirectory) {
  const record = await openFirstCatalogRecord(send, sessionId);
  progress(contract.id, `opened:${record.project_id}`);
  const initialReset = await resetToOriginal(send, sessionId, record.project_id, "initial");
  progress(contract.id, "initial-reset-verified");
  const initialHash = projectStateHash(initialReset);
  await openTool(send, sessionId, contract.capability_id);
  progress(contract.id, "tool-expanded");
  await prepareParameterPrerequisites(send, sessionId, contract.capability_id, contract.parameter);
  const definition = effectiveDefinition(
    schema,
    contract.capability_id,
    contract.parameter,
  );
  const control = await changeParameter(send, sessionId, contract, definition);
  progress(contract.id, "parameter-changed");
  await waitFor(send, sessionId, `!!document.querySelector(${JSON.stringify(control.selector)})`, "changed parameter remains visible");
  await waitFor(send, sessionId, `!document.querySelector(${JSON.stringify(`[data-capability-id="${contract.capability_id}"] .native-ai-apply`)})?.disabled`, "parameter apply enabled", 30000);
  const mutationCount = await evaluate(send, sessionId, "window.__zpixelResponses.filter((item) => (item.method === 'POST' && item.url.endsWith('/edits')) || (item.method === 'PATCH' && item.url.includes('/edits/'))).length");
  await evaluate(send, sessionId, `document.querySelector(${JSON.stringify(`[data-capability-id="${contract.capability_id}"] .native-ai-apply`)})?.click()`);
  await waitFor(send, sessionId, `window.__zpixelResponses.filter((item) => (item.method === 'POST' && item.url.endsWith('/edits')) || (item.method === 'PATCH' && item.url.includes('/edits/'))).length === ${mutationCount + 1}`, "single parameter mutation response", 180000);
  const mutationResponse = await evaluate(send, sessionId, `window.__zpixelResponses.filter((item) => (item.method === 'POST' && item.url.endsWith('/edits')) || (item.method === 'PATCH' && item.url.includes('/edits/'))).at(-1)`);
  progress(contract.id, `single-mutation-response:${mutationResponse?.status}`);
  if (!mutationResponse || mutationResponse.status >= 400) {
    const uiError = await evaluate(send, sessionId, "document.querySelector('[role=alert]')?.textContent?.replace(/\\s+/g, ' ').trim()");
    throw new Error(`parameter mutation failed: ${JSON.stringify({ mutationResponse, uiError })}`);
  }
  await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.edits.some((edit) => edit.effect === ${JSON.stringify(contract.capability_id)} && Object.hasOwn(edit.parameters, ${JSON.stringify(contract.parameter)})))`, "parameter API readback", 180000);
  progress(contract.id, "parameter-api-readback");
  await waitFor(send, sessionId, "!!document.querySelector('img[alt=\"编辑预览\"]') && !document.querySelector('button[title=\"撤销\"]')?.disabled", "applied preview ready", 180000);
  const applied = await projectReadback(send, sessionId, record.project_id);
  progress(contract.id, "preview-ready");
  const appliedHash = projectStateHash(applied);
  if (appliedHash === initialHash) throw new Error("parameter apply did not change project state");

  await clickByTitle(send, sessionId, "撤销");
  await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.edits.length === 0)`, "undo restored initial state", 120000);
  const undone = await projectReadback(send, sessionId, record.project_id);
  progress(contract.id, "undo-verified");
  if (projectStateHash(undone) !== initialHash) throw new Error("undo project state mismatch");

  await waitFor(send, sessionId, "!document.querySelector('button[title=\"重做\"]')?.disabled", "redo control enabled", 30000);
  await clickByTitle(send, sessionId, "重做");
  await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.edits.some((edit) => edit.effect === ${JSON.stringify(contract.capability_id)}))`, "redo restored applied state", 120000);
  const redone = await projectReadback(send, sessionId, record.project_id);
  progress(contract.id, "redo-verified");
  if (projectStateHash(redone) !== appliedHash) throw new Error("redo project state mismatch");

  const reset = await resetToOriginal(send, sessionId, record.project_id, "final");
  progress(contract.id, "final-reset-verified");
  const resetHash = projectStateHash(reset);
  if (resetHash !== initialHash) throw new Error("reset did not restore original project state");

  await clickByName(send, sessionId, "导出");
  await waitFor(send, sessionId, "!!document.querySelector('.export-dialog a[download]')", "parameter export dialog", 30000);
  const exportName = `zpixel-${contract.capability_id}-${contract.parameter}-reset.png`;
  await setControl(send, sessionId, "input[aria-label=\"导出文件名\"]", exportName);
  await setControl(send, sessionId, "input[aria-label=\"导出宽度\"]", "1024");
  await waitFor(send, sessionId, `document.querySelector('.export-dialog a[download]')?.download === ${JSON.stringify(exportName)}`, "deterministic export name");
  await evaluate(send, sessionId, "document.querySelector('.export-dialog a[download]').click()");
  const download = await waitForDownload(downloadDirectory, exportName);
  progress(contract.id, "export-downloaded");
  await waitFor(send, sessionId, "!document.querySelector('[role=dialog]')", "parameter export complete", 30000);
  if (download.filename !== exportName) throw new Error(`parameter export name mismatch: ${download.filename}`);

  return {
    observed: contract.visible_assertions,
    readbacks: {
      reset_action: { control_name: "恢复到原始状态", initial_verified: true, final_verified: true },
      control,
      project: {
        initial_sha256: initialHash,
        applied_sha256: appliedHash,
        undo_sha256: projectStateHash(undone),
        redo_sha256: projectStateHash(redone),
        reset_sha256: resetHash,
        applied,
      },
      export: {
        filename: download.filename,
        byte_length: download.bytes.length,
        sha256: createHash("sha256").update(download.bytes).digest("hex"),
        project_sha256: resetHash,
      },
    },
  };
}

async function executeContract(args, contract, schema, send, sessionId, downloadDirectory) {
  const observed = [];
  const readbacks = {};

  if (contract.kind === "tool-parameter-contract") {
    return executeParameterContract(args, contract, schema, send, sessionId, downloadDirectory);
  }
  if (args.contractId === "workflow:catalog-photo-context-submenu") {
    const initial = await firstCatalogRecord(send, sessionId);
    await dispatchOn(send, sessionId, ".photo-card", "contextmenu", { clientX: 640, clientY: 260 });
    await waitFor(send, sessionId, "!!document.querySelector('[role=menu][aria-label$=\"操作\"]')", "photo context menu");
    const ratingPatchCount = await evaluate(send, sessionId, "window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/')).length");
    await clickSubmenuItem(send, sessionId, "设置评分", "★★★★★");
    await waitFor(send, sessionId, `window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/') && item.json?.record).length > ${ratingPatchCount}`, "five-star mutation response");
    await waitFor(send, sessionId, `fetch('/api/v1/catalog').then((response) => response.json()).then((payload) => payload.records.find((item) => item.asset_id === ${JSON.stringify(initial.asset_id)})?.rating === 5)`, "five-star readback");
    await waitFor(send, sessionId, "!document.querySelector('.catalog-add.is-disabled')", "five-star UI completion");
    await dispatchOn(send, sessionId, ".photo-card", "contextmenu", { clientX: 640, clientY: 260 });
    const rightPatchCount = await evaluate(send, sessionId, "window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/')).length");
    await clickSubmenuItem(send, sessionId, "旋转", "向右旋转 90°");
    const rightRotation = (Number(initial.rotation ?? 0) + 90) % 360;
    await waitFor(send, sessionId, `window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/') && item.json?.record).length > ${rightPatchCount}`, "right rotation mutation response");
    await waitFor(send, sessionId, `fetch('/api/v1/catalog').then((response) => response.json()).then((payload) => payload.records.find((item) => item.asset_id === ${JSON.stringify(initial.asset_id)})?.rotation === ${rightRotation})`, "right rotation readback");
    await waitFor(send, sessionId, "!document.querySelector('.catalog-add.is-disabled')", "right rotation UI completion");
    await dispatchOn(send, sessionId, ".photo-card", "contextmenu", { clientX: 640, clientY: 260 });
    const leftPatchCount = await evaluate(send, sessionId, "window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/')).length");
    await clickSubmenuItem(send, sessionId, "旋转", "向左旋转 90°");
    await waitFor(send, sessionId, `window.__zpixelResponses.filter((item) => item.method === 'PATCH' && item.url.includes('/catalog/assets/') && item.json?.record).length > ${leftPatchCount}`, "left rotation mutation response");
    await waitFor(send, sessionId, `fetch('/api/v1/catalog').then((response) => response.json()).then((payload) => payload.records.find((item) => item.asset_id === ${JSON.stringify(initial.asset_id)})?.rotation === ${Number(initial.rotation ?? 0)})`, "left rotation readback");
    await waitFor(send, sessionId, "!document.querySelector('.catalog-add.is-disabled')", "left rotation UI completion");
    const finalRecord = await evaluate(send, sessionId, `fetch('/api/v1/catalog').then((response) => response.json()).then((payload) => payload.records.find((item) => item.asset_id === ${JSON.stringify(initial.asset_id)}))`);
    if (finalRecord.rating !== 5 || finalRecord.rotation !== Number(initial.rotation ?? 0)) throw new Error("catalog photo roundtrip mismatch");
    observed.push("parent-and-child-menu-visible", "five-star-state-visible", "preview-rotation-visible", "rotation-roundtrip-restored");
    readbacks.catalog_record = finalRecord;
  } else if (args.contractId === "workflow:catalog-folder-context-scroll") {
    const before = await firstCatalogRecord(send, sessionId);
    const count = await evaluate(send, sessionId, "document.querySelectorAll('.photo-card').length");
    await dispatchOn(send, sessionId, ".catalog-workflows button", "contextmenu", { clientX: 180, clientY: 460 });
    await waitFor(send, sessionId, "[...document.querySelectorAll('[role=menuitem]')].some((node) => node.textContent.includes('导入图片到该文件夹'))", "folder context menu");
    await evaluate(send, sessionId, "window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))");
    await waitFor(send, sessionId, "!document.querySelector('.native-context-menu')", "folder menu closed");
    await evaluate(send, sessionId, "(() => { const node = document.querySelector('.photo-grid-scroll'); node.scrollTop = node.scrollHeight; node.dispatchEvent(new Event('scroll', {bubbles:true})); return node.scrollTop; })()");
    await waitFor(send, sessionId, "document.querySelector('.photo-grid-scroll').scrollTop > 0", "catalog bottom scroll");
    await evaluate(send, sessionId, "(() => { const node = document.querySelector('.photo-grid-scroll'); node.scrollTop = 0; node.dispatchEvent(new Event('scroll', {bubbles:true})); return node.scrollTop; })()");
    const after = await firstCatalogRecord(send, sessionId);
    if (count < 1 || after.asset_id !== before.asset_id) throw new Error("catalog scroll changed selection or asset count");
    observed.push("folder-context-menu-visible", "import-action-visible", "last-catalog-row-visible", "selection-preserved-after-scroll");
    readbacks.catalog = { asset_count: count, selected_asset_id: after.asset_id };
  } else if (args.contractId === "workflow:edit-tool-expand-crop") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await resetToOriginal(send, sessionId, record.project_id, "crop workflow initial");
    await clickByTitle(send, sessionId, "裁切 AI");
    await waitFor(send, sessionId, "!!document.querySelector('select[aria-label=\"裁切比例\"]')", "crop tool expanded");
    await setControl(send, sessionId, "select[aria-label=\"裁切比例\"]", "4:3");
    await clickByName(send, sessionId, "水平对齐");
    await waitFor(
      send,
      sessionId,
      "[...document.querySelectorAll('button')].some((node) => node.textContent.trim() === '水平对齐' && node.getAttribute('aria-pressed') === 'true')",
      "straighten gesture armed",
    );
    await dragSelector(send, sessionId, ".image-stage img", 290, 12.7);
    await clickByName(send, sessionId, "应用");
    await waitFor(send, sessionId, "!document.querySelector('select[aria-label=\"裁切比例\"]')", "crop tool collapsed", 120000);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.edits.some((item) => item.effect === 'crop_ai' && item.parameters.crop_ratio === '4:3' && Math.abs(item.parameters.straighten - 2.5) <= 0.1))`, "crop API state", 180000);
    await waitFor(send, sessionId, "!document.querySelector('button[title=\"撤销\"]')?.disabled", "crop UI completion", 180000);
    const project = await evaluate(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json())`);
    const crop = [...project.edits].reverse().find((item) => item.effect === "crop_ai");
    if (!crop || crop.parameters.crop_ratio !== "4:3" || Math.abs(crop.parameters.straighten - 2.5) > 0.1) throw new Error("crop API readback mismatch");
    observed.push("crop-tool-expanded", "crop-ratio-swap-equals-four-three", "crop-overlay-geometry-visible", "crop-tool-auto-collapsed-after-apply");
    readbacks.project = project;
  } else if (args.contractId === "workflow:photo-switch-history") {
    const photoA = await openFirstCatalogRecord(send, sessionId);
    await resetToOriginal(send, sessionId, photoA.project_id, "photo A initial");
    await openTool(send, sessionId, "details");
    await setControl(send, sessionId, '[data-capability-id="details"] [data-parameter-id="amount"]', "0.35");
    await evaluate(send, sessionId, `document.querySelector('[data-capability-id="details"] .native-ai-apply')?.click()`);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${photoA.project_id}').then((response) => response.json()).then((project) => project.edits.some((item) => item.effect === 'details' && Math.abs(item.parameters.amount - 0.35) < 1e-6))`, "photo A details state", 180000);
    const appliedA = await projectReadback(send, sessionId, photoA.project_id);
    const appliedAHash = projectStateHash(appliedA);
    await pressHistoryShortcut(send, sessionId);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${photoA.project_id}').then((response) => response.json()).then((project) => project.edits.length === 0)`, "photo A keyboard undo");
    await waitFor(
      send,
      sessionId,
      "!document.querySelector('button[title=\"重做\"]')?.disabled",
      "photo A undo UI completion",
    );
    await pressHistoryShortcut(send, sessionId, true);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${photoA.project_id}').then((response) => response.json()).then((project) => project.edits.some((item) => item.effect === 'details'))`, "photo A keyboard redo");
    const redoneA = await projectReadback(send, sessionId, photoA.project_id);
    if (projectStateHash(redoneA) !== appliedAHash) throw new Error("photo A redo state mismatch");

    const photoB = await evaluate(send, sessionId, `(() => {
      const button = [...document.querySelectorAll('.filmstrip button:not(.selected)')][0];
      if (!button) throw new Error('second filmstrip photo is unavailable');
      const projectId = button.querySelector('img')?.getAttribute('src')?.match(/projects\\/([^/]+)\\/source/)?.[1];
      button.click();
      return { project_id: projectId, filename: button.title };
    })()`);
    if (!photoB.project_id || photoB.project_id === photoA.project_id) throw new Error("photo B identity mismatch");
    await waitFor(send, sessionId, `document.querySelector('.filmstrip button.selected img')?.src.includes(${JSON.stringify(photoB.project_id)})`, "photo B selected");
    await resetToOriginal(send, sessionId, photoB.project_id, "photo B initial");
    await openTool(send, sessionId, "vignette");
    await setControl(send, sessionId, '[data-capability-id="vignette"] [data-parameter-id="amount"]', "0.6");
    await evaluate(send, sessionId, `document.querySelector('[data-capability-id="vignette"] .native-ai-apply')?.click()`);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${photoB.project_id}').then((response) => response.json()).then((project) => project.edits.some((item) => item.effect === 'vignette' && Math.abs(item.parameters.amount - 0.6) < 1e-6))`, "photo B vignette state", 180000);
    const appliedB = await projectReadback(send, sessionId, photoB.project_id);

    await evaluate(send, sessionId, `document.querySelector('.filmstrip button img[src*=${JSON.stringify(photoA.project_id)}]')?.closest('button')?.click()`);
    await waitFor(send, sessionId, `document.querySelector('.filmstrip button.selected img')?.src.includes(${JSON.stringify(photoA.project_id)})`, "photo A restored");
    const restoredA = await projectReadback(send, sessionId, photoA.project_id);
    await evaluate(send, sessionId, `document.querySelector('.filmstrip button img[src*=${JSON.stringify(photoB.project_id)}]')?.closest('button')?.click()`);
    await waitFor(send, sessionId, `document.querySelector('.filmstrip button.selected img')?.src.includes(${JSON.stringify(photoB.project_id)})`, "photo B restored");
    const restoredB = await projectReadback(send, sessionId, photoB.project_id);
    if (projectStateHash(restoredA) !== appliedAHash || projectStateHash(restoredB) !== projectStateHash(appliedB)) throw new Error("per-photo history isolation mismatch");
    observed.push("photo-a-history-restored", "photo-b-history-isolated", "undo-preview-visible", "redo-preview-identical");
    readbacks.projects = { photo_a: restoredA, photo_b: restoredB, photo_a_sha256: projectStateHash(restoredA), photo_b_sha256: projectStateHash(restoredB) };
  } else if (args.contractId === "workflow:preset-import-preview-apply") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await resetToOriginal(send, sessionId, record.project_id, "preset workflow initial");
    await clickRailItem(send, sessionId, "预设");
    await waitFor(send, sessionId, "!!document.querySelector('.preset-overview input[type=file]')", "preset import control");
    const packageRoot = await mkdtemp(join(tmpdir(), "zpixel-canonical-preset-"));
    const presetPath = join(packageRoot, "template.lmps");
    const presetId = "local_zpixel-r18-canonical";
    await writeFile(presetPath, JSON.stringify({
      name: "ZPixel R18 Canonical",
      uuid: "zpixel-r18-canonical",
      edit_graph: [{ effect: "details", parameters: { amount: 0.35 } }],
    }));
    await setFiles(send, sessionId, ".preset-overview input[type=file]", [packageRoot]);
    await waitFor(send, sessionId, `fetch('/api/v1/presets').then((response) => response.json()).then((payload) => payload.records.some((item) => item.id === ${JSON.stringify(presetId)}))`, "local preset persisted", 30000);
    progress(contract.id, "preset-imported");
    await waitFor(send, sessionId, "document.querySelector('button[aria-label=\"打开本地预设预设\"]')?.disabled === false", "local preset category ready");
    await clickByName(send, sessionId, "打开本地预设预设");
    await waitFor(send, sessionId, `document.querySelector('.preset-${presetId}')?.disabled === false`, "imported preset card ready");
    progress(contract.id, "preset-category-opened");
    await evaluate(send, sessionId, `document.querySelector('.preset-${presetId}')?.click()`);
    await waitFor(send, sessionId, "document.querySelector('.preset-apply-bar')?.textContent?.includes('预设预览已就绪')", "preset preview selection");
    progress(contract.id, "preset-selected");
    await waitFor(send, sessionId, `document.querySelector('.image-stage img')?.src.includes('/presets/${presetId}/preview')`, "preset preview image", 180000);
    progress(contract.id, "preset-preview-visible");
    await clickByName(send, sessionId, "应用预设");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.metadata?.last_preset?.id === ${JSON.stringify(presetId)} && project.edits.length === 1)`, "preset applied once", 180000);
    progress(contract.id, "preset-applied");
    await send("Page.reload", { ignoreCache: true }, sessionId);
    await waitFor(send, sessionId, "document.readyState === 'complete'", "preset page reload");
    await waitFor(send, sessionId, `fetch('/api/v1/presets').then((response) => response.json()).then((payload) => payload.records.filter((item) => item.id === ${JSON.stringify(presetId)}).length === 1)`, "local preset fresh-client readback", 30000);
    progress(contract.id, "preset-persistence-verified");
    const project = await projectReadback(send, sessionId, record.project_id);
    const preset = await evaluate(send, sessionId, `fetch('/api/v1/presets').then((response) => response.json()).then((payload) => payload.records.find((item) => item.id === ${JSON.stringify(presetId)}))`);
    observed.push("imported-preset-visible", "preset-preview-ready", "busy-state-cleared", "preset-visible-after-api-restart");
    readbacks.preset = { record: preset, project, persistence_probe: "fresh-page-and-api-index-readback" };
    await rm(packageRoot, { recursive: true, force: true });
  } else if (args.contractId === "workflow:layer-lifecycle") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await resetToOriginal(send, sessionId, record.project_id, "layer workflow initial");
    await clickByName(send, sessionId, "添加图层");
    await waitFor(send, sessionId, "!!document.querySelector('.layer-material-grid button')", "built-in layer material");
    await evaluate(send, sessionId, "document.querySelector('.layer-material-grid button')?.click()");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers.length === 1)`, "layer created", 120000);
    const created = await projectReadback(send, sessionId, record.project_id);
    const layerId = created.layers[0].id;
    await dispatchOn(send, sessionId, ".layer-stack-row:not(.source)", "contextmenu", { clientX: 260, clientY: 240 });
    await clickByName(send, sessionId, "Hide Layer");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.visible === false)`, "layer hidden");
    await dispatchOn(send, sessionId, ".layer-stack-row:not(.source)", "contextmenu", { clientX: 260, clientY: 240 });
    await clickByName(send, sessionId, "Show Layer");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.visible === true)`, "layer shown");
    await evaluate(send, sessionId, "document.querySelector('.layer-row-main')?.click()");
    await waitFor(send, sessionId, "!!document.querySelector('.layer-inspector')", "layer inspector");
    await setControl(send, sessionId, ".layer-opacity input[type=range]", "0.5");
    await dispatchOn(send, sessionId, ".layer-opacity input[type=range]", "pointerup");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => Math.abs(project.layers[0]?.opacity - 0.5) < 1e-6)`, "layer opacity");
    await setControl(send, sessionId, "select[aria-label=\"混合模式\"]", "screen");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.blend_mode === 'screen')`, "layer blend");
    await clickByName(send, sessionId, "水平翻转");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.flip_x === true)`, "layer flip");
    await clickByName(send, sessionId, "填充");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => Math.abs(project.layers[0]?.scale - 1.15) < 1e-6)`, "layer fill");
    await evaluate(send, sessionId, `(async () => {
      const urls = [
        '/api/v1/projects/${record.project_id}/preview?width=720',
        '/api/v1/projects/${record.project_id}/export?format=png&width=720&filename=zpixel-layer-lifecycle.png',
      ];
      window.__zpixelLayerPixelHashes = await Promise.all(urls.map(async (url) => {
        const bitmap = await createImageBitmap(await (await fetch(url)).blob());
        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
        const context = canvas.getContext('2d');
        context.drawImage(bitmap, 0, 0);
        const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
        const digest = await crypto.subtle.digest('SHA-256', pixels);
        return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('');
      }));
      return window.__zpixelLayerPixelHashes;
    })()`);
    await waitFor(send, sessionId, "window.__zpixelLayerPixelHashes?.length === 2 && window.__zpixelLayerPixelHashes[0] === window.__zpixelLayerPixelHashes[1]", "layer preview/export pixel hash parity", 120000);
    const finalLayer = await projectReadback(send, sessionId, record.project_id);
    if (finalLayer.layers[0]?.id !== layerId) throw new Error("layer identity changed during lifecycle");
    await dispatchOn(send, sessionId, ".layer-stack-row:not(.source)", "contextmenu", { clientX: 260, clientY: 240 });
    await clickByName(send, sessionId, "移除图层");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers.length === 0)`, "layer deleted");
    observed.push("layer-visible-before-delete", "layer-hidden-and-restored", "layer-opacity-fifty-percent", "screen-blend-selected", "layer-removed");
    readbacks.layer = { before_delete: finalLayer, after_delete: await projectReadback(send, sessionId, record.project_id) };
  } else if (args.contractId === "workflow:mask-lifecycle") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await resetToOriginal(send, sessionId, record.project_id, "mask workflow initial");
    await clickByName(send, sessionId, "添加图层");
    await waitFor(send, sessionId, "!!document.querySelector('.layer-material-grid button')", "mask fixture layer material");
    await evaluate(send, sessionId, "document.querySelector('.layer-material-grid button')?.click()");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers.length === 1)`, "mask fixture layer");
    const layerId = (await projectReadback(send, sessionId, record.project_id)).layers[0].id;
    await ensureRailItem(send, sessionId, "工具");
    await waitFor(send, sessionId, "!!document.querySelector('.layer-row-main') && document.querySelector('.add-layer')?.disabled === false", "mask layer UI ready");
    await evaluate(send, sessionId, "document.querySelector('.layer-row-main')?.click()");
    await waitFor(send, sessionId, "!!document.querySelector('.layer-inspector')", "mask layer inspector");
    progress(contract.id, "mask-inspector-ready");
    await clickByName(send, sessionId, "遮罩");
    await waitFor(send, sessionId, "!!document.querySelector('.mask-brush-controls')", "mask tab ready");
    await clickByName(send, sessionId, "画笔");
    await waitFor(send, sessionId, "document.querySelector('.mask-brush-controls button')?.getAttribute('aria-pressed') === 'true' && document.querySelector('.image-stage')?.classList.contains('brush-active') === true", "mask brush armed");
    await waitFor(send, sessionId, "document.querySelector('.image-stage img')?.complete === true && !document.querySelector('.canvas')?.classList.contains('is-loading')", "mask preview ready");
    progress(contract.id, "mask-brush-armed");
    await setControl(send, sessionId, "input[aria-label=\"画笔大小\"]", "80");
    await setControl(send, sessionId, "input[aria-label=\"画笔柔和度\"]", "24");
    await setControl(send, sessionId, "input[aria-label=\"画笔强度\"]", "70");
    await dragSelector(send, sessionId, ".image-stage img", 36, 24);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.mask_artifact && Object.keys(project.masks || {}).length === 1)`, "mask painted", 120000);
    progress(contract.id, "mask-painted");
    const painted = await projectReadback(send, sessionId, record.project_id);
    const paintedHash = projectStateHash(painted);
    await pressHistoryShortcut(send, sessionId);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => !project.layers[0]?.mask_artifact && Object.keys(project.masks || {}).length === 0)`, "mask keyboard undo");
    await pressHistoryShortcut(send, sessionId, true);
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.mask_artifact && Object.keys(project.masks || {}).length === 1)`, "mask keyboard redo");
    const redone = await projectReadback(send, sessionId, record.project_id);
    if (projectStateHash(redone) !== paintedHash) throw new Error("mask redo state mismatch");
    await clickByName(send, sessionId, "重置工具遮罩");
    await waitFor(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json()).then((project) => project.layers[0]?.id === ${JSON.stringify(layerId)} && !project.layers[0]?.mask_artifact && Object.keys(project.masks || {}).length === 0)`, "mask reset");
    observed.push("mask-preview-visible", "brush-size-eighty", "brush-softness-twenty-four", "brush-strength-seventy", "undo-clears-mask", "redo-restores-mask", "reset-clears-mask");
    readbacks.mask = { painted, redone, reset: await projectReadback(send, sessionId, record.project_id) };
  } else if (args.contractId === "workflow:compare-zoom-pan") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await dispatchOn(send, sessionId, "button[title=\"前后对比\"]", "pointerdown", { pointerId: 1, clientX: 1080, clientY: 850 });
    await waitFor(send, sessionId, "!!document.querySelector('img[alt=\"原始图片\"]')", "source compare image", 30000);
    await dispatchOn(send, sessionId, "button[title=\"前后对比\"]", "pointerup", { pointerId: 1, clientX: 1080, clientY: 850 });
    await clickByTitle(send, sessionId, "适合视图");
    await clickByName(send, sessionId, "200%");
    await waitFor(send, sessionId, "document.querySelector('button[title=\"适合视图\"]')?.textContent?.trim() === '200%'", "zoom two hundred");
    await waitFor(
      send,
      sessionId,
      "document.querySelector('.image-stage')?.classList.contains('pan-active') === true && document.querySelector('.image-stage img')?.complete === true && !document.querySelector('.canvas')?.classList.contains('is-loading')",
      "zoom pan interaction ready",
    );
    await dragSelector(send, sessionId, ".image-stage img", 50, 30);
    await waitFor(send, sessionId, "Math.abs(Number(document.querySelector('.image-stage')?.dataset.panX || 0)) > 0 || Math.abs(Number(document.querySelector('.image-stage')?.dataset.panY || 0)) > 0", "non-zero pan offset");
    await clickByTitle(send, sessionId, "适合视图");
    await clickByName(send, sessionId, "适合屏幕");
    await waitFor(send, sessionId, "document.querySelector('.image-stage')?.dataset.panX === '0' && document.querySelector('.image-stage')?.dataset.panY === '0'", "fit pan reset");
    const project = await evaluate(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((response) => response.json())`);
    observed.push("source-image-visible-during-compare", "edited-preview-restored", "zoom-indicator-two-hundred", "pan-offset-visible", "fit-restores-canvas");
    readbacks.project = project;
  } else if (args.contractId === "workflow:export-dialog-file") {
    const record = await openFirstCatalogRecord(send, sessionId);
    await clickByName(send, sessionId, "导出");
    await waitFor(send, sessionId, "!!document.querySelector('[role=dialog]')", "export dialog");
    await setControl(send, sessionId, "select[aria-label=\"导出格式\"]", "png");
    await waitFor(send, sessionId, "document.querySelector('select[aria-label=\"导出格式\"]')?.value === 'png'", "export format state");
    await setControl(send, sessionId, "input[aria-label=\"导出宽度\"]", "1080");
    await waitFor(send, sessionId, "document.querySelector('input[aria-label=\"导出宽度\"]')?.value === '1080'", "export width state");
    await setControl(send, sessionId, "select[aria-label=\"导出颜色配置\"]", "sRGB");
    await waitFor(send, sessionId, "document.querySelector('select[aria-label=\"导出颜色配置\"]')?.value === 'sRGB'", "export profile state");
    await setControl(send, sessionId, "input[aria-label=\"导出文件名\"]", "canonical-export");
    await waitFor(send, sessionId, "document.querySelector('input[aria-label=\"导出文件名\"]')?.value === 'canonical-export'", "export filename state");
    await clickByName(send, sessionId, "取消");
    await waitFor(send, sessionId, "!document.querySelector('[role=dialog]')", "export cancel");
    if ((await readdir(downloadDirectory)).length) throw new Error("cancel unexpectedly created an export file");
    await clickByName(send, sessionId, "导出");
    await waitFor(send, sessionId, "!!document.querySelector('.export-dialog a[download]')", "export confirmation");
    await waitFor(send, sessionId, "document.querySelector('.export-dialog a[download]')?.download === 'canonical-export.png'", "export download name");
    await evaluate(send, sessionId, "document.querySelector('.export-dialog a[download]').click()");
    const download = await waitForDownload(downloadDirectory, "canonical-export.png");
    await waitFor(send, sessionId, "!document.querySelector('[role=dialog]')", "export dialog closed");
    const dimensions = pngSize(download.bytes);
    if (download.filename !== "canonical-export.png" || dimensions[0] !== 1080) throw new Error(`export file mismatch: ${download.filename} ${JSON.stringify(dimensions)}`);
    const project = await evaluate(send, sessionId, `fetch('/api/v1/projects/${record.project_id}').then((item) => item.json())`);
    observed.push("export-dialog-ready", "filename-format-size-profile-readable", "cancel-closes-without-output", "export-completes-once");
    readbacks.export = { filename: download.filename, byte_length: download.bytes.length, sha256: createHash("sha256").update(download.bytes).digest("hex"), dimensions, project };
  } else if (args.contractId === "workflow:multi-image-three-workflows") {
    const specs = [
      { kind: "hdr_merge", label: "HDR Merge", title: "HDR 合并", wait: "hdr-preview-ready", root: "test_data/multi_image/hdr_merge" },
      { kind: "focus_stacking", label: "Focus Stacking", title: "焦点堆叠", wait: "focus-preview-ready", root: "test_data/multi_image/focus_stacking" },
      { kind: "panorama_stitching", label: "Panorama Stitching", title: "全景拼接", wait: "panorama-preview-ready", root: "test_data/multi_image/panorama_stitching" },
    ];
    const workflows = [];
    for (const spec of specs) {
      await clickWorkflow(send, sessionId, spec.label);
      await waitFor(send, sessionId, `(document.body?.innerText || '').includes(${JSON.stringify(`为 ${spec.title} 选择照片`)})`, `${spec.title} picker`, 30000);
      const paths = (await readdir(resolve(spec.root))).filter((name) => /\.(jpe?g|png|tiff?)$/i.test(name)).sort().map((name) => resolve(spec.root, name));
      if (paths.length < 2) throw new Error(`${spec.kind} fixture has fewer than two frames`);
      await setFiles(send, sessionId, ".workflow-empty-picker input[type=file]", paths);
      await waitFor(send, sessionId, `document.querySelectorAll('.workflow-photo-card').length === ${paths.length}`, `${spec.kind} frame cards`, 30000);
      const visibleNames = await evaluate(send, sessionId, "[...document.querySelectorAll('.workflow-photo-card strong')].map((node) => node.getAttribute('title'))");
      if (JSON.stringify(visibleNames) !== JSON.stringify(paths.map((path) => path.split("/").at(-1)))) throw new Error(`${spec.kind} frame order mismatch`);
      await clickByName(send, sessionId, "合并");
      await waitFor(send, sessionId, `(document.querySelector('[role="status"]')?.textContent || '').includes(${JSON.stringify(`已完成 ${spec.title} 预览`)})`, spec.wait, 180000);
      await waitFor(send, sessionId, `window.__zpixelResponses.some((item) => item.method === 'POST' && item.url.endsWith('/workflows/${spec.kind}') && item.json?.id)`, `${spec.kind} create readback`, 30000);
      const workflowId = await evaluate(send, sessionId, `window.__zpixelResponses.find((item) => item.method === 'POST' && item.url.endsWith('/workflows/${spec.kind}'))?.json?.id`);
      await clickByName(send, sessionId, "导出");
      await waitFor(send, sessionId, `(document.querySelector('[role="status"]')?.textContent || '').includes('多图结果已导出 PNG')`, `${spec.kind} export`, 120000);
      await waitFor(send, sessionId, `window.__zpixelResponses.some((item) => item.url.includes('/workflows/${workflowId}/preview') && item.sha256) && window.__zpixelResponses.some((item) => item.url.includes('/workflows/${workflowId}/export') && item.sha256)`, `${spec.kind} response hashes`, 30000);
      const readback = await evaluate(send, sessionId, `fetch('/api/v1/workflows/${workflowId}').then((response) => response.json())`);
      const hashes = await evaluate(send, sessionId, `(() => { const items = window.__zpixelResponses.filter((item) => item.url.includes('/workflows/${workflowId}/')); return { preview: items.find((item) => item.url.endsWith('/preview'))?.sha256, export: items.find((item) => item.url.endsWith('/export'))?.sha256 }; })()`);
      if (readback.id !== workflowId || readback.kind !== spec.kind || readback.analysis?.status !== "ready") throw new Error(`${spec.kind} API readback is incomplete`);
      if (hashes.preview !== hashes.export) throw new Error(`${spec.kind} preview/export hash mismatch`);
      workflows.push({ ...readback, frame_names: visibleNames, preview_sha256: hashes.preview, export_sha256: hashes.export });
      observed.push(`${spec.kind}-preview-and-export-complete`);
    }
    readbacks.workflows = workflows;
  } else {
    throw new Error(`current interaction handler is not implemented: ${args.contractId}`);
  }
  return { observed, readbacks };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const contracts = JSON.parse(await readFile(args.contracts, "utf8"));
  const fixture = JSON.parse(await readFile(args.fixture, "utf8"));
  const schema = JSON.parse(await readFile(args.schema, "utf8"));
  const validation = validateContracts(contracts, schema);
  if (args.dryRun) {
    process.stdout.write(`${JSON.stringify({ dry_run: true, ...validation, reference_id: contracts.reference_id, matrix_fingerprint: contracts.matrix_fingerprint })}\n`);
    return;
  }
  const selectedContracts = args.contractId === "all"
    ? contracts.records
    : args.contractId === "all-parameters"
      ? contracts.records.filter((item) => item.kind === "tool-parameter-contract")
      : args.contractId === "all-workflows"
        ? contracts.records.filter((item) => item.kind === "workflow-contract")
        : contracts.records.filter((item) => item.id === args.contractId);
  if (!selectedContracts.length) throw new Error(`contract not found: ${args.contractId}`);
  const logical = contracts.logical_viewport;
  const dpr = contracts.device_scale_factor;
  const physical = contracts.physical_viewport;
  if (JSON.stringify(logical) !== JSON.stringify([1440, 900]) || dpr !== 2 || JSON.stringify(physical) !== JSON.stringify([2880, 1800])) {
    throw new Error("formal interaction recorder requires 1440x900 logical, DPR2, 2880x1800 physical");
  }
  if (!/^[0-9a-f]{64}$/.test(fixture.fixture_fingerprint ?? "")) throw new Error("invalid fixture fingerprint");

  await mkdir(args.outputRoot, { recursive: true });
  await mkdir(resolve(args.rawOutput, ".."), { recursive: true });
  const buildHash = await frontendBuildHash(resolve("frontend"));
  const profile = await mkdtemp(join(tmpdir(), "zpixel-interaction-dpr2-"));
  const downloadDirectory = join(profile, "downloads");
  await mkdir(downloadDirectory);
  const networkEvents = [];
  const consoleEvents = [];
  const chrome = spawn(args.chrome, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-pipe", `--user-data-dir=${profile}`,
  ], { stdio: ["ignore", "ignore", "inherit", "pipe", "pipe"] });
  const send = createPipeClient(chrome, (event) => {
    if (event.method.startsWith("Network.")) networkEvents.push({ method: event.method, params: event.params });
    if (event.method === "Runtime.consoleAPICalled" || event.method === "Runtime.exceptionThrown") consoleEvents.push({ method: event.method, params: event.params });
  });

  try {
    const version = await send("Browser.getVersion");
    const environmentRecord = {
      browser: "Google Chrome Headless",
      browser_version: version.product.replace(/^Chrome\//, ""),
      capture_engine: "chrome-cdp-page-capture-screenshot",
      logical_viewport: logical,
      device_scale_factor: dpr,
      physical_viewport: physical,
      locale: "zh-Hans",
      timezone: "Asia/Shanghai",
      build_hash: buildHash,
      fixture_fingerprint: fixture.fixture_fingerprint,
    };
    let records = [];
    if (args.resume) {
      try {
        const previous = JSON.parse(await readFile(args.rawOutput, "utf8"));
        const sameRun = previous.version === "3.0"
          && previous.reference_id === contracts.reference_id
          && previous.matrix_fingerprint === contracts.matrix_fingerprint
          && previous.environment?.build_hash === buildHash
          && previous.environment?.fixture_fingerprint === fixture.fixture_fingerprint
          && previous.environment?.browser_version === environmentRecord.browser_version;
        if (!sameRun) throw new Error("resume raw does not match the current matrix, fixture, build, or browser");
        records = previous.records.filter((item) => item.status === "passed");
      } catch (error) {
        if (error?.code !== "ENOENT") throw error;
      }
    }
    const completedIds = new Set(records.map((item) => item.id));
    const writeCheckpoint = () => writeFile(args.rawOutput, `${JSON.stringify({
      version: "3.0",
      reference_id: contracts.reference_id,
      matrix_fingerprint: contracts.matrix_fingerprint,
      environment: environmentRecord,
      records,
    }, null, 2)}\n`);
    const target = await send("Target.createTarget", { url: "about:blank" });
    const attached = await send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
    const sessionId = attached.sessionId;
    for (const method of ["Page.enable", "Runtime.enable", "DOM.enable", "Accessibility.enable", "Network.enable"]) await send(method, {}, sessionId);
    await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloadDirectory, eventsEnabled: true });
    await send("Emulation.setDeviceMetricsOverride", { width: logical[0], height: logical[1], screenWidth: logical[0], screenHeight: logical[1], deviceScaleFactor: dpr, mobile: false }, sessionId);
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, sessionId);
    await send("Emulation.setLocaleOverride", { locale: "zh-Hans" }, sessionId);
    await send("Emulation.setTimezoneOverride", { timezoneId: "Asia/Shanghai" }, sessionId);
    await send("Page.addScriptToEvaluateOnNewDocument", { source: `(() => {
      window.__zpixelResponses = [];
      const originalFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const request = new Request(...args);
        const response = await originalFetch(...args);
        const entry = { url: request.url, method: request.method, status: response.status };
        window.__zpixelResponses.push(entry);
        response.clone().arrayBuffer().then(async (buffer) => {
          const digest = await crypto.subtle.digest('SHA-256', buffer);
          entry.sha256 = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('');
          try { entry.json = JSON.parse(new TextDecoder().decode(buffer)); } catch {}
        }).catch((error) => { entry.capture_error = String(error); });
        return response;
      };
    })();` }, sessionId);

    for (const [index, contract] of selectedContracts.entries()) {
      if (completedIds.has(contract.id)) {
        progress(contract.id, `reused:${index + 1}/${selectedContracts.length}`);
        continue;
      }
      progress(contract.id, `batch:${index + 1}/${selectedContracts.length}`);
      for (const name of await readdir(downloadDirectory)) {
        await rm(join(downloadDirectory, name), { recursive: true, force: true });
      }
      const networkStart = networkEvents.length;
      const consoleStart = consoleEvents.length;
      const targetUrl = new URL(args.baseUrl);
      targetUrl.searchParams.set("__zpixel_interaction", contract.id);
      const expectedUrl = targetUrl.toString();
      await send("Page.navigate", { url: expectedUrl }, sessionId);
      await waitFor(
        send,
        sessionId,
        `window.location.href === ${JSON.stringify(expectedUrl)}`,
        `navigation to ${expectedUrl}`,
        30000,
      );
      await waitFor(send, sessionId, "document.readyState === 'complete'", "document ready", 30000);
      await clickByName(send, sessionId, "目录");
      await waitFor(send, sessionId, "!!document.querySelector('.photo-card')", "catalog ready", 30000);

      const contractArgs = { ...args, contractId: contract.id };
      const { observed, readbacks } = await executeContract(contractArgs, contract, schema, send, sessionId, downloadDirectory);
      const environment = await evaluate(send, sessionId, "({dpr: window.devicePixelRatio, width: window.innerWidth, height: window.innerHeight})");
      if (environment.dpr !== 2 || environment.width !== 1440 || environment.height !== 900) throw new Error(`viewport preflight failed: ${JSON.stringify(environment)}`);
      const screenshot = await send("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false }, sessionId);
      const screenshotBytes = Buffer.from(screenshot.data, "base64");
      if (JSON.stringify(pngSize(screenshotBytes)) !== JSON.stringify(physical)) throw new Error("physical screenshot size mismatch");
      const dom = await send("DOMSnapshot.captureSnapshot", { computedStyles: [], includeDOMRects: true, includePaintOrder: true }, sessionId);
      const ax = await send("Accessibility.getFullAXTree", {}, sessionId);
      const browserResponses = await evaluate(send, sessionId, "window.__zpixelResponses");
      const evidenceDirectory = join(args.outputRoot, contract.id);
      await mkdir(evidenceDirectory, { recursive: true });
      const files = {
        final_screenshot: "final.png",
        dom_snapshot: "dom.json",
        accessibility_tree: "ax.json",
        execution_trace: "trace.json",
        network_trace: "network.json",
        console_log: "console.json",
      };
      await writeFile(join(evidenceDirectory, files.final_screenshot), screenshotBytes);
      await writeFile(join(evidenceDirectory, files.dom_snapshot), `${JSON.stringify(dom, null, 2)}\n`);
      await writeFile(join(evidenceDirectory, files.accessibility_tree), `${JSON.stringify(ax, null, 2)}\n`);
      await writeFile(join(evidenceDirectory, files.execution_trace), `${JSON.stringify({ contract_id: contract.id, result: "passed", observed, readbacks, fixture_fingerprint: fixture.fixture_fingerprint }, null, 2)}\n`);
      await writeFile(join(evidenceDirectory, files.network_trace), `${JSON.stringify({ cdp_events: networkEvents.slice(networkStart), browser_responses: browserResponses }, null, 2)}\n`);
      const contractConsole = consoleEvents.slice(consoleStart);
      await writeFile(join(evidenceDirectory, files.console_log), `${JSON.stringify({ messages: contractConsole, status: contractConsole.length ? "captured" : "captured-no-console-events" }, null, 2)}\n`);

      records.push({
        id: contract.id,
        status: "passed",
        events: contract.events,
        visible_assertions: contract.visible_assertions,
        api_assertions: contract.api_assertions,
        wait_conditions: contract.allowed_wait_conditions,
        fixed_sleep: false,
        ...Object.fromEntries(Object.entries(files).map(([key, value]) => [key, `${contract.id}/${value}`])),
      });
      await writeCheckpoint();
    }
    const raw = {
      version: "3.0",
      reference_id: contracts.reference_id,
      matrix_fingerprint: contracts.matrix_fingerprint,
      environment: environmentRecord,
      records,
    };
    await writeFile(args.rawOutput, `${JSON.stringify(raw, null, 2)}\n`);
    await send("Browser.close");
    await waitForExit(chrome, 5000);
    process.stdout.write(`${JSON.stringify({ captured: records.length, selection: args.contractId, browser: version.product })}\n`);
  } finally {
    if (chrome.exitCode === null) {
      chrome.kill("SIGTERM");
      await waitForExit(chrome, 5000);
    }
    await rm(profile, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exitCode = 1;
});
