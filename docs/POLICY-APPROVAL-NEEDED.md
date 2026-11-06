# Policy pages vs the actual manual process — only what needs your approval

Reviewed on 2026-11-06: privacy, refund, payment-and-delivery, terms and educational-disclaimer pages (Amharic), against the real
process: customer fills name/phone → pays Telebirr/CBE → sends proof on Telegram → **you verify in your own record** → you send the five PDFs on Telegram.
Your delivery target: **immediately after payment verification.**
Nothing below is changed on the site. Bracketed `[__]` values are yours to choose. ⚖ = have an Ethiopian lawyer check the wording.
The Amharic proposals are drafts for a native speaker and the lawyer to review.

## What already matches reality (no change needed)
Steps and wording of the purchase process (name/phone → pay → send proof → *you verify* → delivery); "sending proof alone does not mean the
payment is verified"; no PIN/password/OTP is ever requested; resend if lost / will not open / wrong file; duplicate or wrong payment handled
without waiting 30 days; refund to the same Telebirr/CBE account; the refund conditions (24 of 30 days, four weekly reviews, request days 31–37);
minimal child data in practice notes; the checkout screen itself already says **"ክፍያዎን ካረጋገጥን በኋላ፣ 5ቱን የPDF መመሪያዎች ወዲያውኑ በTelegram እንልክልዎታለን"** — which is exactly your target.
(Correction to my earlier draft: the privacy page **does** already state the right to ask for access, correction and deletion — section 8.)

## Decisions and wording for you to approve
| # | Where | Issue | Proposed (draft) |
|---|---|---|---|
| **1** | *Not a policy:* which five PDFs are the product | Newest files are named `DRAFT`, `HOLD`, `TRIAL`; older versions also exist | Confirm the final five (table in `CONTROLLED-TEST-ORDER.md`) and give them clean customer-facing names. **Blocks the test order.** |
| 2 | Payment & delivery §4; Terms §5 | They say delivery time "may vary" and will be "stated on the checkout page"; the checkout states "immediately after verification" but no verification window | Replace with: «ክፍያዎ ከተረጋገጠ በኋላ የParentWise መመሪያዎች ወዲያውኑ በTelegram ይላኩልዎታል። የክፍያ ማስረጃዎ ከደረሰን በኋላ ክፍያውን በ**[__]** ሰዓት ውስጥ ለማረጋገጥ እንሠራለን።» Choose the verification window from the test order. |
| 3 | Payment & delivery §1; Terms §3 | "ይህ የአንድ ጊዜ ክፍያ…" ("this is a one-time payment") — wording you do not want | §1: «ዋጋው የParentWiseን አምስቱንም ዲጂታል መመሪያዎች ያካትታል። ወርሃዊ ክፍያ ወይም የሚደጋገም የአባልነት ክፍያ የለም።» Terms §3: delete the sentence «ይህ የአንድ ጊዜ ክፍያ ነው።» (The phrase "የአንድ ጊዜ የደህንነት ኮድ (OTP)" is unrelated; leave it.) |
| 4 | Payment & delivery §10; Terms §12 | **No support hours or reply time anywhere** | Add: «የድጋፍ ሰዓት፦ **[ሰኞ–ቅዳሜ፣ __ እስከ __ (የአዲስ አበባ ሰዓት)]**። በዚህ ሰዓት ውስጥ በ**[__]** ሰዓት ውስጥ ምላሽ ለመስጠት እንሠራለን።» Set from the test order. |
| 5 | Privacy §4 ⚖ | Lists "payment service" providers; the manual flow uses none (money moves in Telebirr/CBE) | «…የድረ ገጽ ማስተናገጃ፣ የመረጃ ማከማቻና የመልዕክት መላላኪያ (Telegram) አገልግሎቶችን። ክፍያዎ በTelebirr ወይም በCBE በኩል ስለሚተላለፍ፣ እነዚህ ተቋማት የክፍያዎን መዝገብ በራሳቸው ደንብ ይይዛሉ።» |
| 6 | Privacy §7 ⚖ | Retention is only "as long as needed" — no periods | «የግዢና የክፍያ መዝገቦችን እስከ **[24]** ወር እንይዛለን፤ የክፍያ ደረሰኝ ምስሎችን ከገንዘብ ተመላሽ ጊዜው ማብቂያ በኋላ በ**[30]** ቀን ውስጥ እንሰርዛለን።» Periods are proposals; the lawyer confirms legal minimums. |
| 7 | Privacy §8 | Rights exist but not **how** or **how fast** | Add: «ጥያቄዎን በTelegram አድራሻችን ይላኩ፤ በ**[__]** የሥራ ቀናት ውስጥ እንመልሳለን።» |
| 8 | Privacy §9 ⚖ | Mentions cookies/measurement "may" be used; the site uses none today (visit counting is switched off) | No change now. **If you add ad pixels (Meta/TikTok) or analytics, this section and a visitor notice must be updated first.** Confirm: no pixels at launch. |
| 9 | Refund §6 | Promises review in **3 working days** and refund in **5 working days** | Confirm you can keep these alone, or lengthen. The 7-day request window counts from the **delivery date**, so the order log records it. |
| 10 | Checkout page; terms ⚖ | The holder name shown to customers ("Kidus Elias") is a person; nowhere says who the seller is or how the name relates to ParentWise. No seller identity (name/registration/contact) appears in the terms | Decide a short, **true** line on the checkout (for example whose account it is) and whether the terms must show seller details. I have not written new claims here. |

## What I did not change
No policy page was edited. The only website changes on the review branch are listed in `docs/LAUNCH-READINESS-REVIEW.md`.
