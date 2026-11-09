const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const port = 9222;

  console.log('Starting Chrome on port', port);
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    'http://localhost:8000/resources/',
  ], { detached: false });

  chromeProc.stderr.on('data', (d) => {
    // console.log('[Chrome stderr]', d.toString());
  });

  // Wait for Chrome to be ready
  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const list = await res.json();
      const pageTarget = list.find((t) => t.type === 'page' && t.url.includes('resources')) || list.find((t) => t.type === 'page');
      if (pageTarget && pageTarget.webSocketDebuggerUrl) {
        wsUrl = pageTarget.webSocketDebuggerUrl;
        console.log('Found page target:', pageTarget.url, wsUrl);
        break;
      }
    } catch (e) {
      // waiting
    }
  }

  if (!wsUrl) {
    console.error('Failed to connect to Chrome remote debugging!');
    chromeProc.kill();
    process.exit(1);
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
      console.log('[Browser Console]', data.params.type, data.params.args.map(a => a.value || a.description).join(' '));
    } else if (data.method === 'Runtime.exceptionThrown') {
      console.error('[Browser Exception]', data.params.exceptionDetails);
    }
  };

  await new Promise((r) => (ws.onopen = r));
  console.log('WebSocket connected to Chrome DevTools Protocol');

  await send('Runtime.enable');
  await send('Page.enable');

  console.log('Navigating explicitly to http://localhost:8000/resources/...');
  await send('Page.navigate', { url: 'http://localhost:8000/resources/' });

  // Wait until document.readyState is 'complete' or at least interactive
  for (let i = 0; i < 40; i++) {
    await sleep(250);
    const ready = await evalJs('document.readyState');
    if (ready === 'complete') {
      console.log('Page readyState is complete after', (i + 1) * 250, 'ms');
      break;
    }
  }
  // Extra pause for deferred public.js execution
  await sleep(800);

  // Evaluate document status
  async function evalJs(expr) {
    const res = await send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
    });
    if (res.exceptionDetails) {
      console.error('Eval error for:', expr, res.exceptionDetails);
    }
    return res.result ? res.result.value : undefined;
  }

  console.log('\n--- DIAGNOSTICS ---');
  const title = await evalJs('document.title');
  console.log('Page title:', title);

  const triggersCount = await evalJs('document.querySelectorAll(".fx-article-modal-trigger").length');
  console.log('Triggers found (.fx-article-modal-trigger):', triggersCount);

  const readMoreCount = await evalJs('document.querySelectorAll(".fx-read-more-link").length');
  console.log('Read more links found (.fx-read-more-link):', readMoreCount);

  const overlayExists = await evalJs('Boolean(document.getElementById("fx-article-modal-overlay"))');
  console.log('Overlay element exists:', overlayExists);

  const overlayHidden = await evalJs('document.getElementById("fx-article-modal-overlay") ? document.getElementById("fx-article-modal-overlay").hasAttribute("hidden") : null');
  console.log('Overlay has hidden attr initially:', overlayHidden);

  const fnExists = await evalJs('typeof window.fxOpenArticleModal');
  console.log('typeof window.fxOpenArticleModal:', fnExists);

  // Now click trigger 1!
  console.log('\n--- CLICKING CARD 1 "Read Article" ---');
  await evalJs(`
    const btn = document.querySelectorAll(".fx-article-modal-trigger")[0];
    btn.click();
  `);

  await sleep(500);

  const card1Expanded = await evalJs(`
    document.querySelectorAll(".fx-resource-card")[0].classList.contains("is-expanded")
  `);
  console.log('Card 1 is-expanded (SHOULD BE FALSE):', card1Expanded);

  const overlayHasHiddenAfter = await evalJs(`
    document.getElementById("fx-article-modal-overlay").hasAttribute("hidden")
  `);
  console.log('Overlay has hidden attr after click (SHOULD BE FALSE):', overlayHasHiddenAfter);

  const overlayIsOpen = await evalJs(`
    document.getElementById("fx-article-modal-overlay").classList.contains("is-open")
  `);
  console.log('Overlay has .is-open class (SHOULD BE TRUE):', overlayIsOpen);

  const modalTitle = await evalJs(`
    document.getElementById("fx-modal-title").textContent
  `);
  console.log('Modal title populated:', modalTitle);

  const modalCat = await evalJs(`
    document.getElementById("fx-modal-category-text").textContent
  `);
  console.log('Modal category populated:', modalCat);

  const modalDate = await evalJs(`
    document.getElementById("fx-modal-date").textContent
  `);
  console.log('Modal date populated:', modalDate);

  const modalImg = await evalJs(`
    document.getElementById("fx-modal-image").src
  `);
  console.log('Modal image populated:', modalImg);

  const modalDesc = await evalJs(`
    document.getElementById("fx-modal-desc").textContent
  `);
  console.log('Modal desc populated:', modalDesc);

  const computedDisplay = await evalJs(`
    window.getComputedStyle(document.getElementById("fx-article-modal-overlay")).display
  `);
  const computedOpacity = await evalJs(`
    window.getComputedStyle(document.getElementById("fx-article-modal-overlay")).opacity
  `);
  const computedVisibility = await evalJs(`
    window.getComputedStyle(document.getElementById("fx-article-modal-overlay")).visibility
  `);
  console.log('Overlay computed styles -> display:', computedDisplay, 'opacity:', computedOpacity, 'visibility:', computedVisibility);

  // Capture screenshot of open modal
  const screenshotData = await send('Page.captureScreenshot', { format: 'png' });
  const ssPath = path.join(__dirname, 'modal_card1_open.png');
  fs.writeFileSync(ssPath, Buffer.from(screenshotData.data, 'base64'));
  console.log('Saved screenshot of open modal to:', ssPath);

  // Test close by X
  console.log('\n--- TESTING CLOSE BY X BUTTON ---');
  await evalJs(`
    document.getElementById("fx-modal-close").click();
  `);
  await sleep(400);

  const overlayIsOpenAfterClose = await evalJs(`
    document.getElementById("fx-article-modal-overlay").classList.contains("is-open")
  `);
  console.log('Overlay has .is-open after X click (SHOULD BE FALSE):', overlayIsOpenAfterClose);

  // Test click Card 2
  console.log('\n--- CLICKING CARD 2 "Read Article" ---');
  await evalJs(`
    const btn2 = document.querySelectorAll(".fx-article-modal-trigger")[1];
    btn2.click();
  `);
  await sleep(500);

  const modalTitle2 = await evalJs(`
    document.getElementById("fx-modal-title").textContent
  `);
  console.log('Card 2 Modal title populated:', modalTitle2);

  const modalCat2 = await evalJs(`
    document.getElementById("fx-modal-category-text").textContent
  `);
  console.log('Card 2 Modal category populated:', modalCat2);

  // Capture screenshot of card 2
  const screenshotData2 = await send('Page.captureScreenshot', { format: 'png' });
  const ssPath2 = path.join(__dirname, 'modal_card2_open.png');
  fs.writeFileSync(ssPath2, Buffer.from(screenshotData2.data, 'base64'));
  console.log('Saved screenshot of card 2 modal to:', ssPath2);

  // Test close by Escape key
  console.log('\n--- TESTING CLOSE BY ESCAPE KEY ---');
  await evalJs(`
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
  `);
  await sleep(400);
  const overlayIsOpenAfterEsc = await evalJs(`
    document.getElementById("fx-article-modal-overlay").classList.contains("is-open")
  `);
  console.log('Overlay has .is-open after Escape (SHOULD BE FALSE):', overlayIsOpenAfterEsc);

  // Test click outside modal
  console.log('\n--- TESTING CLOSE BY CLICKING OUTSIDE ---');
  await evalJs(`
    const btn3 = document.querySelectorAll(".fx-article-modal-trigger")[2];
    btn3.click();
  `);
  await sleep(500);
  console.log('Card 3 opened. Now clicking overlay backdrop outside modal box...');
  await evalJs(`
    document.getElementById("fx-article-modal-overlay").click();
  `);
  await sleep(400);
  const overlayIsOpenAfterBackdrop = await evalJs(`
    document.getElementById("fx-article-modal-overlay").classList.contains("is-open")
  `);
  console.log('Overlay has .is-open after backdrop click (SHOULD BE FALSE):', overlayIsOpenAfterBackdrop);

  ws.close();
  chromeProc.kill();
  console.log('\nAll browser diagnostics complete!');
}

run().catch((err) => {
  console.error('Fatal error during browser test:', err);
  process.exit(1);
});
