# Automating payment verification — feasibility note (for later; nothing is built)

Status: 2026-11-06. **Not implemented and not recommended for launch day.** Launch uses your own manual check in your own Telebirr/CBE record.
Facts below come from public project pages found by search; I did **not** open or run any of these tools, and licences, maintenance and
current reliability are **unverified**.

## Short answer
**Yes, partly, and it can be added later.** What can be automated well is *looking up a transaction number* and comparing amount, recipient, time and status.
What cannot be trusted is a *screenshot* on its own: reading the text of an image (OCR) shows what the image says, not whether the payment is real.

## What exists (open source / free, unofficial)
- `cheki` / `ethio-receipt-verify` (Python package): checks CBE, Telebirr and other receipts by reference number using the banks' public receipt pages. <https://pypi.org/project/cheki/>
- `verpay` (TypeScript, self-hosted REST API): CBE and Telebirr; also tries to read a screenshot with an AI model and cross-check it with the provider. <https://github.com/robiabebe/verpay>
- `verifier-api` (TypeScript/Express): Telebirr and CBE by reference number. <https://www.github.com/Vixen878/verifier-api>
- `telebirr-receipt` (Python): fetches a Telebirr receipt by its number and parses it. <https://pypi.org/project/telebirr-receipt/>
- Verify.ET: a web lookup (independent, **not** an Ethio telecom product). <https://verify.et/verify/telebirr>

## Limits and risks (be honest about these)
1. **Unofficial.** They read public receipt pages; the pages can change and the tools can break without notice.
2. **Location.** Telebirr checks reportedly need an Ethiopian IP address; running them abroad may fail.
3. **Screenshots lie.** A fake or edited image can look perfect. The check must be on the **full transaction number** against the provider's record, plus amount = 1,500 ብር, recipient = your account, plausible time, not a reused number.
4. **Privacy.** Sending customers' details to a hosted third-party verifier is a data-sharing decision ⚖. Prefer a tool you run yourself, after reviewing its code.
5. **No official merchant API found.** For an official confirmation (callback/API), ask your Telebirr and CBE merchant contacts whether one is available to you.
6. **Never** give any of these tools a bank password, PIN or one-time code.

## Recommended path (staged; you stay in control)
| Stage | What | When |
|---|---|---|
| 0 | Manual check in your own app; ask customers for the **transaction number as text** (this alone cuts your check to seconds) | **Launch** |
| 1 | A private helper that looks up a transaction number and shows MATCH / MISMATCH with the reasons; you still approve every order | After about 20 real orders and once you know your volume |
| 2 | The helper drafts the reply and prepares the delivery; you tap to send | After weeks with no mismatches |
| 3 | Automatic delivery only on a full match; anything odd goes to you | Only with evidence, and only after a security review |

A second, simpler signal worth testing in Stage 1: the **SMS or notification you receive when money arrives** usually carries the amount, the sender and a reference. Matching the customer's transaction number against those messages is harder to fake than a screenshot. Check what your Telebirr and CBE alerts contain before designing around them.

## Questions for you
1. Do your Telebirr and CBE incoming-money alerts include the transaction number and the payer's name?
2. Are you willing to ask customers to type the transaction number into the Telegram message (I can add a "transaction number" prompt to the prefilled message later)?
3. Do you have a Telebirr/CBE merchant contact who can say whether an official verification option exists?
