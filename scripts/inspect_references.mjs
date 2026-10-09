import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
await fs.mkdir("tmp/references", { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
for (const [name, url] of [
  ["jlern", "https://jlern.com/"],
  ["shekunj", "https://www.shekunj.com/"],
]) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: `tmp/references/${name}.png` });
    console.log(name, await page.title());
  } catch (error) {
    console.log(name, String(error));
  }
}
await browser.close();
