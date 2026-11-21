# Truth Layer

Truth Layer is a Streamlit web app that extracts numeric and date claims from a PDF, searches the live web for evidence, and produces a source-linked review. It is built as an assessment prototype for marketing and product teams.

## What it does

- Accepts PDF uploads up to 12 MB and 40 pages.
- Finds sentences containing statistics, dates, percentages, currency, or time periods.
- Searches the live web for each claim and shows source titles, snippets, and links.
- Labels each result **Verified**, **Inaccurate**, or **False / no evidence found**.
- Returns a best-supported fact, explanation, confidence, and downloadable Markdown report.
- Optionally uses an OpenAI API key to reason over retrieved search evidence. Without a key, it uses a conservative lexical and numeric matching fallback.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. Internet access is required for live search. An OpenAI API key is optional; to use one locally, add it to `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-key"
```

The app also accepts a session-only key in its sidebar. It does not write uploaded PDFs or entered keys to disk. When deploying, save any model key in the host's secret manager; never commit it to the repository.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository and push this folder to its default branch.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py` as the main file.
3. Add `OPENAI_API_KEY` to the app's Secrets setting if you want model-assisted verdicts. The live search and fallback remain available without it.
4. Deploy, wait for the app health check, then open the public URL in a private browser window and try a PDF.

The assessment requires a live URL and a GitHub repository. This workspace contains the deployment-ready app but has not been published: publishing requires access to your GitHub and hosting accounts. Do not claim the app is live until the hosted link is verified.

## How verification works

The app uses DuckDuckGo search results as live evidence leads. When an OpenAI key is configured, each extracted claim and its search-result snippets are sent to OpenAI for comparison; the full PDF is not sent. Otherwise, a fallback checks keyword overlap and whether the searched snippets contain matching figures. Each finding links to the retrieved sources so a reviewer can inspect the original context.

Search snippets can be incomplete or stale. “False” means the search did not find supporting evidence; it does not prove the claim is false. The fallback is a prototype heuristic, not a substitute for an editor's review. Verify source dates, units, geography, and population before publishing.

## Limits

- The first version prioritizes sentences with numeric/date content; it does not extract every qualitative claim.
- Scanned PDFs need OCR and are not supported yet.
- Retrieval quality depends on the public search results available at the time of a run.
- Add a configured model key for stronger semantic comparison; key use may incur provider charges.
- This prototype does not retain files or provide multi-user accounts, audit history, or private storage.

## Demo recording (30 seconds)

Use a small PDF with a dated statistic and one deliberately incorrect figure. Show: (1) choosing the PDF, (2) starting the review, (3) opening a claim's source links, and (4) downloading the report. Record the deployed app only after confirming that its URL loads from a private browser window. Keep the recording to 30 seconds and avoid showing API keys.
