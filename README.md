# 🎯 Idincode Researche — Apex Lead Research Engine

<p align="center">
  <img src="https://img.shields.io/badge/version-3.6-blue?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/license-Personal-lightgrey?style=flat-square" alt="license">
  <img src="https://img.shields.io/badge/platform-GitHub%20Actions-black?style=flat-square&logo=github&logoColor=white" alt="platform">
</p>

> **Self-hosted, zero-server B2B lead intelligence pipeline** yang jalan di GitHub Actions runner gratis.
>
> Project ini dipakai untuk mengumpulkan, memperkaya, menilai, dan mengemas data prospect menjadi output yang siap dijual, dipitch, atau dipakai outreach.

---

## 👤 Authors

<table>
  <tr>
    <td align="center">
      <b>Idin Iskandar</b>
    </td>
    <td align="center">
      <b>Nurull Huda Rosalia</b>
    </td>
  </tr>
</table>

📧 [idiniskandar.tech@gmail.com](mailto:idiniskandar.tech@gmail.com)

---

## 📖 Tentang Project Ini

**Idincode Researche** adalah mesin riset lead dan market intelligence untuk kebutuhan B2B outreach.

Tema utama project ini:

- 🔍 Mencari target market dari domain-domain tertentu
- 📡 Mengecek sinyal marketing dan technology stack mereka
- 🎯 Menilai apakah mereka layak jadi prospect
- 📦 Menghasilkan output yang bisa dipakai untuk:
  - Dijual sebagai lead pack
  - Dipakai agency outreach
- Dijadikan sample audit
  - Dijadikan dasar cold email yang lebih personal

Secara sederhana, project ini adalah **pipeline riset prospect niche-agnostic**.

Artinya:

- Hari ini lu bisa scrape `fashion brands`
- Besok bisa `dental clinics`
- Lusa bisa `SaaS`, `law firms`, `real estate`, atau niche lain

Target niche tidak lagi dikunci di kode Python. Selama field `niche` di `targets.yaml` sesuai, sistem akan membaca konfigurasi niche dari file YAML dan menyesuaikan:

- Prompt analyst AI
- Deterministic fallback reasons
- Outreach hook
- Scoring quality
- Scoring qualifier weight

Jadi arah project ini bukan sekadar scraper, tapi **mesin intelligence untuk prospecting dan outreach**.

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

Hasilnya adalah sistem yang bisa:

- Scrape target
- Enrich sinyal digital mereka
- Score opportunity
- Generate CSV
- Generate PDF audit
- Generate email outreach
- Push hasil ke CRM / Google Sheets jika dibutuhkan

Semua dari repo yang sama.

---

## 🎯 Tujuan Project

Project ini dibuat untuk 4 tujuan utama:

1. **📊 Riset market** — Cari dan petakan domain-domain target dalam niche tertentu.
2. **✅ Lead qualification** — Menilai mana prospect yang punya opportunity paling besar untuk dipitch.
3. **📧 Outreach preparation** — Menghasilkan alasan pitch, angle outreach, dan output audit yang siap dikirim.
4. **💰 Monetisasi data** — Data hasil scrape bisa dipakai sendiri atau dijual ke agency / partner / buyer.

---

## 🔮 Visi

> Membangun mesin market-intelligence yang fleksibel, murah dijalankan, dan bisa dipakai ulang lintas niche hanya dengan mengganti target dan config.

## 🚀 Misi

1. Menjalankan automation research tanpa infrastruktur mahal.
2. Menghasilkan lead pack yang punya konteks, bukan sekadar list domain.
3. Membuat sistem yang benar-benar niche-agnostic.
4. Menyatukan scraping, enrichment, scoring, analyst reasoning, export, dan outreach dalam satu repo.
5. Menjadikan GitHub Actions sebagai execution layer utama untuk riset terjadwal.

---

## 🏗️ Konsep Besar Arsitektur

Project ini dibagi menjadi beberapa lapisan kerja:

| Layer | Deskripsi |
|-------|-----------|
| **1. Input Layer** | File YAML seperti `targets.yaml`, `buyers.yaml`, dan `agency_buyers.yaml` |
| **2. Research Layer** | Ambil HTML, cek reachability, deteksi pixel, platform, dan PageSpeed |
| **3. Enrichment Layer** | Tambahan data seperti email, MX, revenue proxy, ads signal, business intelligence, dan competitor signal |
| **4. Qualification Layer** | Hitung `gold_score` dan `quality_score` |
| **5. Analyst Layer** | AI atau fallback deterministic menghasilkan: `gold_reasons`, `outreach_angle`, `bi_summary` |
| **6. Export Layer** | Hasil keluar sebagai CSV tiered, PDF audit, email drafts, CRM payload, atau Sheets |

---

