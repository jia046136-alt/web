import os
import sys
import time
import json
import threading
import ctypes
import re
import schedule
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# === 全局设置 ===
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
CONFIG_FILE = "config.json"

# === 电源管理模块 (V8.0 键盘宏版) ===
class PowerManagement:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    
    # 键盘按键码定义
    VK_LWIN = 0x5B
    VK_X = 0x58
    VK_U = 0x55
    VK_S = 0x53
    KEYEVENTF_KEYUP = 0x0002

    @staticmethod
    def press_key(vk_code):
        """模拟按下并释放一个键"""
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0) # 按下
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(vk_code, 0, PowerManagement.KEYEVENTF_KEYUP, 0) # 抬起

    @staticmethod
    def prevent_sleep():
        ctypes.windll.kernel32.SetThreadExecutionState(PowerManagement.ES_CONTINUOUS | PowerManagement.ES_SYSTEM_REQUIRED)

    @staticmethod
    def allow_sleep():
        ctypes.windll.kernel32.SetThreadExecutionState(PowerManagement.ES_CONTINUOUS)

    @staticmethod
    def force_system_sleep():
        """【物理外挂】模拟 Win+X -> U -> S 连招"""
        print("[电源] 任务完成，正在模拟键盘操作进行睡眠...")
        time.sleep(2)
        
        try:
            # 1. 按下 Win + X 调出系统菜单
            print(" -> 动作: Win + X")
            ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, 0, 0) # 按住 Win
            ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, 0, 0)    # 按下 X
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, PowerManagement.KEYEVENTF_KEYUP, 0) # 松开 X
            ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, PowerManagement.KEYEVENTF_KEYUP, 0) # 松开 Win
            
            # 给菜单弹出的时间
            time.sleep(1.5)
            
            # 2. 按下 U (选中“关机或注销”)
            print(" -> 动作: U")
            PowerManagement.press_key(PowerManagement.VK_U)
            
            # 给子菜单展开的时间
            time.sleep(1.5)
            
            # 3. 按下 S (选中“睡眠”)
            print(" -> 动作: S (晚安!)")
            PowerManagement.press_key(PowerManagement.VK_S)
            
        except Exception as e:
            print(f"键盘模拟失败: {e}")

