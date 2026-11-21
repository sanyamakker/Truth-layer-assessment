"""Truth Layer: evidence-led fact checks for claims found in PDFs."""

from __future__ import annotations

import json
import html
import os
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

import requests
import streamlit as st
from ddgs import DDGS
from pypdf import PdfReader


APP_NAME = "Truth Layer"
MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_PAGES = 40
MAX_CLAIMS = 20
SEARCH_RESULTS = 5
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"


@dataclass
class Claim:
    text: str
    page: int


@dataclass
class Evidence:
    title: str
    url: str
    snippet: str
    domain: str


@dataclass
class Finding:
    claim: str
    page: int
    verdict: str
    corrected_fact: str
    explanation: str
    confidence: str
    evidence: list[Evidence]


NUMBER_RE = re.compile(
    r"(?:\b\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b\d+(?:\.\d+)?\s?%|"
    r"\b\d+(?:\.\d+)?\s?(?:million|billion|trillion|thousand|bn|mn|k)\b|"
    r"(?:\$|₹|€|£)\s?\d[\d,.]*|\b(?:19|20)\d{2}\b|\b\d+(?:\.\d+)?\s?(?:days?|months?|years?)\b)",
    re.I,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "by", "with", "from",
    "as", "at", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that",
    "these", "those", "we", "our", "their", "they", "you", "your", "can", "will", "may", "could",
    "has", "have", "had", "than", "which", "who", "what", "when", "where", "how", "more", "most",
}


def extract_claims(pdf_bytes: bytes) -> tuple[list[Claim], int]:
    reader = PdfReader(__import__("io").BytesIO(pdf_bytes), strict=False)
    if len(reader.pages) > MAX_PAGES:
        raise ValueError(f"This prototype supports up to {MAX_PAGES} pages per PDF.")
    claims: list[Claim] = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").replace("\u00ad", "")
        text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
        for raw in SENTENCE_SPLIT.split(re.sub(r"\s+", " ", text)):
            sentence = raw.strip(" \t\r\n•*-–—")
            words = re.findall(r"[A-Za-z]{2,}", sentence)
            # Author-year citations are references, not claims about the world.
            without_author_year = re.sub(r"\([^)]*\b(?:19|20)\d{2}\b[^)]*\)", " ", sentence)
            citation_only_year = NUMBER_RE.search(sentence) and not NUMBER_RE.search(without_author_year)
            imperative = re.match(
                r"(?i)^(?:please\s+)?(?:design|define|build|identify|extract|verify|report|compare|submit|write|create|ensure|find|use|track|measure)\b",
                sentence,
            )
            if NUMBER_RE.search(sentence) and not citation_only_year and not imperative and len(words) >= 4 and len(sentence) <= 650:
                claims.append(Claim(text=sentence, page=page_no))
                if len(claims) >= MAX_CLAIMS:
                    return claims, len(reader.pages)
    return claims, len(reader.pages)


def search_query_for(claim: str) -> str:
    """Retain the topic and entities while removing the claim's numeric answer."""
    no_numbers = NUMBER_RE.sub(" ", claim)
    tokens = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", no_numbers) if w.lower() not in STOP_WORDS]
    # Short topical queries work better than asking a search engine to validate a sentence.
    return " ".join(tokens[:14]) or claim[:180]


def web_search(query: str, max_results: int = SEARCH_RESULTS) -> list[Evidence]:
    results: list[Evidence] = []
    with DDGS(timeout=12) as ddgs:
        for item in ddgs.text(query, max_results=max_results, backend="auto"):
            url = str(item.get("href") or item.get("url") or "")
            if not url.startswith(("http://", "https://")):
                continue
            results.append(Evidence(
                title=str(item.get("title") or urlparse(url).netloc)[:240],
                url=url,
                snippet=str(item.get("body") or item.get("snippet") or "")[:1200],
                domain=urlparse(url).netloc.removeprefix("www."),
            ))
    return results


def keywords(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text) if w.lower() not in STOP_WORDS}