## 🎛️ Niche-Agnostic by Design

Arsitektur sekarang sudah berubah jadi **config-driven**.

Artinya, logic yang dulu hardcoded per niche sekarang dipindah ke file YAML per niche.

Contoh:

```
src/config/niches/
  default.yaml
  medical_high_ticket.yaml
  fashion_apparel.yaml
```

Setiap file niche bisa mengatur:

- Industry label
- Typical ticket
- Pain point
- Focus prompt
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

Ini inti perubahan paling penting di versi ini.

---

## ⚙️ Arsitektur Eksekusi

```
                 +----------------------------------------------+
                 |         GitHub Actions Runner (FREE)         |
                 |                                              |
 targets.yaml ---| run.py                  -> leads CSV + PDF   |
 buyers.yaml  ---| find_buyer.py           -> buyers CSV        |
 agency_buyers -| find_agency_buyers.py   -> agency CSV        |
                 | generate_emails.py      -> email drafts      |
                 +-------------------+--------------------------+
                                     |
                                     v
                           output/ + artifacts + commits
```

---

## 🔀 Flow Pipeline Leads

Pipeline utama `run.py` menjalankan urutan berikut:

1. Load targets
2. Dedup filter
3. Enrich domain (dengan data quality tracking)
4. Enrich extras
5. Qualify lead
6. AI analyst / fallback analyst
7. Sort + tier
8. Export CSV (dengan confidence columns)
9. Generate PDF
10. Optional push ke CRM
11. Optional push ke Google Sheets

Secara operasional ini adalah lead factory dengan transparency.

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

### Firmographics Confidence

| Level | Criteria |
|-------|----------|
| **High** | Employee count explicit di-extract, atau verified via multiple signals |
| **Medium** | Estimated dari heuristic (location count, careers page, dll) |
| **Low** | Default estimate tanpa supporting signals |

- **Source:** Free enrichment (HTML public data)

### Data Quality Flags

Setiap lead carry flags seperti:

- `pixel_detection_regex_only`
- `possible_js_loaded_pixels`
- `high_false_negative_risk_for_pixels`
- `firmographics_estimated`
- `fashion_headcount_may_be_underestimated`

### CSV Export

Output CSV sekarang include:

- `data_confidence` (HIGH | MEDIUM | LOW)
- `pixel_confidence`
- `firmographics_confidence`
- `pixel_detection_method`
- `firmographics_source`
- `detection_notes`
- `data_quality_flags`

Jadi client tahu exactly apa yang verified vs estimated.

---

## 🎯 Scoring Aware dengan Confidence

### Quality Score

- **Base:** 55 points
- Adjust berdasarkan: gold_score, signals, rules, confidence penalties
- Kalau `pixel_confidence` LOW → minus 4 points (jangan assume missing tracking = opportunity)
- Kalau `firmographics_confidence` LOW → minus 4 points (jangan judge size by undersized estimates)

### Analyst Reasoning

- AI sekarang aware dengan confidence levels
- Jangan overclaim "Missing tracking" kalau pixel detection confidence rendah
- Jangan claim "Enterprise" kalau employee data hanya estimate
- Fallback template juga respect confidence

---

## 🔄 GitHub Actions — 4 Pipeline Terpisah

Setiap pipeline tampil sebagai entry sendiri di tab Actions GitHub.

| Workflow File | Nama di Actions | Script | Fungsi |
|--------------|-----------------|--------|--------|
| `research.yml` | Apex Lead Research \| By Idincode | `run.py` | Scrape + score + export leads |
| `buyers.yml` | Apex Buyer Hunter \| By Idincode | `find_buyer.py` | Cari buyer agency mid/large |
| `agency-buyers.yml` | Apex Agency Buyer Hunter \| By Idincode | `find_agency_buyers.py` | Cari buyer agency kecil/freelancer |
| `emails.yml` | Apex Email Generator \| By Idincode | `generate_emails.py` | Generate cold email drafts |

Semua workflow bisa:

- Jalan manual
- Jalan terjadwal
- Upload artifact
- Commit hasil ke repo
- Degrade gracefully kalau API kosong

---

## 📁 Struktur Projek

```
.
├── .github/workflows/
│   ├── research.yml
│   ├── buyers.yml
│   ├── agency-buyers.yml
│   └── emails.yml
├── run.py
├── find_buyer.py
├── find_agency_buyers.py
├── generate_emails.py
├── make_sample_pack.py
├── targets.yaml
├── buyers.yaml
├── agency_buyers.yaml
├── requirements.txt
└── src/
    ├── analyst.py
    ├── bi_enrich.py
    ├── config/__init__.py
    ├── crm_webhooks.py
    ├── dedup_db.py
    ├── email_generator.py
    ├── email_verifier.py
    ├── enrichers.py
    ├── export.py
    ├── extras.py
    ├── loader.py
    ├── models.py
    ├── niche_loader.py
    ├── pdf_audit.py
    ├── pipeline.py
    ├── qualifier.py
    ├── quality_score.py
    ├── sheets_push.py
    ├── niches/
    │   ├── default.yaml
    │   ├── medical_high_ticket.yaml
    │   └── fashion_apparel.yaml
    └── ...
```

