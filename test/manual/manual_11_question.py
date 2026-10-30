"""手动端到端验证 question 工具的终端交互。

运行：PYTHONPATH=$PWD python test/manual/manual_11_question.py

逐项确认：
1. 输入选项编号 → status=answered、is_free_text=false
2. 输入任意文本 → status=answered、is_free_text=true
3. 输入空行 → 重新提示，不返回
4. Ctrl-C / Ctrl-D → status=cancelled
5. 把 timeout 改为 5 → 到点自动返回 status=timeout
"""
from src.tools.toolkits.question import question

if __name__ == "__main__":
    print(question("选择哪个数据库作为持久层？", ["PostgreSQL", "SQLite", "MySQL"], timeout=30))
    print(question("还有什么需要我注意的约束？", timeout=30))
