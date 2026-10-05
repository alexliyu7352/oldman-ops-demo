# Oldman 运维工具 Demo

一个服务器维护工具：终端里的编号菜单，改 sshd、sysctl、nginx 站点，重启服务，清理数据库里的操作记录。它演示 Oldman 的三块能力：

- [终端交互 `oldman.cli.tui`](https://github.com/alexliyu7352/oldman/blob/main/docs/public/zh/developers/tui.md)：菜单、提问、表单、表格、等待提示、预置答案；
- [运维原语 `oldman.ops`](https://github.com/alexliyu7352/oldman/blob/main/docs/public/zh/developers/ops.md)：可反复执行的配置文件编辑、os-release、systemd；
- [远程文件 `oldman.cli.remote`](https://github.com/alexliyu7352/oldman/blob/main/docs/public/zh/developers/remote.md)：菜单里的一部分功能是本仓库 [`remote/`](remote/) 下的文件，工具运行时从 GitHub 读取。

**所有改动都落在项目自己的沙箱 `var/root` 里**，systemd 由 [`bin/fake_systemctl.py`](bin/fake_systemctl.py) 顶替，所以可以在任何机器上放心运行；「系统信息」只读取本机的 `/etc/os-release`。换成真实服务器见最后一节。

## 安装

需要 Oldman 0.5 系列，0.5.0 及以上（tui、ops、remote 随 0.4.0 发布）。开发框架本身时，也可以按框架文档在本项目的 `.venv` 里 [editable 安装框架源码](https://github.com/alexliyu7352/oldman/blob/main/docs/public/zh/agents/create-service.md#新项目使用本地-python-源码)。从包索引安装：

```bash
uv sync
```

然后初始化配置和数据库：

```bash
./run.sh ops settings init   # 以 data/ops_settings.example.yaml 为模板生成 data/ops_settings.yaml
./run.sh db migrate          # 新数据库会问两次:选 first use,再选 all
```

## 运行

```bash
./run.sh ops menu            # 打开菜单;第一次运行时从 apps/ops/sample_root 建立沙箱
./run.sh ops menu --once     # 执行一个动作就结束
```

| 菜单项 | 来自 | 演示 |
| --- | --- | --- |
| 系统信息 | 本地 | 读 os-release、systemd 状态，表格 |
| SSH 端口 | 本地 | 带校验的提问；改 `Port`，Ubuntu 22.04 及以后另写 ssh.socket 的 override，再重启 ssh |
| 添加站点 | 本地 | 表单（记住上次的答案）、重载 nginx |
| Nginx | [`remote/nginx.py`](remote/nginx.py) | 远程文件自带的菜单，按沙箱里现有的站点生成；删除站点 |
| 安全检查 | [`remote/security.py`](remote/security.py) | 检查 sshd 设置；多选要修复的项，进度条逐项修改 |
| 内核参数 | [`remote/tuning.py`](remote/tuning.py) | 取远程数据文件 [`remote/data/sysctl.conf`](remote/data/sysctl.conf)，写进 sysctl.conf 的标记块 |
| 清理操作记录 | [`remote/cleanup.py`](remote/cleanup.py) | 远程文件直接用工具的模型和数据库删除旧记录 |
| 热修复 | [`remote/hotfix.sh`](remote/hotfix.sh) | 前台运行的 bash 脚本，`read` 直接读终端 |
| 操作记录 | 本地 | 数据库里的操作记录 |
| 更新远程文件 | 本地 | 等待提示；重新下载已缓存的远程文件 |
| 重置沙箱 | 本地 | 把沙箱恢复成样例 |

按 Ctrl-C：在表单里是放弃这次填写、回到菜单；在菜单上等于选 0，子菜单返回上一级，顶层菜单退出。

## 远程文件

[`data/ops_settings.example.yaml`](data/ops_settings.example.yaml) 里的 `remote_base` 是远程文件的基础地址：

```yaml
app_settings:
  ops:
    remote_base: https://raw.githubusercontent.com/alexliyu7352/oldman-ops-demo/main/remote
```

- 第一次用到的文件下载到 `data/remote/`，之后离线也能用；「更新远程文件」重新下载。
- 开发时把它改成 `remote_base: remote`（本仓库的目录），改完文件重新运行就能看到，不用推送。
- 这里用 `main` 分支是为了演示更新；生产上把它换成标签或提交号，每次运行的代码就是确定的。
- 远程 Python 文件导出 `async def run()` 或 `async def menu()`，从 [`apps/ops/toolkit.py`](apps/ops/toolkit.py) 取沙箱路径、systemctl 命令和操作记录，也可以用工具的模型与业务函数；它们不能声明新模型，彼此也不互相导入。

## 无人值守

`ssh-port` 和 `add-site` 的问题带 key，可以用环境变量预置答案，在脚本里运行：

```bash
OLDMAN_ANSWER_SSH_PORT_PORT=2200 ./run.sh ops ssh-port
OLDMAN_ANSWER_ADD_SITE_DOMAIN=api.example.org OLDMAN_ANSWER_ADD_SITE_PORT=9000 ./run.sh ops add-site
./run.sh ops report > state.json   # stdout 只有 JSON,说明文字在 stderr
```

没有终端又没有预置答案时，命令报错并写出要设置的变量；`menu` 一定要有人在终端前操作。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

测试把项目复制到临时目录，用 `tui.simulate_input` 走完菜单的每一项，远程文件分别从本地目录和本地 HTTP 服务读取；命令行部分检查预置答案和报错。

## 换成真实服务器

要让它操作真实服务器，配置改成：

```yaml
app_settings:
  ops:
    remote_base: https://raw.githubusercontent.com/<你的仓库>/<标签>/remote
    root: /
    systemctl: [sudo, systemctl]
```

这时工具会真的修改 `/etc` 并重启服务，需要以能写这些文件的用户运行。「重置沙箱」只对从样例建立的沙箱生效，不会动真实系统。

这个 Demo 演示的是改配置文件、重启服务这些做法，没有处理真实系统之间的差异，用它管理服务器之前要按自己的系统补上。例如：

- 「安全检查」只读主配置 `sshd_config`，没有读 `sshd_config.d/` 里的文件。SSH 服务对同一个设置取第一次出现的值，而这个目录里的文件先于主配置读到，云主机镜像常在那里写 `PasswordAuthentication yes`；这时检查会显示「正常」，修复写进主配置也不会生效。
- 不同版本的系统改 SSH 端口的方式不一样，「SSH 端口」只演示了其中一种。
