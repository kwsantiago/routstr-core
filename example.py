import os
import openai

client = openai.OpenAI(
    api_key=os.environ["CASHU_TOKEN"],
    base_url=os.environ.get("ROUTSTR_API_URL", "https://api.routstr.com/v1"),
    # client=httpx.AsyncClient(
    #     base_url=os.environ.get("ROUTSTR_API_URL", "https://roustrjfsdgfiueghsklchg.onion/v1"),
    #     proxies=os.environ.get("ROUTSTR_PROXY", "socks5://localhost:9050"),
    # ),  # to use onion proxy (tor)
)
history: list = []


def chat():
    while True:
        user_msg = {"role": "user", "content": input("\nYou: ")}
        history.append(user_msg)
        ai_msg = {"role": "assistant", "content": ""}

        for chunk in client.chat.completions.create(
            model=os.environ.get(
                "MODEL", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
            ),
            messages=history,
            stream=True,
        ):
            if len(chunk.choices) > 0:
                ai_msg["content"] += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()
        history.append(ai_msg)


if __name__ == "__main__":
    chat()
