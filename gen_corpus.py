#!/usr/bin/env python3
"""Generate a realistic 61-day memory corpus for the mem-demo rehearsal.

Identical corpus goes on both instances. The Beacon decision (with rationale)
is buried on 2026-06-06 among decoy projects that also made API choices.
"""
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "corpus"
START = date(2026, 5, 9)
END = date(2026, 7, 8)

random.seed(7)

FILLER = [
    "Pi-hole blocklist update; ad-block rate back up to 23%.",
    "Grafana dashboard for the NAS finally shows disk temps correctly.",
    "Rotated the Traefik TLS certs on the home server.",
    "Prometheus scrape for the router kept flapping; bumped the timeout.",
    "Cleaned up 40GB of old container images on the homelab box.",
    "Backup verify ran clean; restore test of one photo album worked.",
    "Uptime Kuma false-alerted twice at night; widened the retry window.",
    "Long run in the morning; 10k, knee held up fine.",
    "Tried the new ramen place near the office; solid, would go back.",
    "Called mom; she is planning the reunion for late August.",
    "Sister confirmed she is staying in Toronto through the winter.",
    "Cousin in Lisbon sent photos from the coast; heat wave there.",
    "Fixed the squeaky pantry door hinge; needed a new screw, not oil.",
    "Tomato seedlings moved outside; marked the beds for drip lines.",
    "Read two chapters of the distributed-systems book before bed.",
    "Swapped the car's cabin air filter; 15 minutes, saved 60 bucks.",
    "Meal-prepped chili and rice for the week.",
    "Neighbor's dog got out again; walked him back around the block.",
    "Checked the forecast before the Saturday hike; pushed it to Sunday.",
    "Storm knocked the power out for 20 minutes; UPS carried the rack.",
    "Watched the F1 race; strategy calls were baffling as usual.",
    "Cleared the garage shelf for the camping gear.",
    "New keyboard switches arrived; lubed and installed half of them.",
    "Library book on urban planning was due; renewed it online.",
    "Batch-scanned a shoebox of old family photos.",
    "Heat wave here too; ran the sprinklers early to save the seedlings.",
    "Dentist appointment moved to next Thursday.",
    "Wrote up notes on the NFS vs iSCSI experiment for the homelab wiki.",
    "Refactored my dotfiles repo; split the zsh config into modules.",
    "Tested the generator before storm season; ran fine on the first pull.",
    "Farmer's market run; got the good peaches before they sold out.",
    "Set up a shared calendar for the family reunion logistics.",
    "Router firmware update went smoothly for once.",
    "NWS put out a heat advisory; skipped the afternoon run.",
    "Tried cold-brew ratios again; 1:8 overnight is the keeper.",
    "Patched the raised bed liner; the drip system stays for now.",
    "Old laptop repurposed as a bedside e-reader server.",
    "Weekly review: inbox zero for the first time in a month.",
]

EVENTS = {
    date(2026, 5, 12): [
        "Started a little hobby project: Nimbus, a CLI that backs up the "
        "family photo library offsite.",
    ],
    date(2026, 5, 14): [
        "Nimbus: compared storage APIs (S3, Wasabi, Backblaze B2). Picked "
        "Backblaze B2 for the price and the simple native API.",
    ],
    date(2026, 5, 18): [
        "Nimbus: first successful full upload run; 82GB in one evening.",
    ],
    date(2026, 5, 21): [
        "New weekend project with the kids: Larkspur, a garden sensor "
        "dashboard. Going with Adafruit IO for the device API since the "
        "feather boards speak it natively.",
    ],
    date(2026, 5, 28): [
        "Larkspur: soil moisture graphs live on the kitchen tablet.",
    ],
    date(2026, 6, 6): [
        "Started a new hobby project: Beacon, a small dashboard that shows "
        "current weather for the cities where family lives.",
        "Researched free weather APIs for Beacon. Ruled out OpenWeather "
        "(needs an API key and the good endpoints sit behind a card-on-file "
        "tier), WeatherAPI.com (key plus commercial-shaped quotas), "
        "Tomorrow.io (way more platform than a hobby app needs), NWS "
        "(free and keyless but US-only, and family is in Toronto and "
        "Lisbon), and Visual Crossing (fine but keyed, 1000 records/day). "
        "Went with Open-Meteo: no key, no signup, generous free "
        "non-commercial tier, current conditions plus 16-day forecast.",
        "Beacon stack decisions: Python with FastAPI; dependencies managed "
        "with uv only, never pip.",
    ],
    date(2026, 6, 13): [
        "Beacon: sketched the city list to start with: Toronto, Lisbon, "
        "Denver.",
    ],
    date(2026, 6, 16): [
        "Shelving Larkspur for the season; the sensors corroded and the "
        "kids moved on. Might revive it in spring.",
    ],
    date(2026, 6, 20): [
        "Poked at Beacon for an hour; a plain JSON file for the city "
        "config feels right, no database needed.",
    ],
    date(2026, 6, 24): [
        "Moved the neighborhood newsletter off Mailchimp to Buttondown; "
        "the API is one POST and the archive page looks better.",
    ],
    date(2026, 7, 2): [
        "Nimbus: monthly backup report script now lands in my inbox on "
        "the 1st.",
    ],
}


def main():
    OUT.mkdir(exist_ok=True)
    d = START
    pool = []
    while d <= END:
        entries = list(EVENTS.get(d, []))
        if not pool:
            pool = FILLER[:]
            random.shuffle(pool)
        for _ in range(random.randint(3, 5)):
            if pool:
                entries.append(pool.pop())
        random.shuffle(entries)
        text = f"# {d.isoformat()}\n\n" + "".join(f"- {e}\n" for e in entries)
        (OUT / f"{d.isoformat()}.md").write_text(text)
        d += timedelta(days=1)
    n = len(list(OUT.glob("*.md")))
    total = sum(len(p.read_text().splitlines()) - 2 for p in OUT.glob("*.md"))
    print(f"wrote {n} files, {total} entries")


if __name__ == "__main__":
    main()
