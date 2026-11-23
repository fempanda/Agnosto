# Agnosto Media Productions — website package

## What is ready

`site/index.html` is a complete, self-contained, mobile-responsive **frontend preview** with working navigation, example catalog search and filters, content-preference controls, and the approved Agnosto visual identity and mission statement. Open it in a browser or upload it to a static hosting service. There are no external dependencies, payments, or API keys.

`server/` contains the **earlier local development backend**, with SQLite artist/media records, applications, inquiries, and an administrator interface. It is not hardened for public deployment and should not be used with real submissions or confidential records. It requires Python and an environment variable for the admin password. See the earlier Milestone 2 README for its development-only operation.

## Publish the frontend for $0 from an iPhone

1. In Safari, create a free GitHub account (if you do not have one).
2. Create a **public** repository named `agnosto-website` (GitHub Pages on free personal accounts generally requires a public repository).
3. Upload `site/index.html` to the **root** of the repository, naming it `index.html`.
4. In repository Settings → Pages, choose **Deploy from a branch**, `main`, and `/ (root)`; save.
5. GitHub will provide a `https://YOUR-USERNAME.github.io/agnosto-website/` URL after deployment. The URL will be publicly accessible. GitHub UI and free-tier terms can change.

**Do not upload `server/`, passwords, private records, or `.sqlite3` database files to a public repository.** The frontend preview contains demonstration content, and the forms deliberately do not transmit submissions. The public site cannot receive real applications until a secure backend, data handling policies, and appropriate services are configured.

## What remains before production launch

A secure, hosted backend with persistent database, administrator MFA and abuse prevention, working email notifications, verified content permissions, privacy/guardian processes, final business contact details, approved real media and artists, accessibility/security testing, backups and operational monitoring. A public URL cannot be created on your behalf without access to a hosting account or an authorized publishing integration.

This package is **not** the fully completed eight-section blueprint and should not be described as a production-ready business service.
