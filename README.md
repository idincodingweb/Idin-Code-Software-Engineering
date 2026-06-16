# 🎯 Idincode Researche — Apex Lead Research Engine

<p align="center">
  <img src="https://img.shields.io/badge/version-3.7-blue?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/license-Personal-lightgrey?style=flat-square" alt="license">
  <img src="https://img.shields.io/badge/platform-GitHub%20Actions-black?style=flat-square&logo=github&logoColor=white" alt="platform">
  <img src="https://img.shields.io/badge/export-Google%20Sheets-green?style=flat-square&logo=googlesheets&logoColor=white" alt="sheets">
</p>

> **Self-hosted, zero-server B2B lead intelligence pipeline** yang jalan di GitHub Actions runner gratis.
>
> Project ini dipakai untuk mengumpulkan, memperkaya, menilai, dan mengemas data prospect menjadi output yang siap dijual, dipitch, atau dipakai outreach — sekarang dengan **Google Sheets sebagai primary export yang rapi dan shareable**.

---

## 👤 Authors

<table>
  <tr>
    <td align="center">
      <b>Idin Iskandar</b><br/>
      <i>Software Engineer & Data Analyst</i>
    </td>
    <td align="center">
      <b>Nurull Huda Rosalia</b><br/>
      <i>Co-founder & Strategic Partner</i>
    </td>
  </tr>
</table>

📧 [idiniskandar.tech@gmail.com](mailto:idiniskandar.tech@gmail.com)

---

## 📖 Tentang Project Ini

**Idincode Researche** adalah mesin riset lead dan market intelligence untuk kebutuhan B2B outreach dan prospecting.

Tema utama project ini:

- 🔍 Mencari target market dari domain-domain tertentu
- 📡 Mengecek sinyal marketing dan technology stack mereka
- 🎯 Menilai apakah mereka layak jadi prospect
- 📦 Menghasilkan output yang bisa dipakai untuk:
  - Dijual sebagai lead pack
  - Dipakai agency outreach
  - Dijadikan sample audit
  - Dijadikan dasar cold email yang lebih personal
  - **Divisualisasikan dalam Google Sheets yang rapi dan professional**

Secara sederhana, project ini adalah **pipeline riset prospect niche-agnostic dengan output visualization yang siap presentasi**.

Artinya:

- Hari ini lu bisa scrape `fashion brands`
- Besok bisa `dental clinics`
- Lusa bisa `SaaS`, `law firms`, `real estate`, atau niche lain

Target niche tidak lagi dikunci di kode Python. Selama field `niche` di `targets.yaml` sesuai, sistem akan membaca konfigurasi niche dari file YAML dan menyesuaikan:

- Prompt analyst AI (Bahasa Indonesia)
- Deterministic fallback reasons
- Outreach hook
- Scoring quality
- Scoring qualifier weight

Jadi arah project ini bukan sekadar scraper, tapi **mesin intelligence untuk prospecting dan outreach dengan output yang professional**.

---

## 📜 History — Kenapa Project Ini Dibangun

Project ini lahir dari kebutuhan praktis: bikin automation yang berguna tanpa modal infrastruktur.

Banyak tutorial automation dan lead-gen bergantung pada:

- VPS
- Workflow SaaS
- API enrichment berbayar
- Orchestration tools tambahan

Masalahnya: itu semua butuh biaya.

Project ini dibangun untuk membuktikan bahwa:

- Pipeline riset lead yang serius bisa dibuat sendiri
- Bisa jalan di GitHub Actions runner gratis
- Bisa dipakai untuk monetisasi data dan outreach
- Tidak harus bergantung pada stack mahal dari awal
- **Output bisa rapi dan professional tanpa design team**

Hasilnya adalah sistem yang bisa:

- Scrape target
- Enrich sinyal digital mereka (tier-aware, marketplace-aware)
- Score opportunity dengan confidence tracking
- Generate Google Sheets (primary, rapi, shareable)
- Generate CSV (fallback)
- Generate PDF audit
- Generate email outreach (Bahasa Indonesia)
- Push hasil ke CRM / Google Sheets jika dibutuhkan

