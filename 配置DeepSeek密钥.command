#!/bin/zsh
set -eu
cd -- "${0:A:h}"
print '配置 DeepSeek API 余额显示。不要把 Key 发到聊天中。'
mkdir -p .runtime
if [[ ! -x .runtime/deepseek-keychain || host/deepseek_keychain.swift -nt .runtime/deepseek-keychain ]]; then
  /usr/bin/swiftc -module-cache-path "${TMPDIR:-/tmp}/waveshare-swift-cache" host/deepseek_keychain.swift -o .runtime/deepseek-keychain
fi
if .runtime/deepseek-keychain set; then
  print '配置完成；确保微雪同步服务正在运行，等待约一分钟。'
else
  print '配置失败，请检查登录钥匙串是否已解锁。'
fi
read '?按回车关闭窗口。'
