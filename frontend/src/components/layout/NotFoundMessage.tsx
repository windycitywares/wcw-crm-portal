import { ButtonLink } from "@/components/ui/Button";

/** The 404 message, laid out exactly like the shop's: a small "Page not found", one large line, the reason and
 *  a single way back. Used inside the CRM frame and on the bare page. */
export function NotFoundMessage() {
  return (
    <div className="px-4 py-28 text-center">
      <p className="text-sm text-muted">Page not found</p>
      <h1 className="mx-auto mt-3 max-w-xl text-5xl">We couldn’t find that page</h1>
      <p className="mt-4 text-muted">It may have moved, or the record is no longer available.</p>
      <ButtonLink href="/dashboard" className="mt-8">
        Go to the dashboard
      </ButtonLink>
    </div>
  );
}
