# Remote access & updates — furby-photobooth

Quick reference for connecting to the Pi from the laptop (Git Bash) and pushing
code updates to the running booth. Assumes Tailscale is running on both machines.

---

## 1. Connect

Open **Git Bash** on the laptop:

```bash
ssh kalekat@furby-photobooth
```

- It will ask for **kalekat's password** (the Pi login password, not Tailscale).
- Nothing appears as you type the password — that's normal. Hit Enter.
- You're in when you see the `kalekat@raspberrypi` prompt.

If the name doesn't resolve, use the Tailscale IP directly:

```bash
ssh kalekat@100.105.222.81
```

(Confirm both machines show **Connected** in the Tailscale admin console if
neither works.)

## 2. Watch the booth (live logs)

```bash
journalctl -u photobooth -f
```

Leave it tailing to watch visits happen in real time. **Ctrl+C** to exit the
live tail. For a scrollback view instead:

```bash
journalctl -u photobooth -n 100        # q to quit the pager
```

## 3. Update the code

The service runs whatever code was on disk when it started — pulling new code
does nothing until you restart it. Full update flow:

```bash
cd ~/Desktop/receipt-photobooth
git pull
sudo systemctl restart photobooth
systemctl status photobooth            # should read: active (running)
```

Then confirm it came up clean:

```bash
journalctl -u photobooth -n 20         # look for "photobooth ready ... waiting for motion"
```

### If the update changed `deploy/photobooth.service`

The installed copy lives in `/etc/systemd/system`, so re-copy and reload:

```bash
sudo cp deploy/photobooth.service /etc/systemd/system/photobooth.service
sudo systemctl daemon-reload
sudo systemctl restart photobooth
```

### If the update added Python dependencies

```bash
cd ~/Desktop/receipt-photobooth/app
pip3 install -r requirements.txt --break-system-packages
sudo systemctl restart photobooth
```

## 4. Disconnect

```bash
exit
```

(or Ctrl+D). The service keeps running on the Pi — it doesn't depend on your
SSH session.

---

## Cheat sheet

| Task | Command |
|---|---|
| Connect | `ssh kalekat@furby-photobooth` |
| Live logs | `journalctl -u photobooth -f` (Ctrl+C to stop) |
| Restart booth | `sudo systemctl restart photobooth` |
| Check status | `systemctl status photobooth` |
| Stop booth | `sudo systemctl stop photobooth` |
| Leave SSH | `exit` |
