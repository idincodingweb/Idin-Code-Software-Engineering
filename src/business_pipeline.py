from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from src.business_export import BusinessCsvExporter
from src.business_export_sheets import BusinessSheetsExporter
from src.business_intel import BusinessIntelResearcher
from src.business_loader import BusinessTargetLoader
from src.business_models import BusinessIntelLead, BusinessIntelTarget


@dataclass(slots=True)
class BusinessPipelineConfig:
    targets_path: Path
    output_dir: Path
    max_concurrency: int = 6
    timeout_seconds: float = 20.0
    user_agent: str = &quot;Mozilla/5.0&quot;
    enable_sheets_export: bool = False
    sheets_id: str | None = None
    sheet_title: str = &quot;IdinCode Business Intelligence&quot;


class BusinessIntelPipeline:
    def __init__(self, config: BusinessPipelineConfig):
        self.config = config
        self.loader = BusinessTargetLoader(config.targets_path)
        self.researcher = BusinessIntelResearcher(
            timeout_seconds=config.timeout_seconds,
            user_agent=config.user_agent,
        )
        self.csv_exporter = BusinessCsvExporter(config.output_dir)

    async def run(self) -&gt; list[BusinessIntelLead]:
        targets = self.loader.load()
        print(f&quot;Loaded {len(targets)} targets.&quot;)

        leads = await self._research_all(targets)
        leads.sort(key=lambda item: (item.business_score, -item.tier), reverse=True)

        for index, lead in enumerate(leads, start=1):
            lead.rank = index

        csv_outputs = self.csv_exporter.export(leads)
        print(&quot;Business-intel CSV exports:&quot;)
        for name, path in csv_outputs.items():
            print(f&quot;  - {name}: {path}&quot;)

        if self.config.enable_sheets_export:
            try:
                sheet_id = BusinessSheetsExporter(
                    spreadsheet_id=self.config.sheets_id,
                    title=self.config.sheet_title,
                ).export(leads)
                print(f&quot;Google Sheets export complete: {sheet_id}&quot;)
            except Exception as exc:
                print(f&quot;Google Sheets export skipped/failed: {exc}&quot;)

        await self.researcher.close()
        return leads

    async def _research_all(self, targets: list[BusinessIntelTarget]) -&gt; list[BusinessIntelLead]:
        semaphore = asyncio.Semaphore(self.config.max_concurrency)

        async def worker(target: BusinessIntelTarget) -&gt; BusinessIntelLead:
            competitors = build_competitor_set(target, targets)
            async with semaphore:
                return await self.researcher.research(target, competitors)

        return await asyncio.gather(*(worker(target) for target in targets))


def build_competitor_set(target: BusinessIntelTarget, targets: list[BusinessIntelTarget]) -&gt; list[str]:
    &quot;&quot;&quot;
    Build competitor set berdasarkan niche, category, location, dan tier.
    Return top 3 competitors sebagai domain/brand names.
    &quot;&quot;&quot;
    scored: list[tuple[int, str]] = []

    for candidate in targets:
        if candidate.domain == target.domain:
            continue

        score = 0

        # Niche match: highest priority
        if candidate.niche and candidate.niche == target.niche:
            score += 5

        # Category match
        if candidate.category and candidate.category == target.category:
            score += 4

        # Location match
        if candidate.location and target.location and candidate.location == target.location:
            score += 2

        # Tier match
        if candidate.tier == target.tier:
            score += 3
        elif abs(candidate.tier - target.tier) == 1:
            score += 1

        if score &gt; 0:
            competitor_name = candidate.brand or candidate.domain
            scored.append((score, competitor_name))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [name for _, name in scored[:3]]
