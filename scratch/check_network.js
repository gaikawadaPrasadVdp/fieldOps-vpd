const { spawn } = require('child_process');

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const port = 9222;

  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
  ]);

  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await sleep(400);
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      const v = await res.json();
      if (v && v.webSocketDebuggerUrl) { wsUrl = v.webSocketDebuggerUrl; break; }
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
    const d = JSON.parse(evt.data);
    if (d.id && callbacks.has(d.id)) {
      callbacks.get(d.id).resolve(d.result);
      callbacks.delete(d.id);
    }
  };
  await new Promise(r => ws.onopen = r);

  const target = await send('Target.createTarget', { url: 'about:blank' });
  const pageWs = new WebSocket(`ws://127.0.0.1:${port}/devtools/page/${target.targetId}`);
  let pageId = 1;
  const pageCb = new Map();
  function pageSend(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = pageId++;
      pageCb.set(id, { resolve, reject });
      pageWs.send(JSON.stringify({ id, method, params }));
    });
  }

  pageWs.onmessage = (evt) => {
    const d = JSON.parse(evt.data);
    if (d.id && pageCb.has(d.id)) {
      pageCb.get(d.id).resolve(d.result);
      pageCb.delete(d.id);
    } else if (d.method === 'Network.requestWillBeSent') {
      console.log('-> REQ:', d.params.request.url);
    } else if (d.method === 'Network.loadingFailed') {
      console.log('XX FAILED:', d.params.errorText, d.params.canceled ? '(canceled)' : '');
    } else if (d.method === 'Page.loadEventFired') {
      console.log('=== LOAD EVENT FIRED! ===');
    }
  };
  await new Promise(r => pageWs.onopen = r);

  await pageSend('Network.enable');
  await pageSend('Page.enable');
  await pageSend('Runtime.enable');

  console.log('Navigating to http://localhost:8000/resources/...');
  await pageSend('Page.navigate', { url: 'http://localhost:8000/resources/' });

  await sleep(4000);

  const readyState = await pageSend('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
  console.log('Final document.readyState:', readyState.result?.value);

  pageWs.close();
  ws.close();
  chromeProc.kill();
}
run().catch(console.error);
