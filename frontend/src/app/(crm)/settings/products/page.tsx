import { redirect } from "next/navigation";

/** Moved: product types & SKUs and extra costs have their own pages under Settings → Catalog. */
export default async function ProductSettingsMoved({ searchParams }: { searchParams: Promise<{ type?: string }> }) {
  const { type } = await searchParams;
  redirect(type ? `/settings/product-types?type=${encodeURIComponent(type)}` : "/settings/product-types");
}
