**English** · [Français](README.fr.md)

# Video Frame Expedition plugin for Claude Code

A plugin that connects Claude Code to
[Video Frame Expedition for DaVinci Resolve](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve),
a local application that analyses your rushes with a local vision model, so that an AI assistant
can edit in DaVinci Resolve knowing what each shot contains.

It brings two things:
- **the connection to the application's MCP server** (`vfe-vision`, 25 tools): analyses, semantic
  search across the library, safe cut points, reframing, and the application's own DaVinci
  Resolve tools (read the open timeline, plan a reframe, build a new timeline, add markers);
- **a skill, `resolve-editing`**, that gives Claude the method: tie the open timeline to the
  analyses, choose shots, write an edit list, get safe cuts, build or modify the edit in a new
  timeline, reframe for another aspect ratio, add markers. It holds the rules and the pitfalls of
  DaVinci Resolve Studio 21.1's scripting API, measured, and tested script templates.

## Requirements

- **Video Frame Expedition for DaVinci Resolve 1.1.1 or newer**, installed and running, on
  Windows 11 or on a Mac with Apple Silicon: see [its README](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve#readme). LM Studio can run
  on the same computer or on another one, under Windows, macOS or Linux.
- **Claude Code**, on the application's computer or on another one (settings below).
- For editing: **DaVinci Resolve Studio 21.1 or later**, under Windows, macOS or Linux. With the
  "Resolve tools for the assistant" box (Connections page), the application drives Resolve even
  on another computer: the AI assistant, the application and Resolve can be on three different
  computers. For the rest (cross-dissolves, effects), DaVinci Resolve Studio's MCP server only
  drives the Resolve of its own computer: add it to Claude Code on that computer (Resolve offers
  it under File › Setup AI Assistants).
- For the helper scripts of the skill: Python 3, with Windows PowerShell on Windows or
  `osascript` (part of macOS) on a Mac.

## Install

In Claude Code:

```text
/plugin marketplace add VideoFrameExpedition/video-frame-expedition-claude-plugin
/plugin install video-frame-expedition@video-frame-expedition
```

Then confirm the options with `/plugin configure video-frame-expedition@video-frame-expedition`:

| Option | Value |
|---|---|
| Application address | `http://127.0.0.1:8765/mcp` (default) when the application runs on this computer; otherwise its address on your local network or Tailscale, such as `http://100.64.12.34:8765/mcp` |
| Access token | Leave it empty on the application's own computer. From another computer: the token shown on the application's Connections page (stored in your system's secure credential store) |

If you had already added the server yourself (`claude mcp add … vfe-vision`), remove that entry so
that Claude Code keeps a single connection.

## Use

Ask in your own words, for instance:
- "Look at the timeline open in Resolve and tell me what each clip contains."
- "Build a 45-second edit of the lake videos, with safe cuts."
- "Make a 9:16 version of this timeline, framed on the people."

Claude uses the skill on its own when a request is about editing in Resolve; you can also call
it with `/video-frame-expedition:resolve-editing`.

Claude never edits your timeline in place: the application's tools build a new timeline, and the
skill duplicates a timeline before changing it. The project is not saved for you: save it in
Resolve when you keep the edit.

## What the plugin contacts

Only the application, at the address you set. The skill's helper scripts call the same address
(read-only tools). DaVinci Resolve's own MCP server, if you add it, is separate from this plugin.
Nothing else is downloaded or sent.

The plugin has no hooks: nothing runs on its own. The skill's scripts (Python, plus PowerShell on
Windows or JavaScript for Automation on macOS) run only when Claude calls them for a task you asked for, and they download nothing. To report a
vulnerability, see [SECURITY.md](SECURITY.md).

## Licence

[Apache License 2.0](LICENSE). See also [NOTICE](NOTICE).

Not affiliated with or endorsed by Blackmagic Design or Anthropic; DaVinci Resolve and Claude are
trademarks of their respective owners.
