import json
import subprocess

from app.models.change import Change, ChangeAnalysis


class OpenCodeClient:
    def __init__(self, command: str = "opencode"):
        self.command = command

    def run(self, prompt: str) -> str:
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
        )

        chunks: list[str] = []

        for line in result.stdout.splitlines():
            if not line.strip():
                continue

            event = json.loads(line)

            if event.get("type") == "text":
                text = event.get("part", {}).get("text")

                if text:
                    chunks.append(text)

        if not chunks:
            raise RuntimeError(
                "OpenCode completed without returning a text response."
            )

        return "".join(chunks)