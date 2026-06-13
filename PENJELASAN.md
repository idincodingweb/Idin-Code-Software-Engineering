# PENJELASAN — Cara Pakai Apex Market Intelligence

Built by **Idin Iskandar**.

Software ini punya **3 pipeline terpisah**:

| Pipeline | Runner | Output | Tujuan |
|----------|--------|--------|--------|
| **Leads** | `run.py` | `output/leads_*.csv` + `output/pdf/*.pdf` | Cari & score klinik/bisnis target (data yang lo JUAL) |
| **Buyers** | `find_buyer.py` | `output/buyers/buyers_*.csv` | Cari agency decision maker (orang yang BELI data lo) |
| **Emails** | `generate_emails.py` | `output/emails/**/*.md` + `emails_index.csv` | Generate cold email personalized (AI) dari hasil 2 pipeline di atas |

---

## 1. Setup (sekali aja)

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env:
#   PAGESPEED_API_KEY=...   (gratis dari Google PageSpeed Insights)
#   IDINCODE_API=...        (kie.ai key — buat AI Analyst & Email Generator)
```

Tanpa `IDINCODE_API`, AI layer auto-fallback ke template (tetap jalan, cuma hasilnya generic).

---

## 2. Pipeline LEADS — `run.py`

Scrape klinik/bisnis dari `targets.yaml`, score, dan export ke tiered CSV.

```bash
python run.py                    # default: targets.yaml, extras+pdf ON, dedup ON
python run.py --no-extras        # skip email/revenue/ads
python run.py --no-pdf           # skip PDF audit
python run.py --ads              # enable Meta Ads detection (slow)
python run.py --competitors      # enable competitor discovery (slow)
python run.py --no-dedup         # nonaktifkan SQLite dedup
python run.py --include-seen     # ikutkan domain yang udah pernah ke-process
python run.py --reset-dedup      # wipe dedup DB sebelum jalan
```

**Output**:
- `output/leads_starter.csv` — top 25 (score ≥ 0.50)
- `output/leads_pro.csv` — top 100 (score ≥ 0.70)
- `output/leads_premium_gold.csv` — top 50 (score ≥ 0.85)
- `output/pdf/*.pdf` — audit per lead premium gold
- `output/dedup.db` — SQLite dedup store (auto-managed)

**PERUBAHAN BARU v3.1**:
- Kolom `emails_found` di CSV tetap **FILTER role-based** otomatis.
- **SQLite dedup**: tiap run, domain yang udah ke-process di-skip otomatis supaya
  lo cuma dapet **fresh leads only**. Bypass dengan `--include-seen` /
  `--reset-dedup`.

---

## 3. Pipeline BUYERS — `find_buyer.py`

Cari decision maker (CEO/Founder/Owner/Partner/Managing Director) di agency
yang berpotensi BELI data leads lo.

```bash
python find_buyer.py                         # default: buyers.yaml, dedup ON
python find_buyer.py --config buyers.yaml    # custom config
python find_buyer.py --no-ai                 # skip Claude, pakai template
python find_buyer.py --no-dedup              # nonaktifkan dedup
python find_buyer.py --include-seen          # ikutkan buyer yg pernah muncul
python find_buyer.py --reset-dedup           # wipe dedup DB
```

**Output**: `output/buyers/buyers_<timestamp>.csv` + `buyers_latest.csv`

**Kolom CSV**:
| Kolom | Isi |
|-------|-----|
| `agency_domain` | Domain agency (e.g. `wonderistagency.com`) |
| `agency_name` | Nama brand (dari `<title>`) |
| `niche_keyword` | Niche query yang nemu agency ini |
| `country` | Country target |
| `person_name` | Nama decision maker |
| `person_title` | Jabatan (CEO/Founder/Partner/dll) |
| `email` | Email personal (HARUS muncul di page; no guessing) |
| `email_confidence` | Selalu `1.00` (cuma terima email scraped) |
| `email_source` | Selalu `scraped` |
| `mx_valid` | `yes`/`no` — domain bisa terima email? |
| `outreach_angle` | Cold-email hook (AI-generated) |
| `why_buy` | Kenapa agency ini cocok beli data lo (AI-generated) |

### Konfigurasi `buyers.yaml`

```yaml
defaults:
  country: US                          # US / UK / AU / CA / GLOBAL
  max_agencies_per_niche: 30           # rate-limit safe untuk DDG
  max_persons_per_agency: 5            # cap per agency
  max_concurrent: 4                    # parallel HTTP

niches:
  - keyword: "dental marketing agency"
    country: US
  - keyword: "healthcare marketing agency"
    country: US
  # tambah niche lain di sini ↓
```

### ⚠️ v3.1 — GUESSED / INFERRED EMAIL DIHAPUS

Versi sebelumnya nebak email pakai pattern inference (`first.last@`, `flast@`,
dll) dengan confidence 0.85. **Sekarang dihapus.** Software cuma terima email
yang LITERAL muncul di page agency. Konsekuensi:

- ✅ Email yang lo kirim 100% valid format & ada di page → bounce rate rendah.
- ❌ Jumlah person per agency turun (agency yang gak tampilin email langsung di-skip).
- ℹ️ Kalau person ke-detect tapi gak ada email scraped → person di-DROP (bukan ditebak).

---

## 4. Pipeline EMAILS — `generate_emails.py` (BARU)

Generate cold email personalized (subject + body + CTA) pakai AI macro yang
sama dengan analyst. Auto-baca CSV terbaru dari leads & buyers.

```bash
python generate_emails.py                       # auto: leads + buyers
python generate_emails.py --source leads        # leads only
python generate_emails.py --source buyers       # buyers only
python generate_emails.py --limit 20            # cap jumlah email
python generate_emails.py --leads-csv x.csv     # override input
python generate_emails.py --buyers-csv x.csv
python generate_emails.py --out output/emails   # output dir
```

**Output**:
- `output/emails/leads/<domain>.md` — 1 file per lead
- `output/emails/buyers/<domain>__<email>.md` — 1 file per buyer person
- `output/emails/emails_index.csv` — daftar semua subject untuk quick scan

**Format file `.md`**:
```markdown
---
source: buyers
agency_domain: wonderistagency.com
person: Michael Anderson
title: CEO
email: michael@wonderistagency.com
subject: Pre-qualified dental leads for Wonderist
---

**Subject:** Pre-qualified dental leads for Wonderist

Hi Michael,

Saw you run Wonderist in the dental marketing space...

_Want a free 10-lead sample?_
```

Tanpa `IDINCODE_API` → tetap jalan pakai template fallback (warning di console).

---

## 5. AI Layer (kie.ai)

Dipakai di **TIGA** pipeline:

- `run.py` → generate `gold_reasons` + `outreach_angle` per klinik
- `find_buyer.py` → generate `outreach_angle` + `why_buy` per agency
- `generate_emails.py` → generate full cold email (subject + body + CTA)

Set `IDINCODE_API` di `.env`. Tanpa key, auto fallback ke template.

---

## 6. Workflow rekomendasi

```bash
# Step 1 — generate leads (data yang lo jual). Fresh leads only by default.
python run.py

# Step 2 — cari buyer (siapa yang beli data ini). Fresh buyers only by default.
python find_buyer.py

# Step 3 — generate cold email untuk semua hasil pipeline 1 & 2
python generate_emails.py

# Step 4 — outreach
# Buka file .md di output/emails/buyers/ → copy-paste subject + body ke email client lo.
# Pitch dengan sample row dari output/leads_premium_gold.csv
```

---

## 7. Dedup DB (SQLite)

File: `output/dedup.db`. Auto-dibuat saat pertama run. Isi:

| Tabel | Isi |
|-------|-----|
| `leads_seen` | `(domain, first_seen, last_seen, runs)` — target leads yg udah pernah ke-process |
| `buyers_seen` | `(domain, email, first_seen, last_seen, runs)` — buyer person yg udah pernah di-deliver |

Kapan reset:
- Lo ganti pitch/niche & mau ulangin dari awal → `--reset-dedup`
- Lo cuma mau re-export TANPA hapus history → `--include-seen`
- Lo gak peduli history → `--no-dedup`

---

## 8. Troubleshooting

| Gejala | Fix |
|--------|-----|
| `DDG HTTP 202` | Rate-limited. Tunggu 5-10 menit atau kurangi `max_agencies_per_niche` |
| `0 agency dengan decision maker valid` | Agency target gak nampilin email decision maker di page. Ganti niche keyword yg lebih mature/established |
| `Semua agency hasilnya udah pernah ke-deliver` | Dedup aktif — pakai `--include-seen` atau `--reset-dedup` |
| AI fallback terus | Cek `IDINCODE_API` di `.env`, atau kie.ai credit habis |
| `No leads/buyers CSV found` (saat `generate_emails.py`) | Jalanin `run.py` / `find_buyer.py` dulu |

---

## 9. Pipeline ke-4 — `find_agency_buyers.py` (v3.2)

Pipeline ini fokus cari **owner agency kecil / freelancer** yang
berpotensi BELI data leads lo. Beda sama `find_buyer.py`:

| Aspek                  | `find_buyer.py` (v3.1)        | `find_agency_buyers.py` (v3.2)            |
|------------------------|-------------------------------|-------------------------------------------|
| Target                 | Decision maker agency mid     | Owner agency kecil (2-20) + freelancer    |
| Kolom output           | email, name, title            | website, **email, phone, ceo_name**       |
| Sumber                 | DDG website only              | DDG website **+ Reddit JSON API**         |
| CEO extraction         | All people via heuristic      | **Hybrid**: heuristic → AI fallback        |
| Config                 | `buyers.yaml`                 | `agency_buyers.yaml`                      |
| Dedup table            | `buyers_seen`                 | `buyers_seen` (shared, domain-level)      |

### Aturan email & phone
- **Email**: scraped LITERAL only (sama dengan v3.1, no guessing).
- **Phone**: `tel:` href dulu (most reliable), fallback regex teks.
  Auto-reject phone dengan ≤2 unique digit (e.g. `111-111-1111`).
- **Drop rule**: kalau agency gak punya email **dan** gak punya phone **dan**
  gak punya CEO → row di-skip.

### Reddit hunter logic
1. Untuk tiap `(subreddit, query)` di `agency_buyers.yaml`, hit
   `/r/{sub}/search.json?q={q}&restrict_sr=1&sort=relevance&t=year`.
2. Untuk tiap post, gabungin `title + selftext` → cocokin ke 25+ phrase
   indicator (`"agency owner"`, `"freelance seo"`, `"i run a small agency"`,
   `"freelance google ads"`, dst).
3. Ekstrak `email` & `website` (skip URL ke linkedin/twitter/fb/youtube/dst).
4. Output 1 row per post yang match.

Delay 1 detik antar query → aman dari rate-limit (~5-10 queries OK).

### AI fallback (CEO extraction)
Cuma kepicu kalau heuristic GAGAL nemu decision maker di `extract_people`.
Prompt Claude (kie.ai) diberi text condensed dari home + about + team page,
return JSON `{"name": "...", "title": "..."}`. Validation:
- name harus 2-5 kata
- kalau JSON invalid / API kosong / gagal → return None (agency lewat path
  no-CEO; tetap dipakai kalau ada email/phone).

### File output
```
output/agency_buyers/agency_buyers_<ts>.csv     # web pipeline
output/agency_buyers/agency_buyers_latest.csv
output/agency_buyers/reddit_buyers_<ts>.csv     # reddit pipeline
output/agency_buyers/reddit_buyers_latest.csv
```

### Kolom CSV web
```
rank, source, website, agency_name, niche_keyword, country,
ceo_name, ceo_title, ceo_source (heuristic|ai),
email, phone, mx_valid, extra_emails, extra_phones, notes
```

### Kolom CSV reddit
```
rank, subreddit, author, post_title, permalink, post_url,
website, email, matched_indicators, score, snippet
```

### Why no LinkedIn / Facebook Groups?
By design — butuh login/paid API, dan kena ToS. Workflow yang
direkomendasikan: export `author` + `website` dari reddit_buyers CSV →
manual lookup di LinkedIn Sales Navigator atau cari profile lo sendiri.

---

# 🆕 v3.3 — Sample Pack & Agency Pitch

## Apa yang baru
Versi ini nambah **2 pipeline pendukung** buat strategi outreach ke agency
luar negeri (US/UK/AU/EU). Sisanya backward-compatible — pipeline lama
(leads, buyers, emails, agency-buyers) ga berubah.

### 1) Sample Pack Generator — `make_sample_pack.py`
Ngubah top-N leads dari `output/leads_*.csv` jadi 2 file siap kirim:

- `output/sample_pack/<niche>_sample_<ts>.csv` — kolom rapi (rank, domain,
  niche, score, primary_issue, owner_email, mx_status, dll).
- `output/sample_pack/<niche>_sample_<ts>.pdf` — cover + per-lead one-pager
  buat ditempel di cold email.

```bash
# default: pakai leads_premium_gold.csv, top 10
python make_sample_pack.py

# 5 sample plastic surgery
python make_sample_pack.py --top 5 --niche plastic_surgery

# input manual
python make_sample_pack.py --input output/leads_pro.csv --top 8 --min-score 0.7
```

Kalau `reportlab` ga ke-install, CSV tetep jadi, PDF di-skip (warning,
ga crash).

### 2) Agency Pitch Mode — `generate_emails.py --source agency-pitch`
Mode email baru: pitch **sample pack** ke owner agency luar negeri.
Bahasa Inggris bersih, tone "minta feedback" bukan hard sell. Subject
otomatis nyebut niche. Body referensiin attachment (CSV + PDF).

```bash
# 1. siapin sample pack
python make_sample_pack.py --top 10 --niche medspa

# 2. cari agency target
python find_agency_buyers.py

# 3. generate pitch email (auto-link ke sample pack terbaru)
python generate_emails.py --source agency-pitch
```

Output:
- `output/emails/agency_pitch/<domain>__<email>.md` (per-recipient)
- frontmatter `attach_csv:` & `attach_pdf:` nge-point ke sample pack
- entry di `output/emails/emails_index.csv` dengan `source=agency_pitch`

Tanpa `IDINCODE_API` tetep jalan pakai template fallback (bahasa Inggris).

### 3) Preset niche tambahan di `agency_buyers.yaml`
Section baru di bagian bawah (semua di-comment, tinggal hapus `##`):
medspa, plastic surgery, cosmetic clinic, aesthetic agency — US/UK/AU.
Backward compatible: niche lama tetap aktif.

## Aturan penting (re-affirmed v3.3)
- Email LITERAL only (no guessing) — sample pack cuma include
  `owner_email` kalau hasil scrape dari HTML + MX-validated.
- Pattern inference email cuma dipakai kalau `confidence >= 0.75` (di
  `src/extras.py`, ga diubah).
- AI macro (kie.ai) + fallback template TETAP jalan. Pipeline agency-pitch
  juga punya fallback EN siap-pakai.
- YAML backward-compatible: nambah field/niche, ga ngerubah yg lama.

---

## 6. v3.4 — Quality Score 0-100, BI Enrichment, CRM Webhooks

### Lead Quality Score 0-100
Kolom CSV baru `quality_score`. `gold_score` (0-1) tetep dipake buat tiering.
Quality score = blend opportunity + contactability + buying signal + revenue
band. Dihitung deterministic dulu (selalu ada), terus DI-REFINE AI kalau
`IDINCODE_API` keisi. AI mati = tetep pake angka deterministic.

### Business Intelligence Enrichment
Kolom baru: `bi_score` (0-100), `employee_range`, `location_count`,
`founded_year`, `social_profiles`, `tech_signals`, `bi_summary`. Semua
di-extract dari HTML publik (gratis). Matikan dengan `python run.py --no-bi`.

### CRM Webhooks
Push leads ke CRM via incoming webhook. Setup:

```bash
# 1. Isi salah satu di .env:
#    CRM_HUBSPOT_WEBHOOK_URL / CRM_PIPEDRIVE_WEBHOOK_URL /
#    CRM_SALESFORCE_WEBHOOK_URL / CRM_AIRTABLE_WEBHOOK_URL /
#    CRM_ZOHO_WEBHOOK_URL / CRM_GENERIC_WEBHOOK_URL (boleh comma-separated)
# 2. Jalanin:
python run.py --crm                      # leads gold_score >= 0.70
python run.py --crm --crm-min-score 0.85 # premium gold only
python run.py --crm --crm-dry-run        # cek payload dulu (gak ngirim)
```

Catatan jujur: ini ngirim ke *incoming webhook* (native automation / Zapier /
Make / Airtable Web API), bukan SDK — biar tool tetep standalone & legal (cuma
HTTP POST). Airtable pakai format `{"records":[{"fields":{...}}]}`, provider lain
flat JSON. CRM OFF by default; error per-provider gak bikin pipeline mati.

**Status roadmap:** Phase 1 → Lead Quality Score AI ✅ · BI Enrichment ✅ ·
CRM Webhooks ✅. Tests: 69/69 ✅.
