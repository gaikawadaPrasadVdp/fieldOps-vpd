const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const port = 9222;

  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
  ], { detached: false });

  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await sleep(400);
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      const v = await res.json();
      if (v && v.webSocketDebuggerUrl) {
        wsUrl = v.webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }

  const ws = new WebSocket(wsUrl);
  let msgId = 1;
  const callbacks = new Map();

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      callbacks.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  ws.onmessage = (evt) => {
    const data = JSON.parse(evt.data);
    if (data.id && callbacks.has(data.id)) {
      const { resolve, reject } = callbacks.get(data.id);
      callbacks.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    } else if (data.method === 'Runtime.consoleAPICalled') {
      console.log('[Console]', data.params.type, data.params.args.map(a => a.value || a.description).join(' '));
    } else if (data.method === 'Runtime.exceptionThrown') {
      console.error('[Exception]', data.params.exceptionDetails.text, data.params.exceptionDetails.exception?.description);
    } else if (data.method === 'Log.entryAdded') {
      console.log('[Browser Log]', data.params.entry.level, data.params.entry.text);
    }
  };

  await new Promise((r) => (ws.onopen = r));

  // Create new target
  const target = await send('Target.createTarget', { url: 'http://localhost:8000/resources/' });
  const pageWs = new WebSocket(`ws://127.0.0.1:${port}/devtools/page/${target.targetId}`);
  
  let pageMsgId = 1;
  const pageCallbacks = new Map();
  function pageSend(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = pageMsgId++;
      pageCallbacks.set(id, { resolve, reject });
      pageWs.send(JSON.stringify({ id, method, params }));
    });
  }

  pageWs.onmessage = (evt) => {
    const data = JSON.parse(evt.data);
    if (data.id && pageCallbacks.has(data.id)) {
      const { resolve, reject } = pageCallbacks.get(data.id);
      pageCallbacks.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    } else if (data.method === 'Runtime.consoleAPICalled') {
      console.log('[Page Console]', data.params.type, data.params.args.map(a => a.value || a.description).join(' '));
    } else if (data.method === 'Runtime.exceptionThrown') {
      console.error('[Page Exception]', data.params.exceptionDetails.text, data.params.exceptionDetails.exception?.description);
    } else if (data.method === 'Log.entryAdded') {
      console.log('[Page Log]', data.params.entry.level, data.params.entry.text);
    }
  };

  await new Promise((r) => (pageWs.onopen = r));
  await pageSend('Runtime.enable');
  await pageSend('Log.enable');
  await pageSend('Page.enable');

  // Wait for page load
  await sleep(3000);

  async function pageEval(expr) {
    const res = await pageSend('Runtime.evaluate', { expression: expr, returnByValue: true });
    return res.result ? res.result.value : undefined;
  }

  console.log('Ready state:', await pageEval('document.readyState'));
  console.log('Has fxOpenArticleModal:', await pageEval('typeof window.fxOpenArticleModal'));
  console.log('Modal overlay in DOM:', await pageEval('Boolean(document.getElementById("fx-article-modal-overlay"))'));

  pageWs.close();
  ws.close();
  chromeProc.kill();
}

run().catch(console.error);
