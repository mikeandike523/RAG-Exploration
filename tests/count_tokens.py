
from termcolor import colored
import prompt_toolkit
from transformers import AutoTokenizer

from src.mistral import MODEL_ID

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
while True:
    prompt = prompt_toolkit.prompt("Enter a word or phrase, or type '!quit' to quit: ").strip()

    if prompt == '!quit':
        print("Goodbye!")
        exit()

    tokens = tokenizer.encode(prompt, return_tensors='pt').squeeze().tolist()

    while tokens[0] == tokenizer.bos_token_id:
        tokens = tokens[1:]  # Remove the BOS token

    print(tokens)

    # Use termcolor to make a readout of hte text decoded, but each inviduidual token is colored blue or magenta alternating.

    for i, token in enumerate(tokens):
        if i % 2 == 0:
            color = "blue"
        else:
            color = "magenta"
        print(colored(tokenizer.decode([token]).replace(" ","_"), color), end="")
    print("")
        


