# Per-order delivery checklist (print or keep beside the log) — manual Telegram delivery

Keep the **order log private**: a spreadsheet shared with nobody (two-step sign-in on that account, no public link).
Never store receipt images, passwords, PINs or one-time codes in it. No child or medical details in the notes.

## Private order log (how to use `ORDER-LOG-TEMPLATE.csv`)
1. Import the CSV into Google Sheets or Excel; set sharing to **only you** (later: one named technical contact).
2. One row per order, filled **as it happens**. Column meaning:
   - **Order no.** running number you assign (`M-0001`, `M-0002`…). **TEST?** yes for rehearsal rows.
   - **First message / Payment checked / Files sent:** the real date and time. **Checked by:** who verified.
   - **Transaction ref:** copied from **your own** Telebirr/CBE record (never from the customer's screenshot alone).
   - **Files confirmed received:** yes only after the customer says they arrived and open.
   - **Status:** `pending`, `delivered`, `refund requested`, `refunded`, `rejected`.
   - **Refund window ends:** delivery date + 37 days (the published request window is days 31 to 37 after delivery).
   - **Delete-by date:** per the retention you approve (draft: 24 months).
3. Back up the sheet to a second private place once a month.

## For every order (tick in order)
- [ ] Message arrived on Telegram from the customer; note the time; reply politely.
- [ ] Name and phone in the message match what they wrote on the order page.
- [ ] **Open your own Telebirr/CBE record**: find the payment. **Amount is exactly 1,500 ብር.** Time and payer plausible.
- [ ] If not found or not exact: do **not** send files; ask for the transaction number; mark `pending`; follow up within the day.
- [ ] Copy the transaction reference into the log. Write your initials and the time in "Checked by".
- [ ] Send the **five PDFs from the private delivery folder, as files**, in order 1→5 (see the controlled test for names, sizes, page counts).
- [ ] Ask the customer to confirm all five arrived and open ("Please confirm you received five files").
- [ ] When confirmed: log "Files confirmed received = yes", status `delivered`, set "Refund window ends".
- [ ] Remind them once, kindly, how to reach you for help (Telegram) and of the 30-day practice guarantee conditions.
- [ ] End of day: any row still `pending` for more than one day gets a follow-up.

## If something goes wrong
- **Lost a file / chat is new:** check the log (name, phone, reference); resend the five files; note it.
- **File will not open:** ask which phone; ask them to open with a PDF viewer; resend; if still failing, resend after re-exporting from the original; note it.
- **Wrong or missing file:** resend the full correct set of five; apologise once; note it.
- **Paid but no files yet:** check your record at once; if found, deliver and log; if not found, say what you checked and ask for the bank/Telebirr confirmation.
- **Duplicate or wrong payment:** tell them honestly; decide the correction; log it; refund to the same account if appropriate.
- **A PDF is shared publicly:** note where and when; do not accuse; ask for removal politely; talk to your technical contact and lawyer before acting.
- **Customer asks to see, correct or delete their data:** confirm identity from the same Telegram account/phone; do it; record the request and date.
