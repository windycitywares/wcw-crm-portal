import type { HelpTopic } from "../types";
import { CATALOG_TOPICS } from "./catalog";
import { CRM_TOPICS } from "./crm";
import { MARKETING_TOPICS } from "./marketing";
import { SETTINGS_TOPICS } from "./settings";
import { ETSY_TOPICS } from "./etsy";

/** Every page with a guide. The first topic whose `match` fits the address wins. */
export const TOPICS: HelpTopic[] = [...ETSY_TOPICS, ...CATALOG_TOPICS, ...CRM_TOPICS, ...MARKETING_TOPICS, ...SETTINGS_TOPICS];

export function topicFor(pathname: string): HelpTopic | undefined {
  return TOPICS.find((t) => t.match.test(pathname));
}

const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");

/** Topics where every word typed appears somewhere in the guide; a title match ranks first. */
export function searchTopics(q: string): HelpTopic[] {
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return TOPICS.map((t) => {
    const title = norm(t.title);
    const body = norm([t.summary, t.keywords ?? "", ...(t.steps ?? []), ...(t.meanings ?? []).map((m) => `${m.term} ${m.text}`), ...(t.tips ?? []).map((x) => `${x.q} ${x.a}`)].join(" "));
    const hay = `${title} ${body}`;
    if (!words.every((w) => hay.includes(w))) return null;
    return { t, score: words.every((w) => title.includes(w)) ? 0 : 1 };
  })
    .filter((x): x is { t: HelpTopic; score: number } => !!x)
    .sort((a, b) => a.score - b.score || a.t.title.localeCompare(b.t.title))
    .map((x) => x.t);
}

/** The Help center groups guides by area, found from the page each one describes. */
export const GROUPS: { label: string; test: (href: string) => boolean }[] = [
  { label: "Overview", test: (h) => ["/dashboard", "/reports", "/account"].includes(h) },
  { label: "Customers and sales", test: (h) => /^\/(customers|contacts|accounts|leads|sales)/.test(h) },
  { label: "Support and tasks", test: (h) => /^\/(inbox|tickets|tasks)/.test(h) },
  { label: "Campaigns", test: (h) => /^\/(campaigns|subscribers)/.test(h) },
  { label: "Suppliers", test: (h) => /^\/suppliers/.test(h) },
  { label: "Etsy", test: (h) => /^\/channels\/etsy/.test(h) },
  { label: "Settings", test: (h) => /^\/settings/.test(h) },
];

export function groupedTopics(list: HelpTopic[] = TOPICS): { label: string; topics: HelpTopic[] }[] {
  return GROUPS.map((g) => ({ label: g.label, topics: list.filter((t) => g.test(t.href)) })).filter((g) => g.topics.length > 0);
}
