# Idincode Researche — Apex Lead Research Engine

> **Self-hosted, zero-modal B2B lead intelligence pipeline** — running on free GitHub Actions runners. Scrape, score, dan generate cold-email feedback ke market global, tanpa server, tanpa N8N, tanpa langganan SaaS.

Built & maintained by **Idin Iskandar** — [idiniskandar.tech@gmail.com](mailto:idiniskandar.tech@gmail.com)

---

## 📖 History — Kenapa Project Ini Dibangun

Project ini lahir karena **gw gabut nonton YouTube**.

Suatu hari gw liat banyak orang jualan tools automation pake **N8N**. Bisnisnya menarik: scrape data → score data → kirim ke buyer. Tapi semua tutorial yang gw tonton butuh **modal**: server VPS untuk N8N, langganan workflow tool, kadang juga langganan API enrichment yang mahal.

Sementara itu **gw ga punya modal**.

Jadi gw bangun versi gw sendiri di atas pondasi yang **100% gratis**: GitHub Actions runner. Hasilnya adalah pipeline ini — sebuah **mesin riset lead** yang jalan otomatis di GitHub schedule, output CSV + PDF + cold email AI-personalized, dan **ga butuh server sama sekali**.

Tujuan komersial-nya jelas: **menjual data hasil scrape ke agency** (digital marketing agency, lead-gen agency, dll) yang butuh prospect list pre-scored. Siapa yang di-scrape? **Bebas, optional, tergantung niche apa yang lagi laku**. Untuk sekarang fokus ke **klinik gigi (dental clinics)** karena terbukti niche dengan marketing-gap tinggi. Kalau besok pivot ke niche lain — misal med spa, hair restoration, dll — gw **cuma ubah `targets.yaml`, ga perlu coding ulang**.

---

## 🎯 Visi

**Membuktikan kalau data-intelligence pipeline kelas agency bisa dibangun, dijalankan, dan dimonetisasi tanpa modal infrastruktur — cukup dengan keberanian coding dan satu runner GitHub yang gratis.**

## 🚀 Misi

1. **Bangun automation tanpa modal.** Awalnya gw gabut nonton orang jualan N8N tools yang butuh modal server — gw mau prove pipeline-nya bisa jalan di GitHub Actions yang free.
2. **Monetisasi data scrape.** Jual data hasil scrape ke agency calon buyer dalam bentuk lead pack pre-scored (CSV + PDF + AI cold email).
3. **Niche-agnostic by design.** Target scrape bisa berubah kapan aja — sekarang klinik gigi, besok bisa apa aja yang penting datanya berguna buat agency. Ganti target = ubah `targets.yaml`, **tanpa coding ulang**.
4. **Go global, soft-feedback first.** Software masih baru dan belum punya nama, jadi semua cold email dikirim dalam bahasa Inggris dengan tone minta-feedback (bukan hard sell). Yang bersedia kasih feedback dapat **sample hasil software gratis**.

---

## 🏗️ Arsitektur

```
                 ┌─────────────────────────────────────────────┐
                 │           GitHub Actions Runner (FREE)      │
                 │                                             │
  targets.yaml ──┤  1) run.py                  → leads CSV+PDF │
  buyers.yaml  ──┤  2) find_buyer.py           → buyers CSV    │
  agency_buyers──┤  3) find_agency_buyers.py   → agency CSV    │
                 │  4) generate_emails.py      → emails/*.md   │
                 └────────────┬────────────────────────────────┘
                              │
                              ▼
              output/  (commit ke repo + artifact ZIP)
```

**Stack:** Python 3.11+ • `httpx` async • `dnspython` • `reportlab` (PDF) • `gspread` (opsional) • SQLite dedup • GitHub Actions • kie.ai (Claude Sonnet) untuk AI macro.

---

## ⚙️ GitHub Actions — 4 Pipeline Terpisah

Setiap pipeline tampil sebagai **entry sendiri** di tab **Actions** GitHub. Bisa di-trigger manual (`workflow_dispatch`) **atau** jalan otomatis sesuai schedule.

| Workflow file | Nama di sidebar Actions | Script | Schedule |
|---|---|---|---|
| `research.yml` | **Apex Lead Research \| By Idincode** | `run.py` | Senin 02:00 UTC |
| `buyers.yml` | **Apex Buyer Hunter \| By Idincode** | `find_buyer.py` | Selasa 02:00 UTC |
| `agency-buyers.yml` | **Apex Agency Buyer Hunter \| By Idincode** | `find_agency_buyers.py` | Rabu 02:00 UTC |
| `emails.yml` | **Apex Email Generator \| By Idincode** | `generate_emails.py` | Manual only |

Semua workflow:
- Commit hasil CSV/email ke repo otomatis kalau jalan via schedule.
- Upload artifact ZIP yang bisa di-download manual dari halaman run.
- Inject 2 secret: `PAGESPEED_API_KEY` + `IDINCODE_API` (kie.ai).
- **Graceful degradation** — kalau `IDINCODE_API` kosong, semua AI macro otomatis pakai **template fallback**, pipeline tetap selesai sampai akhir.