def heuristic_verdict(claim: str, evidence: list[Evidence]) -> tuple[str, str, str, str]:
    """Conservative fallback when no language-model key is configured."""
    if not evidence:
        return ("False", "No corroborating source was found in this search.",
                "The live search returned no usable evidence. Treat this as unverified, not proof that the claim is false.", "Low")
    terms = keywords(claim)
    if not terms:
        return ("False", "No meaningful search terms were available.",
                "The app could not identify enough subject terms to judge this sentence.", "Low")
    # Score each result separately. Aggregating unrelated snippets can make a
    # claim look supported when no single source actually discusses it.
    ranked = sorted(
        ((len(terms & keywords(item.title + " " + item.snippet)) / len(terms), item) for item in evidence),
        key=lambda pair: pair[0], reverse=True,
    )
    relevant = [(score, item) for score, item in ranked if score >= 0.50]
    if not relevant:
        return ("False", "No sufficiently relevant evidence was found.",
                "Search returned pages, but none matched enough of the claim's subject terms. This means no evidence was found in this search, not that the claim is false.", "Low")
    claim_numbers = {re.sub(r"\s", "", x.lower()) for x in NUMBER_RE.findall(claim)}
    relevant_text = " ".join(item.title + " " + item.snippet for _, item in relevant)
    evidence_numbers = {re.sub(r"\s", "", x.lower()) for x in NUMBER_RE.findall(relevant_text)}
    number_match = bool(claim_numbers & evidence_numbers)
    _, best = relevant[0]
    if claim_numbers and number_match:
        return ("Verified", "The retrieved source text contains the claim's key terms and figure.",
                "A relevant search snippet contains the same figure. Check the linked page for matching units, dates, and population before treating this as confirmed.", "Low")
    if claim_numbers and evidence_numbers:
        snippet = re.sub(r"\s+", " ", best.snippet).strip()
        # Surface a short, attributed evidence lead rather than inventing a correction.
        candidate = f"Candidate fact to review ({best.domain}): {snippet[:150]}" if snippet else ""
        if not candidate:
            candidate = f"The search results surface different figures: {', '.join(sorted(evidence_numbers)[:5])}."
        return ("Inaccurate", candidate,
                "A relevant result contains figures, but the snippets do not show the same value. Treat this as a lead only; inspect the source for matching units, date, and population before correcting the PDF.", "Low")
    return ("False", "No matching figure was found in relevant search results.",
            "Some results discuss this topic, but the available snippets do not support the stated figure. This means no evidence for the figure was found in this search, not proof that it is false.", "Low")


def llm_verdict(claim: str, evidence: list[Evidence], api_key: str) -> tuple[str, str, str, str] | None:
    if not api_key:
        return None
    evidence_blob = [{"id": i + 1, "title": e.title, "url": e.url, "snippet": e.snippet} for i, e in enumerate(evidence)]
    prompt = (
        "Fact-check one claim using only the supplied live web search results. Do not use prior knowledge. "
        "Compare exact values, dates, units, geography, population, and timeframe. A result is Verified only when "
        "relevant evidence supports the claim. Use Inaccurate when relevant evidence contradicts it or gives a "
        "different current value; state the best supported correction and cite result IDs in the explanation. "
        "Use False only when the search returns no evidence that supports the claim, and say that this is absence "
        "of evidence rather than proof of falsity. If unclear, choose Inaccurate with Low confidence. "
        "Return JSON only with verdict (Verified/Inaccurate/False), corrected_fact, explanation, confidence (High/Medium/Low).\n\n"
        f"CLAIM: {claim}\n\nSEARCH RESULTS: {json.dumps(evidence_blob, ensure_ascii=False)}"
    )
    try:
        response = requests.post(
            OPENAI_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), "temperature": 0,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=35,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        verdict = parsed.get("verdict")
        if verdict not in {"Verified", "Inaccurate", "False"}:
            return None
        return verdict, str(parsed.get("corrected_fact", ""))[:600], str(parsed.get("explanation", ""))[:900], str(parsed.get("confidence", "Low"))
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def verify_claim(claim: Claim, api_key: str) -> Finding:
    results = web_search(search_query_for(claim.text))
    # Search with the figures included when a broad topic search fails to find
    # the actual values. This helps distinguish a source that mentions the
    # subject from one that supports the specific statistic.
    expected_figures = {
        re.sub(r"\s", "", value.lower())
        for value in NUMBER_RE.findall(claim.text)
        if "%" in value or any(symbol in value for symbol in ("$", "₹", "€", "£"))
    }
    if not expected_figures:
        expected_figures = {
            re.sub(r"\s", "", value.lower())
            for value in NUMBER_RE.findall(claim.text)
            if re.search(r"\d\.\d", value)
        }
    found_figures = {
        re.sub(r"\s", "", value.lower())
        for item in results
        for value in NUMBER_RE.findall(item.title + " " + item.snippet)
    }
    if expected_figures and not expected_figures.issubset(found_figures):
        results.extend(web_search(claim.text[:260], max_results=5))
    elif not results:
        results.extend(web_search(claim.text[:260], max_results=5))
    unique: dict[str, Evidence] = {item.url: item for item in results}
    evidence = list(unique.values())[:SEARCH_RESULTS]
    ai_result = llm_verdict(claim.text, evidence, api_key)
    verdict, corrected, explanation, confidence = ai_result or heuristic_verdict(claim.text, evidence)
    if ai_result is None and api_key:
        explanation += " The AI check was unavailable, so the app used its conservative fallback."
    return Finding(claim.text, claim.page, verdict, corrected, explanation, confidence, evidence)


