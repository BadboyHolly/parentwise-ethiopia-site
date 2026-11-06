# Controlled test order — step by step (manual Telebirr/CBE + Telegram)

Purpose: prove one complete purchase end to end **before spending on ads**: a second person reaches Telegram, a payment is
**independently verified**, the **correct five PDFs** are delivered, the order is **recorded**, and every step is **timed**.
Use the times to set your support promise. Nothing here is automated; no backend is involved.
No password, PIN, one-time code or token is ever typed into chat, a file or this document.

## 0. Before you start (you, about 20 minutes)
1. **Confirm the five final files.** Several versions exist on this computer, and the newest set has names containing
   `DRAFT`, `HOLD` and `TRIAL`. The pages shown on your sales page come from the newest set (checked: Quick Help page 13 on the
   site is page 13 of the 40-page file below), so these five are the likely product. **You must confirm they are the approved final
   versions** (or tell me which are). Customers should not receive names like `HUMAN_HOLD`.

{{MANIFEST}}

   Expected for the test: five files, exactly the pages and sizes above. Core Guide is about 15 MB and START HERE about 5.6 MB.
2. **Make one private delivery folder** with clean names (so every customer gets the same five files). Suggested names:
   `ParentWise_1_Start_Here.pdf`, `ParentWise_2_Core_Guide.pdf`, `ParentWise_3_Action_Workbook.pdf`,
   `ParentWise_4_Quick_Help_and_Scripts.pdf`, `ParentWise_5_30_Day_Practice_Program.pdf`. Copy (do not move) the confirmed files there.
   Run in PowerShell to record the fingerprints and check them later: `Get-FileHash .\*.pdf -Algorithm SHA256`.
   Keep the folder private (not synced to a public link).
3. Prepare the **order log** (`docs/templates/ORDER-LOG-TEMPLATE.csv`) as a private spreadsheet; mark the first row `TEST = yes`.
4. Have your own Telebirr and CBE records open on your phone (the place you verify payments).
5. Choose the tester: a trusted person with their **own phone and Telegram account** who can pay 1,500 ብር. Real money moves
   and can be returned to them afterwards. Run **two passes if possible: one Telebirr, one CBE.**
6. Open <https://parentwise-ethiopia-full-website-preview.onrender.com/> (or the final address) and check you are on the version you intend to sell.
   Note: until the website changes are deployed, the live checkout still works the same way.

## 1. The run (fill in the minutes)
Start a timer at step 1. Write the clock time next to each step.

| # | Who | What | Clock time | Min | OK? |
|---|---|---|---|---|---|
| 1 | Tester | On their phone, open the site, read the page, tap the price button, fill name and phone, choose **Telebirr** (second pass: **CBE**) | | | |
| 2 | Tester | Check the payment screen shows **1,500 ብር**, the recipient number and **the holder's name**, and the "Edit" and copy buttons | | | |
| 3 | Tester | Pay 1,500 ብር to that number from their own Telebirr/CBE | | | |
| 4 | Tester | Tap **ክፍያ ፈጽሜያለሁ**, then the Telegram button; the message opens **already filled** with their name, phone and payment method; add the receipt screenshot and send | | | |
| 5 | **You** | Notice the message (note the time it arrived) and reply | | | |
| 6 | **You** | **Verify independently**: open **your own** Telebirr/CBE record, find the payment, check **amount = 1,500 ብር**, the time and the **payer**. Do not rely on the screenshot. Write the transaction reference in the log | | | |
| 7 | **You** | Send the **five PDFs** to the tester in the same chat **as files** ("Send as file", not as compressed photos/media), in order 1→5 | | | |
| 8 | Tester | Check **each file**: right name, right size (compare with the table above), right **page count**, opens and is readable on **their phone** (do this on Android and on an iPhone if possible) | | | |
| 9 | Tester | Reply "received all five" or list what failed | | | |
| 10 | **You** | Fill the order log row (and the delivery checklist); mark `TEST = yes` | | | |
| 11 | Both | Total time from step 4 (message sent) to step 9 (all five received) | | | |

**Your published target is: verify within 10 minutes, at any hour.** Run **one extra pass in the evening or at night** (for example 21:00–23:00) to see what the promise really costs you.

## 2. Pass / fail
**Pass** only if all are true: the Telegram message reached you; the payment was found in **your own** record with the right amount;
**exactly the five approved files** arrived, open and match the page counts; the log row is complete; the tester could follow
every screen without help. Record every failure (message not delivered, file will not open, wrong or missing file, confusing screen,
slow step) in the "Notes" column of the log.

## 3. Using the result
- **Support promise:** take the measured time for steps 5→7 (notice → files sent), add a safety margin, and use that, not a guess.
  Your goal "immediately after payment verification" is met only if step 6→7 is a few minutes; verification itself (step 5→6) needs its own stated window.
- **If a file fails to open or a size/page count differs:** stop, fix the delivery folder, and repeat the run before selling.
- Send me the filled table, the log row (name/phone removed), and any problems. I will turn them into the final support wording.

## 4. After the test
Delete the tester's receipt screenshot from the chat when you are done (proposal: keep it only if you need it for a dispute), and
note in the log when it was deleted. Return the tester's money if agreed. Keep the log row (marked TEST) for the record.
