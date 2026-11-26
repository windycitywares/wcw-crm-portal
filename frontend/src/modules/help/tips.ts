/** Plain-words explanations for fields that are easy to get wrong. Shown by the ⓘ beside a field's label
 *  (`<Field tip={TIPS.x}>`). Kept here so the wording can be read and edited in one place. */
export const TIPS = {
  // Product types & SKUs
  typeCode: "A short letter or two that stands for this type in its SKUs, for example U for Urn. Changing it changes the SKU of every product of this type.",
  skuTemplate:
    "The pattern every SKU of this type follows. Words in curly braces are filled in for each product: {type} is the short code, {supplier:3} is the supplier's number padded to 3 digits, {product:4} is the product's number padded to 4 digits, and {sizes} is the pieces. Anything else you type, like a dash, is copied as it is. The examples under the fields show the result, so check them.",
  sizeFormat: "How one size is written inside the SKU. {code} is the size's code and {qty} is how many pieces of it. For example {code}{qty} could give S2 for two pieces of size S.",
  sizeSeparator: "What goes between sizes when a variation has more than one, such as a dash or a plus. Up to 3 characters.",
  sizeWords: "Other words Etsy variations use for this size, separated by commas. The CRM looks for them when it reads a variation's name, so “large” and “adult” can both mean the same size.",

  // Extra costs
  extraSign: "Adds is a cost on top of the supplier's price, like packaging. Subtracts is money off, like a discount the supplier gives you.",
  extraMode: "Dollars is a fixed amount. A percentage is a share of the supplier's price, and is always counted per piece.",
  extraApplies: "Per piece is counted for every piece in the order. Once per order is counted one time, however many pieces there are.",
  extraPieces: "Count this cost only for pieces of one size, or leave it on Any size to count every piece.",
  extraWhose: "Supplier's means you owe it to the supplier, so it is added to what you pay them. Ours only changes your profit, and nothing is owed to anyone.",
  extraFrom: "The date this cost starts to count. Leave it empty to start today.",

  // Support
  slaHours: "Counted in business hours, not clock hours, so the clock stops at night, on weekends and on holidays (Settings → Business hours). 8 hours is one working day.",
  slaMatch: "Leave both empty for a policy that applies to every ticket. If more than one policy fits a ticket, the most specific one wins: a policy with a priority beats one with only a type, and that beats a general one.",

  // Email
  smtpSecurity: "How the connection to the mail server is protected. Use the one your email provider gives you: SSL/TLS normally goes with port 465 and STARTTLS with port 587. Choosing one fills in the usual port.",
  replyTo: "Where a customer's reply goes when they press Reply. Leave it empty to use the From address.",
  postalAddress: "A real mailing address. The law requires it at the bottom of marketing emails, so the CRM adds it to every campaign.",
  dailyLimit: "The most emails the CRM sends in any 24 hours. Set it at or below what your email provider allows, or the provider may block you. Campaigns send only as many as there is room for.",
  perMinute: "How many emails go out each minute. A slow, steady pace looks normal to mail providers. Sending too fast can get you flagged as spam.",
  imapSecurity: "How the connection to the mailbox is protected. Use what your email provider says. SSL/TLS normally goes with port 993.",
  imapFolder: "Which folder in the mailbox the CRM reads. Almost always INBOX. The CRM reads unread messages only.",
  imapUsername: "What you type to sign in to the mailbox. If it is the same as the email address, leave this empty.",

  // Sales
  probability: "How likely a deal at this stage is to be won, from 0 to 100. The forecast in Reports multiplies each deal's value by this, so early stages should be low and the last stage before Won should be high.",
} as const;
