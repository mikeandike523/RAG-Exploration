import prompt_toolkit
from termcolor import colored

from run_mistral import Mistral, UnfinishedResponseError, OutOfTokensError, OutOfMemoryError


TOP_P=0.9
TEMPERATURE=0.6

mistral = Mistral(quantization="8bit")

def main():
    messages = []
    
    running=True
    while running:
        prompt = prompt_toolkit.prompt("Enter a prompt, or type !quit to quit: ").strip()
        if prompt == "!quit":
            running=False
            break

        # Complete with unlimted tokens        
        messages.append({
            "role":"user",
            "content":prompt
        })
        try:
            result = mistral.completion(
                {
                        "messages":messages,
                        "top_p":TOP_P,
                        "temperature": TEMPERATURE,
                        "max_tokens":1024
                }
            ).strip()
            messages.append({
                "role":"assistant",
                "content":result
            })
            print(colored(result,"green"))
        except OutOfTokensError as e:
            print("OutOfTokensError", e.total_tokens, e.budget)
        except UnfinishedResponseError as e:
            print("UnfinishedResponseError", e.max_new_tokens, e.generation)
        except OutOfMemoryError as e:
            print("OutOfMemoryError", e.device_or_devices, e.used, e.requested)
        except Exception as e:
            print(str(e))

    print("Goodbye!")

if __name__ == "__main__":
    main()