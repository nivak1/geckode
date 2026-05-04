import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
/** Vercel deploys this folder only — keep the canonical asset here. */
const sourceLogo = path.join(__dirname, "..", "public", "logo.png");
const appDir = path.join(__dirname, "..", "src", "app");
const destIcon = path.join(appDir, "icon.png");
const destApple = path.join(appDir, "apple-icon.png");

if (fs.existsSync(sourceLogo)) {
  fs.mkdirSync(appDir, { recursive: true });
  fs.copyFileSync(sourceLogo, destIcon);
  fs.copyFileSync(sourceLogo, destApple);
  console.log(
    "Synced public/logo.png → src/app/icon.png and apple-icon.png (favicons)",
  );
} else {
  console.warn(
    "frontend/public/logo.png not found — skip favicon sync (add your logo there for Vercel builds)",
  );
}
