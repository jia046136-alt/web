# Weibo Super Topic Auto Check-in (微博超话自动签到助手)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg) ![License](https://img.shields.io/badge/License-MIT-green.svg) ![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-orange.svg)

一个基于 Python + Selenium 的微博超话自动签到工具。
专为 Windows 11 设计，采用现代化 UI，支持托盘最小化、自动识别链接、以及**独家的“物理级”防系统拦截睡眠功能**。

## ✨ 核心功能

* **Win11 风格 UI**：使用 `customtkinter` 构建的现代化深色界面。
* **托盘后台运行**：点击关闭按钮自动最小化到托盘，不占用任务栏。
* **智能链接识别**：无论你粘贴的链接是否换行、断裂，利用正则自动提取有效超话 URL。
* **免登录操作**：调用本地 Edge 浏览器 User Data，保留你的登录状态。
* **静默执行**：默认开启无头模式（Headless），后台悄悄签到，不弹窗干扰。
* **强力睡眠模式 (New)**：
    * 针对联想等新款笔记本无法通过 API 睡眠的问题，**V8.0 版本内置“物理外挂”**。
    * 通过模拟键盘连招 `Win + X` -> `U` -> `S`，绕过系统权限拦截，强制电脑睡眠。

## 🛠️ 安装与使用

### 1. 环境准备
确保已安装 [Python 3.10+](https://www.python.org/) 和 Microsoft Edge 浏览器。

### 2. 安装依赖
```bash
pip install -r requirements.txt