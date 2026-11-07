# Checkout wording for the owner's review, and for Ethiopian legal review

**Status: drafts only. Not live. The Amharic needs a native reader. Everything here needs review by an Ethiopian lawyer before real customer data is collected.**
I am not a lawyer. I understand that Ethiopia's Personal Data Protection Proclamation (No. 1321/2024) applies; please have that confirmed, together with any
registration, notification or breach-reporting duties it creates.

## What changed, and why
Two different things were mixed before. They are now separate:

1. **Order contact (a notice).** We use the name and phone to help with *their order* (for example, to ask for a receipt or to deliver the guides). A short line tells them.
2. **Promotional follow-up (an opt-in).** Tips and offers, and reminders to finish a checkout, need the customer's **own, optional, unticked-by-default choice**, recorded with the date and wording version, and **stoppable at any time**.

The system enforces this: a lead can receive promotional messages only if they opted in and have not stopped. A customer who writes to you first can always be answered.

## Checkout wording (shown only when lead capture is switched on)
**A. Small line under the form (order contact):**
> ስለ ትዕዛዝዎ በዚህ መረጃ እናገኝዎታለን። ዝርዝር

English meaning: *We will contact you about your order using this information. Details* ("Details" links to the privacy policy.)

**B. Optional box, unticked:**
> ስለ ParentWise ጠቃሚ ምክሮችና ቅናሾች በTelegram ወይም በስልክ እንዲላክልኝ እፈቅዳለሁ። በማንኛውም ጊዜ ማቆም እችላለሁ።

English meaning: *I agree to receive ParentWise tips and offers by Telegram or phone. I can stop at any time.*

Recorded: whether A was shown, whether B was ticked, the time, the wording version (`order-notice-2026-11-v1`, `promo-opt-in-2026-11-v1`), and the source (checkout, or "agreed in Telegram" recorded by you).

## How a customer stops
- Every promotional message ends with: **«እነዚህን መልዕክቶች ማቆም ከፈለጉ «አቁም» ብለው ይመልሱ።»** / *(Reply STOP to stop these messages.)*
- When someone replies STOP or asks to stop, press **Stop promotional follow-up** on their lead. It takes effect immediately, and they are locked out of promotional messages (you may still answer them if they write to you).
- Proposed promise on the privacy page: *we stop promotional messages as soon as you ask, and in any case within one business day.* (Owner to confirm.)
- "Do not contact" blocks every kind of message. **Erase lead** deletes the person.

## What the first release collects
Name, phone, checkout progress (which step they reached), their choice about promotions, and two follow-up preferences if you record them (preferred language, best time to talk).
**Not collected in the first release:** child age groups, challenge tags, free-text notes, region, how they heard about you. They are switched off in the software until the owner and a legal reviewer approve them.

## Proposed privacy-policy additions (draft, English; Amharic to be written and checked)
- *What we collect at checkout:* your name and phone number (saved when you continue, even if you do not finish), which checkout steps you reached, and your choices about messages.
- *Why:* to help you with your order and verify your payment (order contact). If you tick the optional box, also to send you ParentWise tips and offers.
- *Your choices:* you can stop promotional messages at any time by replying STOP or asking us; you can ask us to delete your details at any time.
- *How long we keep it:* `[period to be filled after the owner approves; see the retention proposal. The earlier 365-day figure is NOT approved]`.
- *Who can see it:* the founder and, later, named support staff. We do not sell your details. (Confirm this is true for every provider you use before publishing.)
- *Where it is stored:* AletCloud (hosting) and Telegram (where you chat with us). [Lawyer: cross-border and processor wording.]

## Questions for the lawyer
1. Is an order-contact notice enough for the order-related messages, or is consent needed for those too?
2. Are abandoned-checkout reminders "marketing" (opt-in required), as this design assumes?
3. What must the opt-in record contain, and how long must we keep that proof?
4. Are retention, a 90-day hashed deletion ledger, and backup handling acceptable? (See `production_checkout/RETENTION-AND-PURGE-PROPOSAL.md` in the backend repository.)
5. Registration or notification duties; breach notification; who is the responsible person for the data.
6. Is Telegram (a foreign messaging service) acceptable as the contact channel, and what must be said about it?
7. Later, if child age groups or notes are ever enabled: what extra consent or safeguards apply to information about children?
