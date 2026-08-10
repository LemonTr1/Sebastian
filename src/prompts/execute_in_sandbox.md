# 沙箱执行工具使用说明
- 每次执行该工具时，都会在沙箱环境中创建一个全新的隔离运行空间，工具执行结束自动销毁环境。
- 执行前必须审核代码/命令内容，高危（rm -rf /、fork bomb、反弹shell、os.system("reboot") 等）→ 拒绝执行并说明危害
- 沙箱内有 /usr 只读挂载，python3/bash/gcc/g++/java 等编译器可用
- 沙箱内的pip安装，npm安装和go安装会缓存到宿主机的用户目录下，安装包和编译好的python扩展模块会持久化到宿主机的用户目录下以避免重复下载和编译。
- 沙箱内无法执行需要root权限的命令/程序，也无法获取到root权限
- Skill技能系统内的脚本执行优先使用run_script工具而不是在沙箱内执行

# 沙箱挂载规则
- 沙箱内与宿主机的文件系统完全隔离。通过 `code_file_path` 挂载时，**实际行为由代码决定，分为两种模式**：

  **① 目录模式**（code_file_path 指向目录）：
  - 该目录被**整体挂载**到沙箱的 `/workspace/<目录名>/` 下，**保留最后一级目录名**。
  - 例：`code_file_path=/home/user/Desktop/project` → 沙箱内路径为 `/workspace/project/`，其内所有文件都在 `/workspace/project/` 之下（如 `a.txt` 的正确路径是 `/workspace/project/a.txt`，**不是** `/workspace/a.txt`）。

  **② 文件模式**（code_file_path 指向文件）：
  - **该文件的父目录被整体挂载到 `/workspace/` 根**，文件平铺出现在根下，**不保留子目录层级**。
  - 例：`code_file_path=/home/user/script.py` → 沙箱内路径为 `/workspace/script.py`；但**注意**：`/home/user/` 下与 script.py **同级的其他所有文件也会一并出现在 `/workspace/` 根**。
  - ⚠️ 因此挂载文件时，`/workspace/` 下能看到的不止目标文件本身，还有其父目录的全部同级内容。

- **行为指引：挂载后如不确定目录结构，先执行 `ls /workspace` 或 `find /workspace -type f` 清点实际路径，再进行后续操作；禁止凭记忆或猜测直接拼接沙箱内路径。**
- 由于沙箱容量非常有限，秉持**最小挂载原则**，**永远**只挂载必要的，最小的文件或目录，避免挂载整个宿主机目录。
 例如：1. 运行项目(目录)：只挂载`/home/user/Desktop/project`，而不是挂载`/home/user/Desktop`或`/home/user`；2. 执行独立脚本：只挂载`/home/user/Desktop/project/script.py`，而不是挂载整个`/home/user/Desktop/project`。
- 只读模式下，沙箱内的程序/命令无法修改挂载的宿主机的文件或目录，持久化需配合专门工具完成；
- 可读写模式下，沙箱内的程序/命令对挂载的宿主机文件或目录的修改会映射到宿主机中。但涉及文件读取和持久化(如创建/删除/移动/覆写/编辑/重命名/复制/压缩/解压等)，请优先使用更安全更高效的专门工具，当前工具在此场景**优先级最低**。