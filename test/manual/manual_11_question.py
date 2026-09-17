"""手动端到端验证 question 工具的弹窗交互。

运行：PYTHONPATH=$PWD python test/manual/manual_11_question.py

逐项确认：
1. 选选项后提交 → status=answered、is_free_text=false
2. 点击输入框并输入 → 自动切到"其他/自定义回答" → Enter 提交 → is_free_text=true
3. 选"其他"但留空 → 提交被拒、窗口不关、出现提示
4. Esc / 取消按钮 / 点关闭 → status=cancelled
5. 临时把第二个调用的 timeout 改为 5 → 倒计时归零自动关闭、status=timeout
"""
from src.tools.toolkits.question import question

if __name__ == "__main__":
    print(question("选择哪个数据库作为持久层？", ["PostgreSQL", "SQLite", "MySQL"], timeout=30))
    print(question("还有什么需要我注意的约束？", timeout=30))