---

## 🔑 Peran File Penting

| File | Peran |
|------|-------|
| `targets.yaml` | Sumber target utama untuk pipeline leads. Support metadata: brand, tier, notes. |
| `src/loader.py` | Membaca dan memvalidasi target dari YAML. |
| `src/enrichers.py` | Mengambil HTML, mengecek pixel, platform, PageSpeed, dan track detection confidence. |
| `src/bi_enrich.py` | Business Intelligence enrichment (zero-budget, HTML-only). Extract: employee range, location count, founded year, social profiles, tech signals. Track `firmographics_confidence`. |
| `src/qualifier.py` | Mengubah hasil enrichment menjadi QualifiedLead dengan `gold_score`. |
| `src/quality_score.py` | Menghitung `quality_score` 0-100, now aware dengan confidence levels. |
| `src/analyst.py` | Menghasilkan reasoning dan outreach angle via AI atau fallback rules. Now receives confidence flags. |
| `src/export.py` | Mengeluarkan CSV tiered dengan semua confidence columns. |
| `src/pdf_audit.py` | Membuat PDF audit untuk lead pilihan. |
| `src/niche_loader.py` | Memuat config YAML per niche. |
| `src/niches/*.yaml` | Otak konfigurasi niche-specific tanpa ubah kode Python. |

---

## 🏷️ Metadata Target yang Didukung

Sekarang target bisa membawa metadata tambahan, bukan cuma domain.

Contoh field:

- `domain`
- `location`
- `niche`
- `category`
- `brand`
- `tier`
- `notes`

Metadata ini mengalir sampai ke enrichment, qualification, analyst prompt, dan export CSV.

Jadi lu bisa masukin context bisnis langsung di `targets.yaml`, bukan sekadar URL.

---

## 📤 Output yang Dihasilkan

Project ini bisa menghasilkan beberapa jenis output:

### CSV Lead Packs

- `leads_all.csv`
- `leads_starter.csv`
- `leads_pro.csv`
- `leads_premium_gold.csv`

### PDF Audit

Untuk lead yang lolos threshold tertentu.

### Email Drafts

Dari pipeline email generator.

### CRM Push

Optional, via webhook.

### Google Sheets Push

Optional.

---

## 🏆 Scoring System

Ada dua lapisan scoring:

### `gold_score`

- Skala **0.0 - 1.0**
- Lebih fokus ke opportunity dari gap teknis / marketing
- Dipakai untuk sorting dan tier export

### `quality_score`

- Skala **0 - 100**
- Lebih fokus ke kualitas prospect secara keseluruhan
- Gabungan dari: gold score, contactability, buying signals, social / BI / revenue proxies, rules per niche, confidence penalties

Keduanya sekarang bisa dipengaruhi config niche.

---

## 🧠 Analyst Layer

`src/analyst.py` bekerja dalam dua mode:

### AI Mode

Kalau `IDINCODE_API` tersedia, sistem panggil `kie.ai` untuk menghasilkan:

- `gold_reasons`
- `outreach_angle`
- `quality_score` override optional
- `bi_summary`

**Data quality aware:** jangan overclaim kalau confidence rendah.

### Fallback Mode

Kalau AI gagal atau API kosong, sistem pakai deterministic rules dari YAML config niche.

Ini penting karena pipeline tetap selesai walaupun AI mati.

---

## 🎛️ Config-Driven Niche System

Contoh niche config:

- `default.yaml`
- `medical_high_ticket.yaml`
- `fashion_apparel.yaml`

Yang bisa dikustom:

- Industry label
- Typical ticket
- Pain point
- Focus prompt
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

## ⚠️ Known Limitations & Data Quality

### Pixel Detection

| Aspek | Detail |
|-------|--------|
| **Method** | Regex-based HTML parsing (JavaScript NOT executed) |
| **False Negative Rate** | ~30-40% untuk async-loaded pixels |
| **Implication** | Brand besar yang load pixel via Tag Manager mungkin terdeteksi "tidak punya" pixel |
| **Mitigation** | Confidence tracking + AI/fallback awareness |

### Firmographics

| Aspek | Detail |
|-------|--------|
| **Source** | Free enrichment (HTML public data) |
| **Accuracy** | Best-effort estimation |
| **Limitation** | Employee size + revenue often undersized untuk SMB/Enterprise |
| **Mitigation** | Confidence levels + fallback disclaimers |

