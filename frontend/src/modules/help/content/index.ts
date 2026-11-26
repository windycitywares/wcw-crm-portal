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
