#!/usr/bin/env python3
"""Страница умножения: браузер говорит только с этим сервером."""

import json
import os
import re
import sys
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PAGE = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
NUMBER = re.compile(r"-?\d+(\.\d{1,3})?")
HOST = "127.0.0.1"
PORT = 8080


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Нужна переменная {name}.")
    return value


API_KEY = require_env("LANGFLOW_API_KEY")
FLOW_ID = require_env("LANGFLOW_FLOW_ID")
NED_URL = require_env("LANGFLOW_URL").rstrip("/")
ENDPOINT = f"{NED_URL}/api/v1/run/{FLOW_ID}"


def normalize_number(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Каждое число должно быть целым или дробью не более чем с 3 знаками после запятой."
        )
    text = value.strip().replace(",", ".")
    if not NUMBER.fullmatch(text):
        raise ValueError(
            "Каждое число должно быть целым или дробью не более чем с 3 знаками после запятой."
        )
    return format(Decimal(text), "f")


def multiply_on_ned(numbers: list[str]) -> str:
    request = Request(
        ENDPOINT,
        data=json.dumps({"numbers": numbers}).encode(),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("X-API-Key", API_KEY)
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Не удалось вычислить произведение.") from exc
    product = payload.get("product")
    if not isinstance(product, str) or not product:
        raise RuntimeError("Не удалось вычислить произведение.")
    return product


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/":
            self.respond(404, {"detail": "Не найдено"})
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/multiply":
            self.respond(404, {"detail": "Не найдено"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.respond(400, {"detail": "Некорректный запрос."})
            return
        if length < 0 or length > 10_000:
            self.respond(400, {"detail": "Некорректный запрос."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode())
            raw_numbers = payload["numbers"]
            if not isinstance(raw_numbers, list) or not 2 <= len(raw_numbers) <= 5:
                raise ValueError("Нужно от 2 до 5 чисел.")
            numbers = [normalize_number(item) for item in raw_numbers]
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Некорректный запрос."
            self.respond(400, {"detail": message})
            return
        try:
            product = multiply_on_ned(numbers)
        except RuntimeError as exc:
            self.respond(502, {"detail": str(exc)})
            return
        self.respond(200, {"product": product})

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Страница слушает http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
