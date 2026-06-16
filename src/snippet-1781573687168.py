def _is_skincare_like(lead: Any) -> bool:
    niche = (getattr(lead, "niche", None) or "").lower()
    category = (getattr(lead, "category", None) or "").lower()
    text = f"{niche} {category}"
    return any(
        keyword in text
        for keyword in (
            "skincare",
            "beauty",
            "kosmetik",
            "cosmetic",
            "sunscreen",
            "kecantikan",
        )
    )


def _tier_label_id(tier: Optional[int]) -> str:
    """Label tier dalam Bahasa Indonesia."""
    if tier == 1:
        return "tier 1 (market leader)"
    if tier == 2:
        return "tier 2 (scaling brand)"
    if tier == 3:
        return "tier 3 (emerging)"
    return ""


def build_bi_summary(lead: Any) -> str:
    """Fallback deterministic BI summary (1-2 kalimat Bahasa Indonesia) dari field lead."""
    brand = (getattr(lead, "brand", None) or "").strip()
    tier = getattr(lead, "tier", None)
    founded = getattr(lead, "founded_year", None)
    years = getattr(lead, "years_in_business", None)
    emp = getattr(lead, "employee_range", "") or "unknown"
    loc = getattr(lead, "location_count", 0) or 0
    tech = getattr(lead, "tech_signals", []) or []
    social = getattr(lead, "social_profiles", []) or []
    revenue_tier = (getattr(lead, "revenue_tier", "") or "").strip()
    platform = (getattr(lead, "platform", "") or "").strip()
    notes = (getattr(lead, "notes", "") or "").strip()
    firmo_conf = (getattr(lead, "firmographics_confidence", "low") or "low").strip().lower()

    confidence_note = ""
    if firmo_conf == "low":
        confidence_note = " Sinyal ukuran perusahaan masih estimasi dari data publik."
    elif firmo_conf == "medium":
        confidence_note = " Sinyal ukuran perusahaan sebagian terverifikasi dari data publik."

    is_fashion = _is_fashion_like(lead)
    is_skincare = _is_skincare_like(lead)
    tier_label = _tier_label_id(tier)

    if is_fashion or is_skincare:
        category_label = "fashion/apparel" if is_fashion else "skincare/beauty"
        parts: list[str] = []

        intro_bits: list[str] = []
        if brand:
            intro_bits.append(f"{brand} adalah brand {category_label} Indonesia")
        else:
            intro_bits.append(f"Brand {category_label} Indonesia")
        if tier_label:
            intro_bits.append(tier_label)
        if revenue_tier and revenue_tier != "unknown":
            intro_bits.append(f"estimasi revenue tier: {revenue_tier}")
        if intro_bits:
            parts.append(", ".join(intro_bits))

        maturity_bits: list[str] = []
        if founded:
            if years:
                maturity_bits.append(f"berdiri {founded} (~{years} tahun)")
            else:
                maturity_bits.append(f"berdiri sejak {founded}")
        if emp and emp != "unknown":
            maturity_bits.append(f"estimasi tim: {emp} orang")
        if loc > 1:
            maturity_bits.append(f"{loc} titik lokasi terdeteksi")
        if maturity_bits:
            parts.append(", ".join(maturity_bits))

        stack_bits: list[str] = []
        if platform:
            stack_bits.append(f"platform website: {platform}")
        if tech:
            stack_bits.append(f"stack teknologi: {', '.join(tech[:4])}")
        if social:
            stack_bits.append(f"social: {', '.join(social[:5])}")
        if stack_bits:
            parts.append(". ".join(stack_bits))

        if notes:
            parts.append(f"Catatan researcher: {notes}")

        if not parts:
            return (
                f"Brand {category_label} dengan sinyal BI publik terbatas."
                f"{confidence_note}"
            ).strip()

        summary = ". ".join(p[0].upper() + p[1:] for p in parts if p) + "."
        return f"{summary}{confidence_note}".strip()

    # Generic fallback (non-fashion, non-skincare)
    parts = []

    if brand:
        if tier_label:
            parts.append(f"{brand} ({tier_label})")
        else:
            parts.append(brand)

    if founded:
        if years:
            parts.append(f"berdiri {founded} (~{years} tahun)")
        else:
            parts.append(f"berdiri sejak {founded}")

    size_bits = []
    if emp and emp != "unknown":
        size_bits.append(f"estimasi tim {emp} orang")
    if loc and loc > 1:
        size_bits.append(f"{loc} lokasi")
    if size_bits:
        parts.append(", ".join(size_bits))

    if tech:
        parts.append(f"stack teknologi: {', '.join(tech[:5])}")

    if social:
        parts.append(f"social: {', '.join(social[:5])}")

    if revenue_tier and revenue_tier != "unknown":
        parts.append(f"estimasi revenue tier: {revenue_tier}")

    if not parts:
        return f"Sinyal BI publik terbatas.{confidence_note}".strip()

    summary = ". ".join(p[0].upper() + p[1:] for p in parts) + "."
    return f"{summary}{confidence_note}".strip()