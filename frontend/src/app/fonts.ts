import { Open_Sans, Quicksand } from "next/font/google";

/** The shop admin's type: Quicksand for headings, the menu and the brand; Open Sans for text. */
export const display = Quicksand({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-admin-display",
  display: "swap",
});

export const body = Open_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-admin-body",
  display: "swap",
});
