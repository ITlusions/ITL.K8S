#!/usr/bin/env python3
"""Open a tmux session watching all itl-website and WAF activity live.

Builds a tmux session (inside WSL, since this must run from Windows) with:
  - window "monitor": itl-website app logs, Traefik access log (filtered to
    itlusions.nl), pod status watch, k8s events watch
  - window "waf": modsecurity-crs ModSecurity audit log, pod status watch

Re-running kills and recreates the session, so it's always safe to re-run
after redeploys. Needs WSL with a distro that has tmux and a working
kubectl context (see WSL_DISTRO below) - run with no arguments.

Usage: python3 scripts/cluster/tmux_monitor_itl_website.py
"""
from __future__ import annotations

import subprocess
import sys
import time

WSL_DISTRO = "Ubuntu-24.04"
SESSION = "itl-website"

WEBSITE_NAMESPACE = "itl-website"
WEBSITE_SELECTOR = "app.kubernetes.io/name=itl-website"
TRAEFIK_NAMESPACE = "traefik"
TRAEFIK_SELECTOR = "app.kubernetes.io/name=traefik"
WAF_SELECTOR = "app=modsecurity-crs"
ACCESS_LOG_HOST_FILTER = "itlusions"


def wsl_bash(command: str) -> str:
    """Run a command inside the WSL distro's login bash, returning stdout."""
    result = subprocess.run(
        ["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc", command],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def tmux(*args: str) -> str:
    return wsl_bash("tmux " + " ".join(args))


def split_and_run(pane_id: str, direction: str, command: str) -> str:
    """Split `pane_id`, run `command` in the new pane, return its pane ID.

    Targets panes by tmux's stable #{pane_id} (e.g. %3), not by window.index -
    the index of a given pane shifts as the layout grows, since tmux
    renumbers panes by screen position rather than creation order, so a
    hardcoded "window.N" target silently drifts onto the wrong pane after a
    couple of splits.
    """
    new_pane_id = tmux(
        "split-window", direction, "-t", f"'{pane_id}'",
        "-P", "-F", "'#{pane_id}'",
    )
    tmux("send-keys", "-t", f"'{new_pane_id}'", f"'{command}'", "C-m")
    return new_pane_id


def new_window_and_run(window_name: str, command: str) -> str:
    pane_id = tmux(
        "new-window", "-t", SESSION, "-n", window_name,
        "-P", "-F", "'#{pane_id}'",
    )
    tmux("send-keys", "-t", f"'{pane_id}'", f"'{command}'", "C-m")
    return pane_id


def main() -> None:
    subprocess.run(
        ["wsl", "-d", WSL_DISTRO, "--", "tmux", "kill-session", "-t", SESSION],
        check=False,  # fine if no prior session exists
    )

    app_logs = (
        f"kubectl logs -f -n {WEBSITE_NAMESPACE} -l {WEBSITE_SELECTOR} "
        "--all-containers --prefix --tail=50"
    )
    first_pane = tmux(
        "new-session", "-d", "-s", SESSION, "-n", "monitor",
        "-P", "-F", "'#{pane_id}'",
    )
    tmux("send-keys", "-t", f"'{first_pane}'", f"'{app_logs}'", "C-m")

    access_log = (
        f"kubectl logs -f -n {TRAEFIK_NAMESPACE} -l {TRAEFIK_SELECTOR} --tail=20 "
        f"| grep --line-buffered -i {ACCESS_LOG_HOST_FILTER}"
    )
    right_pane = split_and_run(first_pane, "-h", access_log)

    pod_watch = f"kubectl get pods -n {WEBSITE_NAMESPACE} -o wide --watch"
    split_and_run(first_pane, "-v", pod_watch)

    events_watch = f"kubectl get events -n {WEBSITE_NAMESPACE} --watch"
    split_and_run(right_pane, "-v", events_watch)

    waf_logs = f"kubectl logs -f -n {TRAEFIK_NAMESPACE} -l {WAF_SELECTOR} --tail=50"
    waf_pane = new_window_and_run("waf", waf_logs)

    waf_pod_watch = f"kubectl get pods -n {TRAEFIK_NAMESPACE} -l {WAF_SELECTOR} -o wide --watch"
    split_and_run(waf_pane, "-v", waf_pod_watch)

    tmux("select-window", "-t", f"'{SESSION}:monitor'")
    tmux("select-pane", "-t", f"'{first_pane}'")

    # give kubectl a moment to connect before handing back control
    time.sleep(1)

    print(f"tmux session '{SESSION}' ready. Attach with:")
    print(f"  wsl -d {WSL_DISTRO} -- tmux attach -t {SESSION}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: command failed: {e}", file=sys.stderr)
        sys.exit(1)
