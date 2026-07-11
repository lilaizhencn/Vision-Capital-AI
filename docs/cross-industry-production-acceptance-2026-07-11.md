# Cross-Industry Production Acceptance - 2026-07-11

## Verdict

- Document ingestion, bounded parallel parsing, WebSocket final progress, public-source filtering, tenant isolation, and conservative AI fallback passed the exercised acceptance scope.
- AI strategy delivery is now evidence-gated and consistently produces a professionally reviewable preliminary work plan. When the model draft fails, a deterministic claim-ledger plan replaces it instead of returning unsupported prose or a generic refusal.
- No generated strategy should be treated as an investment recommendation. A passed answer is a preliminary diligence work plan and still requires human investment-committee review.

## Authoritative Materials

| Case | Company material | Industry/regulatory material | Size | SHA-256 prefix |
| --- | --- | --- | ---: | --- |
| Financial services | [JPMorgan Chase 2025 Annual Report](https://www.sec.gov/Archives/edgar/data/19617/000162828026023927/annualreport-2025.pdf) | [Federal Reserve Financial Stability Report, November 2025](https://www.federalreserve.gov/publications/files/financial-stability-report-20251107.pdf) | 18,022,059 + 5,119,017 bytes | `f4c1a0475525`, `31f74bcbd3ed` |
| Industrial manufacturing | [Caterpillar 2025 Annual Report](https://www.sec.gov/Archives/edgar/data/18230/000130817926000360/cat015318-ars.pdf) | [NIST Annual Report on the U.S. Manufacturing Economy: 2025](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=961007) | 8,481,626 + 4,465,507 bytes | `0940547e5dd1`, `f32e7f0f2f29` |
| Consumer retail | [Walmart FY2026 Annual Report](https://www.sec.gov/Archives/edgar/data/104169/000010416926000091/wmtfy26annualreport-final.pdf) | [BEA Real-Time Consumer Spending Working Paper](https://www.bea.gov/sites/default/files/papers/BEA-WP2025-4.pdf) | 14,805,939 + 2,648,645 bytes | `550eaf563e00`, `1b60f9332b6f` |

All six downloads passed `%PDF` signature validation before upload.

## Parsing And Progress

- Round 1 exposed an unbounded PDF table-extraction path. Four large filings running together caused API instability; the worker was stopped, table extraction was changed to evenly sample at most 40 pages and cap tables/characters, and interrupted tasks were recovered.
- A periodic stale-parse recovery task now requeues stages orphaned by worker or machine interruption.
- Clean round 2 used three new projects and all six source PDFs, approximately 53.5 MB total. Submission and queueing took 0.57 seconds.
- Clean round 2 completed 6/6 files with zero failures in 141.6 seconds. API polling recorded zero connection errors.
- Database stage intervals proved at least two parse stages overlapped. The worker remains configured for four threads; realized concurrency depends on file size and stage duration.
- WebSocket acceptance returned `completed`, progress `100`, two files, and all-file completion for all three clean-round batches.

## Public Research Quality

- Trusted domains now include the Federal Reserve, NIST, Census, BEA, BLS, and FTC in addition to the existing regulator and international-institution list.
- Industry-specific search routes banking to Federal Reserve material, manufacturing to NIST, and retail/consumer research to Census or BEA.
- SEC valuation/structured-note filings are no longer auto-ingested as company valuation evidence.
- SEC company evidence must be a current 10-K, 10-Q, annual report, proxy statement, or earnings release. Stale and unrelated filings are rejected.
- Parsed company identity is compared with the tenant project company. Mismatched automatically researched files are excluded from RAG.
- The exercised projects removed eight previously ingested low-quality or stale auto-research files and their vector chunks. Failed source records remain as an audit trail.
- Evidence entries are labelled `company_disclosure`, `industry_context`, or `uploaded_evidence`. Industry context cannot support a company fact.

## Evidence Coverage And User Upload Gaps

The workspace records these field-level gaps instead of repeatedly asking for an annual report that is already present:

- Financial case: 5 covered, 3 partial, 0 missing. Obtain company-specific market-share mapping, current comparable-company/market valuation, investment mandate and proposed terms, and product-level economics not available in public filings.
- Industrial case: 4 covered, 4 partial, 0 missing. Obtain product-level competitor and market-share evidence, customer/dealer concentration, management-verified segment outlook, current valuation basis, mandate, and proposed terms.
- Consumer case: 5 covered, 3 partial, 0 missing. Obtain category/geography market-share mapping, customer/cohort and membership retention detail, current valuation basis, mandate, and proposed terms.
- Common private-data gaps: budget-versus-actual model, management interview records, customer references, signed material contracts, detailed pipeline/backlog quality, transaction authorization, position mandate, and final legal/tax terms.

## AI Strategy Acceptance

- Strategy retrieval now balances business, financial statements, cash flow, customers, competition, governance, regulation, market context, and risk rather than using SaaS-specific terms.
- A single source cannot consume the evidence pack. Per-query and per-file limits preserve cross-dimension and cross-source coverage.
- Required output fields are: company-disclosed facts, analyst inference, verification action, IC gate, and cannot-assess items for pre-, during-, and post-investment stages, plus an evidence-gap section.
- Unsupported Arabic numeric lines and invented consecutive-period exit triggers are removed server-side.
- A second claim-level evidence critic checks role boundaries, causal overreach, unsupported events, and invented thresholds before release.
- Successful exercised rounds included: financial 5,001 characters across eight files; industrial 8,168 characters across two files; consumer 1,636 characters across three files. These were not consistently reproduced.
- Every strategy response now includes an exact claim ledger. `C#` claims are company disclosures, `I#` claims are industry scenario context, and `U#` claims are uploaded evidence requiring caveats.
- PDF cover text, tables of contents, publication disclaimers, cross-references, incomplete sentences, and dense table fragments are excluded from the claim ledger.
- Financial statement rows are extracted separately. Multi-period currency rows are admitted only when their unit is explicit or an adjacent table header establishes `USD millions`; otherwise the row is discarded.
- Model reference variants are normalized, and references are attached automatically only when numeric values or high-confidence lexical overlap match a specific ledger claim.
- If the model draft or independent critic fails, the server renders a five-section plan directly from verified claims. The UI identifies this recovery instead of presenting it as an unqualified model answer.

## Stabilization Update - 2026-07-12

- Strategy retrieval now scores financial-statement chunks above cover pages and expands one company filing to at most 12 balanced chunks; public industry context remains capped at eight chunks.
- Clean-project final round: financial, industrial, and consumer all passed the final evidence gate. Durations were 26.2, 34.6, and 30.3 seconds. The first two used deterministic recovery; consumer passed the model/critic path.
- A subsequent consumer unit-guard run passed in 24.4 seconds with 12 company claims, 10 referenced claim IDs, and zero multi-period currency claims lacking a unit.
- Machine audit found all five required sections, no unknown claim IDs, no prohibited causal phrases, no repeated request for an annual filing already present, and no unitless currency-table claims in the final delivered plans.
- Browser acceptance on port 8090 verified login, a live strategy request, evidence-gate status, claim-ledger rendering, source context, and a 390px viewport with no horizontal overflow.
- Full verification after the final guard: 55 backend tests passed and the Vite production build completed successfully.

## Tenant Isolation

- A second live tenant received `404` for another tenant's project, project files, individual file, batch, research workspace, and chat endpoint.
- All checked object keys used `tenants/{owner_id}/{project_id}/...` and matched the owning tenant/project.
- Automated tests also cover cross-tenant projects, files, batches, chat, research, tasks, monitoring, and storage-key boundaries.

## Residual Operating Constraints

- Native model drafts still fail strict evidence gates in some runs. The deterministic recovery path makes final delivery stable, but native-pass rate and 24-35 second strategy latency remain optimization targets.
- The system is production-safe as a research and diligence decision-support tool, not an autonomous investment adviser. Every plan remains conditional on primary-source reconciliation and human investment-committee approval.
- Ant Design emits non-blocking deprecation warnings for legacy `List` and button icon-placement APIs; these do not affect the accepted workflows but should be removed before the next major Ant Design upgrade.
