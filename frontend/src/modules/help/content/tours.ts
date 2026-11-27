import type { TourStep } from "../types";

const HEAD: TourStep = { selector: "main h1", title: "The page", body: "" };
const search = (what: string): TourStep => ({ selector: "main input[type=search]", title: "Search", body: `Type here to find ${what} fast. The list narrows as you type.` });

/** A one-minute walk around a page, by guide id. Three or four stops, each one sentence or two. */
export const TOURS: Record<string, TourStep[]> = {
  "etsy-overview": [
    { ...HEAD, body: "This is how your Etsy shop is doing: sales, costs and profit for the period you pick." },
    { selector: "main select", title: "Pick the period", body: "Change the period and every number on the page follows." },
    { text: "Orders", title: "Behind the numbers", body: "Use the buttons to open the orders, listings and supplier payments that the numbers come from." },
  ],
  "etsy-orders": [
    { ...HEAD, body: "Every paid Etsy order arrives here on its own. Your job is to enter what you paid and how you shipped." },
    search("a buyer or an order number"),
    { selector: "main table", title: "One row per order", body: "Open a row to enter the supplier cost, shipping cost and tracking. The profit works itself out." },
    { text: "Recalculate", title: "Recalculate costs", body: "After changing a product's price or an extra cost, use this to bring older orders up to date. It shows what would change first." },
  ],
  "etsy-products": [
    { ...HEAD, body: "Each Etsy listing as a product. It needs a type, a supplier and prices before its orders can be costed." },
    { selector: "main select", title: "Filters", body: "Find the products that still have no supplier, no prices or variations to check." },
    { selector: "main table", title: "The list", body: "Tick several products to give them a type or a supplier in one go, or open one to enter its prices." },
  ],
  "settings-product-types": [
    { ...HEAD, body: "Each kind of product you sell has its own sizes and its own way of writing a SKU." },
    { selector: "main [role=tablist], main nav", title: "Your types", body: "Pick a type to change its sizes and SKU format, or add a new type." },
    { text: "Template", title: "The SKU template", body: "This is the pattern every SKU of the type follows. Tap the ⓘ for what the words in braces mean. The examples underneath show the result." },
  ],
  customers: [
    { ...HEAD, body: "Everyone who buys from or talks to you. Open a person to see everything about them." },
    search("a customer by name or email"),
    { selector: "main select", title: "Filters", body: "Narrow the list by type, status, tag, owner or number of orders." },
    { selector: "main table", title: "The list", body: "Open a row to see the customer's page: orders, tickets, deals, tasks and notes." },
  ],
  leads: [
    { ...HEAD, body: "People who might become customers. Work them from new to converted." },
    { selector: "main [role=tablist], main [role=group]", title: "Status tabs", body: "Each tab is a status, and the number shows how many leads are in it." },
    { selector: "main table", title: "Your leads", body: "Change a lead's status right in its row. When one is serious, use Convert to create the customer and the deal in one step." },
  ],
  deals: [
    { ...HEAD, body: "Each possible sale, laid out by stage." },
    { selector: "main select", title: "Pipeline", body: "Each pipeline has its own stages. Pick the one you want." },
    { text: "List", title: "Board or list", body: "The board lets you drag a deal to the next stage. The list shows the same deals as a table." },
  ],
  tasks: [
    { ...HEAD, body: "Things someone needs to do: calls, follow-ups and reminders." },
    { selector: "main [role=tablist], main [role=group]", title: "Overdue, today and next", body: "Switch between what is overdue, due today, due soon, or all of it." },
    { selector: "main input[type=checkbox]", title: "Tick when done", body: "Tick a task to mark it done. It moves out of the way but is kept." },
  ],
  tickets: [
    { ...HEAD, body: "Every customer conversation is a ticket. Use this list to see what is open and what is late." },
    search("a ticket by number, like T-123, or by words"),
    { selector: "main select", title: "Filters", body: "Narrow by channel, priority or type. Use Show and Whose tickets to see what is yours." },
    { selector: "main table", title: "The list", body: "Open a ticket to reply, assign it and change its status. Badges show if a deadline is close or missed." },
  ],
  inbox: [
    { ...HEAD, body: "New customer messages from every channel, oldest waiting first." },
    { text: "Waiting on us", title: "Waiting on us", body: "Shows only the conversations where the customer spoke last, so nobody is left unanswered." },
    { selector: "main ul, main [role=list]", title: "The conversations", body: "Click one to read it beside the list, then reply, add a private note or use a saved reply." },
  ],
  campaigns: [
    { ...HEAD, body: "Your email campaigns and how each one did." },
    { text: "Templates", title: "Templates and audiences", body: "A campaign is a template (the email) sent to an audience (the people). Set those up from the menu on the left." },
    { selector: "main table", title: "Campaign report", body: "Open a campaign to see how many were delivered, opened and clicked, and which links people clicked." },
  ],
  suppliers: [
    { ...HEAD, body: "The suppliers who make what you sell, with their contacts and purchasing details." },
    search("a supplier"),
    { selector: "main table", title: "The list", body: "Open a supplier to see its contacts, lead time and the products it supplies with their costs." },
  ],
  dashboard: [
    { ...HEAD, body: "Your CRM at a glance. A good place to start the day." },
    { text: "Quick actions", title: "Quick actions", body: "Add a customer, deal, task, ticket or campaign without going to its page first." },
  ],
};

export const hasTour = (topicId: string) => !!TOURS[topicId];
