# Weibo SuperTopic Auto Sign V3.4 (微博超话自动签到 24h挂机版)

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen)

Weibo SuperTopic Auto Sign 是一款基于 Python (CustomTkinter + Selenium) 开发的现代化 Windows 桌面应用。
V3.4 版本带来了全新的浅色 UI、可视化列表管理，以及专为无人值守设计的 **24小时全局防休眠** 机制。

## ✨ V3.4 核心特性

* **🛡️ 24h 全局防休眠 (New)**: 
    * 新增 **“🛡️ 软件运行时始终保持唤醒”** 开关。
    * 开启后，软件会接管 Windows 电源管理 (调用 Kernel32 API)，强制屏幕常亮，禁止系统自动睡眠。
    * 即使电脑全天闲置，也能确保后台脚本存活，第二天准时触发任务。
* **🎨 现代化 UI**: 
    * 强制浅色清爽主题，适配 Windows 11 风格。
    * 完美的图标支持：任务栏、托盘、弹窗均显示自定义 Logo。
* **📋 可视化列表管理**: 
    * 告别文本文件配置，直接在界面添加/删除超话链接。
    * 支持为每个超话设置 **备注名**。
* **🤖 智能自动化**: 
    * 内置 Edge 驱动自动管理，开箱即用。
    * 每日仅执行一次（基于日期记忆），跨天自动重置。
* **💤 安全睡眠机制**: 
    * 任务完成后支持自动进入睡眠。
    * 包含 60秒 防误触倒计时弹窗，物理级按键宏 (Win+X, U, S) 确保休眠成功。

## 🛠️ 安装与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt