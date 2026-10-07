**English** · [Français](SECURITY.fr.md)

# Security

## Reporting a vulnerability

Please report it privately on GitHub: the **Security** tab of this repository, then **Report a
vulnerability**. Do not open a public issue for it.

## What the plugin does

- It adds one MCP server entry, at the address you set (by default `http://127.0.0.1:8765/mcp`,
  the application on this computer). For an application on another computer it sends that
  application's access token, which Claude Code keeps as a sensitive option.
- It has no hooks: nothing runs on its own. The skill's helper scripts (Python, plus Windows
  PowerShell or macOS's JavaScript for Automation) run only when Claude calls them for a task you asked for. They only call the
  application at that address, with read-only tools, and download nothing.
- In DaVinci Resolve, the skill never changes a timeline in place: it builds new timelines or
  works on a copy, adds markers to the media pool clips, and does not save the project.
- Text that comes from the videos (speech, on-screen text, descriptions) and names read from
  Resolve are data for Claude, never instructions.

The application's own security model is described in
its SECURITY.md ([Windows](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve-windows/blob/main/SECURITY.md),
[macOS](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve-macos/blob/main/SECURITY.md)).
