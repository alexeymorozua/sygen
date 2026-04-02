# Sygen Demo Assets

Recording and promotional materials for Sygen v1.1.9.

## Recording Tools

### asciinema (Terminal Recording)

Best for lightweight terminal demos that can be embedded anywhere.

```bash
# Install
pip install asciinema

# Record a session
asciinema rec demo.cast --idle-time-limit 2

# Play back
asciinema play demo.cast

# Upload to asciinema.org (optional)
asciinema upload demo.cast
```

### Terminalizer (GIF/MP4 from Terminal)

Best for producing GIF/MP4 files from terminal sessions.

```bash
# Install (requires Node.js 16+)
npm install -g terminalizer

# Record
terminalizer record demo

# Render to GIF
terminalizer render demo -o demo.gif

# Render to MP4 (requires ffmpeg)
terminalizer render demo -o demo.mp4 --type mp4
```

### OBS Studio (Full Screen / GUI Recording)

Best for recording Telegram UI interactions, multi-window setups.

```bash
# Install (Ubuntu/Debian)
sudo apt install obs-studio

# Install (macOS)
brew install obs
```

OBS tips:
- Use 1920x1080, 30fps for social media
- Add a "Window Capture" source for the terminal
- Add a second source for the Telegram client if showing both sides

## Demo Scenarios

Each script in `scenarios/` is a self-contained terminal demo. They use
`sleep` and `echo` to simulate real interaction at a readable pace.

### How to Record

```bash
# Option A: asciinema
asciinema rec quickstart.cast -c "bash scenarios/quickstart.sh" --idle-time-limit 2

# Option B: terminalizer
terminalizer record quickstart -c "bash scenarios/quickstart.sh"
terminalizer render quickstart -o quickstart.gif
```

### Scenario List

| Script | Duration | Shows |
|---|---|---|
| `scenarios/quickstart.sh` | ~60s | Install, config, start, first message |
| `scenarios/rag-demo.sh` | ~45s | Enable RAG, restart, query with context |
| `scenarios/multi-agent.sh` | ~50s | Create sub-agent, delegate, get results |

## Social Media Templates

Ready-to-customize post templates in `social/`:

- `reddit-post.md` -- r/selfhosted launch post
- `hackernews-post.md` -- Show HN submission
- `twitter-thread.md` -- 5-tweet launch thread

## Checklist Before Publishing

- [ ] Record all three scenarios with asciinema
- [ ] Generate GIFs with terminalizer for README/social embeds
- [ ] Customize social templates with actual recording links
- [ ] Proof-read posts, remove placeholder URLs
- [ ] Test that `pip install sygen` resolves correctly in demo
