# Recovery Baseline

This project now has a local git recovery baseline and is configured to use:

- Remote: `https://github.com/nsenadhi/remo.git`
- Branch: `main`

## Current state

- Local history is active and clean.
- A first baseline commit already exists locally.
- Remote push is blocked until this machine's GitHub account has write access to the repo.

## What to keep updated

- Keep secrets only in `.env`, never in tracked files.
- Update `.env.example` when new environment variables are required.
- Sync changes regularly with the backup repo.

## Manual sync

Run:

```powershell
.\scripts\sync-recovery.ps1 -Message "Describe the change"
```

This will:

1. Stage all tracked and new files
2. Create a commit
3. Push to `origin/main`

## Continuous backup option

After GitHub write access is fixed, create a Windows Scheduled Task that runs:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\M S I\Desktop\MBZUAi\oncampus\remonineww\remoninew\scripts\sync-recovery.ps1" -Message "Scheduled recovery sync"
```

Run it every 15 or 30 minutes, depending on how often this codebase changes.

## Recovery steps

1. Clone the backup repository.
2. Create `.env` from `.env.example`.
3. Install Python dependencies from `requirements.txt`.
4. Rebuild frontend assets if needed.

## Current note

The GitHub repo was empty when checked on March 18, 2026. This workspace is now the source baseline, and remote recovery will work once push permissions are granted.
