# Security

Do not commit credentials, device configuration, usage logs, firmware backups or machine-specific identifiers. Git ignore rules are defense in depth, not a secret scanner.

WorkBuddy relies on undocumented internals of the installed official app. Review before enabling; use only your own account. Credentials stay in memory and authenticate only to the fixed Tencent billing endpoint. Client updates can break compatibility. DeepSeek keys remain in macOS Keychain and are never sent to the display.

This is a fresh source snapshot. Original Git history, local logs, runtime state, device binaries, backups and handoff notes are excluded. Generic application paths describe supported software, not a particular machine. The glyph subset derives from the OFL font identified in third_party/README.md; proprietary system-font glyphs are not included.
