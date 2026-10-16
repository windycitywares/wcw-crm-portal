"""Asked by deploy/auto-deploy.sh every minute: should we look for updates now?

    python -m app.workers.deploy_gate begin            # prints "go <reason>" or "skip <reason>"
    python -m app.workers.deploy_gate end ok|failed "summary"

Exit code 0 always for `begin` (the shell reads the word), so a broken gate can be detected by the script
and treated as "go" (updates never get stuck because of the gate itself).
"""

from __future__ import annotations

import asyncio
import sys

from app.core.database import SessionFactory, engine
from app.modules import load_modules


async def _main(argv: list[str]) -> str:
    load_modules()
    from app.modules.deploy.service import DeployService

    async with SessionFactory() as session:
        service = DeployService(session)
        if argv[:1] == ["begin"]:
            d = await service.gate_begin()
            out = f"{'go' if d.go else 'skip'} {d.reason}"
        elif argv[:1] == ["end"] and len(argv) >= 2:
            await service.gate_end(argv[1] == "ok", " ".join(argv[2:]))
            out = "recorded"
        else:
            out = "usage: deploy_gate begin | end ok|failed SUMMARY"
    await engine.dispose()
    return out


if __name__ == "__main__":
    print(asyncio.run(_main(sys.argv[1:])))
