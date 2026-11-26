import type { HelpTopic } from "../types";

const MANAGE = { permission: "channels:manage", text: "Add and change product types, sizes, SKU formats and extra costs." };

export const CATALOG_TOPICS: HelpTopic[] = [
  {
    id: "settings-product-types",
    href: "/settings/product-types",
    match: /^\/settings\/product-types/,
    title: "Product types & SKUs",
    summary: "Each kind of product you sell (Urn, Jewelry…) has its own sizes and its own way of writing a SKU. A type without sizes is sold as one item at one price.",
    steps: [
      "Pick a type from the tabs, or add a new one with its code (for example J for Jewelry).",
      "Under Sizes, list the sizes of that type.",
      "Set the SKU format: the pattern every SKU of this type follows. The page shows an example so you can check it.",
      "Open Products afterwards to see the SKUs this produces.",
    ],
    meanings: [
      { term: "Code", text: "A short letter or two that appears in the SKUs of this type." },
      { term: "Hidden", text: "A hidden type is kept but no longer offered when choosing a type." },
      { term: "SKU format needs a look", text: "The pattern has something the CRM cannot fill in. Open the type and read the message." },
    ],
    flow: { id: "etsy", step: "types" },
    affects: ["Changing a code or format changes the SKUs of every product of that type."],
    tips: [{ q: "Where do I add or rename a type?", a: "In Settings → Types → Product types, or on this page. They are the same list." }],
    who: [MANAGE],
    related: [{ href: "/settings/extra-costs", label: "Extra costs" }, { href: "/channels/etsy/products", label: "Products" }],
    keywords: "sku format size code type urn jewelry separator",
  },
  {
    id: "settings-extra-costs",
    href: "/settings/extra-costs",
    match: /^\/settings\/extra-costs/,
    title: "Extra costs",
    summary: "Things added to or taken off the supplier's price, such as packaging or a discount. Each can be per piece or per order, and an amount or a percentage. Minus amounts subtract.",
    steps: [
      "Use “Every product” for costs that apply to everything you sell.",
      "Use a type's own section for costs that apply only to that type.",
      "Choose whether it counts per piece or once per order, and whether it is an amount or a percentage.",
      "Use a minus amount for a discount from the supplier.",
    ],
    meanings: [
      { term: "Per piece", text: "Counted once for every piece in the order." },
      { term: "Per order", text: "Counted once, however many pieces the order has." },
      { term: "Percentage", text: "A share of the supplier's price instead of a fixed amount." },
    ],
    flow: { id: "etsy", step: "extras" },
    affects: ["New costs apply to new orders. To update older ones, use “Recalculate costs” on Etsy orders."],
    tips: [{ q: "A cost applies to one product only.", a: "Add it on that product's own page instead." }],
    who: [MANAGE],
    related: [{ href: "/settings/product-types", label: "Product types & SKUs" }, { href: "/channels/etsy/orders", label: "Etsy orders" }],
    keywords: "packaging discount percentage per piece per order cost",
  },
  {
    id: "settings-channels",
    href: "/settings/channels",
    match: /^\/settings\/channels/,
    title: "Sales channels",
    summary: "The outside shops you sell on. Connecting one here makes it appear under External shops in the menu.",
    steps: [
      "Pick the marketplace at the top. Etsy is the one available today.",
      "Follow the connection steps on the page.",
      "Once connected, listings and orders arrive on their own.",
    ],
    flow: { id: "etsy", step: "connect" },
    before: ["Your Etsy keys. Enter them only on this page and never send them in chat or email."],
    tips: [{ q: "Does connecting change my Etsy shop?", a: "No. The CRM reads listings and orders. Changes from the CRM to Etsy are switched off." }],
    who: [MANAGE],
    related: [{ href: "/channels/etsy", label: "Etsy overview" }],
    keywords: "connect etsy marketplace api keys integration",
  },
];
