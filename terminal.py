"""Interactive login shell in a controlling Unix PTY, rendered by pyte."""
from __future__ import annotations

import codecs
import copy
import os
import queue
import select
import shutil
import shlex
import signal
import struct
import subprocess
import sys
import threading
import secrets
from pathlib import Path

import pyte


class TerminalScreen(pyte.HistoryScreen):
    def __init__(self, columns, lines, send):
        self.send = send
        self.alternate = False
        self.saved_screen = None
        super().__init__(columns, lines, history=2000, ratio=.25)

    def write_process_input(self, data):
        self.send(data.encode())

    def set_mode(self, *modes, **kwargs):
        if kwargs.get("private") and any(mode in (47, 1047, 1049) for mode in modes) and not self.alternate:
            self.saved_screen = {name: copy.deepcopy(getattr(self, name))
                                 for name in ("buffer", "cursor", "history", "margins", "savepoints", "mode")}
            self.reset()
            self.alternate = True
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        super().reset_mode(*modes, **kwargs)
        if kwargs.get("private") and any(mode in (47, 1047, 1049) for mode in modes) and self.alternate:
            for name, value in self.saved_screen.items():
                setattr(self, name, value)
            self.alternate = False
            self.saved_screen = None
            self.dirty.update(range(self.lines))


