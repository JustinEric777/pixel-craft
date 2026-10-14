#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const CAPTURE_RUNNER_VERSION = "1.1.0";

function parseArgs(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error(`invalid argument near ${key ?? "<end>"}`);
    }
    values.set(key.slice(2), value);
  }
  for (const required of ["plan", "output-root", "candidate-root"]) {
    if (!values.has(required)) throw new Error(`missing --${required}`);
  }
  return {
    plan: resolve(values.get("plan")),
    outputRoot: resolve(values.get("output-root")),
    candidateRoot: resolve(values.get("candidate-root")),
    chrome: resolve(values.get("chrome") ?? DEFAULT_CHROME),
    matrixStateId: values.get("matrix-state-id"),
    dryRun: values.get("dry-run") === "true",
    resume: values.get("resume") === "true",
  };
}

const STEP_TYPES = new Set([
  "wait",
  "wait-for-text",
  "wait-for-selector",
  "click-name",
  "click-selector",
  "click-text",
  "double-click-text",
  "fill",
  "set-files",
  "show-tool",
  "change-parameter",
]);
const PARAMETER_TYPES = new Set(["float", "array", "asset", "boolean", "enum"]);

function validatePlan(plan) {
  if (plan.version !== "3.0") throw new Error(`current capture plan requires version 3.0, got ${plan.version}`);
  if (typeof plan.reference_id !== "string" || !plan.reference_id) throw new Error("capture plan has no reference_id");
  if (!/^[0-9a-f]{64}$/.test(plan.matrix_fingerprint ?? "")) throw new Error("capture plan has invalid matrix_fingerprint");
  if (!Array.isArray(plan.records) || plan.records.length !== 170) {
    throw new Error(`current capture plan requires exactly 170 records, got ${plan.records?.length ?? 0}`);
  }
  if (Object.hasOwn(plan, "states")) throw new Error("legacy states container is not accepted");
  const ids = new Set();
  const counts = new Map();
  for (const record of plan.records) {
    if (Object.hasOwn(record, "state")) throw new Error("legacy state field is not accepted");
    if (typeof record.matrix_state_id !== "string" || !record.matrix_state_id.includes(":")) {
      throw new Error("record has invalid matrix_state_id");
    }
    if (ids.has(record.matrix_state_id)) throw new Error(`duplicate matrix_state_id: ${record.matrix_state_id}`);
    ids.add(record.matrix_state_id);
    counts.set(record.kind, (counts.get(record.kind) ?? 0) + 1);
    if (!Array.isArray(record.steps) || record.steps.length === 0) throw new Error(`record has no recipe: ${record.matrix_state_id}`);
    for (const step of record.steps) {
      if (!STEP_TYPES.has(step.type)) throw new Error(`unsupported capture step in ${record.matrix_state_id}: ${step.type}`);
      if (step.type === "show-tool" && (!step.capability_id || !step.locator && !step.title)) {
        throw new Error(`show-tool has no current locator: ${record.matrix_state_id}`);
      }
      if (step.type === "change-parameter") {
        if (!step.capability_id || !step.parameter || !step.locator) throw new Error(`parameter step has no current locator: ${record.matrix_state_id}`);
        if (!PARAMETER_TYPES.has(step.parameter_type)) throw new Error(`unknown parameter type in ${record.matrix_state_id}: ${step.parameter_type}`);
        if (!Object.hasOwn(step, "value")) throw new Error(`parameter step has no canonical value: ${record.matrix_state_id}`);
      }
    }
  }
  const expected = { "workspace-state": 16, "tool-panel-state": 80, "tool-parameter-state": 74 };
  for (const [kind, count] of Object.entries(expected)) {
    if (counts.get(kind) !== count) throw new Error(`capture plan kind count mismatch for ${kind}: ${counts.get(kind) ?? 0} != ${count}`);
  }
  return { supported: plan.records.length, kinds: Object.fromEntries(counts) };
}

function createPipeClient(process) {
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
      if (!message.id || !pending.has(message.id)) continue;
      const { resolve: accept, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else accept(message.result ?? {});
    }
  });

  return (method, params = {}, sessionId) => new Promise((accept, reject) => {
    const id = nextId++;
    pending.set(id, { resolve: accept, reject });
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    process.stdio[3].write(`${JSON.stringify(message)}\0`);
  });
}

function pngSize(bytes) {
  const signature = "89504e470d0a1a0a";
  if (bytes.subarray(0, 8).toString("hex") !== signature) {
    throw new Error("Page.captureScreenshot did not return PNG data");
  }
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
}

