# Idincode Researche — Apex Lead Research Engine

> **Self-hosted, zero-server B2B lead intelligence pipeline** yang jalan di GitHub Actions runner gratis. Project ini dipakai untuk mengumpulkan, memperkaya, menilai, dan mengemas data prospect menjadi output yang siap dijual, dipitch, atau dipakai outreach.

Built & maintained by **Idin Iskandar** — [idiniskandar.tech@gmail.com](mailto:idiniskandar.tech@gmail.com)

---

## Tentang Project Ini

`Idincode Researche` adalah **mesin riset lead dan market intelligence** untuk kebutuhan B2B outreach.

Tema utama project ini:
- mencari target market dari domain-domain tertentu
- mengecek sinyal marketing dan technology stack mereka
- menilai apakah mereka layak jadi prospect
- menghasilkan output yang bisa dipakai untuk:
  - dijual sebagai lead pack
  - dipakai agency outreach
  - dijadikan sample audit
  - dijadikan dasar cold email yang lebih personal

Secara sederhana, project ini adalah **pipeline riset prospect niche-agnostic**.

Artinya:
- hari ini lu bisa scrape `dental clinics`
- besok bisa `fashion brands`
- lusa bisa `SaaS`, `law firms`, `real estate`, atau niche lain

Target niche tidak lagi dikunci di kode Python. Selama field `niche` di `targets.yaml` sesuai, sistem akan membaca konfigurasi niche dari file YAML dan menyesuaikan:
- prompt analyst AI
- deterministic fallback reasons
- outreach hook
- scoring quality
- scoring qualifier weight

Jadi arah project ini bukan sekadar scraper, tapi **mesin intelligence untuk prospecting dan outreach**.

---

## History — Kenapa Project Ini Dibangun

Project ini lahir dari kebutuhan praktis: bikin automation yang berguna tanpa modal infrastruktur.

Banyak tutorial automation dan lead-gen bergantung pada:
- VPS
- workflow SaaS
- API enrichment berbayar
- orchestration tools tambahan

Masalahnya: itu semua butuh biaya.

Project ini dibangun untuk membuktikan bahwa:
- pipeline riset lead yang serius bisa dibuat sendiri
- bisa jalan di GitHub Actions runner gratis
- bisa dipakai untuk monetisasi data dan outreach
- tidak harus bergantung pada stack mahal dari awal

Hasilnya adalah sistem yang bisa:
- scrape target
- enrich sinyal digital mereka
- score opportunity
- generate CSV
- generate PDF audit
- generate email outreach
- push hasil ke CRM / Google Sheets jika dibutuhkan

Semua dari repo yang sama.

---

## Tujuan Project

Project ini dibuat untuk 4 tujuan utama:

1. **Riset market**
   Cari dan petakan domain-domain target dalam niche tertentu.

2. **Lead qualification**
   Menilai mana prospect yang punya opportunity paling besar untuk dipitch.

3. **Outreach preparation**
   Menghasilkan alasan pitch, angle outreach, dan output audit yang siap dikirim.

4. **Monetisasi data**
   Data hasil scrape bisa dipakai sendiri atau dijual ke agency / partner / buyer.

---

## Visi

**Membangun mesin market-intelligence yang fleksibel, murah dijalankan, dan bisa dipakai ulang lintas niche hanya dengan mengganti target dan config.**

## Misi

1. Menjalankan automation research tanpa infrastruktur mahal.
2. Menghasilkan lead pack yang punya konteks, bukan sekadar list domain.
3. Membuat sistem yang benar-benar niche-agnostic.
4. Menyatukan scraping, enrichment, scoring, analyst reasoning, export, dan outreach dalam satu repo.
5. Menjadikan GitHub Actions sebagai execution layer utama untuk riset terjadwal.

---

## Konsep Besar Arsitektur

Project ini dibagi menjadi beberapa lapisan kerja:

1. **Input layer**
   File YAML seperti `targets.yaml`, `buyers.yaml`, dan `agency_buyers.yaml`.

2. **Research layer**
   Ambil HTML, cek reachability, deteksi pixel, platform, dan PageSpeed.

3. **Enrichment layer**
   Tambahan data seperti email, MX, revenue proxy, ads signal, business intelligence, dan competitor signal.

4. **Qualification layer**
   Hitung `gold_score` dan `quality_score`.

5. **Analyst layer**
   AI atau fallback deterministic menghasilkan:
   - `gold_reasons`
   - `outreach_angle`
   - `bi_summary`

