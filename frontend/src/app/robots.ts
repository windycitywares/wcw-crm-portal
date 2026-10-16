import type { MetadataRoute } from "next";

/** The CRM is private: keep every crawler out. */
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", disallow: "/" }] };
}
