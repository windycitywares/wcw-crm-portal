import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

/** User avatar: image or initials in a coloured circle, with optional online status dot. */
export function Avatar({ src, name, status, size = "md", className }: { src?: string | null; name?: string | null; status?: "online" | "away" | "offline"; size?: "sm" | "md" | "lg"; className?: string }) {
  const sizes = { sm: "h-8 w-8 text-xs", md: "h-9 w-9 text-sm", lg: "h-10 w-10 text-base" };
  const initials = name
    ? name
        .split(" ")
        .map((part) => part[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";
  const colorIndex = name ? name.charCodeAt(0) % 6 : 0;
  const colors = ["bg-[#e7f4ea]", "bg-[#e7f1fb]", "bg-[#fdf3e0]", "bg-[#fbeae7]", "bg-[#e6e8f5]", "bg-[#fdecea]"];
  const textColors = ["text-[#1d6b38]", "text-[#1d6b9e]", "text-[#9a5c00]", "text-[#a12a1e]", "text-[#6250d6]", "text-[#a12a1e]"];
  const statusDot = { online: "bg-[#1d6b38]", away: "text-[#9a5c00]", offline: "bg-[#9ca3af]" }[status ?? "offline"];
  return (
    <div className={cn("relative flex shrink-0 items-center justify-center rounded-full overflow-hidden border border-line", sizes[size], className)}>
      {src ? (
        <img src={src} alt="" className="h-full w-full object-cover" />
      ) : (
        <div className={cn("h-full w-full flex items-center justify-center", colors[colorIndex], textColors[colorIndex])}>
          {initials}
        </div>
      )}
      {status && (
        <span className="absolute -right-1 -bottom-1 flex size-2 shrink-0 items-center justify-center rounded-full bg-surface border border-line">
          <span className={cn("size-full rounded-full", statusDot)} aria-hidden="true" />
        </span>
      )}
    </div>
  );
}