Semua dari repo yang sama, tanpa biaya infrastruktur.

---

## 🎯 Tujuan Project

Project ini dibuat untuk 4 tujuan utama:

1. **📊 Riset market** — Cari dan petakan domain-domain target dalam niche tertentu.
2. **✅ Lead qualification** — Menilai mana prospect yang punya opportunity paling besar untuk dipitch.
3. **📧 Outreach preparation** — Menghasilkan alasan pitch, angle outreach, dan output audit yang siap dikirim.
4. **💰 Monetisasi data** — Data hasil scrape bisa dipakai sendiri atau dijual ke agency / partner / buyer dengan confidence transparency.

---

## 🔮 Visi

> Membangun mesin market-intelligence yang fleksibel, murah dijalankan, dan bisa dipakai ulang lintas niche hanya dengan mengganti target dan config — dengan output yang siap presentasi dan shareable.

## 🚀 Misi

1. Menjalankan automation research tanpa infrastruktur mahal.
2. Menghasilkan lead pack yang punya konteks, bukan sekadar list domain.
3. Membuat sistem yang benar-benar niche-agnostic.
4. Menyatukan scraping, enrichment, scoring, analyst reasoning, export, dan outreach dalam satu repo.
5. Menjadikan GitHub Actions sebagai execution layer utama untuk riset terjadwal.
6. **Output DEFAULT dalam Google Sheets yang rapi, professional, dan ready untuk share.**

---

## 🏗️ Konsep Besar Arsitektur

Project ini dibagi menjadi beberapa lapisan kerja:

| Layer | Deskripsi |
|-------|-----------|
| **1. Input Layer** | File YAML seperti `targets.yaml`, `buyers.yaml`, `agency_buyers.yaml` dengan metadata tier-aware |
| **2. Research Layer** | Ambil HTML, cek reachability, deteksi pixel, platform, PageSpeed, dengan confidence tracking |
| **3. Enrichment Layer (BI)** | Tier-aware enrichment: employee range, locations, founded year, social, tech signals, marketplace detection |
| **4. Enrichment Layer (Extras)** | Email, MX, revenue proxy, ads signal, business intelligence, competitor signal |
| **5. Qualification Layer** | Hitung `gold_score` dan `quality_score` dengan confidence penalties |
| **6. Analyst Layer** | AI (Bahasa Indonesia) atau fallback deterministic → `gold_reasons`, `outreach_angle`, `bi_summary` |
| **7. Export Layer (PRIMARY)** | **Google Sheets** (rapi, shareable, formatted) + fallback CSV |
| **8. Audit Layer** | PDF audit untuk lead premium |

---

## 🎛️ Niche-Agnostic by Design

Arsitektur sekarang sudah **config-driven**.

Logic yang dulu hardcoded per niche sekarang dipindah ke file YAML per niche.

Contoh:
src/config/niches/ default.yaml medical_high_ticket.yaml fashion_apparel.yaml skincare_beauty.yaml


Setiap file niche bisa mengatur:

- Industry label
- Typical ticket
- Pain point
- Focus prompt (Bahasa Indonesia)
- Mature business note
- Fallback reasoning rules
- Outreach rules
- Quality score rules
- Qualifier weights
- Response penalty

Dengan model ini:

- `targets.yaml` ganti, niche ganti → pipeline tetap jalan
- Niche baru tinggal tambah file YAML
- Kalau perlu akurasi lebih tinggi, tinggal tambah file YAML niche baru

---

## ⚙️ Arsitektur Eksekusi


             +----------------------------------------------+
             |         GitHub Actions Runner (FREE)         |
             |                                              | targets.yaml ---| run.py -> Google Sheets | buyers.yaml ---| find_buyer.py -> + CSV fallback | agency_buyers -| find_agency_buyers.py -> + PDF audit | | generate_emails.py -> + email drafts | +-------------------+--------------------------+ | v Google Sheets (PRIMARY) CSV + PDF + Artifacts