6. **Export layer**
   Hasil keluar sebagai CSV tiered, PDF audit, email drafts, CRM payload, atau Sheets.

---

## Niche-Agnostic by Design

Arsitektur sekarang sudah berubah jadi **config-driven**.

Artinya, logic yang dulu hardcoded per niche sekarang dipindah ke file YAML per niche.

Contoh:
```txt
src/config/niches/
  default.yaml
  medical_high_ticket.yaml
  fashion_apparel.yaml
```

Setiap file niche bisa mengatur:

metadata industri
focus analyst
mature business note
fallback reason rules
fallback outreach rules
quality score rules
qualifier weights
Hasilnya:

ganti target niche tidak perlu ubah Python code
niche baru tinggal tambah file YAML
kalau niche belum ada config khususnya, sistem fallback ke default.yaml
Ini inti perubahan paling penting di versi sekarang.


# Arsitektur Eksekusi

                 +----------------------------------------------+
                 |         GitHub Actions Runner (FREE)         |
                 |                                              |
targets.yaml --->| run.py                  -> leads CSV + PDF   |
buyers.yaml ---->| find_buyer.py           -> buyers CSV        |
agency_buyers -->| find_agency_buyers.py   -> agency CSV        |
                 | generate_emails.py      -> email drafts      |
                 +-------------------+--------------------------+
                                     |
                                     v
                           output/ + artifacts + commits



# Flow Pipeline Leads
Pipeline utama run.py menjalankan urutan berikut:

load targets
dedup filter
enrich domain
enrich extras
qualify lead
AI analyst / fallback analyst
sort + tier
export CSV
generate PDF
optional push ke CRM
optional push ke Google Sheets
Secara operasional ini adalah lead factory.

# GitHub Actions — 4 Pipeline Terpisah
Setiap pipeline tampil sebagai entry sendiri di tab Actions GitHub.


Workflow file	Nama di Actions	Script	Fungsi
research.yml	Apex Lead Research | By Idincode	run.py	scrape + score + export leads
buyers.yml	Apex Buyer Hunter | By Idincode	find_buyer.py	cari buyer agency mid/large
agency-buyers.yml	Apex Agency Buyer Hunter | By Idincode	find_agency_buyers.py	cari buyer agency kecil/freelancer
emails.yml	Apex Email Generator | By Idincode	generate_emails.py | generate cold email drafts


# Semua workflow bisa:

jalan manual
jalan terjadwal
upload artifact
commit hasil ke repo
degrade gracefully kalau API kosong


# Struktur Project

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
    ├── config.py
    ├── config/
    │   ├── niche_loader.py
    │   └── niches/
    │       ├── default.yaml
    │       ├── medical_high_ticket.yaml
    │       └── fashion_apparel.yaml
    ├── crm_webhooks.py
    ├── dedup_db.py
    ├── email_generator.py
    ├── email_verifier.py
    ├── enrichers.py
    ├── export.py
    ├── extras.py
    ├── loader.py
    ├── models.py
    ├── pdf_audit.py
    ├── pipeline.py
    ├── qualifier.py
    ├── quality_score.py
    ├── sheets_push.py
    └── ...


    Peran File Penting
targets.yaml
Sumber target utama untuk pipeline leads.

src/loader.py
Membaca dan memvalidasi target dari YAML.

src/enrichers.py
Mengambil HTML, mengecek pixel, platform, dan PageSpeed.

src/extras.py
Enrichment tambahan seperti email, ads, revenue proxy, BI, competitor.

src/qualifier.py
Mengubah hasil enrichment menjadi QualifiedLead dengan gold_score.

src/quality_score.py
Menghitung quality_score 0-100 yang sekarang sudah config-driven.

src/analyst.py

Menghasilkan reasoning dan outreach angle via AI atau fallback rules dari config YAML.

src/export.py
Mengeluarkan CSV tiered yang siap dipakai.

src/pdf_audit.py
Membuat PDF audit untuk lead pilihan.

src/config/niche_loader.py
Memuat config YAML per niche.

