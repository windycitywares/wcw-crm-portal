import { notFound } from "next/navigation";

/** Any CRM address that isn't a page: answer 404 inside the CRM's own frame (sidebar and header), as the shop
 *  answers inside its header and footer. Real pages always win over this catch-all. */
export default function Missing() {
  notFound();
}
