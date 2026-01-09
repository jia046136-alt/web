import os
import sys
import time
import json
import threading
import ctypes
import re
import winreg
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ================= 全局配置 =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"
APP_REGISTRY_NAME = "WeiboSuperTopicAutoSignV9"

# ================= 模块1: 物理级电源管理 =================
class PowerManagement:
    """模拟物理按键连招: Win + X -> U -> S"""
    VK_LWIN = 0x5B
    VK_X = 0x58
    VK_U = 0x55
    VK_S = 0x53
    KEYEVENTF_KEYUP = 0x0002

    @staticmethod
    def press_key(vk_code):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(vk_code, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)

    @staticmethod
    def execute_sleep_macro():
        print("💤 执行强制睡眠宏 (Win+X, U, S)...")
        ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, 0, 0)
        time.sleep(0.2)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        time.sleep(1.0)
        PowerManagement.press_key(PowerManagement.VK_U)
        time.sleep(0.5)
        PowerManagement.press_key(PowerManagement.VK_S)

# ================= 模块2: 安全睡眠弹窗 =================
class SafetySleepWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_cancel, on_timeout):
        super().__init__(parent)
        self.on_cancel = on_cancel
        self.on_timeout = on_timeout
        self.remaining_time = 60
        self.is_running = True
        
        self.title("准备睡眠 - 安全确认")
        self.geometry("420x280")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 420) // 2
        y = (screen_height - 280) // 2
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.cancel_sleep)

        self.label_status = ctk.CTkLabel(self, text="✅ 所有任务已完成", font=("Microsoft YaHei", 22, "bold"), text_color="#2CC985")
        self.label_status.pack(pady=(35, 10))

        self.label_desc = ctk.CTkLabel(self, text="系统准备进入睡眠模式", font=("Microsoft YaHei", 14), text_color="gray")
        self.label_desc.pack(pady=(0, 20))

        self.label_timer = ctk.CTkLabel(self, text=f"⏳ {self.remaining_time} 秒后自动睡眠...", font=("Microsoft YaHei", 18, "bold"))
        self.label_timer.pack(pady=10)

        self.btn_cancel = ctk.CTkButton(
            self, text="🚫 取消睡眠 (我在用电脑)", fg_color="#FF4500", hover_color="#CC3700",
            width=220, height=50, font=("Microsoft YaHei", 16, "bold"), command=self.cancel_sleep
        )
        self.btn_cancel.pack(pady=20)
        
        self.timer_loop()

    def timer_loop(self):
        if not self.is_running: return
        if self.remaining_time > 0:
            self.label_timer.configure(text=f"⏳ {self.remaining_time} 秒后自动睡眠...")
            self.remaining_time -= 1
            self.after(1000, self.timer_loop)
        else:
            self.is_running = False
            self.destroy()
            self.on_timeout()

    def cancel_sleep(self):
        self.is_running = False
        self.destroy()
        self.on_cancel()

