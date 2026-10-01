import { spawn } from 'child_process';
import fs from 'fs';

const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9224;
const fileUrl = 'file:///Users/mac/Documents/Developer/Projects/sound-processor/reference/button_states.html';

console.log('Launching Chrome for button_states...');
const chrome = spawn(chromePath, [
  '--headless=new',
  '--no-sandbox',
  '--disable-setuid-sandbox',
  `--remote-debugging-port=${port}`,
  '--window-size=1200,900',
  '--user-data-dir=/tmp/chrome-btn-profile',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  fileUrl
]);

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function getWsUrl() {
  for (let i = 0; i < 20; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const data = await res.json();
      if (data && data.length > 0) {
        const page = data.find(p => p.type === 'page');
        if (page && page.webSocketDebuggerUrl) {
          return page.webSocketDebuggerUrl;
        }
      }
    } catch (e) {}
    await sleep(250);
  }
  throw new Error('Could not connect to Chrome debugging port');
}

async function run() {
  try {
    const wsUrl = await getWsUrl();
    console.log('Connected to CDP at:', wsUrl);
    const ws = new WebSocket(wsUrl);

    let id = 1;
    const pending = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
    };

    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });

    function send(method, params = {}) {
      const msgId = id++;
      return new Promise((resolve) => {
        pending.set(msgId, resolve);
        ws.send(JSON.stringify({ id: msgId, method, params }));
      });
    }

    // Set viewport emulation: exactly 1200x900
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1200,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false
    });

    await sleep(800);

    const evalRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const rows = Array.from(document.querySelectorAll('.matrix-row'));
        const info = rows.map((r, i) => {
          const rect = r.getBoundingClientRect();
          return { i: i+1, tag: r.querySelector('.matrix-mod-tag')?.textContent, top: rect.top, bottom: rect.bottom, height: rect.height };
        });
        const card2 = document.querySelectorAll('.btn-spec-card')[1]?.getBoundingClientRect();
        return { rows: info, card2Bottom: card2?.bottom, windowHeight: window.innerHeight };
      })()`,
      returnByValue: true
    });
    console.log('LAYOUT_DEBUG:', JSON.stringify(evalRes.result?.result?.value, null, 2));

    // Capture screenshot
    const ssRes = await send('Page.captureScreenshot', { format: 'png' });
    if (ssRes.result && ssRes.result.data) {
      fs.writeFileSync('reference/button_states.png', Buffer.from(ssRes.result.data, 'base64'));
      console.log('Successfully saved reference/button_states.png (1200x900)');
    }

    ws.close();
  } catch (err) {
    console.error('Error during execution:', err);
  } finally {
    chrome.kill();
  }
}

run();
