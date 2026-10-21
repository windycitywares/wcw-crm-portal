import Link from "next/link";
import React from "react";
import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

/** Navigation path: home > section > page. Last item is the current page. */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-xs text-muted">
      {items.map((item, i) => {
        const last = i === items.length - 1;
        return (
          <React.Fragment key={item.label}>
            {i > 0 && (
              <span className="mx-1">
                <Icon name="chevronRight" className="size-3" />
              </span>
            )}
            {item.href && !last ? (
              <Link href={item.href} className="hover:text-accent-strong hover:underline">
                {item.label}
              </Link>
            ) : (
              <span className="text-ink font-medium">{item.label}</span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
