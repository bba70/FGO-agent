from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
# 导入 Select 类
from selenium.webdriver.support.ui import Select

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# 1. 指定您的 ChromeDriver 驱动程序路径
driver_path = "D:/desktop/python++/langchain/mooncell/chromedriver-win64/chromedriver.exe"

# 2. 创建一个 Service 对象来管理驱动程序
# 注意：Windows 路径使用反斜杠或双反斜杠
# 或者，最简单的，像下面这样使用正斜杠
service = Service(executable_path=driver_path)

# 3. 使用 Service 对象来初始化 WebDriver
driver = webdriver.Chrome(service=service)

# Step 2: 访问从者列表页
url = 'https://fgo.wiki/w/%E8%8B%B1%E7%81%B5%E5%9B%BE%E9%89%B4'
driver.get(url)

# Step 1: 等待下拉列表加载完成
# 通过 id 定位到 <select> 标签
per_page_dropdown = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, 'per-page'))
)

# Step 2: 创建 Select 对象并选择您想要的选项
# 假设您想选择 '500'，因为这是目前最大的选项
select = Select(per_page_dropdown)
select.select_by_value('500')
# 或者
# select.select_by_visible_text('500')

# Step 3: 等待页面内容更新
# 因为选择选项后会触发 onchange 事件，页面会重新加载数据
# 您需要等待新的内容加载出来
# 这里可以等待 URL 变化，或者等待页面上某个元素刷新
WebDriverWait(driver, 15).until(
    EC.presence_of_element_located((By.LINK_TEXT, "尼莫／诺亚"))
)

# 后续步骤：获取页面源码，用 BeautifulSoup 解析，并提取URL
html_content = driver.page_source
soup = BeautifulSoup(html_content, 'html.parser')
servant_table = soup.find('table', id="lancelot_table_servantlist")

# Step 6: 提取所有从者的URL
servant_urls = []
# 您需要根据网站的实际HTML结构，找到包含从者链接的元素
# 比如，所有从者链接都位于 class="servant-card" 的 div 内部的 a 标签中
for row in servant_table.find_all('tr'):
    cells = row.find_all('td')
    if len(cells) > 2:
        name_cell = cells[2]
        link_tag = name_cell.find('a')
        if link_tag and link_tag.get('href'):
           href = link_tag.get('href')
           ull_url = "https://fgo.wiki" + href
           servant_urls.append(ull_url)


with open('servant_urls.txt', 'w', encoding='utf-8') as f:
    for url in servant_urls:
        f.write(url + '\n')


# Step 7: 关闭浏览器
driver.quit()