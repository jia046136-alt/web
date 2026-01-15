# Weibo SuperTopic Auto Sign V3.0 (微博超话自动签到助手)

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen)

Weibo SuperTopic Auto Sign 是一款基于 Python (CustomTkinter + Selenium) 开发的 Windows 桌面应用。
V3.0 版本采用全新浅色 UI，支持可视化管理超话列表，内置防误触睡眠机制和物理级按键宏，专为无人值守挂机设计。

## ✨ V3.0 新特性

* **🎨 全新 UI**: 强制浅色清爽主题，现代化交互设计。
* **📋 动态列表**: 可视化添加/删除超话链接，支持自定义**备注名**。
* **🤖 智能自动化**: 
    * 自动调用 Edge 浏览器完成签到。
    * 内置 `msedgedriver` 自动下载与版本匹配。
    * 每日仅执行一次（基于日期记忆）。
* **💤 安全睡眠**: 任务完成后支持自动睡眠，包含 60秒 倒计时防误触弹窗。
* **🛡️ 物理宏**: 使用 `Win+X, U, S` 物理按键模拟进入睡眠，规避部分系统 API 休眠失效问题。
* **🚀 工程化**: 提供一键打包脚本，生成单文件 `.exe`。

## 🛠️ 环境依赖

* Windows 10/11
* Microsoft Edge 浏览器
* Python 3.10+

## 📦 安装与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt