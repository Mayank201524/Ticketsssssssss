import json
import subprocess


class OpenCodeClient:
    """Adapter around the local OpenCode CLI."""

    def __init__(
        self,
        command: str = "opencode",
        timeout_seconds: int = 300,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def run(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                [
                    self.command,
                    "run",
                    "--format",
                    "json",
                    prompt,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"OpenCode executable '{self.command}' was not found. "
                "Make sure OpenCode is installed and available on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"OpenCode timed out after {self.timeout_seconds} seconds."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "unknown error"
            raise RuntimeError(
                f"OpenCode failed with exit code {exc.returncode}: {stderr}"
            ) from exc

        chunks: list[str] = []

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"OpenCode returned an invalid JSON event: {line[:200]}"
                ) from exc

            if event.get("type") != "text":
                continue

            part = event.get("part")
            if not isinstance(part, dict):
                continue

            text = part.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)

        if not chunks:
            raise RuntimeError(
                "OpenCode completed without returning a text response."
            )

        return "".join(chunks)