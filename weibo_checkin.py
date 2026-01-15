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
# 1. 强制浅色主题
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"
APP_REGISTRY_NAME = "WeiboSuperTopicAutoSignV3"

# ================= 模块1: 物理级电源管理 (保留原有逻辑) =================
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

# ================= 模块2: 安全睡眠弹窗 (保留原有逻辑) =================
class SafetySleepWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_cancel, on_timeout):
        super().__init__(parent)
        self.on_cancel = on_cancel
        self.on_timeout = on_timeout
        self.remaining_time = 60
        self.is_running = True
        
        self.title("准备进入睡眠")
        self.geometry("420x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        # 居中逻辑
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 420) // 2
        y = (screen_height - 250) // 2
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.cancel_sleep)

        self.label_status = ctk.CTkLabel(self, text="✅ 任务完成，准备待机", font=("Microsoft YaHei", 20, "bold"), text_color="#2E8B57")
        self.label_status.pack(pady=(30, 10))

        self.label_timer = ctk.CTkLabel(self, text=f"⏳ {self.remaining_time} 秒后自动睡眠...", font=("Microsoft YaHei", 16))
        self.label_timer.pack(pady=10)

        self.btn_cancel = ctk.CTkButton(
            self, text="🚫 取消睡眠 (我在用电脑)", fg_color="#FF6347", hover_color="#CD5C5C",
            width=200, height=45, font=("Microsoft YaHei", 14, "bold"), command=self.cancel_sleep
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

# ================= 模块3: V3.0 主界面逻辑 =================
class WeiboCheckInApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("微博超话助手 V3.0 (Light)")
        self.geometry("800x700")
        
        self.config = self.load_config()
        self.is_running = False
        self.tray_icon = None
        
        # 存储动态行的引用列表 [{"id": frame, "url_entry": entry, "note_entry": entry}, ...]
        self.row_widgets = [] 

        self.setup_ui()
        self.load_rows_from_config() # 界面加载完毕后填充数据
        self.sync_registry_switch()

        self.monitor_thread = threading.Thread(target=self.smart_monitor_loop, daemon=True)
        self.monitor_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    def load_config(self):
        default_config = {
            "targets": [],  # V3.0 新结构: [{"url": "...", "note": "..."}]
            "auto_sleep": False,
            "auto_start": False,
            "visible_mode": False,
            "last_checkin_date": "1970-01-01"
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 兼容 V9.1 旧配置 (如果是字符串则转换)
                    if "target_urls" in data:
                        old_urls = re.findall(r'http[s]?://[^\s]+', data["target_urls"])
                        data["targets"] = [{"url": u, "note": "旧数据"} for u in old_urls]
                        del data["target_urls"]
                    return {**default_config, **data}
            except:
                pass
        return default_config

    def save_config(self):
        # 1. 从 UI 获取最新数据
        current_targets = []
        for row in self.row_widgets:
            u = row["url_entry"].get().strip()
            n = row["note_entry"].get().strip()
            if u: # 忽略空行
                current_targets.append({"url": u, "note": n})
        
        self.config["targets"] = current_targets
        self.config["auto_sleep"] = self.switch_sleep.get()
        self.config["visible_mode"] = self.switch_visible.get()
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        
        return len(current_targets)

    def setup_ui(self):
        # --- 顶部标题 ---
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(self.frame_top, text="Weibo SuperTopic V3.0", font=("Arial", 22, "bold"), text_color="#333").pack(side="left")
        ctk.CTkLabel(self.frame_top, text="清爽 · 可视化 · 智能", font=("Microsoft YaHei", 12), text_color="gray").pack(side="left", padx=10, pady=(8,0))

        # --- 核心操作区 (添加/保存) ---
        self.frame_actions = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_actions.pack(padx=20, fill="x")
        
        self.btn_add = ctk.CTkButton(self.frame_actions, text="➕ 添加超话", width=100, command=lambda: self.add_row_ui())
        self.btn_add.pack(side="left", padx=(0, 10))
        
        self.btn_save = ctk.CTkButton(self.frame_actions, text="💾 保存配置", width=100, fg_color="#6c757d", hover_color="#5a6268", command=self.manual_save)
        self.btn_save.pack(side="left")

        # --- 列表滚动区 ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="超话管理列表", height=250, label_font=("Microsoft YaHei", 12, "bold"))
        self.scroll_frame.pack(padx=20, pady=10, fill="x")

        # --- 设置开关区 ---
        self.frame_switches = ctk.CTkFrame(self)
        self.frame_switches.pack(pady=5, padx=20, fill="x")
        
        self.switch_autostart = ctk.CTkSwitch(self.frame_switches, text="开机自启", command=self.toggle_autostart)
        self.switch_autostart.pack(side="left", padx=20, pady=15)
        
        self.switch_sleep = ctk.CTkSwitch(self.frame_switches, text="完成后睡眠(含保护)")
        self.switch_sleep.pack(side="left", padx=20, pady=15)
        if self.config.get("auto_sleep"): self.switch_sleep.select()

        self.switch_visible = ctk.CTkSwitch(self.frame_switches, text="显示浏览器(调试)")
        self.switch_visible.pack(side="left", padx=20, pady=15)
        if self.config.get("visible_mode"): self.switch_visible.select()

        # --- 日志区 ---
        ctk.CTkLabel(self, text="运行日志:", text_color="gray", font=("Microsoft YaHei", 12)).pack(anchor="w", padx=25, pady=(5,0))
        self.textbox_log = ctk.CTkTextbox(self, height=150, font=("Consolas", 11), fg_color="#f0f0f0", text_color="#333")
        self.textbox_log.pack(pady=5, padx=20, fill="both", expand=True)
        
        # --- 底部按钮 ---
        self.btn_run = ctk.CTkButton(self, text="🚀 立即测试所有任务", height=45, font=("Microsoft YaHei", 14, "bold"), command=lambda: threading.Thread(target=self.manual_run).start())
        self.btn_run.pack(pady=15, padx=20, fill="x")

    def add_row_ui(self, url="", note=""):
        """动态添加一行输入框"""
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        
        # URL 输入
        entry_url = ctk.CTkEntry(row_frame, placeholder_text="在此粘贴超话链接...", width=380)
        entry_url.pack(side="left", padx=(0, 5), fill="x", expand=True)
        if url: entry_url.insert(0, url)
        
        # 备注输入
        entry_note = ctk.CTkEntry(row_frame, placeholder_text="备注 (如: AG超玩会)", width=120)
        entry_note.pack(side="left", padx=(0, 5))
        if note: entry_note.insert(0, note)
        
        # 删除按钮
        btn_del = ctk.CTkButton(row_frame, text="🗑️", width=40, fg_color="#dc3545", hover_color="#c82333",
                                command=lambda: self.delete_row_ui(row_frame))
        btn_del.pack(side="left")
        
        # 保存引用
        self.row_widgets.append({
            "frame": row_frame,
            "url_entry": entry_url,
            "note_entry": entry_note
        })

    def delete_row_ui(self, frame_obj):
        """删除一行"""
        for item in self.row_widgets:
            if item["frame"] == frame_obj:
                item["frame"].destroy()
                self.row_widgets.remove(item)
                break

    def load_rows_from_config(self):
        targets = self.config.get("targets", [])
        if not targets:
            self.add_row_ui() # 默认给一行空的
        for t in targets:
            self.add_row_ui(t.get("url", ""), t.get("note", ""))
        self.log_msg(f"📂 已加载 {len(targets)} 个超话配置")

    def manual_save(self):
        count = self.save_config()
        self.log_msg(f"💾 配置已保存，共 {count} 个有效任务")

    # ---------------- 核心逻辑 (保留 V9.1 并适配 V3.0) ----------------
    
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
                self.log_msg("✅ 已设置开机自启")
            else:
                try: winreg.DeleteValue(key, APP_REGISTRY_NAME)
                except: pass
                self.log_msg("❎ 已取消开机自启")
            winreg.CloseKey(key)
            self.config["auto_start"] = is_on
            self.save_config()
        except Exception as e:
            self.log_msg(f"❌ 注册表错误: {e}")
            self.switch_autostart.toggle()

    def smart_monitor_loop(self):
        time.sleep(3)
        self.log_msg("🛡️ 后台智能监测中...")
        while True:
            try:
                today = time.strftime("%Y-%m-%d")
                last_date = self.config.get("last_checkin_date", "1970-01-01")
                
                if today != last_date:
                    self.log_msg(f"📅 新的一天 ({today})，自动启动任务...")
                    time.sleep(10) # 联网缓冲
                    
                    if self.execute_batch_task():
                        self.log_msg("🎉 自动任务全部完成！")
                        self.config["last_checkin_date"] = today
                        self.save_config()
                        if self.switch_sleep.get():
                            self.after(0, self.trigger_safety_sleep)
                    else:
                        self.log_msg("⚠️ 任务未全部成功，30分钟后重试...")
                        time.sleep(1800)
                        continue
                time.sleep(60)
            except Exception as e:
                self.log_msg(f"监测异常: {e}")
                time.sleep(60)

    def manual_run(self):
        self.save_config() # 先保存
        self.log_msg("🔧 开始手动执行...")
        if self.execute_batch_task():
            today = time.strftime("%Y-%m-%d")
            self.config["last_checkin_date"] = today
            self.save_config()
            self.log_msg("✅ 手动执行完毕")
            if self.switch_sleep.get():
                self.after(0, self.trigger_safety_sleep)

    def execute_batch_task(self):
        if self.is_running:
            self.log_msg("⚠️ 正在运行中，请稍候...")
            return False
        
        self.is_running = True
        targets = self.config.get("targets", [])
        
        if not targets:
            self.log_msg("❌ 任务列表为空，请先添加超话链接")
            self.is_running = False
            return False
            
        self.log_msg(f"📋 队列中共有 {len(targets)} 个任务，准备启动 Edge...")

        driver = None
        all_success = True
        
        try:
            options = Options()
            if not self.switch_visible.get():
                options.add_argument("--headless=new")
            
            options.add_argument("--disable-gpu")
            options.add_argument("--log-level=3")
            options.add_argument("--mute-audio")
            user_data = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data')
            options.add_argument(f"--user-data-dir={user_data}")
            options.add_argument("--profile-directory=Default")
            
            try:
                service = Service(EdgeChromiumDriverManager().install())
            except Exception:
                self.log_msg("⚠️ 驱动下载失败，尝试使用系统默认...")
                service = Service()
                
            service.creation_flags = 0x08000000 
            driver = webdriver.Edge(service=service, options=options)
            
            for i, item in enumerate(targets):
                url = item.get("url", "")
                note = item.get("note", "未知超话")
                
                if not url: continue

                self.log_msg(f"👉 [{i+1}/{len(targets)}] 正在检查: {note}")
                try:
                    driver.get(url)
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(2) 
                    
                    xpath = "//a[contains(text(),'签到')] | //div[contains(text(),'签到')] | //span[contains(text(),'签到')]"
                    btns = driver.find_elements(By.XPATH, xpath)
                    
                    clicked = False
                    for btn in btns:
                        txt = btn.text
                        if "已" not in txt and "等级" not in txt and btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            self.log_msg(f"   🖱️ {note}: 签到点击成功")
                            clicked = True
                            time.sleep(2)
                            break
                    
                    if not clicked:
                        if "已签" in driver.page_source:
                            self.log_msg(f"   ℹ️ {note}: 今天已经签过了")
                        else:
                            self.log_msg(f"   ⚠️ {note}: 未找到签到按钮")
                            
                except Exception as e:
                    self.log_msg(f"   ❌ {note} 失败: {str(e)[:30]}")
                    all_success = False 
                
                time.sleep(1)
                
        except Exception as e:
            self.log_msg(f"❌ 浏览器启动失败: {e}")
            all_success = False
        finally:
            if driver: driver.quit()
            self.is_running = False
            
        return all_success

    # ---------------- 辅助功能 ----------------
    def trigger_safety_sleep(self):
        SafetySleepWindow(self, lambda: self.log_msg("👋 用户取消睡眠"), lambda: PowerManagement.execute_sleep_macro())

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
        # 简单绘制一个图标
        image = Image.new('RGB', (64, 64), color=(70, 130, 180))
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill="white")
        menu = (pystray.MenuItem('显示主界面', self.show_window, default=True), pystray.MenuItem('退出程序', self.quit_app))
        self.tray_icon = pystray.Icon("weibo_helper_v3", image, "微博助手V3", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    app = WeiboCheckInApp()
    app.mainloop()