def render_finding(finding: Finding, index: int) -> None:
    colors = {"Verified": "#16856d", "Inaccurate": "#b97414", "False": "#c34d59"}
    status = finding.verdict.upper()
    st.markdown(
        f'<div class="finding"><div class="finding-top"><span class="status" style="background:{colors.get(finding.verdict, "#586579")}">{status}</span>'
        f'<span class="page">PAGE {finding.page:02d} · CLAIM {index:02d}</span></div>'
        f'<div class="claim">{html.escape(finding.claim)}</div></div>', unsafe_allow_html=True)
    if finding.corrected_fact:
        st.markdown(f"**Best supported fact:** {finding.corrected_fact}")
    st.write(finding.explanation)
    st.caption(f"Confidence: {finding.confidence} · Search results are evidence leads; inspect source context before publication.")
    if finding.evidence:
        with st.expander(f"Sources ({len(finding.evidence)})", expanded=True):
            for source in finding.evidence:
                st.markdown(f"[{source.title}]({source.url}) · `{source.domain}`")
                if source.snippet:
                    st.caption(source.snippet)


def to_markdown(findings: list[Finding], filename: str) -> str:
    lines = [f"# Truth Layer report: {filename}", "", "Generated from a live web search. Labels are research leads; review source context before publishing.", ""]
    for i, f in enumerate(findings, 1):
        lines += [f"## {i}. {f.verdict} (page {f.page})", "", f"> {f.claim}", "", f"**Best supported fact:** {f.corrected_fact or 'No confirmed correction found.'}", "", f"{f.explanation}  ", f"Confidence: {f.confidence}", "", "Sources:"]
        lines += [f"- [{e.title}]({e.url}) — {e.snippet}" for e in f.evidence] or ["- No sources returned."]
        lines.append("")
    return "\n".join(lines)


