import { Figtree } from "next/font/google";

/** One UI typeface for the whole CRM (same as the shop's admin). */
export const body = Figtree({
  subsets: ["latin", "latin-ext"],
  variable: "--font-body",
  display: "swap",
});