# ================= 模块3: 主程序逻辑 =================
class WeiboCheckInApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("微博超话自动签到 2.0")
        self.geometry("750x650")
        
        self.config = self.load_config()
        self.is_running = False
        self.tray_icon = None

        self.setup_ui()
        self.sync_registry_switch()

        self.monitor_thread = threading.Thread(target=self.smart_monitor_loop, daemon=True)
        self.monitor_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    def load_config(self):
        default_config = {
            "target_urls": "",  # 变为存储长文本
            "auto_sleep": False,
            "auto_start": False,
            "visible_mode": False, # 新增：是否显示浏览器界面
            "last_checkin_date": "1970-01-01"
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return {**default_config, **json.load(f)}
            except:
                pass
        return default_config

    def save_config(self):
        self.config["target_urls"] = self.textbox_urls.get("1.0", "end-1c") # 获取多行文本
        self.config["auto_sleep"] = self.switch_sleep.get()
        self.config["visible_mode"] = self.switch_visible.get()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def setup_ui(self):
        # 标题
        self.frame_title = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_title.pack(pady=15)
        ctk.CTkLabel(self.frame_title, text="微博超话助手 V2.0", font=("Microsoft YaHei", 24, "bold")).pack()
        ctk.CTkLabel(self.frame_title, text="支持批量链接 | 过程可视化 | 智能睡眠", font=("Microsoft YaHei", 12), text_color="gray").pack()

        # 链接输入区域 (改为 Textbox 以支持多行)
        self.frame_input = ctk.CTkFrame(self)
        self.frame_input.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(self.frame_input, text="超话链接列表 (一行一个，支持直接粘贴混杂文本):").pack(anchor="w", padx=10, pady=5)
        
        self.textbox_urls = ctk.CTkTextbox(self.frame_input, height=100)
        self.textbox_urls.pack(fill="x", padx=10, pady=(0, 10))
        self.textbox_urls.insert("1.0", self.config.get("target_urls", ""))

        # 开关区域
        self.frame_switches = ctk.CTkFrame(self)
        self.frame_switches.pack(pady=5, padx=20, fill="x")
        
        # 1. 开机自启
        self.switch_autostart = ctk.CTkSwitch(self.frame_switches, text="开机自启", command=self.toggle_autostart)
        self.switch_autostart.pack(side="left", padx=15, pady=15)
        
        # 2. 自动睡眠
        self.switch_sleep = ctk.CTkSwitch(self.frame_switches, text="完成后睡眠(含保护)")
        self.switch_sleep.pack(side="left", padx=15, pady=15)
        if self.config.get("auto_sleep"): self.switch_sleep.select()

        # 3. 显示浏览器 (调试用)
        self.switch_visible = ctk.CTkSwitch(self.frame_switches, text="显示浏览器界面(排查卡顿)")
        self.switch_visible.pack(side="left", padx=15, pady=15)
        if self.config.get("visible_mode"): self.switch_visible.select()

        # 日志框
        ctk.CTkLabel(self, text="运行日志:", text_color="gray", font=("Microsoft YaHei", 12)).pack(anchor="w", padx=25, pady=(10,0))
        self.textbox_log = ctk.CTkTextbox(self, height=180, font=("Consolas", 11))
        self.textbox_log.pack(pady=5, padx=20, fill="both", expand=True)
        self.log_msg("🚀 V2.0 就绪，请填入链接并保存配置...")

        # 按钮
        self.btn_run = ctk.CTkButton(self, text="立即手动开始 (测试所有链接)", height=40, command=lambda: threading.Thread(target=self.manual_run).start())
        self.btn_run.pack(pady=15)

    # ---------------- 注册表自启 ----------------
    def sync_registry_switch(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_REGISTRY_NAME)
            self.switch_autostart.select()
            self.config["auto_start"] = True
            winreg.CloseKey(key)
        except:
            self.switch_autostart.deselect()
            self.config["auto_start"] = False

    def toggle_autostart(self):
        is_on = self.switch_autostart.get()
        app_path = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if is_on:
                winreg.SetValueEx(key, APP_REGISTRY_NAME, 0, winreg.REG_SZ, app_path)
                self.log_msg("✅ 已开机自启")
            else:
                try: winreg.DeleteValue(key, APP_REGISTRY_NAME)
                except: pass
                self.log_msg("❎ 已关闭自启")
            winreg.CloseKey(key)
            self.config["auto_start"] = is_on
            self.save_config()
        except Exception as e:
            self.log_msg(f"❌ 注册表错误: {e}")
            self.switch_autostart.toggle()

    # ---------------- 智能监测循环 ----------------
    def smart_monitor_loop(self):
        time.sleep(2)
        self.log_msg("🛡️ 后台监测启动...")
        while True:
            try:
                today = time.strftime("%Y-%m-%d")
                last_date = self.config.get("last_checkin_date", "1970-01-01")
                
                if today != last_date:
                    self.log_msg(f"📅 新日期 ({today})，准备执行任务...")
                    time.sleep(10) # 联网缓冲
                    
                    if self.execute_batch_task():
                        self.log_msg("🎉 所有任务均已完成！")
                        self.config["last_checkin_date"] = today
                        self.save_config()
                        if self.switch_sleep.get():
                            self.after(0, self.trigger_safety_sleep)
                    else:
                        self.log_msg("⚠️ 部分任务失败或网络不通，30分钟后重试...")
                        time.sleep(1800)
                        continue
                time.sleep(60)
            except Exception as e:
                self.log_msg(f"监测异常: {e}")
                time.sleep(60)

    def manual_run(self):
        self.log_msg("🔧 手动触发...")
        if self.execute_batch_task():
            today = time.strftime("%Y-%m-%d")
            self.config["last_checkin_date"] = today
            self.save_config()
            self.log_msg("✅ 手动执行完毕")
            if self.switch_sleep.get():
                self.after(0, self.trigger_safety_sleep)

    def execute_batch_task(self):
        """执行所有链接的签到任务"""
        if self.is_running:
            self.log_msg("⚠️ 正在运行中...")
            return False
        
        self.is_running = True
        
        # 1. 提取所有链接
        raw_text = self.textbox_urls.get("1.0", "end-1c")
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', raw_text)
        
        if not urls:
            self.log_msg("❌ 未检测到链接，请在上方输入框粘贴链接")
            self.is_running = False
            return False
            
        self.log_msg(f"📋 检测到 {len(urls)} 个超话链接，准备开始...")

        # 2. 配置浏览器
        driver = None
        all_success = True
        
        try:
            options = Options()
            # 根据开关决定是否无头
            if not self.switch_visible.get():
                options.add_argument("--headless=new") 
            
            options.add_argument("--disable-gpu")
            options.add_argument("--log-level=3")
            options.add_argument("--mute-audio")
            
            user_data = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data')
            options.add_argument(f"--user-data-dir={user_data}")
            options.add_argument("--profile-directory=Default")
            
            self.log_msg("🚀 正在启动 Edge 浏览器...")
            try:
                service = Service(EdgeChromiumDriverManager().install())
            except Exception as e:
                self.log_msg("⚠️ 自动下载驱动失败 (可能网络问题)，尝试直接启动...")
                service = Service() # 尝试使用系统默认路径
                
            service.creation_flags = 0x08000000 
            driver = webdriver.Edge(service=service, options=options)
            
            # 3. 循环执行签到
            for i, url in enumerate(urls):
                self.log_msg(f"👉 [{i+1}/{len(urls)}] 正在访问超话...")
                try:
                    driver.get(url)
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(2) # 等待渲染
                    
                    # 查找签到按钮 (增强版 XPath)
                    xpath = "//a[contains(text(),'签到')] | //div[contains(text(),'签到')] | //span[contains(text(),'签到')]"
                    btns = driver.find_elements(By.XPATH, xpath)
                    
                    clicked = False
                    for btn in btns:
                        txt = btn.text
                        if "已" not in txt and "等级" not in txt and btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            self.log_msg(f"   🖱️ 点击签到")
                            clicked = True
                            time.sleep(2)
                            break
                    
                    if not clicked:
                        if "已签" in driver.page_source:
                            self.log_msg(f"   ℹ️ 本页已签到")
                        else:
                            self.log_msg(f"   ⚠️ 未找到按钮，可能需登录或页面结构变更")
                            
                except Exception as e:
                    self.log_msg(f"   ❌ 当前链接出错: {str(e)[:50]}")
                    all_success = False # 标记有失败，但继续下一个
                
                time.sleep(1) # 链接间隔
                
        except Exception as e:
            self.log_msg(f"❌ 浏览器严重错误 (驱动/网络): {e}")
            self.log_msg("💡 建议开启'显示浏览器界面'开关以排查问题")
            all_success = False
        finally:
            if driver:
                driver.quit()
            self.is_running = False
            
        return all_success

    # ---------------- 辅助功能 ----------------
    def trigger_safety_sleep(self):
        SafetySleepWindow(self, lambda: self.log_msg("👋 取消睡眠"), lambda: PowerManagement.execute_sleep_macro())

    def log_msg(self, msg):
        full_msg = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        self.textbox_log.insert("end", full_msg)
        self.textbox_log.see("end")

    def hide_to_tray(self):
        self.withdraw()
        if not self.tray_icon: self.create_tray_icon()

    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()

    def quit_app(self, icon, item):
        self.save_config()
        self.tray_icon.stop()
        self.destroy()
        sys.exit()

    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color=(30, 144, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill="white")
        menu = (pystray.MenuItem('显示主界面', self.show_window, default=True), pystray.MenuItem('退出', self.quit_app))
        self.tray_icon = pystray.Icon("weibo_helper", image, "微博助手", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    app = WeiboCheckInApp()
    app.mainloop()