st.set_page_config(page_title="Truth Layer · Fact-check PDFs", page_icon="◉", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
.stApp { background: #f6f7f4; color: #172327; }
section[data-testid="stSidebar"] { background: #102d2d; }
section[data-testid="stSidebar"] * { color: #eef3eb !important; }
.hero { padding: 2.1rem 0 1.4rem; border-bottom: 1px solid #d9ded5; margin-bottom: 1.2rem; }
.eyebrow { font: 500 11px 'DM Mono', monospace; letter-spacing: .16em; color: #527a6e; text-transform: uppercase; }
.hero h1 { font: 800 clamp(34px,5vw,56px) 'Manrope',sans-serif; letter-spacing: -.055em; margin: .28rem 0 .35rem; color: #102d2d; }
.hero p { font-size: 15px; color: #56645f; max-width: 760px; margin: 0; }
.finding { padding: 1.15rem 1.25rem; margin: 1.1rem 0 .7rem; border-left: 3px solid #bad0c1; background: #fff; }
.finding-top { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.status { padding:5px 8px; color:#fff; font:500 10px 'DM Mono',monospace; letter-spacing:.1em; }
.page { color:#7b8983; font:11px 'DM Mono',monospace; letter-spacing:.08em; }
.claim { font-size:18px; line-height:1.5; color:#172327; }
div[data-testid="stFileUploader"] { border: 1px dashed #92a79b; background: #fff; }
.footnote { font-size:12px; color:#69766f; }
</style>
<div class="hero"><div class="eyebrow">Evidence review · PDF to fact-check</div><h1>Truth Layer</h1><p>Find the numbers that need a second look. Extract claims from a PDF, check them against live web sources, and review the evidence behind each verdict.</p></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Review settings")
    st.markdown("**Search:** Live web results\n\n**Output:** Claim-by-claim evidence report")
    st.markdown("---")
    saved_key = os.getenv("OPENAI_API_KEY", "")
    try:
        saved_key = st.secrets.get("OPENAI_API_KEY", saved_key)
    except Exception:
        pass
    api_key = st.text_input("Optional OpenAI API key", value=saved_key, type="password", help="Each extracted claim and its search snippets are sent to OpenAI for comparison. The app does not store the key or PDF.")
    st.caption("Without a key, the app uses a conservative evidence-matching fallback. Search still runs live.")
    st.markdown("---")
    st.caption("Prototype · Review source dates, scope, and units before publication.")

uploaded = st.file_uploader("Choose a PDF", type=["pdf"], help="PDFs up to 12 MB and 40 pages.")
if uploaded:
    data = uploaded.getvalue()
    if len(data) > MAX_PDF_BYTES:
        st.error("This PDF is over the 12 MB limit. Please upload a smaller file.")
    else:
        st.info(f"**{uploaded.name}** · {len(data) / 1024:.0f} KB")
        if st.button("Extract claims and check sources", type="primary", use_container_width=True):
            try:
                claims, page_count = extract_claims(data)
                st.session_state.findings = []
                st.session_state.filename = uploaded.name
                st.session_state.pages = page_count
                if not claims:
                    st.warning("No numeric or date claims were detected. This prototype prioritizes sentences containing figures, dates, percentages, or monetary amounts.")
                else:
                    progress = st.progress(0, text="Preparing claim review…")
                    findings: list[Finding] = []
                    for i, claim in enumerate(claims):
                        try:
                            findings.append(verify_claim(claim, api_key))
                        except Exception as exc:
                            findings.append(Finding(claim.text, claim.page, "False", "No source results were returned.", f"Search failed for this claim: {type(exc).__name__}. This is not evidence that the claim itself is false.", "Low", []))
                        progress.progress((i + 1) / len(claims), text=f"Checking claim {i + 1} of {len(claims)}")
                    st.session_state.findings = [asdict(x) for x in findings]
                    progress.empty()
            except Exception as exc:
                st.error(f"The PDF could not be read: {exc}")

if st.session_state.get("findings"):
    findings = [Finding(**{**x, "evidence": [Evidence(**e) for e in x["evidence"]]}) for x in st.session_state.findings]
    verified = sum(x.verdict == "Verified" for x in findings)
    inaccurate = sum(x.verdict == "Inaccurate" for x in findings)
    false = sum(x.verdict == "False" for x in findings)
    st.markdown("### Review results")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Claims found", len(findings))
    c2.metric("Verified", verified)
    c3.metric("Inaccurate", inaccurate)
    c4.metric("No evidence found", false)
    st.caption("‘False’ means the live search found no supporting evidence. It does not prove a claim is false.")
    for i, finding in enumerate(findings, 1):
        render_finding(finding, i)
    report = to_markdown(findings, st.session_state.get("filename", "document.pdf"))
    st.download_button("Download review report", report, file_name="truth-layer-report.md", mime="text/markdown")
else:
    st.markdown("<p class='footnote'>The app extracts sentences with numbers, dates, percentages, or amounts. Each claim gets its own search and source links.</p>", unsafe_allow_html=True)
