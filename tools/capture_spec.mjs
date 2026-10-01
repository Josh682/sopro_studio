import { spawn } from 'child_process';
import fs from 'fs';

const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9223;
const fileUrl = 'file:///Users/mac/Documents/Developer/Projects/sound-processor/reference/vu_meter_spec.html';

console.log('Launching Chrome for vu_meter_spec...');
const chrome = spawn(chromePath, [
  '--headless=new',
  '--no-sandbox',
  '--disable-setuid-sandbox',
  `--remote-debugging-port=${port}`,
  '--window-size=1200,720',
  '--user-data-dir=/tmp/chrome-spec-profile',
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

    // Set viewport emulation: exactly 1200x720
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1200,
      height: 720,
      deviceScaleFactor: 1,
      mobile: false
    });

    await sleep(800);

    // Capture screenshot
    const ssRes = await send('Page.captureScreenshot', { format: 'png' });
    if (ssRes.result && ssRes.result.data) {
      fs.writeFileSync('reference/vu_meter_spec.png', Buffer.from(ssRes.result.data, 'base64'));
      console.log('Successfully saved reference/vu_meter_spec.png (1200x720)');
    }

    ws.close();
  } catch (err) {
    console.error('Error during execution:', err);
  } finally {
    chrome.kill();
  }
}

run();