---

## 🔀 Flow Pipeline Leads

Pipeline utama `run.py` menjalankan urutan berikut:

1. **Load targets** — dari `targets.yaml` dengan metadata
2. **Dedup filter** — hindari duplicate processing
3. **Enrich domain** — HTML fetch, pixel detection, platform, PageSpeed, confidence tracking
4. **Enrich BI** — tier-aware: employee range, locations, tech signals, marketplace detection
5. **Enrich extras** — email, revenue, ads signal, competitors
6. **Qualify lead** — hitung gold_score dengan confidence awareness
7. **Score quality** — hitung quality_score 0-100, aware dengan confidence penalties
8. **AI analyst** — generate gold_reasons, outreach_angle, bi_summary (Bahasa Indonesia)
9. **Sort + tier** — ranking by score, split ke tiers
10. **Export Google Sheets** — primary output, rapi dengan formatting + auto-width + filter
11. **Export CSV** — fallback untuk backward compatibility
12. **Generate PDF** — audit untuk top leads
13. **Optional push** — CRM webhook atau Google Sheets push

Secara operasional ini adalah **lead factory dengan transparency dan professional output**.

---

## 📊 Data Quality & Confidence Tracking

Sekarang pipeline track confidence level untuk setiap data point:

### Pixel Detection Confidence

| Level | Criteria |
|-------|----------|
| **High** | 3+ pixels detected, low false-negative risk |
| **Medium** | 1-2 pixels detected, atau JS-heavy site dengan partial visibility |
| **Low** | 0 pixels detected (bisa false negative, jangan overclaim) |

- **Method:** HTML regex saja (JavaScript NOT executed)
- **Disclaimer:** "Tracking visibility is low-confidence because static HTML scanning may miss JavaScript-loaded tags"

### Firmographics Confidence

| Level | Criteria |
|-------|----------|
| **High** | Employee count explicit di-extract, atau verified via multiple signals |
| **Medium** | Estimated dari heuristic + tier metadata override |
| **Low** | Default estimate tanpa supporting signals |

- **Source:** Free enrichment (HTML public data)
- **Tier Override:** Tier 1 brands diestimasi minimal 201-500 staff (research-verified)

### Marketplace Detection

Sekarang sistem detect presence di:

- Shopee, TikTok Shop, Tokopedia, Lazada, Blibli, Zalora
- Populate `marketplaces` field → boost firmographics confidence

### Data Quality Flags

Setiap lead carry flags seperti:

- `pixel_detection_regex_only`
- `possible_js_loaded_pixels`
- `high_false_negative_risk_for_pixels`
- `firmographics_estimated`
- `tier1_size_override_applied`
- `marketplace_presence_*`

### CSV/Sheets Export

Output sekarang include:

- `data_confidence` (HIGH | MEDIUM | LOW)
- `pixel_confidence`
- `firmographics_confidence`
- `pixel_detection_method`
- `firmographics_source`
- `detection_notes` (Bahasa Indonesia)
- `data_quality_flags`
- `marketplaces` (NEW)

Jadi client tahu exactly apa yang verified vs estimated.

---

## 🎯 Scoring Aware dengan Confidence

### Quality Score

- **Base:** 55 points
- Adjust berdasarkan: gold_score, signals, rules, confidence penalties, tier bonus
- Kalau `pixel_confidence` LOW → minus 4 points (jangan assume missing tracking = opportunity)
- Kalau `firmographics_confidence` LOW → minus 4 points (jangan judge size by undersized estimates)
- Kalau `tier` == 1 → bonus +10 points (market leader)

### Analyst Reasoning (Bahasa Indonesia)

- AI sekarang aware dengan confidence levels
- Jangan overclaim "Missing tracking" kalau pixel detection confidence rendah
- Jangan claim "Enterprise" kalau employee data hanya estimate
- Fallback template juga respect confidence
- **Output SEMUA dalam Bahasa Indonesia** ✅

