import src.Modules.CodeModules.CodeSessionBuffer
from src.Modules.CodeModules.CodeSessionBuffer import code_session_buffer

def main():
    for i in range(5):
        code_session_buffer.write({"role": "user", "content": "你好"})
        print(code_session_buffer.read_all())

if __name__ == "__main__":
    main()