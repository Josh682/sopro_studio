import { chromium } from 'playwright';
import path from 'path';
import { pathToFileURL } from 'url';
import fs from 'fs';

/**
 * Capture a high-DPI screenshot of an HTML document using Playwright Chromium.
 * 
 * @param {string} htmlPath - Path to HTML file (relative or absolute)
 * @param {string} pngPath - Output path for screenshot PNG
 * @param {Object} [options] - Configuration options
 * @param {number} [options.width=1152] - Viewport width in CSS pixels
 * @param {number} [options.height=768] - Viewport height in CSS pixels
 * @returns {Promise<string>} - Resolves with absolute output PNG path
 */
export async function screenshot(htmlPath, pngPath, options = {}) {
  const width = options.width || 1152;
  const height = options.height || 768;

  const absHtmlPath = path.isAbsolute(htmlPath) ? htmlPath : path.resolve(process.cwd(), htmlPath);
  const absPngPath = path.isAbsolute(pngPath) ? pngPath : path.resolve(process.cwd(), pngPath);
  const fileUrl = pathToFileURL(absHtmlPath).href;

  const outDir = path.dirname(absPngPath);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width, height },
      deviceScaleFactor: 2,
    });

    await page.goto(fileUrl, { waitUntil: 'networkidle' });

    // Ensure all web fonts are loaded and ready before taking the screenshot
    await page.evaluate(() => document.fonts.ready);

    // Capture screenshot with animations disabled
    await page.screenshot({
      path: absPngPath,
      animations: 'disabled',
    });

    return absPngPath;
  } finally {
    await browser.close();
  }
}

// Direct CLI runner support
const isDirectRun = process.argv[1] && (
  process.argv[1].endsWith('shot.mjs') ||
  (typeof import.meta.filename === 'string' && path.resolve(process.argv[1]) === path.resolve(import.meta.filename))
);

if (isDirectRun) {
  const args = process.argv.slice(2);
  const htmlPath = args[0] || 'reference/test_empty.html';
  const pngPath = args[1] || 'reference/test_empty.png';
  const width = parseInt(args[2], 10) || 1152;
  const height = parseInt(args[3], 10) || 768;

  screenshot(htmlPath, pngPath, { width, height })
    .then((saved) => {
      console.log(`[shot.mjs] Screenshot successfully captured: ${saved}`);
    })
    .catch((err) => {
      console.error('[shot.mjs] Error capturing screenshot:', err);
      process.exit(1);
    });
}
