/** One page's help, written in plain words and kept in code so it ships with the page it describes. */
export interface HelpTopic {
  id: string;
  /** The address of the page this describes (the one search results and "related" links open). */
  href: string;
  /** Which addresses show this help. The first topic that matches wins, so put specific pages first. */
  match: RegExp;
  title: string;
  /** Two or three sentences: what this page is for. */
  summary: string;
  /** Numbered: how to do the main jobs here. */
  steps?: string[];
  /** What the buttons, filters, badges and columns mean. */
  meanings?: { term: string; text: string }[];
  /** Where the page sits in a bigger flow, and which box is "you are here". */
  flow?: { id: FlowId; step?: string };
  /** What to have ready first. */
  before?: string[];
  /** What changing things here does elsewhere. */
  affects?: string[];
  tips?: { q: string; a: string }[];
  /** Who can do what: shown with a tick when the signed-in person has the permission. */
  who?: { permission: string; text: string }[];
  related?: { href: string; label: string }[];
  /** Extra words people might search for. */
  keywords?: string;
}

export type FlowId = "etsy" | "sales" | "support" | "campaigns" | "suppliers" | "setup";

export interface FlowNode {
  id: string;
  label: string;
  href: string;
  note: string;
}

export interface Flow {
  id: FlowId;
  title: string;
  intro: string;
  nodes: FlowNode[];
}

/** One stop on a page tour. The target is found by `selector`, or by the first button, link, heading or label whose text contains `text`.
 *  If nothing is found the step is still shown, without a highlight. */
export interface TourStep {
  selector?: string;
  text?: string;
  title: string;
  body: string;
}
