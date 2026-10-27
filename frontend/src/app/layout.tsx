import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/lib/auth";
import { themeBootScript } from "@/lib/theme";
import { body, display } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Windy City Wares CRM", template: "%s | WCW CRM" },
  description: "Internal CRM for the Windy City Wares team.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#f4f5fa" };

/** Root template: fonts, theme tokens and the signed-in user. Pages choose their frame via route groups. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        {/* Applies the light/dark choice (shared with the shop and windycitywares.com) before first paint. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