async function loadExistingRecord({
  matrixStateId,
  rawScreenshot,
  candidateScreenshot,
  rawDom,
  rawAx,
  rawCapture,
  plan,
  version,
  physical,
  logical,
  dpr,
}) {
  try {
    const [screenshotBytes, candidateBytes, domBytes, axBytes, captureBytes] = await Promise.all([
      readFile(rawScreenshot),
      readFile(candidateScreenshot),
      readFile(rawDom),
      readFile(rawAx),
      readFile(rawCapture),
    ]);
    const capture = JSON.parse(captureBytes.toString("utf8"));
    JSON.parse(domBytes.toString("utf8"));
    JSON.parse(axBytes.toString("utf8"));
    const environment = capture.environment ?? {};
    const valid =
      capture.matrix_state_id === matrixStateId &&
      capture.capture_runner_version === CAPTURE_RUNNER_VERSION &&
      capture.reference_id === plan.reference_id &&
      capture.matrix_fingerprint === plan.matrix_fingerprint &&
      capture.browser === version.product &&
      environment.dpr === dpr &&
      environment.width === Number(logical[0]) &&
      environment.height === Number(logical[1]) &&
      pngSize(screenshotBytes).every((value, index) => value === physical[index]) &&
      screenshotBytes.equals(candidateBytes);
    return valid ? { matrix_state_id: matrixStateId, screenshot: rawScreenshot, environment } : null;
  } catch {
    return null;
  }
}

async function delay(milliseconds) {
  await new Promise((accept) => setTimeout(accept, milliseconds));
}

async function waitForExit(process, timeoutMs) {
  if (process.exitCode !== null) return;
  await Promise.race([
    new Promise((accept) => process.once("exit", accept)),
    delay(timeoutMs),
  ]);
}

async function evaluate(send, sessionId, expression) {
  const result = await send(
    "Runtime.evaluate",
    { expression, awaitPromise: true, returnByValue: true },
    sessionId,
  );
  if (result.exceptionDetails) {
    throw new Error(`browser evaluation failed: ${JSON.stringify(result.exceptionDetails)}`);
  }
  return result.result?.value;
}

async function waitForReady(send, sessionId, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(send, sessionId, "document.readyState === 'complete'")) return;
    await delay(100);
  }
  throw new Error("page did not reach readyState=complete");
}

async function waitForText(send, sessionId, text, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  const encoded = JSON.stringify(text);
  while (Date.now() < deadline) {
    const found = await evaluate(
      send,
      sessionId,
      `((document.body?.innerText || '').replace(/\\s+/g, '')).includes((${encoded}).replace(/\\s+/g, ''))`,
    );
    if (found) return;
    await delay(100);
  }
  const visible = await evaluate(
    send,
    sessionId,
    "(document.body?.innerText || '').replace(/\\s+/g, ' ').slice(0, 1000)",
  );
  throw new Error(`visible text did not appear: ${text}; body=${visible}`);
}

async function waitForName(send, sessionId, name, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  const encoded = JSON.stringify(name);
  while (Date.now() < deadline) {
    const found = await evaluate(
      send,
      sessionId,
      `(() => {
        const targetName = ${encoded};
        const candidates = [...document.querySelectorAll('button, [role="button"], summary, label, a')];
        return candidates.some((element) =>
          (element.getAttribute('aria-label') || element.textContent || '').replace(/\\s+/g, ' ').trim() === targetName
        );
      })()`,
    );
    if (found) return;
    await delay(100);
  }
  throw new Error(`click target did not appear: ${name}`);
}

async function waitForSelector(send, sessionId, selector, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  const encoded = JSON.stringify(selector);
  while (Date.now() < deadline) {
    const found = await evaluate(
      send,
      sessionId,
      `Boolean(document.querySelector(${encoded}))`,
    );
    if (found) return;
    await delay(100);
  }
  throw new Error(`visible selector did not appear: ${selector}`);
}

async function waitForVisibleImages(send, sessionId, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const ready = await evaluate(
      send,
      sessionId,
      `(() => {
        const visible = [...document.images].filter((image) => image.src && image.getClientRects().length > 0);
        return visible.every((image) => image.complete && image.naturalWidth > 0 && image.naturalHeight > 0);
      })()`,
    );
    if (ready) return;
    await delay(100);
  }
  throw new Error("visible images did not finish decoding");
}

function clickByNameExpression(name) {
  const encoded = JSON.stringify(name);
  return `(() => {
    const targetName = ${encoded};
    const candidates = [...document.querySelectorAll('button, [role="button"], summary, label, a')];
    const target = candidates.find((element) =>
      (element.getAttribute('aria-label') || element.textContent || '').replace(/\\s+/g, ' ').trim() === targetName
    );
    if (!target) throw new Error('click target not found: ' + targetName);
    target.click();
    return true;
  })()`;
}