---

## 🔄 GitHub Actions — 4 Pipeline Terpisah

Setiap pipeline tampil sebagai entry sendiri di tab Actions GitHub.

| Workflow File | Nama di Actions | Script | Fungsi |
|--------------|-----------------|--------|--------|
| `research.yml` | Apex Lead Research \| By Idincode | `run.py` | Scrape + enrich + score + export ke Sheets |
| `buyers.yml` | Apex Buyer Hunter \| By Idincode | `find_buyer.py` | Cari buyer agency mid/large |
| `agency-buyers.yml` | Apex Agency Buyer Hunter \| By Idincode | `find_agency_buyers.py` | Cari buyer agency kecil/freelancer |
| `emails.yml` | Apex Email Generator \| By Idincode | `generate_emails.py` | Generate cold email drafts (Bahasa Indonesia) |

Semua workflow bisa:

- Jalan manual (trigger di GitHub UI)
- Jalan terjadwal (cron schedule)
- Upload artifact (CSV, PDF)
- Commit hasil ke repo
- Degrade gracefully kalau API kosong
- **Export ke Google Sheets (jika enable)**

---

## 📁 Struktur Project

. ├── .github/workflows/ │ ├── research.yml │ ├── buyers.yml │ ├── agency-buyers.yml │ └── emails.yml ├── run.py ├── find_buyer.py ├── find_agency_buyers.py ├── generate_emails.py ├── make_sample_pack.py ├── targets.yaml ├── buyers.yaml ├── agency_buyers.yaml ├── requirements.txt └── src/ ├── analyst.py # AI analyst (Bahasa Indonesia) ├── bi_enrich.py # BI enrichment (tier-aware, marketplace-aware) ├── config/init.py ├── crm_webhooks.py ├── dedup_db.py ├── email_generator.py # Email draft generator ├── email_verifier.py ├── enrichers.py # HTML enrichment + pixel detection ├── export.py # CSV export ├── export_sheets.py # Google Sheets export (NEW) ├── extras.py ├── loader.py ├── models.py ├── niche_loader.py # Load niche config ├── pdf_audit.py ├── pipeline.py # Main orchestrator (updated) ├── qualifier.py ├── quality_score.py ├── sheets_push.py ├── config/niches/ │ ├── default.yaml │ ├── medical_high_ticket.yaml │ ├──fashion_apparel.yaml │ └── skincare_beauty.yaml └── ...


---

## 🔑 Peran File Penting

| File | Peran |
|------|-------|
| `targets.yaml` | Sumber target utama untuk pipeline leads. Support metadata: brand, tier, location, niche, category, notes. |
| `src/loader.py` | Membaca dan memvalidasi target dari YAML. |
| `src/enrichers.py` | Fetch HTML, deteksi pixel, platform, PageSpeed, track detection confidence. |
| `src/bi_enrich.py` | BI enrichment (zero-budget, HTML-only) **tier-aware**: employee range, location count, founded year, social, tech signals, marketplaces. Track `firmographics_confidence`. |
| `src/qualifier.py` | Mengubah hasil enrichment menjadi QualifiedLead dengan `gold_score`. |
| `src/quality_score.py` | Menghitung `quality_score` 0-100, aware dengan confidence levels + tier bonus. |
| `src/analyst.py` | Menghasilkan reasoning dan outreach angle **via AI (Bahasa Indonesia)** atau fallback rules. Aware dengan confidence flags. |
| `src/export.py` | CSV export tiered dengan confidence columns. |
| `src/export_sheets.py` | **Google Sheets export (PRIMARY)** — rapi, formatted, shareable. |
| `src/pdf_audit.py` | Membuat PDF audit untuk lead pilihan. |
| `src/niche_loader.py` | Memuat config YAML per niche. |
| `src/config/niches/*.yaml` | Otak konfigurasi niche-specific tanpa ubah kode Python. |
| `src/pipeline.py` | **Main orchestrator — updated untuk Sheets-first export.** |

