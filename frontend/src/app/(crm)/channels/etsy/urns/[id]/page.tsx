import { redirect } from "next/navigation";

export default async function UrnMoved({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/channels/etsy/products/${encodeURIComponent(id)}`);
}
