# Troubleshooting

[Back to the README](../README.md)

Common issues and their resolutions when operating ChaosticTool.

## 1. Terminal & PTY Issues

### Error: `termios` or `pty` module unavailable
- **Cause**: Pseudo-terminals are a POSIX kernel primitive. If running on native Windows without WSL, the CLI falls back to standard pipe execution.
- **Fix**: For interactive terminal tools on Windows, use the embedded WSL2 Kali Linux backend enabled in Settings, or run ChaosticTool inside Windows Terminal.

### ANSI colors not showing in CLI
- **Fix**: Verify your terminal supports ANSI escape sequences. Ensure `NO_COLOR` is not set in your environment:
  ```bash
  unset NO_COLOR
  export TERM=xterm-256color
  ```

---

## 2. Desktop Interface (GUI)

### Error: `could not connect to display` / headless crash
- **Cause**: Qt requires an X11 or Wayland server.
- **Fix**: When running on a remote headless server or continuous integration runner, set:
  ```bash
  export QT_QPA_PLATFORM=offscreen
  ```
  Or run inside a virtual frame buffer:
  ```bash
  xvfb-run -a chaostictool-desktop
  ```

### High CPU usage with animations on remote desktop
- **Fix**: Enable static rendering:
  ```bash
  export CHAOSTIC_REDUCED_MOTION=1
  ```
  Or toggle **Reduced Motion** in the application Settings.

---

## 3. Offensive Tools & Permissions

### Error: Tool requires root privileges (e.g. `nmap -sS`)
- **Cause**: Raw socket SYN scans require `CAP_NET_RAW` or root permissions.
- **Fix**:
  - On Linux: Grant capabilities or launch with `sudo`:
    ```bash
    sudo setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)
    ```
  - On Windows: Enable the privileged execution profile in Settings, which delegates to Kali Linux under WSL2.