---

## 🏷️ Metadata Target yang Didukung

Sekarang target bisa membawa metadata tambahan, bukan cuma domain.

Contoh field:

```yaml
targets:
  - domain: example.com
    brand: Example Brand
    niche: fashion_apparel
    category: streetwear
    tier: 1
    location: Indonesia (Jakarta)
    notes: "Top 5 nasional, budget iklan gede"
```
Metadata ini mengalir sampai ke enrichment, qualification, analyst prompt, dan export Sheets.

Jadi lu bisa masukin context bisnis langsung di targets.yaml, bukan sekadar URL.

📤 Output yang Dihasilkan
Project ini sekarang menghasilkan output utama Google Sheets + fallback/komplemen:

Google Sheets (PRIMARY) ✅
leads_all — semua leads, untuk reference
leads_starter — score ≥ 0.30, untuk prospecting
leads_pro — score ≥ 0.50, untuk outreach
leads_premium_gold — score ≥ 0.70, untuk close
Format: Auto-width columns, bold header, frozen row 1, filter enabled, professional look
Shareable: Link langsung untuk team, investor, atau client

CSV (FALLBACK)
Jika Google Sheets API gagal
Untuk integrasi tool lain
Same structure sebagai Sheets
PDF Audit
Untuk lead yang lolos threshold tertentu
Detail analysis + rekomendasi
Ready untuk kirim ke client
Email Drafts
Cold email templates (Bahasa Indonesia)
Personalized per lead tier
Dari pipeline email generator
CRM Push
Optional, via webhook
🏆 Scoring System
Ada dua lapisan scoring:


gold_score
Skala 0.0 - 1.0
Lebih fokus ke opportunity dari gap teknis / marketing
Dipakai untuk sorting dan tier export
Updated: aware dengan tier metadata
quality_score
Skala 0 - 100
Lebih fokus ke kualitas prospect secara keseluruhan
Gabungan dari: gold score, contactability, buying signals, social / BI / revenue proxies, rules per niche, confidence penalties, tier bonus
Keduanya sekarang bisa dipengaruhi config niche.

🧠 Analyst Layer (Bahasa Indonesia)
src/analyst.py bekerja dalam dua mode:

AI Mode (BAHASA INDONESIA) 🇮🇩
Kalau IDINCODE_API tersedia, sistem panggil kie.ai untuk menghasilkan dalam Bahasa Indonesia: 
gold_reasons — penjelasan kenapa lead ini opportunity
outreach_angle — hook subject line untuk email
quality_score override optional
bi_summary — ringkasan business intelligence
Data quality aware: jangan overclaim kalau confidence rendah.

Fallback Mode
Kalau AI gagal atau API kosong, sistem pakai deterministic rules dari YAML config niche juga dalam Bahasa Indonesia.

Ini penting karena pipeline tetap selesai dan output tetap rapi.

🎛️ Config-Driven Niche System
Contoh niche config:

default.yaml
medical_high_ticket.yaml
fashion_apparel.yaml
skincare_beauty.yaml

Yang bisa dikustom per niche:

Industry label (Bahasa Indonesia)
Typical ticket
Pain point
Focus prompt (Bahasa Indonesia)
Mature business note (Bahasa Indonesia)
Fallback reasoning rules (Bahasa Indonesia)
Outreach rules (Bahasa Indonesia)
Quality score rules
Qualifier weights
Response penalty
Dengan model ini:

targets.yaml ganti, niche ganti → pipeline tetap jalan
Niche baru tinggal tambah file YAML
Kalau perlu akurasi lebih tinggi, tinggal tambah file YAML niche baru
⚠️ Known Limitations & Data Quality
Pixel Detection

