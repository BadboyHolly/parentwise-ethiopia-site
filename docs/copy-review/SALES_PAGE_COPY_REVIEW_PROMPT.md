# Prompt: Professional copy review of the ParentWise Ethiopia sales page

Copy everything between the lines into your reviewer (a human copywriter or an AI). The full page text is attached below the prompt in this file, so the review works even if the live link is behind a paywall, cached, or not yet updated.

---

## ROLE
You are a senior direct-response copywriter, conversion strategist and **native Amharic editor** who has sold digital products to first-time, skeptical buyers on mobile phones in Ethiopia. You review copy like a professional: specific, evidence-based, and willing to cut. You do not flatter.

## THE PAGE TO REVIEW
- **Live site (mobile-first, review at 375px wide):** https://parentwise-ethiopia-full-website-preview.onrender.com/
- **Version this review is about:** branch `deploy/parentwise-full-site-preview-20261021`, commit `d64d014` ("One brand font system... redesigned trust section"). If the live site does not yet show the new trust section (two doctor cards with a one-line teaser and a "ሙሉውን ያንብቡ" button) and the Inter font for English text, it has not been redeployed yet. In that case treat the **attached text as the source of truth**.
- **Related pages (for tone consistency only):** /order.html (checkout, 3 steps) and /policies/*.html (terms, privacy, refund, payment-delivery, educational disclaimer).

## BUSINESS FACTS (verified; do not contradict or embellish)
- Product: **ParentWise Child Behavior & Discipline System**, 5 digital PDFs: Start Here, Core Guide, Action Workbook, Quick Help & Parent Scripts, 30-Day Practice Program. No printed book.
- Price: **1,500 ብር** (shown only like this).
- Buying flow: parent enters name and phone, pays by **Telebirr or CBE bank transfer**, sends proof (name, phone, screenshot) on **Telegram**, and after confirmation receives the 5 PDFs on Telegram.
- Promise: a **30-day practice guarantee** with a refund policy page.
- Audience: Ethiopian mothers and fathers of children aged **2–12**, mostly on phones, Amharic first.
- Evidence: sources from WHO, UNICEF, CDC and others are listed for transparency only. The page states that these institutions have **not** endorsed ParentWise. The two doctor reviews (Dr. Meron Haylu PhD, Dr. Yohannes Assefa MD) are the **only** testimonials.

## BRAND VOICE (from the locked Brand Guide v1.1)
Calm authority for real parenting. Credible, calm, modern, practical, human, clear, evidence-led. "Clear before clever. Respectful without being soft. Evidence-led without sounding academic. Practical without oversimplifying. **Never shame parents.**" It must not feel childish, fear-based, judgmental, NGO-like or hospital-like. Master tagline (keep exactly): **How We Raise Matters.** The guide's campaign headline for this product, to be *transcreated* (not translated literally) and approved by a native speaker: "Parenting should not feel like the same fight every day."

## HARD RULES (a suggestion that breaks one of these is wrong)
1. Do **not** invent testimonials, numbers, statistics, awards, buyer counts, or outcomes. If a stronger claim needs a fact, write `[NEEDS FACT: ...]` instead.
2. The doctors' names, titles, dates and quotes stay **exactly as written**. You may flag risk in them, but do not rewrite them.
3. No fake urgency, countdowns, scarcity or pressure.
4. Never use the words "subscription" or "one-time payment" (or their Amharic equivalents). The price appears only as "1,500 ብር".
5. Do not promise results ("your child will..."). Describe what the parent gets and can try.
6. Every Amharic suggestion must come with a **literal English back-translation** and the label `needs native review`.
7. Keep the institutional disclaimer ("these institutions are sources, not endorsers").

## HOW TO REVIEW
Work through the attached copy section by section, reading it as a **cold, skeptical Ethiopian parent on a phone**, in order, never skipping ahead. Where the parent would hesitate, say so.

## DELIVERABLES (in this order, keep each tight)
1. **Verdict (5 lines):** the 5 biggest copy problems costing sales, ranked, each with the exact sentence that causes it.
2. **Section-by-section audit table:** columns = Section | Its job | What works | What fails (quote it) | Severity P0/P1/P2 | Fix (one line).
3. **Headline and hero:** diagnose the current H1 and subhead, then give **3 alternative H1 + subhead pairs in Amharic** (with English back-translation), including one transcreation of the campaign headline.
4. **Objection map:** the 8 most likely objections of a cold Ethiopian buyer (e.g. "is this a scam?", paying by transfer to someone unknown, Telegram delivery, will it work for my child's age, is it too foreign, is it in clear Amharic). For each: where the page answers it, where it doesn't, and a draft answer using **only verified facts**.
5. **FAQ gaps:** missing questions with draft answers (mark `[NEEDS FACT]` where unsure).
6. **Claims and compliance audit:** list every claim, mark Verified / Unverified / Risky, and give a safe rewrite for the risky ones. Pay special attention to "extremely effective"-style wording in the doctor quotes (flag only), any outcome language, and the payment phrase noted in Known Issues.
7. **Amharic quality review:** spelling, spacing, punctuation (፣ ። ፤), consistent formal address (ዎ-forms), consistent terms (e.g. መመሪያ vs ሲስተም), unnecessary English words, sentence length for mobile reading. List what a native speaker must confirm.
8. **Buttons and microcopy:** every button/link label, with a stronger or clearer alternative where useful, plus the sticky bottom bar.
9. **Length and order:** what to cut, merge or move up (the page is about 12,900px tall on a phone; the full offer starts about 65% down). Give a recommended section order with reasons.
10. **Prioritised action list:** P0 (do now) / P1 / P2, each with expected impact (High/Med/Low) and effort (S/M/L).
11. **Rewrite pack:** final, ready-to-paste Amharic rewrites (with English back-translation) for the 10 highest-impact strings.

## KNOWN ISSUES TO CHECK (seeds, not conclusions: confirm or reject each)
- The H1 has no space after the comma: "ሲል፣ምን".
- The offer contains "አንድ ጊዜ የሚከፈል ዋጋ" ("one-time payable price"), which may break hard rule 4.
- The purpose sentence "ዓላማው የዛሬን ችግር ማስቆም ብቻ ሳይሆን…" appears twice on the page.
- The six-step method labels (CHECK, CALM, CONNECT, DIRECT, FOLLOW THROUGH, TEACH & RECONNECT) and "THE PARENTWISE METHOD / HOW WE RAISE MATTERS." repeat in English on every card.
- The hero video is a placeholder ("በቅርቡ"); the video will be added later, so judge the copy around it, not its absence.
- The "How it helps" and "Six steps" sections overlap in message.
- Doctor quote wording is strong; assess credibility risk for a cold buyer.

## OUTPUT RULES
Be concise. Use tables where asked. Quote the exact original text you are criticising. Separate **fact** (from the page) from **opinion** (your judgment). End with a short list of **what you could not verify**.

---

# ATTACHED: FULL SALES-PAGE COPY (in page order, mobile; commit d64d014)
Legend: `##`/`###`/`####` = headings, `[BUTTON]` = tappable button or link, `(image: ...)` = image alt text. English-only repeated card labels are included as they appear.


---
### SECTION: HERO (first screen)
ከ2 እስከ 12 ዓመት ያሉ ልጆችን ለሚያሳድጉ ወላጆች
## ልጅዎ «እምቢ» ሲል፣ምን ማለትና ምን ማድረግ እንዳለብዎት ይወቁ።
ParentWise ሳይጮኹና ሳይቆጡ በቤትዎ የሚደጋገሙ ጭቅጭቆችን ለመቀነስና ጥሩ ልማዶችን ለማስተማር የሚረዳ ግልጽ መመሪያ ነው። የንግግር ምሳሌዎች፣ የተግባር ቅጾችና የ30 ቀን እቅድ ተካትተዋል።
▶የParentWise ማብራሪያ ቪዲዮ · በቅርቡ
[BUTTON] ParentWiseን በ1,500 ብር ያግኙ →
በቴሌብር ወይም በCBE ባንክ ዝውውር ይክፈሉ
(image: ዶ/ር ዮሐንስ አሰፋ)
ዶ/ር ዮሐንስ አሰፋ (MD)
የሕፃናት ሕክምና ስፔሻሊስት (አዲስ አበባ)
«የልጆችን አእምሮ ሳያሸማቅቁ በዲሲፕሊን ለማሳደግ የሚያግዝ ሳይንሳዊ መመሪያ ነው።»


---
### SECTION: PRICE STRIP
ParentWise Child Behavior & Discipline System1,500 ብር
አምስቱም የParentWise ክፍሎች ተካትተዋል።
በዲጂታል PDF ፋይሎች የ30 ቀን የልምምድ እቅድ


---
### SECTION: PAIN POINTS
02
### ከእነዚህ ውስጥ የትኞቹ ያጋጥሙዎታል?
ልጅ ማሳደግ ሁልጊዜ ቀላል አይደለም። ተመሳሳይ ነገር ደጋግመው መናገር፣ ጭቅጭቅን መፍታትና የራስዎን ቁጣ መቆጣጠር አንዳንድ ቀን ያደክማል።
(image: Mother supporting a frustrated young boy during a difficult moment)
#### ሲነግሩት አይሰማም
አንድ ነገር እንዲያደርግ ደጋግመው ይነግሩታል። ሳያደርገው ሲቀር፣ በመጨረሻ ድምፅዎን ከፍ ያደርጋሉ።
(image: Father listening to a daughter who has crossed her arms in disagreement)
#### «እምቢ» ብሎ ይከራከራል
አንድ ነገር እንዲያደርግ ሲጠይቁት «አልፈልግም» ይላል። ምክንያቱን ቢያስረዱትም ክርክሩ ይቀጥላል።
(image: Mother gently talking with a sad child sitting on the floor)
#### ሲናደድ ማረጋጋት ይከብዳል
የፈለገውን ሳያገኝ ሲቀር ያለቅሳል ወይም ይጮኻል። በዚያ ሰዓት ምን ማድረግ እንዳለብዎት ግራ ይገባዎታል።
(image: Father speaking calmly with an older child holding a smartphone)
#### ስልኩን ማስቀመጥ አይፈልግም
የስልክ ጊዜው ሲያበቃ «ገና ትንሽ» ይላል። እንዲያስቀምጠው ሲነግሩት ክርክር ይጀምራል።
(image: Mother helping a girl and boy resolve a dispute over a wooden toy)
#### ልጆችዎ ሲጣሉ
አንዱ ሌላውን ይወቅሳል። ሁለቱንም ሰምተው ግጭቱን እንዴት መፍታት እንዳለብዎት ይከብድዎታል።
(image: Ethiopian mother feeling overwhelmed during a parenting challenge)
#### በንዴት ምላሽ ይሰጣሉ
አንዳንዴ ተበሳጭተው የማይፈልጉትን ነገር ይናገራሉ። ከተረጋጉ በኋላ ግን በተናገሩት ነገር ይጸጸታሉ።


---
### SECTION: HOW IT HELPS
04
### ParentWise እንዴት ይረዳዎታል?
የልጅዎን ባህሪ ለመረዳት፣ በአስቸጋሪ ሰዓት ተገቢውን ምላሽ ለመስጠትና ለቤተሰብዎ የሚስማማ እቅድ ለማውጣት የሚረዳዎት ግልጽ መመሪያ።
#### የልጅዎን ባህሪ ይረዱ
ልጅዎ ሲናደድ ወይም «እምቢ» ሲል፣ ከዚያ በፊት ምን እንደተፈጠረ ማስተዋል ይማራሉ።
የሚደጋገሙ ሁኔታዎችን ለመለየት የሚረዱ ጥያቄዎችንና ምሳሌዎችን ያገኛሉ።
#### ምን ማለትና ቀጥሎ ምን ማድረግ እንዳለብዎት ይወቁ
ልጅዎ «እምቢ» ሲል ወይም ሲናደድ፣ ሊጠቀሙባቸው የሚችሉ የንግግር ምሳሌዎችን ያገኛሉ።
ወዲያውኑ ባይስማማም፣ ቀጥሎ ምን ማድረግ እንደሚችሉ ይማራሉ።
#### እቅድ አውጥተው በየቀኑ ይለማመዱ
ለቤተሰብዎ ግልጽ ሕጎችን ያዘጋጁ።
የ30 ቀን የልምምድ እቅዱንና የተግባር ቅጾችን ተጠቅመው የተማሩትን ይሞክሩ። ምን እንደረዳዎትና ምን መቀየር እንዳለብዎት ይከታተሉ።
ዓላማው የዛሬን ችግር ማስቆም ብቻ ሳይሆን፣ ልጅዎ ቀስ በቀስ ጥሩ ልማዶችን እንዲያዳብር መርዳትም ነው።


---
### SECTION: SIX STEPS (METHOD)
06 · OUR METHOD
### የParentWise ስድስት እርምጃዎች
ልጅዎ «እምቢ» ሲል፣ ሲናደድ ወይም የተናገሩትን ሳያደርግ ሲቀር፣ ከየት መጀመርና ቀጥሎ ምን ማድረግ እንዳለብዎት ማወቅ ይረዳዎታል።
የParentWise ስድስት እርምጃዎች ሁኔታውን እንዲረዱ፣ በተረጋጋ መንገድ ምላሽ እንዲሰጡና በኋላ ልጅዎን የተሻለ ባህሪ እንዲያስተምሩ ያግዛሉ።
[BUTTON] 01CHECK
[BUTTON] 02CALM
[BUTTON] 03CONNECT
[BUTTON] 04DIRECT
[BUTTON] 05FOLLOW THROUGH
[BUTTON] 06TEACH & RECONNECT
(image: ParentWise CHECK: mother observes her young child upset on the floor)
PARENTWISE · STEP 01
01
THE PARENTWISE METHOD01 / 06
01 — CHECK:
#### ሁኔታውን መረዳት
ምን እንደተፈጠረና ከዚያ በፊት ምን እንደነበረ ያስተውሉ። ልጅዎ የጠየቁትን ነገር አሁን ማድረግ ይችላል?
HOW WE RAISE MATTERS.
(image: ParentWise CALM: mother pauses to manage her emotions while child waits)
PARENTWISE · STEP 02
02
THE PARENTWISE METHOD02 / 06
02 — CALM:
#### ራስን ማረጋጋት
በንዴት ከመመለስዎ በፊት ትንሽ ቆም ይበሉ። ድምፅዎን ዝቅ አድርገው በተረጋጋ መንገድ ይናገሩ።
HOW WE RAISE MATTERS.
(image: ParentWise CONNECT: mother kneels to talk and listen to her child)
PARENTWISE · STEP 03
03
THE PARENTWISE METHOD03 / 06
03 — CONNECT:
#### መቀራረብ
የልጅዎን ትኩረት ይሳቡ። ምን እንደሚሰማው ለመረዳት ይሞክሩ። ይህ ግን ያስቀመጡትን ተገቢ ወሰን መተው ማለት አይደለም።
HOW WE RAISE MATTERS.
(image: ParentWise DIRECT: father gives a calm clear instruction to his child)
PARENTWISE · STEP 04
04
THE PARENTWISE METHOD04 / 06
04 — DIRECT:
#### ግልጽ መመሪያ መስጠት
ልጅዎ ምን እንዲያደርግ እንደሚፈልጉ በአጭሩና በግልጽ ይንገሩት።
HOW WE RAISE MATTERS.
(image: ParentWise FOLLOW THROUGH: child places blocks in a basket while father watches)
PARENTWISE · STEP 05
05
THE PARENTWISE METHOD05 / 06
05 — FOLLOW THROUGH:
#### ወሰኑን በተግባር ማዋል
ተገቢ ወሰን ካስቀመጡ፣ ልጅዎ ወዲያውኑ ባይስማማም በተረጋጋ መንገድ በተግባር ያውሉት።
HOW WE RAISE MATTERS.
(image: ParentWise TEACH AND RECONNECT: mother and child share a warm hug)
PARENTWISE · STEP 06
06
THE PARENTWISE METHOD06 / 06
06 — TEACH & RECONNECT:
#### ማስተማር እና እንደገና መቀራረብ
ሁኔታው ከተረጋጋ በኋላ ከልጅዎ ጋር ስለተፈጠረው ይነጋገሩ። በሚቀጥለው ጊዜ ምን ማድረግ እንደሚችል አብረው ይለማመዱ። ቅሬታ ከተፈጠረም እንደገና ለመቀራረብ ጊዜ ይውሰዱ።
HOW WE RAISE MATTERS.
01 / 06
ዓላማው የዛሬን ችግር ማስቆም ብቻ ሳይሆን፣ ልጅዎ ቀስ በቀስ ጥሩ ልማዶችን እንዲያዳብር መርዳትም ነው።


---
### SECTION: INSIDE: PREVIEW OF THE PDF PAGES
05
### ParentWise ከውስጥ ምን ይመስላል?
ከመግዛትዎ በፊት የParentWise የተግባር ቅጾች፣ የንግግር ምሳሌዎችና የ30 ቀን እቅድ እንዴት እንደሚቀርቡ የሚያሳዩ የንድፍ ምሳሌዎችን ይመልከቱ።
ከታች ያሉትን ትሮች ተጠቅመው PDFውን ይቀይሩ፤ ገጾቹን ለማየት ወደ ጎን ያንሸራትቱ።
[BUTTON] Quick Help
[BUTTON] Workbook
[BUTTON] 30-Day
(image: ልጄ «እምቢ» ሲለኝ — ምን ማድረግ)
(image: ምን ማለትና ምን ማስወገድ)
(image: የመረጋጋት ዕቅድ ገጽ)
(image: ሳምንታዊ የባህሪ መከታተያ ገጽ)
(image: የባህሪ መርማሪ ገጽ)
(image: የ30 ቀን ካርታ)
(image: የሳምንት 1 የዕለት ልምምድ)
(image: የ30 ቀን የመሻሻል መከታተያ)
#### ልጄ «እምቢ» ሲለኝ
ምን ማድረግ፣ ምን ማለትና ምን ማስወገድ እንዳለብዎት ደረጃ በደረጃ።
[BUTTON] ገጹን አስፍተው ይመልከቱ ⤢
ከሙሉ ጥቅሉ የተወሰዱ ናሙና ገጾች


---
### SECTION: WHAT YOU GET
### በParentWise ምን ያገኛሉ?
እርስ በርስ የሚደጋገፉ አምስት ክፍሎችን በአንድ ላይ ያገኛሉ።
#### START HERE
ለልጅዎ ዕድሜና ለገጠምዎት ችግር ተገቢውን ክፍል የሚያሳይ መምሪያ።
#### CORE GUIDE
ስለ ባህሪ፣ ስሜትና የቤተሰብ ሕጎች 7 ዋና ትምህርቶች።
#### ACTION WORKBOOK
የባህሪ መከታተያ፣ የቤተሰብ ሕግና የልምምድ እቅድ ቅጾች።
#### QUICK HELP & PARENT SCRIPTS
በአስቸጋሪ ጊዜ ምን ማለትና ማድረግ እንደሚችሉ የሚያሳዩ ምሳሌዎች።
#### 30-DAY PRACTICE PROGRAM
የየቀኑ አጭር ልምምዶችና የ30 ቀን መከታተያ እቅድ።
አምስቱም ክፍሎች በ1,500 ብር ግዢ ውስጥ ተካትተዋል።
[BUTTON] ParentWiseን በ1,500 ብር ያግኙ


---
### SECTION: TRUST: RESEARCH + DOCTORS
Trust & Credibility
### በምርምር የተደገፈ፣ ለኢትዮጵያ ቤተሰቦች የተዘጋጀ።
ParentWise ስለ ልጆች ባህሪና አስተዳደግ የተደረጉ ምርምሮችን በማጣቀስ የተዘጋጀ የወላጅነት ትምህርት ፕሮግራም ነው።
የምርምር ምንጮች
RESEARCH FOUNDATION
(image: WHO)
(image: UNICEF)
(image: CDC)
(image: University of Oxford)
(image: University of Cape Town)
(image: Stellenbosch University)
(image: Parenting for Lifelong Health)
(image: Triple P)
(image: The Incredible Years)
ለParentWise ዝግጅት ከተጠቀምንባቸው ምንጮች መካከል የዓለም ጤና ድርጅት (WHO)፣ ዩኒሴፍ (UNICEF) እና CDC ያቀረቧቸው የልጆች አስተዳደግ መመሪያዎች ይገኙበታል።
i
እነዚህ ተቋማት የመረጃ ምንጮች ናቸው፤ ParentWiseን አጽድቀዋል ወይም ደግፈዋል ማለት አይደለም።Sources are provided for research transparency; inclusion does not imply endorsement, approval, partnership or affiliation.
▤ምንጮቹን በዝርዝር ይመልከቱ
ስለ ምንጮቹ ያንብቡ፤ ዋናውን ድረ ገጽ ይክፈቱ
11 ምንጮች ⌄
የሚከተሉት ለበለጠ ንባብ የተመረጡ ምንጮች ናቸው። ጥናቶቹ ሁሉ ParentWise ራሱን የፈተኑ አይደሉም።
##### 01 · የመመሪያና የማጠቃለያ ምንጮች
መመሪያዎችና የምርምር ማጠቃለያዎች
01WHO መመሪያWHO guidelines on parenting interventions (2023)በወላጅነት ድጋፍ፣ በልጅ ጥበቃና በወላጅ–ልጅ ግንኙነት ላይ የተዘጋጀ መመሪያ።who.int↗
02UNICEF የወላጅ ምክርPositive parenting vs. strict parenting (2026)በፍቅር፣ በግልጽ ወሰንና በተረጋጋ ምላሽ ላይ የተዘጋጀ የወላጅ መረጃ።unicef.org↗
03CDC የዕድሜ መመሪያPositive Parenting Tips (2026)በልጅ ዕድሜ ደረጃ መሠረት የተደራጁ የወላጅነትና የልጅ ዕድገት ምክሮች።cdc.gov↗
04UNICEF Evaluation የግምገማ ሪፖርትA decade of evidence on parenting, caregiving and family-focused programmingየወላጅነትና የቤተሰብ ድጋፍ ፕሮግራሞች የምርምር ማጠቃለያ።unicef.org↗
##### 02 · የጥናትና የምርምር ሥራዎች
ጥናቶችና የተቋማት የምርምር ሥራ
05University of Cape Town የመጀመሪያ ደረጃ ጥናትParenting for Lifelong Health for Young Children — randomized trial (2020)በደቡብ አፍሪካ ከ2–9 ዓመት ልጆች ቤተሰቦች ጋር የተካሄደ የፕሮግራም ሙከራ።pmc.ncbi.nlm.nih.gov↗
06University of Oxford የምርምር ፕሮጀክትParenting for Lifelong Health SUPER studyየወላጅነት ፕሮግራሞችን ለማስፋፋትና ለመገምገም የተደረገ የምርምር ሥራ።spi.ox.ac.uk↗
07WHO / research collaborators የምርምር ትብብርParenting for Lifelong Health — partnership overviewWHO እና የተለያዩ የምርምር ተቋማት የተሳተፉበት የወላጅነት አጋርነት መረጃ።who.int↗
##### 03 · ፕሮግራሞችና የማስረጃ ስብስቦች
ፕሮግራሞች እና የጥናት መረጃ ቤቶች
08WHO / PLH የፕሮግራም መረጃParenting for Lifelong Health for Young Childrenለታዳጊ ልጆች የተዘጋጀውን የወላጅነት ፕሮግራም የሚያስተዋውቅ ገጽ።who.int↗
09Parenting for Lifelong Health የፕሮግራም ድረ ገጽParenting for Lifelong Health — official programme siteበተለያዩ አገሮች የሚጠቀሙባቸውን የወላጅነት መሣሪያዎችና ፕሮግራሞች ያሳያል።parentingforlifelonghealth.org↗
10Triple P / University of Queensland የማስረጃ ስብስብTriple P evidence base — University of Queenslandስለ Triple P የወላጅነት ፕሮግራም የተሰበሰቡ ጥናቶች እና የማስረጃ መረጃዎች።pfsc-evidence.psy.uq.edu.au↗
11The Incredible Years የጥናት ስብስብThe Incredible Years — research libraryየወላጅነት፣ የልጅ ማህበራዊ ችሎታና የባህሪ ድጋፍ ፕሮግራሞች ጥናቶች።incredibleyears.com↗
የባለሙያዎች ግምገማ
(image: Portrait provided for ዶ/ር ሜሮን ኃይሉ (PhD))
የባለሙያ ግምገማ · 01
#### ዶ/ር ሜሮን ኃይሉ (PhD)
የሕፃናትና ቤተሰብ ሥነ-ልቦና ባለሙያ
መስከረም 2019 ዓ.ም.
«በክሊኒኬ ለሚመጡ ወላጆች በሙሉ እንዲጠቀሙበት የምመክረው ተግባራዊ ሲስተም!»
«ዛሬ ላይ የስልክ ሱስ፣ የልጆች እልህና ያለ ምክንያት ማልቀስ በብዙ ቤተሰቦች ውስጥ ትልቅ ፈተና ሆኗል። ይህ መመሪያ የሥነ-ልቦና ንድፈ-ሐሳቦችን (Theories) ብቻ የሚዘረዝር ሳይሆን፣ ወላጆች ልጃቸው ሲቆጣ ወይም ሲያኮርፍ በዚያች ደቂቃ ምን ማለትና ማድረግ እንዳለባቸው ደረጃ በደረጃ የሚያሳይ ነው። በውስጡ ያሉት የልምድ መከታተያዎች (Routine Trackers) የልጆችን ባህሪ በአጭር ጊዜ ለመቀየር እጅግ ውጤታማ ናቸው።»
(image: Portrait provided for ዶ/ር ዮሐንስ አሰፋ (MD))
የባለሙያ ግምገማ · 02
#### ዶ/ር ዮሐንስ አሰፋ (MD)
የሕፃናት ሕክምና ስፔሻሊስት (አዲስ አበባ)
መስከረም 2019 ዓ.ም.
«የልጆችን አእምሮ ሳያሸማቅቁ በዲሲፕሊን ለማሳደግ የሚያግዝ ሳይንሳዊ መመሪያ ነው።»
«በሕፃናት ሕክምና ሥራዬ ብዙ ወላጆች 'ልጄ አልታዘዝ አለኝ' ብለው በጭንቀት ያማክሩኛል። ቁጣና ግርፊያ የልጆችን የአእምሮ እድገትና በራስ መተማመን እንደሚጎዳ ሳይንስ ያረጋግጣል፤ ግን ወላጆች 'ታዲያ ምን እናድርግ?' ለሚለው ተግባራዊ መልስ ያጡ ነበር። ParentWise Ethiopia ይህንን ክፍተት በሚገባ የሞላ፣ በዓለም አቀፍ የሕፃናት እድገት ጥናቶች ላይ የተመሠረተና ለኛ ማህበረሰብ እንዲሆን ተደርጎ የተዘጋጀ ድንቅ ሲስተም ነው።»
[BUTTON] ParentWiseን በ1,500 ብር ያግኙ
በቴሌብር ወይም በCBE ባንክ ዝውውር ይክፈሉ


---
### SECTION: THE OFFER (price, guarantee, how to buy)
የParentWise ሙሉ ጥቅል
### ሙሉውን ParentWise በ1,500 ብር ያግኙ።
አምስቱም የParentWise ክፍሎች ተካትተዋል።
ትምህርቶች፣ የንግግር ምሳሌዎች፣ የተግባር ቅጾችና የ30 ቀን የልምምድ እቅድ።
አንድ ጊዜ የሚከፈል ዋጋ
1,500ብር
ለ30 ቀን የልምምድ እቅድ — በቀን 50 ብር ገደማ
በቴሌብር ወይም በCBE ባንክ ዝውውር ይክፈሉ · ድጋፍ በቴሌግራም
ይዘቱን በዲጂታል PDF ፋይሎች ያገኛሉ።
[BUTTON] ParentWiseን በ1,500 ብር ያግኙ
የክፍያ አማራጮች
(image: telebirr brand logo — Ethio telecom)
telebirr
(image: Commercial Bank of Ethiopia (CBE) emblem)
CBE
በቴሌብር ወይም በCBE ባንክ ዝውውር መክፈል ይችላሉ።
የParentWise ድጋፍ — Telegram ↗
30-DAY PRACTICE GUARANTEE
#### የ30 ቀን የተግባር ዋስትና
ParentWiseን ያለ ምንም ስጋት ለ30 ቀናት በቤትዎ ይሞክሩት።
አንድ በተደጋጋሚ የሚያስቸግርዎትን ባህሪ ይምረጡ፣ የተግባር ቅጾቹን ይጠቀሙ፣ የ30 ቀን የልምምድ እቅዱንም ይከተሉ።
ይህንን አድርገው በቤትዎ ውስጥ የሚታይ መሻሻል ካላገኙ፣ በገንዘብ ተመላሽ መመሪያችን መሠረት
የከፈሉትን 1,500 ብር ሙሉ በሙሉ እንመልስልዎታለን።
Read the 30-Day Guarantee & Refund Policy →
ቀላል የግዢ ሂደት
#### እንዴት ይገዛሉ?
01
##### ትዕዛዝዎን ያስገቡ
ስምዎንና ስልክ ቁጥርዎን ያስገቡ።
02
##### ክፍያ ይፈጽሙ
በተገለጸው የቴሌብር ወይም የባንክ አድራሻ 1,500 ብር ይክፈሉ።
03
##### ማስረጃዎን ይላኩ
ስምዎን፣ ስልክ ቁጥርዎንና የክፍያ ማስረጃዎን በቴሌግራም ይላኩ።
04
##### ParentWiseን ይቀበሉ
ክፍያዎ ከተረጋገጠ በኋላ አምስቱ የParentWise PDF መመሪያዎች ወዲያውኑ በTelegram ይላኩልዎታል።


---
### SECTION: FAQ + CLOSING
11
### ስለ ParentWise ጥያቄ አለዎት?
1 — ParentWiseን በስልኬ መጠቀም እችላለሁ?+
አዎ። የParentWise PDF ፋይሎችን በስልክ ወይም በኮምፒውተር መክፈት ይችላሉ። የታተመ መጽሐፍ አይላክልዎትም።
2 — መጠቀም ከመጀመሬ በፊት አምስቱንም መመሪያዎች አንብቤ መጨረስ አለብኝ?+
አያስፈልግም። መጀመሪያ «ከዚህ ይጀምሩ» የሚለውን አጭር መመሪያ ያንብቡ። ከዚያ በአሁኑ ጊዜ ከሚያስቸግርዎት ጉዳይ ጋር የሚዛመደውን ክፍል አንብበው በተግባር ይጀምሩ።
3 — መመሪያዎቹን እንዴት እቀበላለሁ?+
በቴሌብር ወይም በCBE ክፍያ ከፈጸሙ በኋላ፣ የትዕዛዝ መረጃዎንና ደረሰኝዎን ወይም የዝውውር ቁጥርዎን በTelegram ይላኩልን። ክፍያዎን ካረጋገጥን በኋላ፣ አምስቱን የPDF መመሪያዎች ወዲያውኑ እንልክልዎታለን።
4 — Telegram ያስፈልገኛል?+
አዎ። የክፍያ ማስረጃዎን የሚልኩትና መመሪያዎቹን የሚቀበሉት በTelegram ነው። ክፍያ ከመፈጸምዎ በፊት Telegram መጠቀም እንደሚችሉ ያረጋግጡ።
5 — ክፍያ ከፈጸምኩ በኋላ ፋይሎቹ ባይደርሱኝስ?+
ስምዎን፣ ስልክ ቁጥርዎንና የክፍያ ማስረጃዎን ይዘው በParentWise የቴሌግራም አድራሻ ያነጋግሩን። የትዕዛዝዎን ሁኔታ ለማረጋገጥ እንረዳዎታለን።
ParentWise Telegram ድጋፍ ↗
6 — የልጄ ባህሪ ወዲያውኑ ባይቀየርስ?+
ParentWise ወላጆች በተረጋጋና በተደራጀ መንገድ ምላሽ እንዲሰጡ የሚያስተምር ፕሮግራም ነው። የልጅዎ ባህሪ ወዲያውኑ እንደሚቀየር ቃል አይገባም። የሚታየው መሻሻል እንደ ልጁና እንደ ቤተሰቡ ሁኔታ ይለያያል።
7 — ParentWise የባለሙያ እገዛን ይተካል?+
አይተካም። ParentWise ለወላጆች የተዘጋጀ የትምህርት ፕሮግራም ነው። ከባድ ወይም እየተባባሰ የሚሄድ የባህሪ፣ የጤና ወይም የልጅ እድገት ችግር ካለ፣ የባለሙያ እገዛ ያስፈልጋል።
(image: Illustrated Ethiopian family sitting together on a sofa)
How We Raise Matters.
### ልጆቻችንን የምናሳድግበት መንገድ ዋጋ አለው።
ልጅዎን ለመረዳት፣ በአስቸጋሪ ጊዜ የተሻለ ምላሽ ለመስጠትና ጥሩ ልማዶችን ለማስተማር የሚረዱ ተግባራዊ ዘዴዎችን ይማሩ።
ParentWise Child Behavior & Discipline System1,500 ብር
አምስቱም የParentWise ክፍሎች ተካትተዋል
በዲጂታል PDF ፋይሎች
የ30 ቀን የልምምድ እቅድ
[BUTTON] ParentWiseን በ1,500 ብር ያግኙ
የ30 ቀን የተግባር ዋስትናParentWiseን ያለ ምንም ስጋት ለ30 ቀናት በቤትዎ ይሞክሩት።
በቴሌብር ወይም በCBE ባንክ ዝውውር ይክፈሉ


---
### SECTION: FOOTER
(image: ParentWise Ethiopia)
How We Raise Matters.
#### Policies
Terms & Conditions
Privacy Policy
Educational Disclaimer
30-Day Guarantee & Refund Policy
Payment & Delivery Policy
Telegram Support
© 2026 ParentWise Ethiopia


---
### SECTION: FOOTER
(image: ParentWise Ethiopia)
How We Raise Matters.
#### Policies
Terms & Conditions
Privacy Policy
Educational Disclaimer
30-Day Guarantee & Refund Policy
Payment & Delivery Policy
Telegram Support
© 2026 ParentWise Ethiopia

