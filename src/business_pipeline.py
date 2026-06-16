from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from src.business_export import BusinessCsvExporter
from src.business_intel import BusinessIntelResearcher
from src.business_loader import BusinessTargetLoader
from src.business_models import BusinessIntelTarget


@dataclass
class BusinessPipelineConfig:
    targets_path: Path
    output_dir: Path
    max_concurrency: int = 6
    timeout_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0"


class BusinessIntelPipeline:
    def __init__(self, config: BusinessPipelineConfig):
        self.config = config
        self.loader = BusinessTargetLoader(config.targets_path)
        self.researcher = BusinessIntelResearcher(
            timeout_seconds=config.timeout_seconds,
            user_agent=config.user_agent,
        )
        self.csv_exporter = BusinessCsvExporter(config.output_dir)

    async def run(self):
        targets = self.loader.load()
        leads = await self._research_all(targets)
        leads.sort(key=lambda item: (item.business_score, -item.tier), reverse=True)

        for index, lead in enumerate(leads, start=1):
            lead.rank = index

        csv_outputs = self.csv_exporter.export(leads)
        print("Business-intel CSV exports:")
        for name, path in csv_outputs.items():
            print("  - " + name + ": " + str(path))

        await self.researcher.close()
        return leads

    async def _research_all(self, targets):
        semaphore = asyncio.Semaphore(self.config.max_concurrency)

        async def worker(target):
            competitors = build_competitor_set(target, targets)
            async with semaphore:
                return await self.researcher.research(target, competitors)

        return await asyncio.gather(*(worker(target) for target in targets))


def build_competitor_set(target: BusinessIntelTarget, targets):
    scored = []
    for candidate in targets:
        if candidate.domain == target.domain:
            continue
        score = 0
        if candidate.niche and candidate.niche == target.niche:
            score += 5
        if candidate.category and candidate.category == target.category:
            score += 4
        if candidate.location and target.location and candidate.location == target.location:
            score += 2
        if candidate.tier == target.tier:
            score += 3
        elif abs(candidate.tier - target.tier) == 1:
            score += 1
        if score > 0:
            name = candidate.brand or candidate.domain
            scored.append((score, name))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [name for _, name in scored[:3]]
