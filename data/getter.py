from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import re
import os
import random # 导入 random 库

# --- 配置部分 ---
DRIVER_PATH = "D:/desktop/python++/langchain/mooncell/chromedriver-win64/chromedriver.exe"
# 增加 User-Agent 伪装，模拟浏览器
# User-Agent 可以在网站 https://www.whatismybrowser.com/detect/what-is-my-user-agent/ 查找
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/108.0.1462.42",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/108.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
]

SERVANT_EDIT_URLS = []
with open('servant_urls_edit.txt', 'r', encoding='utf-8') as file:
    for line in file:
        line = line.strip()
        if line.startswith('https://fgo.wiki/index.php?title='):
            SERVANT_EDIT_URLS.append(line)

# --- 初始化 WebDriver ---
def get_driver():
    """初始化并返回配置好的 WebDriver"""
    try:
        service = Service(executable_path=DRIVER_PATH)
        chrome_options = webdriver.ChromeOptions()
        # 伪装 User-Agent
        chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        # 启用无头模式（可选，如果需要后台运行）
        # chrome_options.add_argument("--headless")
        # 避免被网站检测出是自动化工具
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"初始化 Selenium WebDriver 失败: {e}")
        print("请确保 chromedriver.exe 的路径正确，且版本与您的 Chrome 浏览器匹配。")
        return None

# --- 抓取和解析函数 ---
def fetch_and_parse_with_selenium(driver, url: str) -> dict:
    """
    使用 Selenium 抓取、解析单个从者页面，并保存源码供调试。
    """
    try:
        print(f"正在访问: {url}")
        driver.get(url)

        wait = WebDriverWait(driver, 30)  # 增加等待时间
        textarea_element = wait.until(
            EC.presence_of_element_located((By.ID, "wpTextbox1"))
        )
        print("Textarea 元素已定位。")

        wikitext = ""
        max_retries = 10
        for i in range(max_retries):
            wikitext = textarea_element.get_attribute('value')
            if wikitext and "{{从者数据" in wikitext:
                print(f"Textarea 内容已加载 (尝试 {i+1}/{max_retries})。")
                break
            time.sleep(0.5)

        if not wikitext:
            print("警告: 等待超时，textarea 内容为空。")
            return None

        # 4. 保存wikitext
        pattern = re.compile(r'title=([^&]+)')
        match = pattern.search(url)
        if match:
            servant_name = match.group(1)
            print(f"从 URL 中提取到从者名称: {servant_name}")
        else:
            print("警告: 未能从 URL 中提取从者名称。")
            return None
        
        # 确保输出文件夹存在
        output_dir = 'textarea'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 移除文件名中可能存在的无效字符
        safe_servant_name = re.sub(r'[\\/:*?"<>|]', '', servant_name)

        with open(f'{output_dir}/{safe_servant_name}.txt', 'w', encoding='utf-8') as f:
            f.write(wikitext)
        print(f"文件 '{safe_servant_name}.txt' 已成功保存。")
        
        # 5. 增加随机等待，这是最核心的反封禁措施
        # 等待时间可以根据你的需求调整，这里设置为 5-15 秒
        sleep_time = random.uniform(5, 15)
        print(f"正在随机等待 {sleep_time:.2f} 秒...")
        time.sleep(sleep_time)

    except Exception as e:
        print(f"处理 {url} 时发生严重错误: {e}")
        # 如果出错，等待更长时间再继续，避免连续出错被封
        long_sleep_time = random.uniform(30, 60)
        print(f"发生错误，等待 {long_sleep_time:.2f} 秒后继续...")
        time.sleep(long_sleep_time)
        return None


# --- 程序主入口 ---
if __name__ == "__main__":
    driver = get_driver()
    if not driver:
        exit()

    print(f"🚀 开始抓取 {len(SERVANT_EDIT_URLS)} 个从者页面...")

    over_list = os.listdir('textarea')

    for url in SERVANT_EDIT_URLS:
        # 在每个循环开始前增加一个较短的随机延迟

        pattern = re.compile(r'title=([^&]+)')
        match = pattern.search(url)
        if match:
            servant_name = match.group(1)
            print(f"从 URL 中提取到从者名称: {servant_name}")
        else:
            print("警告: 未能从 URL 中提取从者名称。")
            continue
        
        if f'{servant_name}.txt' in over_list:
            print(f'文件 {servant_name}.txt 已存在，跳过')
            continue


        short_sleep = random.uniform(1, 3)
        time.sleep(short_sleep)
        
        try:
            fetch_and_parse_with_selenium(driver, url)
        except Exception as e:
            print(f"处理 {url} 时发生错误: {e}")
            print("尝试重新启动浏览器会话...")
            # 关闭旧的驱动
            try:
                driver.quit()
            except:
                pass # 忽略关闭失败的错误
            # 重新获取一个新的驱动
            driver = get_driver()
            if not driver:
                print("🚨 无法重新启动浏览器，程序退出。")
                break
            # 重新尝试抓取当前的 URL
            fetch_and_parse_with_selenium(driver, url)

    # --- 最终关闭浏览器 ---
    print("\n✅ 所有任务完成，正在关闭浏览器...")
    driver.quit()