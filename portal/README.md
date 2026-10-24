# Portal deployment

`laya.manef.dev` — the public page plus the device registry.

## Why a container with Traefik labels

Writing `/etc/dokploy/traefik/dynamic/*.yml` needs root. The only passwordless sudo rule
on this host covers another application's file, so this deployment uses the Docker
provider instead: `dokploy-network` plus labels achieve the same routing with the access
the deploy user actually has.

```bash
cd ~/apps/laya-portal/portal
docker compose up -d --build
```

## What it serves

| route | purpose |
|---|---|
| `GET /` | landing page: what the NPU is for, four-step install, live counters |
| `GET /api/devices` | the registry table |
| `GET /api/summary` | totals by device and OS, used by the hero counters |
| `POST /api/device/register` | called by local installs every 5 minutes |
| `POST /api/device/check` | the ID field on the page |

## Data

SQLite at `/data/portal.sqlite` inside the container, mounted from
`/home/antinrml/apps/laya-portal-data`. Back it up with:

```bash
docker cp laya-portal:/data/portal.sqlite ./portal-backup.sqlite
```

Stored per device: ID, OS, architecture, app version, which OpenVINO devices compiled,
first/last seen and a report count. No text, no prompts, no paths, no credentials.

`portal.sqlite` is gitignored in the parent repository — it holds real device records.