src/config/niches/*.yaml
Otak konfigurasi niche-specific tanpa ubah kode Python.


# Metadata Target yang Didukung
Sekarang target bisa membawa metadata tambahan, bukan cuma domain.

Contoh field:

domain
location
niche
category
brand
tier
notes
Metadata ini mengalir sampai ke:

enrichment
qualification
analyst prompt
export CSV
Jadi lu bisa masukin context bisnis langsung di targets.yaml, bukan sekadar URL.

# Output yang Dihasilkan
Project ini bisa menghasilkan beberapa jenis output:

# CSV lead packs

leads_all.csv
leads_starter.csv
leads_pro.csv
leads_premium_gold.csv

# PDF audit
Untuk lead yang lolos threshold tertentu.

# Email drafts 
Dari pipeline email generator

# CRM push
Optional, via webhook

# Google Sheets push
Optional

# Scoring System
Ada dua lapisan scoring:

gold_score
skala 0.0 - 1.0
lebih fokus ke opportunity dari gap teknis / marketing
dipakai untuk sorting dan tier export
quality_score
skala 0 - 100
lebih fokus ke kualitas prospect secara keseluruhan
gabungan dari:
gold score
contactability
buying signals
social / BI / revenue proxies
rules per niche
Keduanya sekarang bisa dipengaruhi config niche.

# Analyst Layer
src/analyst.py bekerja dalam dua mode:

AI mode Kalau IDINCODE_API tersedia, sistem panggil kie.ai untuk menghasilkan:

gold_reasons
outreach_angle
quality_score override optional
bi_summary
Fallback mode Kalau AI gagal atau API kosong, sistem pakai deterministic rules dari YAML config niche.

Ini penting karena pipeline tetap selesai walaupun AI mati.

# Config-Driven Niche System

Contoh niche config:

default.yaml
medical_high_ticket.yaml
fashion_apparel.yaml
Yang bisa dikustom:

industry label
typical ticket
pain point
focus prompt
mature business note
fallback reasoning rules
outreach rules
quality score rules
qualifier weights
response penalty
Dengan model ini:

targets.yaml ganti
niche ganti
pipeline tetap jalan
kalau perlu akurasi lebih tinggi, tinggal tambah file YAML niche baru

# Quick Start !! Idin Code Set-up
python -m pip install -r requirements.txt
python run.py
python find_buyer.py
python find_agency_buyers.py
python generate_emails.py

Kalau mau pakai file target custom:
python run.py --targets targets.yaml

# Environment Variables
Minimal:

PAGESPEED_API_KEY
IDINCODE_API
Optional:

MYEMAILVERIFIER_API_KEY
ZEROBOUNCE_API_KEY
HUNTER_API_KEY
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT
GSHEET_SPREADSHEET_ID
Tanpa API optional, pipeline tetap jalan dengan graceful fallback.


# Requirements
Dependency utama:

httpx
pyyaml
python-dotenv
dnspython
reportlab
gspread
google-auth
Install: python -m pip install -r requirements.txt


# Tema Komersial Project Ini
Kalau dijelaskan secara bisnis, tema project ini adalah:

# B2B market intelligence + lead packaging + outreach preparation.

Bukan sekadar crawler.

Value project ini ada pada:

pemilihan target
enrichment signal
scoring
reasoning
audit packaging
readiness untuk dipitch
Jadi output akhirnya adalah prospect intelligence yang siap dipakai.

# Cocok Untuk Siapa
Project ini cocok untuk:

lead generation operator
agency owner
freelancer outreach
market researcher
solo founder yang mau jualan service
orang yang mau monetisasi hasil scrape dengan konteks yang lebih tajam

# Prinsip Desain
self-hosted
low-cost
graceful degradation
niche-agnostic
config-driven
async-first
export-friendly
operational di GitHub Actions

# Roadmap Singkat
v3.1 — no email guessing
v3.2 — quality score + BI enrichment
v3.3 — agency pitch mode + sample pack bundler
v3.4 — email verification + sheets push + CRM webhooks
v3.5 — global soft-feedback email strategy
v3.6 — config-driven niche engine, metadata-aware targets, YAML-based analyst/scoring behavior
Lisensi & Kontak
Personal project, no public license.

Kontak: idiniskandar.tech@gmail.com

# Penutup
Alhamdulillah, setelah rangkaian update ini, struktur project jadi jauh lebih rapi, fleksibel, dan siap dipakai lintas niche tanpa harus bongkar kode inti setiap kali ganti target market.

Marilah kita panjatkan puji dan syukur atas kehadirat Allah Subhanahu wa Ta'ala yang telah menciptakan bumi dan seisinya, menciptakan manusia dengan akal dan kemampuan berpikir, sehingga lahir ilmu, teknologi, sains, dan berbagai kemudahan yang bisa dipakai untuk membangun sesuatu yang bermanfaat.

# Semoga project ini jadi alat yang berguna, menghasilkan manfaat, dan membuka jalan rezeki yang baik.

```
Built without modal. Built with akal, kerja, dan izin Allah.
```

