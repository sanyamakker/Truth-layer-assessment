# Truth Layer - test results and demo notes

## Test method

The deployed app was opened in a private browser window and run against multiple PDFs. Search results are live, so counts can vary between runs. “No evidence found” means the search did not find support; it does not prove a statement is false.

## Runs already shown

| PDF | Claims found | Verified | Inaccurate | No evidence found | Notes |
|---|---:|---:|---:|---:|---|
| `Assessment_Product Management Trainee.pdf` | 1 | 0 | 1 | 0 | The extracted sentence is an assessment instruction about a product roadmap, not a factual trap claim. Do not use this run as proof of false-claim detection. |
| `demo rp.pdf` | 20 | 2 | 2 | 16 | Latest screenshot provided (Nov. 22, 4:40 PM). The highlighted GCF-Net result had Low confidence and matching snippets; treat it as a lead that needs source-context review. |

Earlier `demo rp.pdf` runs showed different counts. Keep the latest run as the displayed snapshot and explain that live-search results vary. Do not combine counts from separate runs.

## Controlled QA document - observed run

The app was run on `Truth_Layer_QA_Test_Claims.pdf`. The summary below records the screenshot. Individual rows still need to be matched to their app verdicts; do not fill in expected outcomes as if they were app results.

| Test input | Expected reference / review standard | App output (fill after run) | Human review |
|---|---|---|---|
| Eiffel Tower height stated as 500 m | Official Eiffel Tower page gives 330 m including antennas. This should be contradicted. https://www.toureiffel.paris/en/news/history-and-culture/300-330-meters-story-towers-height | Not extracted | Missed numeric claim |
| WHO pandemic characterization dated March 11, 2019 | WHO says it characterized COVID-19 as a pandemic on March 11, 2020. The year in the test input is wrong. https://www.who.int/europe/emergencies/situations/covid-19/ | Inaccurate; Low confidence; 5 source links shown | Mismatch flagged, but displayed candidate snippets do not clearly establish the correct year; manual WHO check confirms 2020 |
| Taj Mahal placed in Mumbai; construction said to start in 1900 | UNESCO places it in Agra and says construction started in 1632. Both place and date in the input are wrong. https://whc.unesco.org/en/list/252/ | Displayed FALSE; no source results; TimeoutException; Low confidence | Unresolved because search failed; not a successful fact check |
| Generative AI said to increase productivity by 40% for every company within 12 months | Too broad without study, population, metric, or source. App should request context or return insufficient evidence; do not label it definitively false solely because a search misses it. | Displayed FALSE; no source results; TimeoutException; Low confidence | Unresolved; app has not established the claim is false |
| Productivity said to rise exactly 50% across every industry and job type | Too broad and unsupported as stated; require a source, definition, population, and timeframe. | Displayed FALSE; explanation/source detail not visible in screenshots | Needs full card review; do not infer the basis for the verdict |
| Generic statement that AI is transforming all industries rapidly | Non-specific and has no measurable scope. Note whether the app skips it; the extractor prioritizes numeric/date claims. | Not extracted | Expected for a numeric/date-first extractor; state this scope limitation |

### Run observed on Nov. 22, 2026 (4:50 PM screenshot)

| Claims found | Verified | Inaccurate | No evidence found | Assessment |
|---:|---:|---:|---:|---|
| 4 | 0 | 1 | 3 | Partial detection. The false-date claim was labeled Inaccurate, but the visible result has Low confidence and its displayed candidate fact does not state the correct 2020 date. Three claims had no supporting evidence found. |

The test PDF contains five numeric/date claims plus one generic claim. The four cards visible across the screenshots are Claims B, C, D, and E. Claim A (the Eiffel Tower height) is missing from the extracted results. Claim F (the broad statement without a number) was also not extracted, which matches the prototype's numeric/date-first extraction scope.

**Claim B shown in the screenshot:** “WHO characterized COVID-19 as a pandemic on March 11, 2019.” App verdict: **Inaccurate**; confidence: **Low**. The candidate text shown is from a non-primary search result and does not establish the correct date. Manual comparison with WHO's official page confirms the pandemic characterization date was March 11, 2020: https://www.who.int/europe/emergencies/situations/covid-19/. Record the app result as a useful mismatch flag with a weak correction/evidence trail, not as fully verified fact-checking.

**Claim C shown in the screenshot:** The Taj Mahal location/date statement is displayed as **FALSE**, but the app says no source results were returned and `TimeoutException`; confidence is Low. This must be recorded as **unresolved because search failed**, not as a successfully established false claim. UNESCO's official page says the Taj Mahal is in Agra and construction began in 1632: https://whc.unesco.org/en/list/252/.

**Claim D shown in the screenshot:** The broad 40% AI productivity claim is displayed as **FALSE**, while the app reports no sources and `TimeoutException`; confidence is Low. Record this as **unresolved because search failed**. The app has not supported the 40% figure or established a correction.

**Claim E shown in the screenshot:** The broad 50% productivity claim is displayed with a **FALSE** badge. Its explanation/source area is not visible in the screenshots, so leave that detail unverified until reviewed.

This run exposes a labeling issue: the three summary items counted under “No evidence found” are shown on the cards with a **FALSE** badge. The app's timeout message correctly says a failed search is not evidence that the claim is false, but the badge can mislead viewers. State this limitation plainly in the demo and report. Do not describe the run as passing false-claim detection: one contradiction was flagged, one numeric claim was missed, and two visible cards show search timeouts.

Keep the observed summary as **4 / 0 / 1 / 3**. In the table above, the visible individual outcomes are B = Inaccurate; C and D = displayed FALSE with timeout/no sources; E = displayed FALSE (details pending); A = not extracted; F = not extracted.

## How to run the controlled test

1. Open the deployed app in Chrome Incognito (`Command + Shift + N`).
2. Upload `Truth_Layer_QA_Test_Claims.pdf` and click **Extract claims and check sources**.
3. Write the actual claim count and status totals in the table above. Open each relevant claim and record one source title/domain, the snippet, and the app confidence.
4. Compare the first three claims with the official references linked above. Mark each as supported, contradicted, or unresolved after checking the source page itself. For broad claims, judge whether the app explains what context is missing.
5. If the app marks a wrong statement Verified, or gives a correction without a source that supports it, record that as a failure/limitation. Do not hide it; explain what should improve.

## 30-second demo plan

Use one completed run of `demo rp.pdf`. Keep the screen zoom readable and show the summary, one claim card, and one expanded source.

**Narration:** “This is Truth Layer, a PDF fact-checking prototype. I upload a report, and it extracts claims with figures or dates. For each one, it shows a verdict, confidence, explanation, and live source leads. Here is one example and its linked evidence. Search snippets are leads, so I check the full source and matching context before treating a claim as confirmed.”

On Mac, press `Command + Shift + 5`, choose **Record Selected Portion**, use **Options** to select a microphone if desired, and record the app for about 30 seconds. Stop the recording and play it once to confirm the claim and source are legible. Send the final video to Nutan mam.