### Recommendation

Sebelum blast outreach atau claim "audit definitive", lakukan spot-check manual 5-10 leads tier 1.

---

## 🚀 Quick Start

```bash
python -m pip install -r requirements.txt
python run.py
python find_buyer.py
python find_agency_buyers.py
python generate_emails.py
```

---

## 🔐 Environment Variables

### Minimal

- `PAGESPEED_API_KEY`
- `IDINCODE_API`

### Optional

- `MYEMAILVERIFIER_API_KEY`
- `ZEROBOUNCE_API_KEY`
- `HUNTER_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`
- `GSHEET_SPREADSHEET_ID`

Tanpa API optional, pipeline tetap jalan dengan graceful fallback.

---

## 📦 Requirements

Dependency utama:

- `httpx`
- `pyyaml`
- `python-dotenv`
- `dnspython`
- `reportlab`
- `gspread`
- `google-auth`

Install:

```bash
python -m pip install -r requirements.txt
```

---

## 💼 Tema Komersial Project Ini

Kalau dijelaskan secara bisnis, tema project ini adalah:

> **B2B market intelligence + lead packaging + outreach preparation.**

Bukan sekadar crawler.

Value project ini ada pada:

- Pemilihan target
- Enrichment signal
- Scoring
- Reasoning
- Audit packaging
- Readiness untuk dipitch
- Transparency soal data quality limitations

Jadi output akhirnya adalah prospect intelligence yang honest dan siap dipakai.

---

## 📍 Positioning Bisnis

❌ Jangan claim: "Audit akurat 100%, coba pakai."

✅ Claim lebih baik: "Research-grade prospect list dengan transparency soal data quality. HIGH_CONFIDENCE results = pixel verified + firmographics cross-checked. LOW_CONFIDENCE results = estimated, use for prospecting angles only."

**Pricing model:**

- HIGH_CONFIDENCE tier → full price
- LOW_CONFIDENCE tier → diskon + disclaimer

---

## 👥 Cocok Untuk Siapa

Project ini cocok untuk:

- Lead generation operator
- Agency owner
- Freelancer outreach
- Market researcher
- Solo founder yang mau jualan service
- Orang yang mau monetisasi hasil scrape dengan konteks yang lebih tajam

---

## 🛡️ Prinsip Desain

| Prinsip | Deskripsi |
|---------|-----------|
| **Self-hosted** | Jalan di infra sendiri, tidak bergantung SaaS |
| **Low-cost** | GitHub Actions runner gratis sebagai execution layer |
| **Graceful degradation** | Tetap jalan walaupun API mati |
| **N/Agnostic** | Ganti niche tanpa ubah kode |
| **Config-driven** | Semua behavior niche di YAML |
| **Async-first** | Non-blocking pipeline |
| **Export-friendly** | CSV, PDF, email, CRM, Sheets |
| **Operational di GitHub Actions** | Terjadwal tanpa VPS |
| **Transparent** | Honest soal data quality limitations |

---

## 🗺️ Roadmap Singkat

| Versi | Fitur |
|-------|-------|
| v3.1 | No email guessing |
| v3.2 | Quality score + BI enrichment |
| v3.3 | Agency pitch mode + sample pack bundler |
| v3.4 | Email verification + sheets push + CRM webhooks |
| v3.5 | Global soft-feedback email strategy |
| v3.6 | Config-driven niche engine, metadata-aware targets, YAML-based analyst/scoring behavior, data quality tracking & confidence levels |
| v3.7 *(planned)* | Playwright/Selenium integration untuk JavaScript pixel detection (paid tier) |

---

## 📄 Lisensi & Kontak

Personal project, no public license.

📧 **Kontak:** [idiniskandar.tech@gmail.com](mailto:idiniskandar.tech@gmail.com)

---

## 🙏 Penutup

Alhamdulillah, setelah rangkaian update ini, struktur project jadi jauh lebih rapi, fleksibel, honest soal keterbatasan data, dan siap dipakai lintas niche tanpa harus bongkar kode inti setiap kali ganti target market.

Marilah kita panjatkan puji dan syukur atas kehadirat Allah Subhanahu wa Ta'ala yang telah menciptakan bumi dan seisinya, menciptakan manusia dengan akal dan kemampuan berpikir, sehingga lahir ilmu, teknologi, sains, dan berbagai kemudahan yang bisa dipakai untuk membangun sesuatu yang bermanfaat.

Semoga project ini jadi alat yang berguna, menghasilkan manfaat, membuka jalan rezeki yang baik, dan dipercaya karena transparency dan integrity dalam setiap data yang dihasilkan.

**Alhamdulillah wa syukur.**

---

<p align="center">
  <i>Built without modal. Built with akal, kerja, dan izin Allah.</i> 🙏
</p>
