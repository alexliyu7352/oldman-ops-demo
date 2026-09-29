#!/usr/bin/env bash
# 热修复示例:在沙箱里写一条维护公告。参数:沙箱根目录。
set -eu

root="$1"
# 读不到输入(没有终端)时按"否"处理。
read -r -p "在 $root/etc/motd 写入维护公告?[y/N] " answer || answer=n
case "$answer" in
    y | Y | yes)
        echo "本机正在维护:$(date -u '+%Y-%m-%d %H:%M UTC')" > "$root/etc/motd"
        echo "已写入 $root/etc/motd"
        ;;
    *)
        echo "没有改动。"
        ;;
esac
