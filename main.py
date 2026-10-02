import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

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
if not api_key or not model_name:
    raise SystemExit("В .env нужны key_openai и model_openai.")

# 1) Модель OpenAI из .env
llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0)


# 2) Инструмент, который агент может вызывать
@tool
def multiply(a: int, b: int) -> int:
    """Умножает два целых числа a и b."""
    return a * b


# 3) Собираем агента
agent = build_agent(llm, tools=[multiply])


def ask_agent(text: str) -> str:
    """Отправляет одно сообщение агенту и возвращает финальный ответ."""
    result = agent.invoke({"messages": [HumanMessage(content=text)]})
    return result["messages"][-1].content


# 4) Интерактивный режим
if __name__ == "__main__":
    print("Агент запущен ✅")
    print(f"Модель: {model_name}")
    print("Примеры: 'Сколько будет 7 умножить на 8?' или 'Умножь 12 на 5'")
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
