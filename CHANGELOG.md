# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.2] - 2026-07-20

### Changed

- Redesigned the interactive API documentation and its responsive layout.
- Derived the documentation base URL from the incoming request so examples match
  the deployed host.

## [1.1.1] - 2026-07-20

### Fixed

- Made FIA page navigation wait for the scraper form instead of relying on the
  network-idle event.
- Reduced navigation race conditions while selecting seasons, championships, and
  events, including the previous-season fallback flow.

## [1.1.0] - 2026-07-20

### Added

- Added `X-API-Key` authentication for scraping, discovery, and document-download
  endpoints.
- Added a public `/health` endpoint for deployment health checks.
- Added Railway deployment configuration.

### Changed

- Updated the Docker image and Python dependency installation for production
  deployment.
- Configured a single Gunicorn worker and Chromium options suitable for
  memory-constrained containers.
- Closed upstream download responses after streaming completes.

### Security

- Restricted document downloads to HTTPS URLs hosted on `fia.com` or its
  subdomains.
- Used constant-time comparison when validating API keys.
