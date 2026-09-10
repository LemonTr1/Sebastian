from src.utils.load_prompt import get_prompt_loader

if __name__ == "__main__":
    print(get_prompt_loader().load_prompt("bash"))