Aspek	Detail
Method	Regex-based HTML parsing (JavaScript NOT executed)
False Negative Rate	~25-30% untuk async-loaded pixels (improved dari tier-aware detection)
Implication	Brand besar yang load pixel via Tag Manager mungkin terdeteksi "tidak punya" pixel
Mitigation	Confidence tracking + AI awareness + tier-based estimation

Firmographics
Aspek	Detail
Source	Free enrichment (HTML public data) + marketplace signals
Accuracy	Best-effort estimation, improved dengan tier override
Limitation	Employee size + revenue often undersized untuk SMB/Enterprise
Mitigation	Confidence levels + tier-aware override + fallback disclaimers (Bahasa Indonesia)

Recommendation
Sebelum blast outreach atau claim "audit definitive", lakukan spot-check manual 5-10 leads tier 1.

🚀 Quick Start
Setup

# Install dependencies
python -m pip install -r requirements.txt

# Setup environment (minimal)
export PAGESPEED_API_KEY="your_key"
export IDINCODE_API="your_api_token"
export GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT='{"type":"service_account",...}'

Run Pipeline 

# Lead research (PRIMARY: Google Sheets export)
python run.py

# Find buyers
python find_buyer.py

# Find agency buyers
python find_agency_buyers.py

# Generate emails
python generate_emails.py


Custom Parameters

# Export to Sheets saja (no CSV fallback)
python run.py --enable-sheets-export --no-pdf

# Specify Sheets ID untuk update existing spreadsheet
python run.py --sheets-id "YOUR_SPREADSHEET_ID"

# Include extras (email verify, ads tracking, competitors)
python run.py --enable-ads --enable-competitors

# Enable CRM push
python run.py --enable-crm --crm-min-score 0.70

🔐 Environment Variables
Minimal (Sheets Export Works)
PAGESPEED_API_KEY — Google PageSpeed Insights (free tier 25k/day)
IDINCODE_API — kie.ai API untuk AI analyst (Bahasa Indonesia output)
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT — Google Service Account JSON untuk Sheets API (free)
Optional (Advanced Features)
MYEMAILVERIFIER_API_KEY — Email verification
ZEROBOUNCE_API_KEY — Email validation (backup)
HUNTER_API_KEY — Email finding
GSHEET_SPREADSHEET_ID — Default Sheets ID untuk push
CRM webhooks (HubSpot, Pipedrive, dll)
Tanpa API optional, pipeline tetap jalan dengan graceful fallback.

📦 Requirements
Dependency utama:

httpx — async HTTP client
pyyaml — YAML parsing
python-dotenv — env var management
dnspython — DNS/MX validation
reportlab — PDF generation
gspread — Google Sheets API client
google-auth — Google authentication
aiohttp — async HTTP (bonus)
Install:

python -m pip install -r requirements.txt


💼 Tema Komersial Project Ini
Kalau dijelaskan secara bisnis, tema project ini adalah:

B2B market intelligence + lead packaging + consultation delivery + data transparency.

Bukan sekadar crawler atau list penjual.

Value project ini ada pada:

Pemilihan target — niche-specific, tier-aware
Enrichment signal — comprehensive, zero-budget
Scoring — multi-dimensional, confidence-aware
Reasoning — AI-powered (Bahasa Indonesia), context-rich
Audit packaging — PDF professional, ready untuk kirim
Data transparency — honest soal quality limitations
Output visualization — Google Sheets yang rapi & shareable

Jadi output akhirnya adalah prospect intelligence yang honest, professional, dan siap dipakai untuk outreach atau konsultasi.

📍 Positioning Bisnis
❌ Jangan claim:

"Audit akurat 100%, coba pakai"
"Semua data verified definitive"
✅ Claim lebih baik:

"Research-grade prospect list dengan transparency soal data quality"
"HIGH_CONFIDENCE results = pixel verified + firmographics cross-checked"
"LOW_CONFIDENCE results = estimated, use for prospecting angles only"
"Output dalam Google Sheets rapi, siap share ke team atau investor"

