# Automatic deploys

Every push to `main` runs the tests on GitHub. If they pass, that exact commit goes live on
https://goa.ayushchougula.in about two minutes later. Watch it in the repo's **Actions** tab.

```
push to main → GitHub Actions: pytest (with a PostGIS database)
             → ssh deployer@server <commit>  → /usr/local/bin/pawsos-deploy <commit>
                 1. fetch main, refuse any commit that is not on it
                 2. check out the commit in /opt/pawsos-site, pip install, restart pawsos-site
                    (its start-up runs alembic upgrade head)
                 3. /health and /dashboard must answer within 30 s, or it goes back to the
                    previous commit and the run fails
                 4. swap the website files in /var/www/pawsos-site in one move
             → the workflow checks /health, /dashboard, /demo and / on the live domain
```

Pull requests run the tests only.

## What it deploys, and what it does not

| On the server | Serves | Deployed by this pipeline |
|---|---|---|
| `/var/www/pawsos-site` | the website: `/`, `/demo` | yes |
| `/opt/pawsos-site` (`pawsos-site.service`, port 8041) | `/dashboard`, invented demo data | yes |
| `/opt/pawsos` (`pawsos.service`, port 8040) | the sandbox and the Telegram bot | **no** |

`/opt/pawsos` runs code that is not on GitHub yet (for example migration `0011_ai_description`).
Deploying `main` there would remove that work, and the app would not start because its database
is at a migration `main` does not have. Push that code to `main` first, then add it here.

## Security

- The deploy key is used for nothing else. Its private half is the GitHub secret `DEPLOY_SSH_KEY`.
- On the server it belongs to the user `deployer`, and `authorized_keys` forces it to run
  `sudo /usr/local/bin/pawsos-deploy "$SSH_ORIGINAL_COMMAND"`. No shell, no forwarding.
- `sudo` lets `deployer` run that one script and nothing else (`/etc/sudoers.d/pawsos-deploy`).
- The script accepts only a 40-character commit id that is on `main`.
- The server's host key is pinned in the secret `DEPLOY_KNOWN_HOSTS`; the server's address is in `DEPLOY_HOST`.
- The installed script is a root-owned copy. Changing `deploy/pawsos-deploy.sh` in git does **not**
  change what runs on the server until someone with server access reinstalls it:
  `sudo install -m 755 deploy/pawsos-deploy.sh /usr/local/bin/pawsos-deploy`.

## Undo a deploy

- Fastest: in GitHub, revert the bad commit on `main`. The revert deploys like any other commit.
- By hand on the server: `sudo pawsos-deploy <earlier commit sha>` (it must be on `main`).
- Website files only: the previous set is kept in `/var/www/pawsos-site.prev`.
- Database migrations do not roll back on their own. A migration that breaks the app needs a
  new commit that fixes it.

## Logs

- Each deploy appends to `/var/log/pawsos-deploy.log` on the server.
- The app: `journalctl -u pawsos-site -n 100`.
