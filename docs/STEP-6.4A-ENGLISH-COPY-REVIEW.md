# STEP 6.4A — English Source Copy for Founder and Native Amharic Review

**Status:** Draft meaning only. No Amharic translations are proposed or approved here. Do not publish these temporary English staging messages to production. The approved Amharic checkout wording and visual design remain unchanged.

For every item below, approve the meaning, then obtain native Amharic review before replacing the staging placeholder.

## Stage 1 — Enter details

| Placement | Temporary English staging message | Intended meaning for approved Amharic copy |
|---|---|---|
| Staging notice | “This is an isolated test. Use fictional details only. Do not send money.” | Tell testers this is a test environment, only fictional data is allowed, and no transfer should be made. |
| Primary action | “Continue” (existing approved Amharic control remains in place) | Submit the customer name, Ethiopian phone number and chosen method to create the order. |
| Form errors and network retry | Existing form validation/error text and “Retry with the same details.” | Explain what field needs correction or that the same order request can safely be retried. |

## Stage 2 — Make payment and submit a claim

| Placement | Temporary English staging message | Intended meaning for approved Amharic copy |
|---|---|---|
| Instructions | “Pay exactly 1,500 ETB to the fictional recipient below. After sending the transfer, tap ‘I have paid’ and enter the transaction reference. This is an isolated test; do not send real money.” | State the exact amount, direct the buyer to the selected recipient, explain the next action, and warn that this staging account is fictional. |
| Copy action | “Copy Number”; “Copied”; “Fictional recipient copied”; “Clipboard unavailable; select the displayed number manually.” | Copy only the currently displayed recipient number and provide success or manual-selection feedback. |
| Primary action after transfer | “I have paid” | Open the reference-entry step only; this action does not mean payment is confirmed. |
| Reference help | “Find the transaction reference in your payment SMS or bank transaction details. If you cannot find it, contact ParentWise on Telegram for help.” | Explain where to find the transfer reference and point a stuck customer to official Telegram support. |
| Reference field/action | “Fictional transaction reference”; “Submit reference for checking” | Ask for the transfer reference and send it as a claim for manual review, not proof of payment. |
| Pending state | “Under Review”; “Your reference is being checked. Payment is not confirmed yet.” | Reassure the buyer that the claim arrived while clearly saying funds are still unverified. |
| Refresh/error | “Refresh order status”; “Status refresh failed. Check your connection and try again.”; generic request/retry errors; “We restored the details tied to your pending order request. Select Continue to safely retry it.” | Offer a safe retry and explain when a refresh or request cannot be completed. |
| Recovery code | “Before leaving, copy this code or write it down and keep it private. You will need it to find your order again.”; “Copy recovery code”; “Recovery code copied. Keep it private.”; “Clipboard unavailable. Select and save the complete code manually.”; “Hide code” | Tell the buyer to save the private code before leaving, offer copy with manual selection fallback, and let them hide it after saving. |
| Recovery form | “Recover an existing order”; “Order ID”; “Private recovery code”; “Recover order”; “Enter the complete order ID and recovery code.”; “Order could not be recovered. Check the ID and code.” | Explain that both values are needed to recover an order, and offer a privacy-preserving failure message that does not reveal which value was correct. |

## Stage 3 — Get the guides

| Placement | Temporary English staging message | Intended meaning for approved Amharic copy |
|---|---|---|
| Approval | “Payment Confirmed”; “Ready to Download”; “Payment is confirmed. Your guides are being prepared. Refresh this page shortly.”; “Payment confirmed. Your guides are ready.” | State that a founder completed independent verification and the five downloads are now available. |
| Rejection/retry | “No payment confirmation yet. If your last claim was rejected, you may try again after checking the details.” | Make clear that payment is unconfirmed and allow the buyer to submit a corrected reference if appropriate. |
| Download actions | “Download guide 1” through “Download guide 5” | Clearly distinguish the five files and give each a simple download action. |
| Android help | “After approval, tap Download. On Android, find the file in Downloads or open it from the download notification.” | Explain the common Android download location and notification without promising identical behavior on every phone. |
| Download error | “Download could not be completed. Try again or contact support.” or storage/network error | Tell the buyer a file could not be provided and offer the approved support/recovery path without exposing technical details. |
| Support | Existing official Telegram link remains; review whether the existing Amharic support explanation covers order recovery, pending verification and download problems. | Direct customers to the official ParentWise Telegram support channel when they cannot continue. |

## Review checklist

- Approve every meaning and its placement.
- Have a native Amharic reviewer check clarity for first-time digital-product buyers.
- Confirm no message implies “I have paid” or a submitted reference confirms payment.
- Confirm recipient instructions correspond to the production payment method and account before production copy is enabled.
- Keep stage-only English, fictional recipients and dummy downloads out of production.
\n\n## Additional temporary system messages\n\nThe staging page also presents a temporary test-order success notice, submission/network retry notices, recovery success/failure notices, and a generic download failure message. Have the founder and native reviewer approve meaning and tone for each; keep them out of production until localized. The backend status values shown in the checkout (Awaiting Payment, Under Review, Payment Confirmed, Ready to Download) also require approved Amharic labels.\n