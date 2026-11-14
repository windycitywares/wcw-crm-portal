import type { Metadata } from "next";
import { NotFoundMessage } from "@/components/layout/NotFoundMessage";

export const metadata: Metadata = { title: "Page not found" };

export default function CrmNotFound() {
  return <NotFoundMessage />;
}