Pricing Model
HIGH_CONFIDENCE tier → full price (Rp 5-15juta audit)
LOW_CONFIDENCE tier → diskon + disclaimer
Subscription → Rp 2-5juta/bulan untuk monthly insights update
👥 Cocok Untuk Siapa
Project ini cocok untuk:

Lead generation operator (agency, freelancer)
Agency owner (yang jualan research/audit)
Market researcher
Solo founder yang mau jualan service
Sales team (yang butuh prospect list per niche)
Orang yang mau monetisasi hasil scrape dengan konteks yang lebih tajam
Consultant yang ingin deliver research dengan professional output

🛡️ Prinsip Desain
Prinsip	Deskripsi
Self-hosted	Jalan di infra sendiri, tidak bergantung SaaS
Low-cost	GitHub Actions runner gratis sebagai execution layer
Graceful degradation	Tetap jalan walaupun API mati
Niche-agnostic	Ganti niche tanpa ubah kode Python
Config-driven	Semua behavior niche di YAML
Async-first	Non-blocking, concurrent enrichment
Export-flexible	Sheets (primary), CSV, PDF, email, CRM
Data-transparent	Honest soal quality limitations + confidence tracking Bahasa Indonesia	Output analyst semua dalam Bahasa Indonesia
Operational di GitHub Actions	Terjadwal tanpa VPS, no infrastructure cost

🗺️ Roadmap
Versi	Status	Fitur
v3.1	✅	No email guessing
v3.2	✅	Quality score + BI enrichment
v3.3	✅	Agency pitch mode + sample pack bundler
v3.4	✅	Email verification + sheets push + CRM webhooks
v3.5	✅	Global soft-feedback email strategy
v3.6	✅	Config-driven niche engine, metadata-aware targets, tier-aware BI, data quality tracking & confidence levels
v3.7	✅	Google Sheets as PRIMARY export, Bahasa Indonesia analyst output, direct-to-brand positioning
v3.8 (planned)	🔄	Playwright/SeleSelenium integration untuk JavaScript pixel detection (paid tier)
v3.9 (planned)	🔄	Multi-language analyst output (beyond Bahasa Indonesia)
v4.0 (planned)	🔄	Advanced attribution modeling + customer data platform consolidation

📄 Lisensi & Kontak
Personal project, no public license.

📧 Kontak: idiniskandar.tech@gmail.com

🎤 Real-World Validation
Scarlett Official (skincare_beauty, tier 1) — Actually responded positif ke data + positioning ini. Admin mereka confirmed akan help & offer konsultasi. Proof that model works! ✅

🙏 Penutup
Alhamdulillah, setelah evolusi dari v3.1 sampai v3.7, struktur project jadi:

✅ Rapi dan modular
✅ Fleksibel lintas niche
✅ Honest soal keterbatasan data (confidence tracking)
✅ Output professional (Google Sheets primary)
✅ Bahasa Indonesia (analyst output yang natural)
✅ Validated in market (Scarlett Official response)
✅ Siap untuk monetisasi dengan integrity
Marilah kita panjatkan puji dan syukur atas kehadirat Allah Subhanahu wa Ta'ala yang telah menciptakan bumi dan seisinya, menciptakan manusia dengan akal dan kemampuan berpikir, sehingga lahir ilmu, teknologi, sains, dan berbagai kemudahan yang bisa dipakai untuk membangun sesuatu yang bermanfaat.

Semoga project ini jadi alat yang berguna, menghasilkan manfaat, membuka jalan rezeki yang baik, dan dipercaya karena transparency dan integrity dalam setiap data yang dihasilkan.

Semoga pula output research ini membantu brand-brand Indonesia untuk optimize marketing strategy mereka dengan insight yang honest dan actionable.

Alhamdulillah wa syukur.

<p align="center"> <i>Built without modal.</i><br/> <i>Built with akal, kerja, dan izin Allah.</i><br/> <i>Built for honesty, transparency, dan trust.</i><br/> 🙏 </p> ```
