import time

import requests
import prompt_toolkit
from termcolor import colored
from transformers import AutoTokenizer

MODEL="mistralai/Mistral-Nemo-Instruct-2407"
TEMPERATURE=0.6
TOP_P=0.9

url = "http://localhost:8008/v1/chat/completions"

MAX_SEQ_LENGTH=8192
SPEC_TOK_BUFFER=8 # eos, sep, pad, INST, etc.

tokenizer = AutoTokenizer.from_pretrained(MODEL)
tokenizer.pad_token_id = tokenizer.eos_token_id

def count_conversation_tokens(messages):
    tokens=tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
    )["input_ids"].squeeze().tolist()


    num_tokens = len(tokens)

    return num_tokens

def get_max_tokens(messages):
    num_tokens = count_conversation_tokens(messages)

    return MAX_SEQ_LENGTH - num_tokens - SPEC_TOK_BUFFER

def main():
    messages = []

    while True:

        question = prompt_toolkit.prompt("Enter a question, or type '!quit' to quit: ").strip()

        if question == "!quit":
            print("Goodbye!")
            exit()

        messages.append({"role": "user", "content": question})

        max_tokens = get_max_tokens(messages)

        print(colored(f"Conversation Token Count: {count_conversation_tokens(messages)}","cyan"))
        print(colored(f"Max (New) Tokens: {max_tokens}","yellow"))

        start_time = time.time()

        try:
            response = requests.post(url, json={
                "max_tokens": max_tokens,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "messages": messages,
            })

            response.raise_for_status()

            completion = response.json()["choices"][0]["message"]["content"]

            print(colored(completion, "green"))

            messages.append({"role": "assistant", "content": completion})

            end_time = time.time()

            print(colored(f"Execution Time: {end_time - start_time:.2f} seconds", "blue"))
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
    


if __name__ == "__main__":
    main()