async function runStep(send, sessionId, step) {
  if (step.type === "wait") {
    await delay(Number(step.milliseconds));
    return;
  }
  if (step.type === "wait-for-text") {
    await waitForText(send, sessionId, String(step.text), Number(step.timeout_ms ?? 10000));
    return;
  }
  if (step.type === "wait-for-selector") {
    await waitForSelector(
      send,
      sessionId,
      String(step.selector),
      Number(step.timeout_ms ?? 10000),
    );
    return;
  }
  if (step.type === "click-name") {
    await waitForName(send, sessionId, String(step.name), Number(step.timeout_ms ?? 30000));
    await evaluate(send, sessionId, clickByNameExpression(String(step.name)));
    return;
  }
  if (step.type === "click-selector") {
    const selector = JSON.stringify(String(step.selector));
    await evaluate(
      send,
      sessionId,
      `(() => { const target = document.querySelector(${selector}); if (!target) throw new Error('selector not found'); target.click(); return true; })()`,
    );
    return;
  }
  if (step.type === "click-text") {
    await waitForSelector(
      send,
      sessionId,
      String(step.selector),
      Number(step.timeout_ms ?? 10000),
    );
    const selector = JSON.stringify(String(step.selector));
    const targetText = JSON.stringify(String(step.text));
    await evaluate(
      send,
      sessionId,
      `(() => {
        const expected = ${targetText};
        const target = [...document.querySelectorAll(${selector})].find((element) =>
          (element.getAttribute('aria-label') || element.textContent || '').replace(/\\s+/g, ' ').trim() === expected
        );
        if (!target) throw new Error('text target not found: ' + expected);
        target.click();
        return true;
      })()`,
    );
    return;
  }
  if (step.type === "double-click-text") {
    await waitForSelector(
      send,
      sessionId,
      String(step.selector),
      Number(step.timeout_ms ?? 10000),
    );
    const selector = JSON.stringify(String(step.selector));
    const targetText = JSON.stringify(String(step.text));
    await evaluate(
      send,
      sessionId,
      `(() => {
        const expected = ${targetText};
        const target = [...document.querySelectorAll(${selector})].find((element) =>
          (element.getAttribute('aria-label') || element.textContent || '').replace(/\\s+/g, ' ').trim() === expected
        );
        if (!target) throw new Error('double-click target not found: ' + expected);
        target.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window }));
        return true;
      })()`,
    );
    return;
  }
  if (step.type === "fill") {
    const selector = JSON.stringify(String(step.selector));
    const value = JSON.stringify(String(step.value));
    await evaluate(
      send,
      sessionId,
      `(() => { const target = document.querySelector(${selector}); if (!target) throw new Error('fill target not found'); target.value = ${value}; target.dispatchEvent(new Event('input', {bubbles:true})); target.dispatchEvent(new Event('change', {bubbles:true})); return true; })()`,
    );
    return;
  }
  if (step.type === "set-files") {
    const documentNode = await send("DOM.getDocument", { depth: -1, pierce: true }, sessionId);
    const query = await send(
      "DOM.querySelector",
      { nodeId: documentNode.root.nodeId, selector: String(step.selector) },
      sessionId,
    );
    if (!query.nodeId) throw new Error(`file input not found: ${step.selector}`);
    await send(
      "DOM.setFileInputFiles",
      { nodeId: query.nodeId, files: step.files.map((path) => resolve(PROJECT_ROOT, path)) },
      sessionId,
    );
    return;
  }
  if (step.type === "show-tool") {
    const capabilityId = JSON.stringify(String(step.capability_id));
    const title = JSON.stringify(String(step.title ?? ""));
    const expanded = Boolean(step.expanded);
    await evaluate(send, sessionId, `(() => {
      const capabilityId = ${capabilityId};
      const title = ${title};
      const tool = document.querySelector('[data-capability-id="' + CSS.escape(capabilityId) + '"]') ||
        [...document.querySelectorAll('.tool')].find((node) =>
          (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim().startsWith(title)
        );
      if (!tool) throw new Error('tool not found: ' + capabilityId);
      tool.scrollIntoView({ block: 'center', inline: 'nearest' });
      const toggle = tool.matches('button,[role="button"]') ? tool : tool.querySelector('button,[role="button"],summary');
      if (!toggle) throw new Error('tool toggle not found: ' + capabilityId);
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true' || tool.classList.contains('expanded');
      if (isExpanded !== ${expanded}) toggle.click();
      return true;
    })()`);
    return;
  }
  if (step.type === "change-parameter") {
    const selector = JSON.stringify(String(step.locator));
    const parameterType = JSON.stringify(String(step.parameter_type));
    const value = JSON.stringify(step.value);
    await evaluate(send, sessionId, `(() => {
      const selector = ${selector};
      const parameterType = ${parameterType};
      const value = ${value};
      const target = document.querySelector(selector);
      if (!target) throw new Error('parameter locator not found: ' + selector);
      target.scrollIntoView({ block: 'center', inline: 'nearest' });
      if (parameterType === 'boolean') {
        const checked = target.matches('input[type="checkbox"]') ? target.checked : target.getAttribute('aria-pressed') === 'true';
        if (checked !== value) target.click();
      } else if (parameterType === 'array' || parameterType === 'asset' || (parameterType === 'enum' && !(target instanceof HTMLInputElement || target instanceof HTMLSelectElement))) {
        target.dispatchEvent(new CustomEvent('zpixel:set-parameter', { bubbles: true, detail: { value } }));
      } else {
        const prototype = target instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
        if (!setter) throw new Error('parameter has no native value setter: ' + selector);
        setter.call(target, String(value));
        target.dispatchEvent(new Event('input', { bubbles: true }));
        target.dispatchEvent(new Event('change', { bubbles: true }));
      }
      const readback = target.matches('input[type="checkbox"]') ? target.checked : target.value ?? target.getAttribute('data-value');
      return { readback };
    })()`);
    return;
  }
  throw new Error(`unsupported capture step: ${step.type}`);
}

