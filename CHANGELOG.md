# Change Log

## [Unreleased]

## [0.9.4] - 2023-11-22

### Fixed
 * Support for ZoneMinder 1.36.33

### Changed
 * Removed support for ZoneMinder 1.30 - requires 1.32+ API

## [0.9.3] - 2021-06-03

### Added
 * Support for ZoneMinder 1.36

### Fixed
 * Monitor status scraped from Console in 1.34
 * Detecting monitor passwords in middle of monitor URL

## [0.9.2] - 2020-12-22

### Added
 * Customizable threshold for percentage of capturing monitors

### Fixed
 * Capturing monitor percentage threshold
 * Threshold event clearing
 * Storage detection

## [0.9.1] - 2020-12-21

### Fixed
 * Data collection continues if Events are not available

## [0.9.0] - 2020-12-19

### Added
 * Support for ZoneMinder 1.32 and 1.34
 * Storage volume modeling and monitoring
 * Per-monitor framerates and bandwdith

### Fixed
 * Modeler and graphs for ZoneMinder 1.32
 * Daemon total bandwidth on on ZoneMinder 1.34

### Changed
 * Storage graphs moved to Storage components from Daemon
 * Datasource class file organization

## 0.7.0 - 2019-03-17
 * Alpha release

[Unreleased]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.9.4...HEAD
[0.9.4]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.9.3...0.9.4
[0.9.3]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.9.2...0.9.3
[0.9.2]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.9.1...0.9.2
[0.9.1]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.9.0...0.9.1
[0.9.0]: https://github.com/daviswr/ZenPacks.daviswr.ZoneMinder/compare/0.7.0...0.9.0
