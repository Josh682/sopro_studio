import { spawn } from 'child_process';
import http from 'http';

const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9222;
const fileUrl = 'file:///Users/mac/Documents/Developer/Projects/sound-processor/reference/dashboard_grid.html';

console.log('Launching Chrome...');
const chrome = spawn(chromePath, [
  '--headless=new',
  '--no-sandbox',
  '--disable-setuid-sandbox',
  `--remote-debugging-port=${port}`,
  '--window-size=1120,720',
  '--user-data-dir=/tmp/chrome-measure-profile',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  fileUrl
]);

chrome.stderr.on('data', d => {
  console.log('stderr:', d.toString());
});
chrome.on('exit', code => {
  console.log('chrome exited with code:', code);
});

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
    } catch (e) {
      // wait and retry
    }
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

    // Set viewport emulation
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1120,
      height: 720,
      deviceScaleFactor: 1,
      mobile: false
    });

    // Wait for layout
    await sleep(500);

    // Evaluate measurements
    const evalRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const cards = Array.from(document.querySelectorAll('.card'));
        const cardMeasurements = cards.map((c, i) => {
          const mod = c.getAttribute('data-module') || ('MOD-0' + (i+1));
          const title = c.querySelector('.card-title')?.textContent?.trim() || '';
          return {
            index: i + 1,
            module: mod,
            title: title,
            clientWidth: c.clientWidth,
            clientHeight: c.clientHeight,
            scrollWidth: c.scrollWidth,
            scrollHeight: c.scrollHeight,
            offsetHeight: c.offsetHeight,
            diff: c.scrollHeight - c.clientHeight,
            overflow: c.scrollHeight > c.clientHeight
          };
        });

        const doc = document.documentElement;
        const body = document.body;
        const viewportInfo = {
          windowInnerWidth: window.innerWidth,
          windowInnerHeight: window.innerHeight,
          docClientWidth: doc.clientWidth,
          docClientHeight: doc.clientHeight,
          docScrollWidth: doc.scrollWidth,
          docScrollHeight: doc.scrollHeight,
          bodyScrollHeight: body.scrollHeight,
          hasHorizontalScroll: doc.scrollWidth > doc.clientWidth,
          hasVerticalScroll: doc.scrollHeight > doc.clientHeight
        };

        return { cardMeasurements, viewportInfo };
      })()`,
      returnByValue: true
    });

    const measurementData = evalRes.result?.result?.value;
    console.log('MEASUREMENT_DATA:' + JSON.stringify(measurementData, null, 2));

    // Capture screenshot to reference/dashboard_grid.png as well!
    const ssRes = await send('Page.captureScreenshot', { format: 'png' });
    if (ssRes.result && ssRes.result.data) {
      import('fs').then(fs => {
        fs.writeFileSync('reference/dashboard_grid.png', Buffer.from(ssRes.result.data, 'base64'));
        console.log('Screenshot saved to reference/dashboard_grid.png');
      });
    }

    ws.close();
  } catch (err) {
    console.error('Error during execution:', err);
  } finally {
    chrome.kill();
  }
}

run();