async function navigate(send, sessionId, url, matrixStateId) {
  const target = new URL(url);
  target.searchParams.set("__zpixel_capture", matrixStateId);
  const expectedUrl = target.toString();
  await send("Page.navigate", { url: expectedUrl }, sessionId);
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const currentUrl = await evaluate(send, sessionId, "window.location.href");
    if (currentUrl === expectedUrl) break;
    await delay(100);
  }
  const currentUrl = await evaluate(send, sessionId, "window.location.href");
  if (currentUrl !== expectedUrl) {
    throw new Error(`page did not navigate to ${expectedUrl}: ${currentUrl}`);
  }
  await waitForReady(send, sessionId);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const plan = JSON.parse(await readFile(args.plan, "utf8"));
  const validation = validatePlan(plan);
  const logical = plan.logical_viewport ?? [1440, 900];
  const dpr = Number(plan.device_scale_factor ?? 2);
  const physical = logical.map((value) => Math.round(Number(value) * dpr));
  if (dpr !== 2) throw new Error(`formal capture requires DPR 2, got ${dpr}`);
  const records = args.matrixStateId
    ? plan.records.filter((record) => record.matrix_state_id === args.matrixStateId)
    : plan.records;
  if (records.length === 0) throw new Error(`capture plan has no matrix_state_id: ${args.matrixStateId}`);
  if (args.dryRun) {
    process.stdout.write(`${JSON.stringify({ dry_run: true, supported: validation.supported, selected: records.length, kinds: validation.kinds, reference_id: plan.reference_id, matrix_fingerprint: plan.matrix_fingerprint })}\n`);
    return;
  }

  const profile = await mkdtemp(join(tmpdir(), "zpixel-ui-dpr2-"));
  const chrome = spawn(
    args.chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      "--remote-debugging-pipe",
      `--user-data-dir=${profile}`,
    ],
    { stdio: ["ignore", "ignore", "inherit", "pipe", "pipe"] },
  );
  const send = createPipeClient(chrome);

  try {
    const version = await send("Browser.getVersion");
    const target = await send("Target.createTarget", { url: "about:blank" });
    const attached = await send(
      "Target.attachToTarget",
      { targetId: target.targetId, flatten: true },
    );
    const sessionId = attached.sessionId;
    for (const method of ["Page.enable", "Runtime.enable", "DOM.enable", "Accessibility.enable"]) {
      await send(method, {}, sessionId);
    }
    await send(
      "Emulation.setDeviceMetricsOverride",
      {
        width: Number(logical[0]),
        height: Number(logical[1]),
        screenWidth: Number(logical[0]),
        screenHeight: Number(logical[1]),
        deviceScaleFactor: dpr,
        mobile: false,
      },
      sessionId,
    );
    await send(
      "Emulation.setEmulatedMedia",
      { features: [{ name: "prefers-reduced-motion", value: "reduce" }] },
      sessionId,
    );
    await send("Emulation.setLocaleOverride", { locale: plan.locale ?? "zh-Hans" }, sessionId);
    await send(
      "Emulation.setTimezoneOverride",
      { timezoneId: plan.timezone ?? "Asia/Shanghai" },
      sessionId,
    );

    const viewportName = `${physical[0]}x${physical[1]}`;
    const rawDirectory = join(args.outputRoot, viewportName);
    const candidateDirectory = join(args.candidateRoot, viewportName);
    await mkdir(rawDirectory, { recursive: true });
    await mkdir(candidateDirectory, { recursive: true });
    const capturedRecords = [];

    for (const record of records) {
      const matrixStateId = record.matrix_state_id;
      const rawScreenshot = join(rawDirectory, `${matrixStateId}.png`);
      const candidateScreenshot = join(candidateDirectory, `${matrixStateId}.png`);
      const rawDom = join(rawDirectory, `${matrixStateId}.dom.json`);
      const rawAx = join(rawDirectory, `${matrixStateId}.ax.json`);
      const rawCapture = join(rawDirectory, `${matrixStateId}.capture.json`);
      if (args.resume) {
        const existing = await loadExistingRecord({
          matrixStateId,
          rawScreenshot,
          candidateScreenshot,
          rawDom,
          rawAx,
          rawCapture,
          plan,
          version,
          physical,
          logical,
          dpr,
        });
        if (existing) {
          capturedRecords.push(existing);
          continue;
        }
      }
      await navigate(
        send,
        sessionId,
        record.url ?? plan.base_url,
        matrixStateId,
      );
      for (const step of record.steps ?? []) await runStep(send, sessionId, step);
      await waitForVisibleImages(send, sessionId);
      await delay(Number(record.settle_ms ?? plan.settle_ms ?? 250));

      const environment = await evaluate(
        send,
        sessionId,
        "({dpr: window.devicePixelRatio, width: window.innerWidth, height: window.innerHeight, readyState: document.readyState})",
      );
      if (
        environment.dpr !== dpr ||
        environment.width !== Number(logical[0]) ||
        environment.height !== Number(logical[1])
      ) {
        throw new Error(`viewport preflight failed for ${matrixStateId}: ${JSON.stringify(environment)}`);
      }

      const screenshot = await send(
        "Page.captureScreenshot",
        { format: "png", fromSurface: true, captureBeyondViewport: false },
        sessionId,
      );
      const screenshotBytes = Buffer.from(screenshot.data, "base64");
      const actual = pngSize(screenshotBytes);
      if (actual[0] !== physical[0] || actual[1] !== physical[1]) {
        throw new Error(`physical screenshot mismatch for ${matrixStateId}: ${actual} != ${physical}`);
      }
      const dom = await send(
        "DOMSnapshot.captureSnapshot",
        { computedStyles: [], includeDOMRects: true, includePaintOrder: true },
        sessionId,
      );
      const ax = await send("Accessibility.getFullAXTree", {}, sessionId);

      await writeFile(rawScreenshot, screenshotBytes);
      await writeFile(candidateScreenshot, screenshotBytes);
      await writeFile(rawDom, `${JSON.stringify(dom, null, 2)}\n`);
      await writeFile(rawAx, `${JSON.stringify(ax, null, 2)}\n`);
      await writeFile(
        rawCapture,
        `${JSON.stringify({
          matrix_state_id: matrixStateId,
          kind: record.kind,
          reference_id: plan.reference_id,
          matrix_fingerprint: plan.matrix_fingerprint,
          url: record.url ?? plan.base_url,
          environment,
          browser: version.product,
          protocol_version: version.protocolVersion,
          capture_runner_version: CAPTURE_RUNNER_VERSION,
          capture_method: "native-dpr2",
          steps: record.steps ?? [],
        }, null, 2)}\n`,
      );
      capturedRecords.push({ matrix_state_id: matrixStateId, screenshot: rawScreenshot, environment });
    }

    await writeFile(
      join(args.outputRoot, "capture-run.json"),
      `${JSON.stringify({
        version: "1.0",
        plan: basename(args.plan),
        reference_id: plan.reference_id,
        matrix_fingerprint: plan.matrix_fingerprint,
        browser: version.product,
        capture_runner_version: CAPTURE_RUNNER_VERSION,
        logical_viewport: logical,
        device_scale_factor: dpr,
        physical_viewport: physical,
        records: capturedRecords,
      }, null, 2)}\n`,
    );
    await send("Browser.close");
    await waitForExit(chrome, 5000);
    process.stdout.write(`${JSON.stringify({ captured: capturedRecords.length, browser: version.product })}\n`);
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
