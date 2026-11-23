import { redirect } from "next/navigation";

/** Urns were renamed Products (the shop sells more than urns); old links keep working. */
export default function UrnsMoved() {
  redirect("/channels/etsy/products");
}