class ShellTerminal:
    def __init__(self, project: Path, columns=132, lines=36, shell=None):
        self.project = project.resolve()
        self.columns, self.lines = columns, lines
        self.master = None
        self.process = None
        self.output = queue.Queue()
        self.error = ""
        self.bytes_received = 0
        self.screen = TerminalScreen(columns, lines, self.send)
        self.stream = pyte.Stream(self.screen)
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.reader = None
        self.shell = shell or os.environ.get("SHELL", "/bin/zsh" if sys.platform == "darwin" else "/bin/bash")
        self.phone_marker = ""
        self.phone_command = ""
        self.screen_binary = shutil.which("screen") if sys.platform == "darwin" else None
        self.screen_session = f"openrpg-{os.getuid()}-{secrets.token_hex(4)}"

    @property
    def shell_name(self):
        return Path(self.shell).name

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.running:
            return
        binary = shutil.which(self.shell)
        if not binary:
            self.error = f"Shell tidak ditemukan: {self.shell}"
            return
        if os.name != "posix":
            self.error = "Terminal tertanam saat ini mendukung macOS dan Linux."
            return
        import fcntl
        import pty
        import termios

        self.close()
        self.error = ""
        self.bytes_received = 0
        self.screen.alternate = False
        self.screen.saved_screen = None
        self.screen.reset()
        self.decoder.reset()
        self.project.mkdir(parents=True, exist_ok=True)
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", self.lines, self.columns, 0, 0))
        env = os.environ.copy()
        env.update(TERM="xterm-256color", COLORTERM="truecolor", COLUMNS=str(self.columns), LINES=str(self.lines))
        # GUI-launched apps can inherit LC_ALL=C, which makes GNU screen
        # replace Braille, box-drawing, and other TUI glyphs with question marks.
        env.pop("LC_ALL", None)
        env["LANG"] = "en_US.UTF-8"
        env["LC_CTYPE"] = "en_US.UTF-8"
        try:
            command = [sys.executable, str(Path(__file__).resolve()), "--pty-child", binary]
            if self.screen_binary:
                command.extend(("--screen", self.screen_binary, "--session", self.screen_session))
            self.process = subprocess.Popen(
                command,
                stdin=slave, stdout=slave, stderr=slave,
                cwd=self.project, env=env, start_new_session=True,
            )
        except OSError as exc:
            self.error = str(exc)
            os.close(self.master)
            self.master = None
        finally:
            os.close(slave)
        if self.running:
            self.reader = threading.Thread(target=self._read, args=(self.master, self.process), daemon=True)
            self.reader.start()

    def _read(self, master, process):
        while process.poll() is None:
            try:
                if select.select([master], [], [], 0.1)[0]:
                    data = os.read(master, 65536)
                    if not data:
                        break
                    self.output.put(data)
            except (OSError, ValueError):
                break

    def poll(self):
        # Parse on the game thread, keeping the renderer and terminal buffer in sync.
        for _ in range(128):
            try:
                data = self.output.get_nowait()
            except queue.Empty:
                break
            self.bytes_received += len(data)
            decoded = self.decoder.decode(data)
            # Modern TUIs query the terminal's capabilities before rendering.
            if "\x1b[>c" in decoded or "\x1b[>0c" in decoded:
                self.send(b"\x1b[>0;136;0c")
            if "\x1b[?u" in decoded:
                self.send(b"\x1b[?0u")
            if "\x1b[?2026$p" in decoded:
                self.send(b"\x1b[?2026;2$y")
            self.stream.feed(decoded)

    def send(self, data: bytes):
        if self.master is not None and self.running:
            try:
                os.write(self.master, data)
            except OSError:
                pass

    def paste(self, text):
        data = text.encode("utf-8")
        if 2004 << 5 in self.screen.mode:
            data = b"\x1b[200~" + data + b"\x1b[201~"
        self.send(data)

    def run_from_phone(self, command):
        """Run a typed command in the real login shell and append a detectable completion marker."""
        if not command.strip():
            return "Tulis perintah atau prompt dahulu."
        if not self.running:
            self.start()
        if not self.running:
            return self.error or "Terminal tidak tersedia."
        token = secrets.token_hex(6)
        marker = f"__OPENRPG_PHONE_DONE_{token}__"
        escaped = "".join(f"\\{ord(char):03o}" for char in marker)
        self.phone_marker = marker
        self.phone_command = command
        self.send((command + f"; printf '{escaped}\\n'\r").encode("utf-8"))
        return "Prompt dikirim ke terminal. Saya akan memberi notifikasi saat perintah selesai."

    def open_external(self):
        """Open a native Terminal.app client attached to this exact shell session."""
        if not self.running:
            self.start()
        if not self.running:
            return self.error or "Terminal belum dapat dijalankan."
        if not self.screen_binary:
            return "Agar Terminal.app berbagi sesi yang sama, utilitas screen perlu tersedia di macOS."
        osascript = shutil.which("osascript")
        if not osascript:
            return "AppleScript Terminal.app tidak tersedia di sistem ini."
        shell_command = (f"cd {shlex.quote(str(self.project))} && "
                         f"{shlex.quote(self.screen_binary)} -U -x -S {shlex.quote(self.screen_session)}")
        applescript_command = shell_command.replace("\\", "\\\\").replace('"', '\\"')
        script = ("tell application \"Terminal\"\n"
                  "  activate\n"
                  f"  do script \"{applescript_command}\"\n"
                  "end tell")
        try:
            result = subprocess.run([osascript, "-e", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Terminal.app gagal dibuka: {exc}"
        if result.returncode:
            return "Terminal.app gagal dibuka: " + (result.stderr.strip() or "AppleScript mengembalikan error.")
        return "Terminal.app dibuka pada sesi yang sama. Input dan layar tersinkron dengan terminal game dan ponsel."

    def scroll(self, pages):
        if self.screen.alternate:
            return
        for _ in range(abs(pages)):
            (self.screen.prev_page if pages > 0 else self.screen.next_page)()

    def return_to_bottom(self):
        while self.screen.history.position < self.screen.history.size:
            self.screen.next_page()

    def close(self):
        if self.running:
            # HUP lets the shell notify its jobs before the PTY is closed.
            try:
                os.killpg(self.process.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
        self.master = None
        if self.reader:
            self.reader.join(timeout=0.3)
            self.reader = None
        while not self.output.empty():
            self.output.get_nowait()


def pty_child(shell, screen=None, session=None):
    import fcntl
    import termios
    # Popen created a new session. Acquire the slave as its controlling terminal
    # so job control and Ctrl+C target the foreground command, just like Terminal.app.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.tcsetpgrp(0, os.getpgrp())
    if screen:
        os.execvpe(screen, [screen, "-U", "-D", "-RR", "-S", session or "openrpg", shell, "-il"], os.environ)
    os.execvpe(shell, [shell, "-il"], os.environ)


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "--pty-child":
    shell = sys.argv[2]
    screen = sys.argv[4] if len(sys.argv) >= 5 and sys.argv[3] == "--screen" else None
    session = sys.argv[6] if screen and len(sys.argv) >= 7 and sys.argv[5] == "--session" else None
    pty_child(shell, screen, session)
