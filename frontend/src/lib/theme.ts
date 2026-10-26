/**
 * Light/dark mode, shared with windycitywares.com and shop.windycitywares.com.
 *
 * The choice lives in one cookie, `wcw-theme` ("classic" = light, "midnight" = dark — the shop's names), set for
 * the whole windycitywares.com domain, so switching on any of the three sites carries over to the others.
 * The CRM's older `wcw.theme` localStorage value ("light" | "dark") is still read as a fallback, then the
 * device's preference. The CRM keeps its own palettes (globals.css `.dark`); only the choice is shared.
 * Same cookie as wcw-shop-portal frontend/src/lib/themes.ts and wcw-main-site lib/theme.ts.
 */
export type Theme = "light" | "dark";

const COOKIE = "wcw-theme";
const LEGACY_KEY = "wcw.theme";

function cookieDomain(): string {
  const h = location.hostname;
  return h === "windycitywares.com" || h.endsWith(".windycitywares.com") ? "; domain=.windycitywares.com" : "";
}

export function readTheme(): Theme {
  try {
    const m = document.cookie.match(/(?:^|;\s*)wcw-theme=([^;]*)/);
    const shared = m ? decodeURIComponent(m[1]) : null;
    if (shared === "midnight") return "dark";
    if (shared === "classic") return "light";
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy === "dark" || legacy === "light") return legacy;
  } catch {
    /* storage blocked: fall through to the device */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function saveTheme(theme: Theme) {
  const secure = location.protocol === "https:" ? "; secure" : "";
  const value = theme === "dark" ? "midnight" : "classic";
  document.cookie = `${COOKIE}=${value}; path=/; max-age=31536000; samesite=lax${cookieDomain()}${secure}`;
  try {
    localStorage.setItem(LEGACY_KEY, theme);
  } catch {
    /* the cookie still carries it */
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/** Inline <head> script: applies the saved mode before first paint (no light flash on a dark choice). */
export const themeBootScript = `(function(){try{var m=document.cookie.match(/(?:^|;\\s*)wcw-theme=([^;]*)/);var s=m?decodeURIComponent(m[1]):null;var d=s==="midnight"?true:s==="classic"?false:null;if(d===null){var l=localStorage.getItem("wcw.theme");d=l==="dark"?true:l==="light"?false:!!(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches);}if(d)document.documentElement.classList.add("dark");}catch(e){}})();`;
