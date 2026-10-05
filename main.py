import asyncio
import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from typing import Annotated, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, field_validator

try:
    from langchain.agents import create_agent as _create_agent

    def build_agent(llm, tools):
        return _create_agent(llm, tools=tools)

except Exception:
    from langgraph.prebuilt import create_react_agent as _create_react_agent

    def build_agent(llm, tools):
        return _create_react_agent(llm, tools=tools)


load_dotenv()

api_key = os.getenv("key_openai")
model_name = os.getenv("model_openai")
public_api_key = os.getenv("LANGFLOW_API_KEY")
flow_id = os.getenv("LANGFLOW_FLOW_ID")

_required = {
    "key_openai": api_key,
    "model_openai": model_name,
    "LANGFLOW_API_KEY": public_api_key,
    "LANGFLOW_FLOW_ID": flow_id,
}
_missing = [name for name, value in _required.items() if not value]
if _missing:
    raise SystemExit("В .env нужны: " + ", ".join(_missing) + ".")

# 1) Модель OpenAI из .env
llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0)

_NUMBER = re.compile(r"-?\d+(\.\d{1,3})?")
_agent_lock = asyncio.Lock()


class ProductNotReady(Exception):
    """Агент завершился, не вызвав инструмент с тем же произведением."""


def normalize_number(value: object) -> str:
    """Принимает целое или дробь не более чем с 3 знаками после запятой."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(
            "Каждое число должно быть целым или дробью не более чем с 3 знаками после запятой."
        )
    if isinstance(value, float):
        text = format(Decimal(str(value)), "f")
    elif isinstance(value, int):
        text = str(value)
    else:
        text = value.strip().replace(",", ".")
    if not _NUMBER.fullmatch(text):
        raise ValueError(
            "Каждое число должно быть целым или дробью не более чем с 3 знаками после запятой."
        )
    return format(Decimal(text), "f")


def format_product(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def multiply_values(numbers: list[str]) -> str:
    if not 2 <= len(numbers) <= 5:
        raise ValueError("Нужно от 2 до 5 чисел.")
    product = Decimal("1")
    for raw in numbers:
        product *= Decimal(normalize_number(raw))
    return format_product(product)


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


# 2) Инструмент, который агент может вызывать
@tool
def multiply(numbers: list[str]) -> str:
    """Перемножает от 2 до 5 чисел.

    Каждое число передавай строкой: целое или дробь не больше чем с 3 знаками
    после запятой. Пример: ["1.5", "2", "-0.25"].
    """
    return multiply_values(numbers)


# 3) Собираем агента
agent = build_agent(llm, tools=[multiply])


def ask_agent(text: str) -> str:
    """Отправляет одно сообщение агенту и возвращает финальный ответ."""
    result = agent.invoke({"messages": [HumanMessage(content=text)]})
    return message_text(result["messages"][-1].content)


def invoke_agent(numbers: list[str]) -> str:
    """Просит агента перемножить числа и сверяет ответ инструмента."""
    expected = Decimal(multiply_values(numbers))
    prompt = (
        "Перемножь эти числа инструментом multiply. "
        "Передай их списком строк без изменений: "
        + ", ".join(numbers)
    )
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    messages = result["messages"]
    matched = False
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name != "multiply":
            continue
        if getattr(message, "status", "success") == "error":
            continue
        try:
            if Decimal(message_text(message.content)) == expected:
                matched = True
        except InvalidOperation:
            continue
    if not matched:
        raise ProductNotReady
    return message_text(messages[-1].content)


class RunBody(BaseModel):
    numbers: list[str]

    @field_validator("numbers", mode="before")
    @classmethod
    def validate_numbers(cls, values: object) -> list[str]:
        if not isinstance(values, list):
            raise ValueError("Поле numbers должно быть списком.")
        if not 2 <= len(values) <= 5:
            raise ValueError("Нужно от 2 до 5 чисел.")
        return [normalize_number(item) for item in values]


class RunResponse(BaseModel):
    product: str
    answer: str


app = FastAPI()


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "up"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/run/{requested_flow_id}", response_model=RunResponse)
async def run_flow(
    requested_flow_id: str,
    body: RunBody,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> RunResponse:
    if x_api_key is None or not secrets.compare_digest(x_api_key, public_api_key):
        raise HTTPException(status_code=401, detail="Неверный API-ключ")
    if not secrets.compare_digest(requested_flow_id, flow_id):
        raise HTTPException(status_code=404, detail="Сценарий не найден")
    try:
        async with _agent_lock:
            answer = await asyncio.to_thread(invoke_agent, body.numbers)
    except ProductNotReady:
        raise HTTPException(status_code=502, detail="Агент не вернул произведение") from None
    return RunResponse(product=multiply_values(body.numbers), answer=answer)


# 4) Интерактивный режим
if __name__ == "__main__":
    print("Агент запущен ✅")
    print(f"Модель: {model_name}")
    print("Примеры: 'Сколько будет 7 умножить на 8?' или 'Умножь 1.5, 2 и -0.25'")
    print("Выход: exit / quit\n")

    while True:
        user_text = input("Ты: ").strip()
        if user_text.lower() in ("exit", "quit"):
            print("Пока 👋")
            break

        try:
            answer = ask_agent(user_text)
            print("Агент:", answer, "\n")
        except Exception as e:
            print("Ошибка:", e)
            print("Проверь key_openai и model_openai в .env и доступ к api.openai.com.\n")
