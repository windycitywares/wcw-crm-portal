import type { Flow, FlowId } from "./types";

/** The big pictures: the order things are done in, one box per page. Every box opens its page. */
export const FLOWS: Record<FlowId, Flow> = {
  etsy: {
    id: "etsy",
    title: "From Etsy listing to supplier payment",
    intro: "Set things up once (the first four boxes), then orders flow through on their own.",
    nodes: [
      { id: "connect", label: "Connect Etsy", href: "/settings/channels", note: "Link your shop once, so listings and orders arrive here." },
      { id: "types", label: "Product types & SKUs", href: "/settings/product-types", note: "Say what you sell, its sizes and how its SKU is written." },
      { id: "listings", label: "Listings", href: "/channels/etsy/listings", note: "Your Etsy listings, copied in. You only read them here." },
      { id: "products", label: "Products", href: "/channels/etsy/products", note: "Give each listing a type, a supplier and what one piece costs." },
      { id: "variations", label: "Check variations", href: "/channels/etsy/products/review", note: "Confirm what each Etsy variation means (how many pieces, which size)." },
      { id: "extras", label: "Extra costs", href: "/settings/extra-costs", note: "Add things like packaging or a discount, per piece or per order." },
      { id: "skus", label: "SKUs vs Etsy", href: "/channels/etsy/skus", note: "Compare the SKU each variation should have with what Etsy has." },
      { id: "orders", label: "Orders", href: "/channels/etsy/orders", note: "Paid orders arrive on their own. Enter what you paid and shipped." },
      { id: "payments", label: "Supplier payments", href: "/channels/etsy/payments", note: "See what you owe each supplier and mark what you have paid." },
    ],
  },
};