# === 签到核心逻辑 ===
class CheckInWorker:
    def __init__(self, log_callback):
        self.log = log_callback
        self.running = False

    def clean_user_data_locks(self, user_data_path):
        locks = ['SingletonLock', 'SingletonSocket', 'SingletonCookie']
        for lock_name in locks:
            lock_path = os.path.join(user_data_path, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except:
                    pass

    def run_task(self, config):
        if self.running:
            self.log("任务正在运行中，请勿重复触发...")
            return
        
        self.running = True
        self.log(">>> 开始执行签到任务...")
        PowerManagement.prevent_sleep()
        
        os.environ['no_proxy'] = '*'
        os.environ['NO_PROXY'] = '*'
        for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(k, None)

        user_data = config.get("user_data_path", "")
        urls = config.get("urls", [])
        
        if not urls:
            self.log("[错误] 没有检测到有效的超话链接！")
            self.running = False
            return

        if not os.path.exists(user_data):
            self.log("[错误] User Data 路径不存在！")
            self.running = False
            return

        self.clean_user_data_locks(user_data)

        driver = None
        try:
            edge_options = Options()
            edge_options.add_argument(f"--user-data-dir={user_data}")
            edge_options.add_argument("--profile-directory=Default")
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_argument("--disable-features=msEdgeStartupBoost")
            edge_options.add_argument("--remote-debugging-port=9222")
            edge_options.add_argument("--log-level=3")
            edge_options.add_argument("--headless=new") 
            
            self.log("正在启动后台引擎...")
            try:
                service = Service(EdgeChromiumDriverManager().install())
                driver = webdriver.Edge(service=service, options=edge_options)
            except:
                driver = webdriver.Edge(options=edge_options)
            
            self.log(f"引擎启动成功，共 {len(urls)} 个任务...")
            
            for i, url in enumerate(urls):
                self.log(f"--- 正在处理 ({i+1}/{len(urls)}) ---")
                self.check_one(driver, url)
                time.sleep(2)
                
            self.log("所有签到任务已完成！")
            
        except Exception as e:
            self.log(f"[致命错误] {str(e)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            PowerManagement.allow_sleep()
            self.running = False
            
            # 检查自动休眠
            if config.get("auto_sleep", False):
                self.log("任务完成，即将模拟按键休眠...")
                PowerManagement.force_system_sleep()

    def check_one(self, driver, url):
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                driver.set_page_load_timeout(60)
                driver.get(url)
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(3)

                targets = driver.find_elements(By.XPATH, "//*[contains(text(), '签到')]")
                valid_btn = None
                for t in targets:
                    try:
                        txt = t.text.strip()
                        if "签到" in txt and "已" not in txt and "连续" not in txt and len(txt) < 6 and t.is_displayed():
                            valid_btn = t
                            break
                    except:
                        continue
                
                if valid_btn:
                    self.log(f" -> 锁定按钮: [{valid_btn.text}]")
                    try:
                        driver.execute_script("arguments[0].click();", valid_btn)
                    except:
                        valid_btn.click()
                    self.log(" -> 动作: 点击完成")
                    time.sleep(2)
                    return

                is_done = False
                try:
                    done_elements = driver.find_elements(By.XPATH, "//*[text()='已签到']")
                    for el in done_elements:
                        if el.is_displayed():
                            is_done = True
                            break
                except:
                    pass
                    
                if is_done:
                    self.log(" -> 状态: 检测到【已签到】，跳过。")
                    return
                else:
                    self.log(f" -> 未找到按钮 (第{attempt}次重试)")
                    if attempt < max_retries:
                        driver.refresh()
                        time.sleep(3)

            except Exception as e:
                self.log(f" -> 错误: {str(e)[:30]}")

# === GUI 主程序 ===
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("微博超话自动签到 - 物理外挂版")
        self.geometry("750x600")
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.worker = CheckInWorker(self.log_msg)
        self.config = self.load_config()
        self.tray_icon = None
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="自动签到助手", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_save = ctk.CTkButton(self.sidebar, text="保存配置", command=self.save_config)
        self.btn_save.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_run = ctk.CTkButton(self.sidebar, text="立即运行", fg_color="green", command=self.start_thread)
        self.btn_run.grid(row=2, column=0, padx=20, pady=10)
        
        self.main_frame = ctk.CTkScrollableFrame(self, label_text="配置面板")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        ctk.CTkLabel(self.main_frame, text="Edge User Data 路径:").pack(anchor="w", pady=(10, 0))
        self.entry_path = ctk.CTkEntry(self.main_frame, width=400)
        self.entry_path.pack(fill="x", pady=5)
        self.entry_path.insert(0, self.config.get("user_data_path", ""))
        
        ctk.CTkLabel(self.main_frame, text="自动运行时间 (格式 HH:MM):").pack(anchor="w", pady=(10, 0))
        self.entry_time = ctk.CTkEntry(self.main_frame, width=100)
        self.entry_time.pack(anchor="w", pady=5)
        self.entry_time.insert(0, self.config.get("schedule_time", "12:00"))
        
        self.switch_sleep_var = ctk.BooleanVar(value=self.config.get("auto_sleep", False))
        self.switch_sleep = ctk.CTkSwitch(self.main_frame, text="任务完成后自动让电脑睡眠 (Win+X, U, S)", variable=self.switch_sleep_var)
        self.switch_sleep.pack(anchor="w", pady=10)
        
        ctk.CTkLabel(self.main_frame, text="超话链接 (自动识别):").pack(anchor="w", pady=(10, 0))
        self.txt_urls = ctk.CTkTextbox(self.main_frame, height=180, wrap="none")
        self.txt_urls.pack(fill="x", pady=5)
        self.txt_urls.insert("0.0", "\n".join(self.config.get("urls", [])))
        
        ctk.CTkLabel(self.main_frame, text="运行日志:").pack(anchor="w", pady=(20, 0))
        self.txt_log = ctk.CTkTextbox(self.main_frame, height=120, state="disabled", wrap="word")
        self.txt_log.pack(fill="x", pady=5)

        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def load_config(self):
        default = {
            "user_data_path": r"C:\Users\YourUserName\AppData\Local\Microsoft\Edge\User Data",
            "urls": [],
            "schedule_time": "12:00",
            "auto_sleep": False
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default
        return default

    def save_config(self):
        raw_text = self.txt_urls.get("0.0", "end")
        urls = re.findall(r'https?://[^\s\n\r]+', raw_text)
        urls = list(set(urls))
        self.log_msg(f"识别到 {len(urls)} 个有效链接。")
        new_conf = {
            "user_data_path": self.entry_path.get().strip(),
            "urls": urls,
            "schedule_time": self.entry_time.get().strip(),
            "auto_sleep": self.switch_sleep_var.get()
        }
        with open(CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(new_conf, f, indent=4, ensure_ascii=False)
        self.config = new_conf
        self.log_msg("配置已保存！")

    def log_msg(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def start_thread(self):
        self.save_config()
        t = threading.Thread(target=self.worker.run_task, args=(self.config,))
        t.start()

    def run_scheduler(self):
        while True:
            schedule_time = self.config.get("schedule_time", "12:00")
            current_time = time.strftime("%H:%M")
            if current_time == schedule_time and not self.worker.running:
                self.log_msg(f"⏰ 到达设定时间 {schedule_time}，自动启动...")
                t = threading.Thread(target=self.worker.run_task, args=(self.config,))
                t.start()
                time.sleep(61)
            time.sleep(2)

    def hide_window(self):
        self.withdraw()
        if not self.tray_icon:
            self.create_tray_icon()
        self.tray_icon.notify("程序后台运行中...", "微博助手")

    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()

    def quit_app(self, icon, item):
        self.tray_icon.stop()
        self.destroy()
        sys.exit()

    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color=(30, 144, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill="white")
        menu = (
            pystray.MenuItem('显示窗口', self.show_window, default=True),
            pystray.MenuItem('立即运行', lambda: self.start_thread()),
            pystray.MenuItem('退出', self.quit_app)
        )
        self.tray_icon = pystray.Icon("WeiboHelper", image, "微博签到助手", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()