import os
import openai

client = openai.OpenAI(
    api_key=os.environ["CASHU_TOKEN"],
    base_url=os.environ.get("ROUTSTR_API_URL", "https://api.routstr.com/v1"),
)
history: list = []


def chat():
    while True:
        message = input("\nYou: ")

        for chunk in client.chat.completions.create(
            model=os.environ.get(
                "MODEL", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
            ),
            messages=history + [{"role": "user", "content": message}],
            stream=True,
        ):
            if len(chunk.choices) > 0:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()


if __name__ == "__main__":
    chat()