`emails.yml` punya 2 input optional:
- `source`: `auto` | `leads` | `buyers` | `agency_pitch`
- `limit`: cap jumlah email per run

---

## ✉️ Email Strategy — Soft Feedback, Bukan Hard Sell

Karena software ini **masih baru dan belum punya nama**, semua cold email diset dengan tone **minta feedback**, bukan jualan langsung. Target global → semua email **bahasa Inggris**.

Setiap email otomatis berakhir dengan:

> *If you're open to giving honest feedback, I'll happily send you a sample of my software's output.*
>
> — Idin Iskandar
> idiniskandar.tech@gmail.com

Diatur lewat 3 konstanta sentral di `src/email_generator.py`:

```python
SENDER_NAME   = "Idin Iskandar"
SENDER_EMAIL  = "idiniskandar.tech@gmail.com"
FEEDBACK_LINE = "If you're open to giving honest feedback, I'll happily send you a sample of my software's output."
SIGNATURE     = f"— {SENDER_NAME}\n{SENDER_EMAIL}"
```

Semua **3 mode** (`leads`, `buyers`, `agency_pitch`) — baik AI macro maupun fallback template — pakai konstanta yang sama. Mau ganti sender? **Edit 1 file, semua email auto-update.**

---

## 📁 Struktur Project

```
.
├── .github/workflows/
│   ├── research.yml              # Apex Lead Research
│   ├── buyers.yml                # Apex Buyer Hunter
│   ├── agency-buyers.yml         # Apex Agency Buyer Hunter
│   └── emails.yml                # Apex Email Generator
├── run.py                        # Pipeline 1: leads
├── find_buyer.py                 # Pipeline 2: agency buyer hunter (mid/large)
├── find_agency_buyers.py         # Pipeline 3: small/freelancer agency owners
├── generate_emails.py            # Pipeline 4: AI cold emails
├── make_sample_pack.py           # Bundle sample CSV+PDF untuk attach
├── targets.yaml                  # ← ganti file ini = ganti target scrape
├── buyers.yaml
├── agency_buyers.yaml
├── requirements.txt
└── src/
    ├── config.py
    ├── analyst.py / qualifier.py / pipeline.py
    ├── enrichers.py / bi_enrich.py
    ├── email_generator.py        # ← sender + feedback line di sini
    ├── email_verifier.py         # SMTP RCPT + MX + provider fallback
    ├── dedup_db.py               # SQLite dedup
    ├── pdf_audit.py              # ReportLab PDF
    ├── sheets_push.py            # Google Sheets export (opsional)
    ├── crm_webhooks.py
    ├── quality_score.py          # 0-100 lead grading
    └── ... (loader, models, export, etc)
```

---

## 🚦 Quick Start (Local)

```bash
python -m pip install -r requirements.txt
cp .env.example .env              # isi PAGESPEED_API_KEY + IDINCODE_API
python run.py                     # pipeline leads
python find_buyer.py              # pipeline buyers
python find_agency_buyers.py      # pipeline agency buyers
python generate_emails.py         # generate cold email
```

Output ada di `output/` (CSV per tier, PDF audit, dan `output/emails/*.md`).

---

## 🔐 Secrets

Cuma 2 secret yang dibutuhkan, sisanya optional & auto-skip kalau kosong:

| Secret | Wajib? | Dipakai oleh |
|---|---|---|
| `PAGESPEED_API_KEY` | recommended | enrichers (PageSpeed Insights) |
| `IDINCODE_API` | recommended | AI macro (kie.ai / Claude Sonnet) |
| `MYEMAILVERIFIER_API_KEY` / `ZEROBOUNCE_API_KEY` / `HUNTER_API_KEY` | optional | email_verifier (fallback chain) |
| `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` + `GSHEET_SPREADSHEET_ID` | optional | sheets_push |

Tanpa secret apapun pipeline **tetap jalan** — AI fallback ke template, verifier fallback ke MX-only, sheets push auto-skip.

---

## 🧪 Tests

```bash
python -m pytest tests/ -v
```

42+ tests cover: loader, qualifier, analyst, enrichers, dedup, export, email gen, quality score.

---

## 🛣️ Roadmap Singkat

- v3.1 — no email guessing (only literal scraped emails)
- v3.2 — quality_score 0-100 + bi_enrich
- v3.3 — agency_pitch mode + sample_pack bundler
- v3.4 — email_verifier (SMTP RCPT) + sheets_push + crm_webhooks
- **v3.5 (current)** — 4 workflow terpisah di GitHub Actions + global soft-feedback email tone + sentralisasi sender identity

---

## 📜 Lisensi & Kontak

Personal project, no public license. Reach out: **idiniskandar.tech@gmail.com**.

> Built without modal. Powered by gabut. 🔥
