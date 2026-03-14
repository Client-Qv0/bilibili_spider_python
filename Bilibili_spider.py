import os
import asyncio
import random
import re
import sys
import itertools
import threading
import tkinter as tk
from tkinter import messagebox
import requests
import json
from bs4 import BeautifulSoup
from lxml import etree
from bilibili_api import video, comment, Credential
from bilibili_api.comment import CommentResourceType, OrderType
import time
import datetime

cookie = ''

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
    'referer': 'https://www.bilibili.com',
    'cookie': "",
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'

}

sessdata = ""
bili_jct = ""
buvid3 = ""

url = ''
bvid = ''
video_url = ''
audio_url = ''
final_filename = ''

video_info_keys = ''
video_key = ''
keys = ''  # 弹幕、评论参数

'''把以"秒"为单位的时间转化为x时x分x秒'''
def format_time(seconds):
    """
    将秒转换为 小时:分钟:秒.毫秒 格式
    """
    # 处理负数？
    if seconds < 0:
        return "-" + format_time(-seconds)

    # 计算小时、分钟、秒
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    # 格式化输出
    if hours > 0:
        return f"{hours}时{minutes:02d}分{secs:05.3f}秒"
    else:
        return f"{minutes}分{secs:05.3f}秒"


'''
检测输入的BV号/网址链接是否正确
如果正确，函数自动获取BV号和网址链接
并用全局变量bvid和url接收
'''
def process_bilibili_input(raw_input):
    """
    处理B站视频输入，返回 (完整的带参数URL, 纯净的BV号)
    """
    raw_input = raw_input.strip()

    # 1. 定义基础的URL模板（不带参数）
    base_url_template = "https://www.bilibili.com/video/{bvid}"
    # 固定的跟踪参数（
    fixed_params = "/?spm_id_from=333.1007.tianma.1-1-1.click"

    # 2. 判断是否为完整链接（包含 bilibili.com/video/）
    video_pattern = r'(https?://(?:www\.)?bilibili\.com/video/)(BV[a-zA-Z0-9]+)([?&/].*)?'
    match = re.search(video_pattern, raw_input)
    global url, bvid
    if match:
        # 情况1：输入是完整链接
        url = raw_input  # 保留用户输入的完整链接（含参数）
        bvid = match.group(2)  # 只提取纯净的BV号
        print(f"检测到链接，纯净BV号：{bvid}")

    # 3. 判断是否为纯BV号（以BV开头）
    elif raw_input.startswith('BV') and re.match(r'^BV[a-zA-Z0-9]{10,}$', raw_input):
        # 情况2：输入是BV号
        bvid = raw_input
        # 用模板拼接完整的URL，并加上你指定的参数
        url = base_url_template.format(bvid=bvid) + fixed_params
        print(f"检测到BV号，已补全链接：{url}")

    else:
        # 情况3：格式错误
        print('B站视频BV号/视频链接有问题QAQ\n程序即将退出')
        global video_info_keys, video_key, keys
        video_info_keys = ''
        video_key = ''
        keys = ''  # 弹幕参数
        time.sleep(2)


'''检测标题是否有Windows文件名不允许的字符：\\ / : * ? " < > |'''
def check_title(base_name):
    flag = 0
    illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    while flag == 0:
        for char in base_name:
            if char not in illegal_chars:
                flag = 1
                continue
            else:
                flag = 0
                print('有Windows文件名不允许的字符：\\ / : * ? " < > |')
                print('请重新输入文件名：')
                base_name = input()
                break
    return base_name


'''下载视频时的加载画面'''
class Spinner:
    """简单的旋转动画类"""

    def __init__(self, message="正在下载"):
        self.message = message
        self.spinner = itertools.cycle(['-', '\\', '|', '/'])
        self.running = False
        self.thread = None

    def spin(self):
        while self.running:
            print(f'\r{self.message}...... {next(self.spinner)}', end='', flush=True)
            time.sleep(0.2)

    def __enter__(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.thread:
            self.thread.join()
        print('\r' + ' ' * 50, end='', flush=True)  # 清除动画行


'''
勾选框函数之一：
获取视频信息，找到并保存视频的名称、视频网址，音频网址
默认不勾选也执行
勾选后，会把获取到的视频信息保存
'''
def get_video_info(get_video_info_keys):  # 修改1：添加参数
    print(f"执行 get_video_info 函数，参数 video_info_keys={get_video_info_keys}")  # 修改2：打印参数
    process_bilibili_input(raw_input=url)
    global sessdata, bili_jct, buvid3
    try:
        sessdata, bili_jct, buvid3 = parse_bilibili_cookie(cookie_str=headers['cookie'])
    except:
        sessdata = ''
        bili_jct = ''
        buvid3 = ''

    base_request = requests.get(url=url, headers=headers)
    info = re.findall('window.__playinfo__=(.*?)</script>', base_request.text)[0]
    info_json = json.loads(info)
    
    info_2 = re.findall('window.__INITIAL_STATE__=(.*?)};', base_request.text)[0] + '}'
    info_2_json = json.loads(info_2)

    _video_url = info_json['data']['dash']['audio'][0]['baseUrl']
    _audio_url = info_json['data']['dash']['video'][0]['baseUrl']
    html = etree.HTML(base_request.text)
    _filename = html.xpath('/html/body/div[2]/div[2]/div[1]/div[1]/div[1]/div/h1')[0]
    print('标题名称：', _filename.text)
    soup = BeautifulSoup(base_request.text, 'lxml')

    _author = soup.find('meta', attrs={'name': 'author'}).get('content')
    print(f'作者：{_author}')
    _video_time = info_json['data']['timelength']
    print(f'视频时长:{format_time(_video_time / 1000)}')
    print(f'BV号：{bvid}')
    print(f'视频链接：{url}')
    try:
        _author_info = html.xpath('//*[@id="mirror-vdcon"]/div[2]/div/div[1]/div[1]/div[2]/div[1]/div/div[2]')[0].text

    except:
        _author_info = soup.find('meta', itemprop="description").get('content').split("作者简介", 1)[1].strip()
    print(f"播放:{info_2_json['videoData']['stat']['view']}", end='  ')
    print(f"点赞:{info_2_json['videoData']['stat']['like']}", end='  ')
    print(f"评论:{info_2_json['videoData']['stat']['reply']}", end='  ')
    print(f"弹幕:{info_2_json['videoData']['stat']['danmaku']}", end='  ')
    print(f"收藏:{info_2_json['videoData']['stat']['favorite']}", end='  ')
    print(f"分享:{info_2_json['videoData']['stat']['share']}", end='  ')
    print(f"投币:{info_2_json['videoData']['stat']['coin']}")
    print(f"aid:{info_2_json['videoData']['stat']['aid']}")
    print(f"oid:{info_2_json['videoData']['stat']['aid']}")
    video_summary = html.xpath('//*[@id="v_desc"]/div[1]/span/text()')[0]
    print('作者简介：', _author_info)
    print()
    print(f'视频简介：\n{video_summary}')
    print('\n')
    global final_filename
    final_filename = check_title(_filename.text)
    if get_video_info_keys == '1':
        with open(f'{final_filename}_视频简介.txt', 'w', encoding='utf-8') as f:
            f.write(f'标题名称：{_filename.text}\n')
            f.write(f'作者：{_author}\n')
            f.write(f'视频时长：{format_time(_video_time / 1000)}\n')
            f.write(f'BV号：{bvid}\n')
            f.write(f'视频链接：{url}\n')
            f.write(f"播放：{info_2_json['videoData']['stat']['view']}  ")
            f.write(f"点赞：{info_2_json['videoData']['stat']['like']}  ")
            f.write(f"评论：{info_2_json['videoData']['stat']['reply']}  ")
            f.write(f"弹幕：{info_2_json['videoData']['stat']['danmaku']}  ")
            f.write(f"收藏：{info_2_json['videoData']['stat']['favorite']}  ")
            f.write(f"分享：{info_2_json['videoData']['stat']['share']}  ")
            f.write(f"投币：{info_2_json['videoData']['stat']['coin']}\n")
            f.write(f"aid：{info_2_json['videoData']['stat']['aid']}\n")
            f.write(f"oid：{info_2_json['videoData']['stat']['aid']}\n\n")
            f.write(f'作者简介：{_author_info}\n')
            f.write(f'视频简介：\n{video_summary}\n\n')
    global video_url,audio_url
    video_url = _video_url
    audio_url = _audio_url
    time.sleep(3)


'''下载视频、音频'''
def download_video(audio_url,video_url):
    with Spinner("正在下载视频"):
        video_content = requests.get(video_url,headers=headers).content
        time.sleep(random.uniform(1, 2))
        audio_content = requests.get(audio_url, headers=headers).content
        with open(f'bilibili_base_video_视频部分.mp4','wb')as f:
            f.write(video_content)
        print('\n已下载视频部分')
        with open(f'bilibili_base_video_音频部分.mp3','wb')as f:
            f.write(audio_content)
        print('已下载音频部分')
    time.sleep(2)


'''
获取ffmpeg视频合并工具的位置，保障代码在pyinstaller后仍能找到文件位置
'''
def get_ffmpeg_path():
    """
    获取ffmpeg.exe的路径（兼容开发环境和打包后）
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe运行环境
        base_path = sys._MEIPASS  # 这是临时解压目录
    else:
        # 开发环境
        base_path = os.path.dirname(os.path.abspath(__file__))

    # 构建ffmpeg路径
    ffmpeg_exe = os.path.join(base_path, "ffmpeg-8.0.1-full_build", "bin", "ffmpeg.exe")

    # 检查文件是否存在（调试用）
    if not os.path.exists(ffmpeg_exe):
        print(f"❌ 找不到ffmpeg，尝试查找...")
        # 列出目录内容看看
        ffmpeg_dir = os.path.join(base_path, "ffmpeg-8.0.1-full_build")
        if os.path.exists(ffmpeg_dir):
            print(f"找到ffmpeg目录，内容：{os.listdir(ffmpeg_dir)}")
        else:
            print(f"base_path: {base_path}")
            print(f"目录内容：{os.listdir(base_path)}")

    return ffmpeg_exe


'''
调用ffmpeg合并视频，音频
b站的视频是画面与音频分离的
'''
def combine_file():
    ffmpeg_address = get_ffmpeg_path()
    cmd = fr'{ffmpeg_address} -i "bilibili_base_video_视频部分.mp4" -i "bilibili_base_video_音频部分.mp3" -c:v copy -c:a aac -strict experimental "bilibili_final_video合成视频.mp4"'
    print('\n正在合并视频中......')
    time.sleep(3.5)
    os.system(cmd)
    time.sleep(2)
    os.replace("bilibili_final_video合成视频.mp4", f'{final_filename}.mp4')


'''
勾选框函数之一：
    下载视频
不勾选、勾选不全的情况下不执行
'''
def get_video(get_video_key):
    if get_video_key == '':
        return
    print(f"执行 get_video 函数，参数 video_key={get_video_key}")
    download_video(video_url, audio_url)
    if '2' in get_video_key:
        combine_file()
    if '1' in get_video_key:
        os.replace("bilibili_base_video_视频部分.mp4", f'{final_filename}_视频部分.mp4')
    else:
        os.system('del bilibili_base_video_视频部分.mp4')
    if '3' in get_video_key:
        os.replace("bilibili_base_video_音频部分.mp3", f'{final_filename}_音频部分.mp3')
    else:
        os.system('del bilibili_base_video_音频部分.mp3')
    print('视频合下载完毕')


'''
勾选框函数之一：
    保存弹幕
不勾选、勾选不全的情况下不执行
'''
def get_demo(get_demo_key):
    if get_demo_key == '':
        return
    flap = 0
    for i in '123456':
        if i in get_demo_key:
            flap = flap + 1
            break
    for i in '789':
        if i in get_demo_key:
            flap = flap + 1
            break
    if flap != 2:
        return
    print(f"执行 get_demo 函数，参数 keys={get_demo_key}")

    time.sleep(random.uniform(2, 3))
    """同步方式获取弹幕"""
    # 1. 先获取cid
    view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"

    resp = requests.get(view_url, headers=headers)
    cid = resp.json()['data']['cid']

    # 2. 直接请求弹幕XML
    danmu_url = f"http://comment.bilibili.com/{cid}.xml"
    print(danmu_url, '\n\n')
    danmu_resp = requests.get(danmu_url, headers=headers)

    # 3. 解析XML
    soup = BeautifulSoup(danmu_resp.content, 'xml')
    # print(soup)
    danmu_s = soup.find_all('d')
    danmu_s.sort(key=lambda x: (
        float(x.get('p').split(',')[0]),
        int(x.get('p').split(',')[4]),
        int(x.get('p').split(',')[7])
    ))

    file_handlers = {}

    if '7' in get_demo_key:
        open(f"{final_filename}_弹幕.txt", 'w', encoding='utf-8')
        file_handlers['1'] = open(f"{final_filename}_弹幕.txt", 'a', encoding='utf-8')

    if '8' in get_demo_key:
        open(f"{final_filename}_弹幕.xlsx", 'w', encoding='utf-8')
        file_handlers['2'] = open(f"{final_filename}_弹幕.xlsx", 'a', encoding='utf-8-sig')

    if '9' in get_demo_key:
        open(f"{final_filename}_弹幕.md", 'w', encoding='utf-8')
        file_handlers['3'] = open(f"{final_filename}_弹幕.md", 'a', encoding='utf-8')
        # 如果是新文件，写入标题
        if os.path.getsize(f"{final_filename}_弹幕.md") == 0:
            file_handlers['3'].write("# B站弹幕记录\n\n")
            file_handlers['3'].write(f"抓取时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    try:
        for dm in danmu_s:
            # 解析弹幕数据
            dm_list = dm.get('p').split(',')
            dm_time = format_time(float(dm_list[0]))
            dm_color = format(int(dm_list[3]), '06x')
            dm_launch_time = datetime.datetime.fromtimestamp(int(dm_list[4]))

            # 弹幕类型转换
            dm_type = dm_list[1]
            if dm_list[1] == '1':
                dm_type = '滚动'
            elif dm_list[1] == '5':
                dm_type = '置顶'
            elif dm_list[1] == '4':
                dm_type = '底部'

            dm_id = dm_list[7]
            dm_text = dm.text

            # ========== 控制台输出（保持不变）==========
            console_parts = []
            if '1' in get_demo_key:
                console_parts.append(f'时间:{dm_time}')
            if '2' in get_demo_key:
                console_parts.append(f'发布:{dm_launch_time}')
            if '3' in get_demo_key:
                console_parts.append(f'类型:{dm_type}')
            if '4' in get_demo_key:
                console_parts.append(f'颜色:#{dm_color}')
            if '5' in get_demo_key:
                console_parts.append(f'弹幕编号:{dm_id}')

            if console_parts:
                print(' '.join(console_parts))

            if '6' in get_demo_key:
                print(f'内容:{dm_text}')
            print()

            # ========== TXT格式写入 ==========
            if '7' in get_demo_key and '1' in file_handlers:
                file_txt = file_handlers['1']
                txt_parts = []
                if '1' in get_demo_key:
                    txt_parts.append(f'时间:{dm_time}')
                if '2' in get_demo_key:
                    txt_parts.append(f'发布:{dm_launch_time}')
                if '3' in get_demo_key:
                    txt_parts.append(f'类型:{dm_type}')
                if '4' in get_demo_key:
                    txt_parts.append(f'颜色:#{dm_color}')
                if '5' in get_demo_key:
                    txt_parts.append(f'弹幕编号:{dm_id}')

                if txt_parts:
                    file_txt.write(' '.join(txt_parts) + '\n')

                if '6' in get_demo_key:
                    file_txt.write(f'内容:{dm_text}\n')

                file_txt.write('\n')
                file_txt.flush()

            # ========== Excel格式写入（用制表符分隔）==========
            if '8' in get_demo_key and '2' in file_handlers:
                file_excel = file_handlers['2']
                excel_cells = []
                if '1' in get_demo_key:
                    excel_cells.append(dm_time+' ')
                if '2' in get_demo_key:
                    excel_cells.append(str(dm_launch_time)+' ')
                if '3' in get_demo_key:
                    excel_cells.append(dm_type+' ')
                if '4' in get_demo_key:
                    excel_cells.append(f'#{dm_color}c'+' ')
                if '5' in get_demo_key:
                    excel_cells.append(dm_id+' ')
                if '6' in get_demo_key:
                    excel_cells.append('\n'+dm_text+' ')

                file_excel.write('\t'.join(excel_cells) + '\n')
                file_excel.flush()

            # ========== Markdown格式写入 ==========
            if '9' in get_demo_key and '3' in file_handlers:
                file_md = file_handlers['3']

                # 构建第一行的各个部分
                line_parts = []

                if '1' in get_demo_key:
                    line_parts.append(f'**时间：** {dm_time}')

                if '2' in get_demo_key:
                    line_parts.append(f'**发布：** {dm_launch_time}')

                if '3' in get_demo_key:
                    line_parts.append(f'**类型：** {dm_type}')

                if '4' in get_demo_key:
                    line_parts.append(f'**颜色：** <span style="color:#{dm_color};">⬤ </span>#{dm_color}')

                if '5' in get_demo_key:
                    line_parts.append(f'**ID：** {dm_id}')

                # 写入第一行（如果有任何字段被选中）
                if line_parts:
                    file_md.write(f'- {" | ".join(line_parts)}\n')

                # 写入内容
                if '6' in get_demo_key:
                    if dm_color != "ffffff":
                        file_md.write(f'  **内容：**<span style="color:#{dm_color};">{dm_text}</span>\n')
                    else:
                        file_md.write(f'  **内容：**：{dm_text}\n')

                # 每条弹幕后加空行
                file_md.write('\n\n')
                file_md.flush()

    finally:
        # 关闭所有文件
        for f in file_handlers.values():
            f.flush()
            f.close()

        if file_handlers:
            print(f"✅ 弹幕数据已追加写入到文件")
    time.sleep(random.uniform(1,3))


'''
程序ui主界面
'''
class BilibiliCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("B站爬虫工具")
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        # 存储各控件状态的变量
        self.url_var = tk.StringVar()
        self.cookie_var = tk.StringVar()
        self.use_cookie = tk.BooleanVar(value=False)

        # 主勾选框
        self.video_info_var = tk.BooleanVar(value=False)
        self.video_var = tk.BooleanVar(value=False)
        self.comment_var = tk.BooleanVar(value=False)
        self.danmu_var = tk.BooleanVar(value=False)

        # 视频子选项
        self.video_silent = tk.BooleanVar(value=False)  # 1
        self.video_normal = tk.BooleanVar(value=False)  # 2
        self.video_audio = tk.BooleanVar(value=False)  # 3

        # 弹幕子选项（编号1-6）- 全部一列
        self.danmu_time = tk.BooleanVar(value=False)  # 1
        self.danmu_send_time = tk.BooleanVar(value=False)  # 2
        self.danmu_type = tk.BooleanVar(value=False)  # 3
        self.danmu_color = tk.BooleanVar(value=False)  # 4
        self.danmu_id = tk.BooleanVar(value=False)  # 5
        self.danmu_content = tk.BooleanVar(value=False)  # 6

        # 弹幕保存格式（编号7-9）- 放在右侧一列
        self.danmu_txt = tk.BooleanVar(value=False)  # 7
        self.danmu_excel = tk.BooleanVar(value=False)  # 8
        self.danmu_md = tk.BooleanVar(value=False)  # 9

        # 评论子选项（0-B）- 全部一列
        self.comment_username = tk.BooleanVar(value=False)  # 0
        self.comment_avatar = tk.BooleanVar(value=False)  # 1
        self.comment_content = tk.BooleanVar(value=False)  # 2
        self.comment_like = tk.BooleanVar(value=False)  # 3
        self.comment_vid = tk.BooleanVar(value=False)  # 4
        self.comment_oid = tk.BooleanVar(value=False)  # 5
        self.comment_rpid = tk.BooleanVar(value=False)  # 6
        self.comment_root = tk.BooleanVar(value=False)  # 7
        self.comment_level = tk.BooleanVar(value=False)  # 8
        self.comment_gender = tk.BooleanVar(value=False)  # 9
        self.comment_ip = tk.BooleanVar(value=False)  # A
        self.comment_time = tk.BooleanVar(value=False)  # B

        # 评论保存格式（X-Z）- 放在右侧一列
        self.comment_excel = tk.BooleanVar(value=False)  # X
        self.comment_txt = tk.BooleanVar(value=False)  # Y
        self.comment_md = tk.BooleanVar(value=False)  # Z

        # 创建所有框架
        self.setup_ui()

        # 绑定主勾选框的事件
        self.video_info_check.config(command=self.toggle_video_info_options)
        self.video_check.config(command=self.toggle_video_options)
        self.danmu_check.config(command=self.toggle_danmu_options)
        self.comment_check.config(command=self.toggle_comment_options)

        # 初始设置所有子选项为灰色不可选
        self.set_all_subs_state('disabled')

    def setup_ui(self):
        # ===== 第1行：URL区（横条）=====
        url_frame = tk.Frame(self.root, bg='#f0f0f0', relief=tk.RAISED, bd=2)
        url_frame.place(x=10, y=10, width=780, height=70)

        tk.Label(url_frame, text="请输入B站视频BV号/视频链接：").place(x=10, y=10)
        self.url_entry = tk.Entry(url_frame, textvariable=self.url_var, width=80)
        self.url_entry.place(x=10, y=35, width=760)

        # ===== 右侧Cookie区（位置不变）=====
        self.cookie_frame = tk.Frame(self.root, bg='#d0d0d0', relief=tk.RAISED, bd=2)
        self.cookie_frame.place(x=270, y=90, width=520, height=150)

        self.cookie_check = tk.Checkbutton(
            self.cookie_frame, text="使用cookie：", variable=self.use_cookie,
            command=self.on_cookie_check
        )
        self.cookie_check.place(x=10, y=10)

        self.cookie_text = tk.Text(self.cookie_frame, width=60, height=4, state='disabled')
        self.cookie_text.place(x=10, y=40, width=500, height=70)

        # ===== 四个主勾选框（按照你提供的坐标）=====
        # 视频信息 - 左上
        self.video_info_check = tk.Checkbutton(
            self.root, text="视频信息", variable=self.video_info_var,
            font=('Arial', 10, 'bold')
        )
        self.video_info_check.place(x=20, y=100)

        # 视频 - 左中
        self.video_check = tk.Checkbutton(
            self.root, text="视频", variable=self.video_var,
            font=('Arial', 10, 'bold')
        )
        self.video_check.place(x=20, y=250)

        # 弹幕 - 左下
        self.danmu_check = tk.Checkbutton(
            self.root, text="弹幕", variable=self.danmu_var,
            font=('Arial', 10, 'bold')
        )
        self.danmu_check.place(x=20, y=400)

        # 评论 - 中下偏右
        self.comment_check = tk.Checkbutton(
            self.root, text="评论", variable=self.comment_var,
            font=('Arial', 10, 'bold'), state='disabled'
        )
        self.comment_check.place(x=400, y=400)

        # ===== 视频子选项框架（位于视频右侧）- 默认灰色 =====
        self.video_sub_frame = tk.Frame(self.root, bg='#FFAEC9', relief=tk.RAISED, bd=2)
        self.video_sub_frame.place(x=100, y=210, width=160, height=130)

        tk.Label(self.video_sub_frame, text="视频选项", bg='#FFAEC9', font=('Arial', 9, 'bold')).place(x=10, y=5)

        self.video_silent_check = tk.Checkbutton(
            self.video_sub_frame, text="1.无声视频", variable=self.video_silent,
            state='disabled'
        )
        self.video_silent_check.place(x=20, y=30)

        self.video_normal_check = tk.Checkbutton(
            self.video_sub_frame, text="2.视频", variable=self.video_normal,
            state='disabled'
        )
        self.video_normal_check.place(x=20, y=60)

        self.video_audio_check = tk.Checkbutton(
            self.video_sub_frame, text="3.音频", variable=self.video_audio,
            state='disabled'
        )
        self.video_audio_check.place(x=20, y=90)

        # ===== 弹幕子选项框架（位于弹幕右侧）- 默认绿色 =====
        # 弹幕字段区
        self.danmu_field_frame = tk.Frame(self.root, bg='#88FFC4', relief=tk.RAISED, bd=2)
        self.danmu_field_frame.place(x=100, y=350, width=150, height=200)

        tk.Label(self.danmu_field_frame, text="弹幕字段", bg='#88FFC4', font=('Arial', 9, 'bold')).place(x=10, y=5)

        # 全部一列，从上到下
        y_pos = 30
        self.danmu_time_check = tk.Checkbutton(self.danmu_field_frame, text="1.时间", variable=self.danmu_time,
                                               state='disabled')
        self.danmu_time_check.place(x=20, y=y_pos)
        y_pos += 25

        self.danmu_send_time_check = tk.Checkbutton(self.danmu_field_frame, text="2.发布时间",
                                                    variable=self.danmu_send_time, state='disabled')
        self.danmu_send_time_check.place(x=20, y=y_pos)
        y_pos += 25

        self.danmu_type_check = tk.Checkbutton(self.danmu_field_frame, text="3.类型", variable=self.danmu_type,
                                               state='disabled')
        self.danmu_type_check.place(x=20, y=y_pos)
        y_pos += 25

        self.danmu_color_check = tk.Checkbutton(self.danmu_field_frame, text="4.颜色", variable=self.danmu_color,
                                                state='disabled')
        self.danmu_color_check.place(x=20, y=y_pos)
        y_pos += 25

        self.danmu_id_check = tk.Checkbutton(self.danmu_field_frame, text="5.弹幕编号", variable=self.danmu_id,
                                             state='disabled')
        self.danmu_id_check.place(x=20, y=y_pos)
        y_pos += 25

        self.danmu_content_check = tk.Checkbutton(self.danmu_field_frame, text="6.内容", variable=self.danmu_content,
                                                  state='disabled')
        self.danmu_content_check.place(x=20, y=y_pos)

        # 弹幕保存格式区（放在弹幕字段区右侧）- 默认灰色
        self.danmu_save_frame = tk.Frame(self.root, bg='#A8FFD3', relief=tk.RAISED, bd=2)
        self.danmu_save_frame.place(x=250, y=380, width=150, height=150)

        tk.Label(self.danmu_save_frame, text="保存格式", bg='#A8FFD3', font=('Arial', 9, 'bold')).place(x=10, y=5)

        y_pos = 30
        self.danmu_txt_check = tk.Checkbutton(self.danmu_save_frame, text="7.txt", variable=self.danmu_txt,
                                              state='disabled')
        self.danmu_txt_check.place(x=20, y=y_pos)
        y_pos += 30

        self.danmu_excel_check = tk.Checkbutton(self.danmu_save_frame, text="8.excel", variable=self.danmu_excel,
                                                state='disabled')
        self.danmu_excel_check.place(x=20, y=y_pos)
        y_pos += 30

        self.danmu_md_check = tk.Checkbutton(self.danmu_save_frame, text="9.md", variable=self.danmu_md,
                                             state='disabled')
        self.danmu_md_check.place(x=20, y=y_pos)

        # ===== 评论子选项框架（位于评论右侧）- 默认灰色 =====
        # 评论字段区
        self.comment_field_frame = tk.Frame(self.root, bg='#7DFFFF', relief=tk.RAISED, bd=2)
        self.comment_field_frame.place(x=500, y=250, width=150, height=320)

        tk.Label(self.comment_field_frame, text="评论字段", bg='#7DFFFF', font=('Arial', 9, 'bold')).place(x=10, y=5)

        # 全部一列，从上到下
        y_pos = 30
        self.comment_username_check = tk.Checkbutton(self.comment_field_frame, text="0.用户名",
                                                     variable=self.comment_username, state='disabled')
        self.comment_username_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_avatar_check = tk.Checkbutton(self.comment_field_frame, text="1.头像",
                                                   variable=self.comment_avatar, state='disabled')
        self.comment_avatar_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_content_check = tk.Checkbutton(self.comment_field_frame, text="2.内容",
                                                    variable=self.comment_content, state='disabled')
        self.comment_content_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_like_check = tk.Checkbutton(self.comment_field_frame, text="3.点赞", variable=self.comment_like,
                                                 state='disabled')
        self.comment_like_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_vid_check = tk.Checkbutton(self.comment_field_frame, text="4.vid", variable=self.comment_vid,
                                                state='disabled')
        self.comment_vid_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_oid_check = tk.Checkbutton(self.comment_field_frame, text="5.会员", variable=self.comment_oid,
                                                state='disabled')
        self.comment_oid_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_rpid_check = tk.Checkbutton(self.comment_field_frame, text="6.rpid", variable=self.comment_rpid,
                                                 state='disabled')
        self.comment_rpid_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_root_check = tk.Checkbutton(self.comment_field_frame, text="7.root", variable=self.comment_root,
                                                 state='disabled')
        self.comment_root_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_level_check = tk.Checkbutton(self.comment_field_frame, text="8.等级", variable=self.comment_level,
                                                  state='disabled')
        self.comment_level_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_gender_check = tk.Checkbutton(self.comment_field_frame, text="9.性别",
                                                   variable=self.comment_gender, state='disabled')
        self.comment_gender_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_ip_check = tk.Checkbutton(self.comment_field_frame, text="A.IP地址", variable=self.comment_ip,
                                               state='disabled')
        self.comment_ip_check.place(x=20, y=y_pos)
        y_pos += 22

        self.comment_time_check = tk.Checkbutton(self.comment_field_frame, text="B.发布时间",
                                                 variable=self.comment_time, state='disabled')
        self.comment_time_check.place(x=20, y=y_pos)

        # 评论保存格式区（放在评论字段区右侧）- 默认灰色
        self.comment_save_frame = tk.Frame(self.root, bg='#7DFFFF', relief=tk.RAISED, bd=2)
        self.comment_save_frame.place(x=655, y=350, width=150, height=150)

        tk.Label(self.comment_save_frame, text="保存格式", bg='#7DFFFF', font=('Arial', 9, 'bold')).place(x=10, y=10)

        y_pos = 40
        self.comment_excel_check = tk.Checkbutton(self.comment_save_frame, text="X.excel", variable=self.comment_excel,
                                                  state='disabled')
        self.comment_excel_check.place(x=20, y=y_pos)
        y_pos += 30

        self.comment_txt_check = tk.Checkbutton(self.comment_save_frame, text="Y.txt", variable=self.comment_txt,
                                                state='disabled')
        self.comment_txt_check.place(x=20, y=y_pos)
        y_pos += 30

        self.comment_md_check = tk.Checkbutton(self.comment_save_frame, text="Z.md", variable=self.comment_md,
                                               state='disabled')
        self.comment_md_check.place(x=20, y=y_pos)

        # ===== 底部：运行按钮 =====
        btn_frame = tk.Frame(self.root, relief=tk.RAISED, bd=2)
        btn_frame.place(x=10, y=560, width=780, height=30)

        self.run_btn = tk.Button(btn_frame, text="运行", command=self.run_crawl, width=20, bg='#4CAF50', fg='white')
        self.run_btn.place(relx=0.5, rely=0.5, anchor='center')

    def set_all_subs_state(self, state):
        """设置所有子选项框的状态"""
        # 视频子选项
        self.video_silent_check.config(state=state)
        self.video_normal_check.config(state=state)
        self.video_audio_check.config(state=state)

        # 弹幕子选项
        self.danmu_time_check.config(state=state)
        self.danmu_send_time_check.config(state=state)
        self.danmu_type_check.config(state=state)
        self.danmu_color_check.config(state=state)
        self.danmu_id_check.config(state=state)
        self.danmu_content_check.config(state=state)
        self.danmu_txt_check.config(state=state)
        self.danmu_excel_check.config(state=state)
        self.danmu_md_check.config(state=state)

        # 评论子选项
        self.comment_username_check.config(state=state)
        self.comment_avatar_check.config(state=state)
        self.comment_content_check.config(state=state)
        self.comment_like_check.config(state=state)
        self.comment_vid_check.config(state=state)
        self.comment_oid_check.config(state=state)
        self.comment_rpid_check.config(state=state)
        self.comment_root_check.config(state=state)
        self.comment_level_check.config(state=state)
        self.comment_gender_check.config(state=state)
        self.comment_ip_check.config(state=state)
        self.comment_time_check.config(state=state)
        self.comment_excel_check.config(state=state)
        self.comment_txt_check.config(state=state)
        self.comment_md_check.config(state=state)

    def toggle_video_info_options(self):
        """视频信息被勾选时"""
        if self.video_info_var.get():
            # 视频信息不需要子选项，只执行函数
            pass

    def toggle_video_options(self):
        """视频被勾选时"""
        if self.video_var.get():
            self.video_silent_check.config(state='normal')
            self.video_normal_check.config(state='normal')
            self.video_audio_check.config(state='normal')
        else:
            self.video_silent_check.config(state='disabled')
            self.video_normal_check.config(state='disabled')
            self.video_audio_check.config(state='disabled')
            # 同时取消勾选
            self.video_silent.set(False)
            self.video_normal.set(False)
            self.video_audio.set(False)

    def toggle_danmu_options(self):
        """弹幕被勾选时"""
        danmu_state = 'normal' if self.danmu_var.get() else 'disabled'

        # 弹幕字段
        self.danmu_time_check.config(state=danmu_state)
        self.danmu_send_time_check.config(state=danmu_state)
        self.danmu_type_check.config(state=danmu_state)
        self.danmu_color_check.config(state=danmu_state)
        self.danmu_id_check.config(state=danmu_state)
        self.danmu_content_check.config(state=danmu_state)

        # 弹幕保存格式
        self.danmu_txt_check.config(state=danmu_state)
        self.danmu_excel_check.config(state=danmu_state)
        self.danmu_md_check.config(state=danmu_state)

        if not self.danmu_var.get():
            # 取消所有弹幕子选项的勾选
            self.danmu_time.set(False)
            self.danmu_send_time.set(False)
            self.danmu_type.set(False)
            self.danmu_color.set(False)
            self.danmu_id.set(False)
            self.danmu_content.set(False)
            self.danmu_txt.set(False)
            self.danmu_excel.set(False)
            self.danmu_md.set(False)

    def toggle_comment_options(self):
        """评论被勾选时"""
        if self.comment_var.get() and self.use_cookie.get():
            comment_state = 'normal'
        else:
            comment_state = 'disabled'
            if not self.use_cookie.get():
                self.comment_var.set(False)

        # 评论字段
        self.comment_username_check.config(state=comment_state)
        self.comment_avatar_check.config(state=comment_state)
        self.comment_content_check.config(state=comment_state)
        self.comment_like_check.config(state=comment_state)
        self.comment_vid_check.config(state=comment_state)
        self.comment_oid_check.config(state=comment_state)
        self.comment_rpid_check.config(state=comment_state)
        self.comment_root_check.config(state=comment_state)
        self.comment_level_check.config(state=comment_state)
        self.comment_gender_check.config(state=comment_state)
        self.comment_ip_check.config(state=comment_state)
        self.comment_time_check.config(state=comment_state)

        # 评论保存格式
        self.comment_excel_check.config(state=comment_state)
        self.comment_txt_check.config(state=comment_state)
        self.comment_md_check.config(state=comment_state)

        if comment_state == 'disabled':
            # 取消所有评论子选项的勾选
            self.comment_username.set(False)
            self.comment_avatar.set(False)
            self.comment_content.set(False)
            self.comment_like.set(False)
            self.comment_vid.set(False)
            self.comment_oid.set(False)
            self.comment_rpid.set(False)
            self.comment_root.set(False)
            self.comment_level.set(False)
            self.comment_gender.set(False)
            self.comment_ip.set(False)
            self.comment_time.set(False)
            self.comment_excel.set(False)
            self.comment_txt.set(False)
            self.comment_md.set(False)

    def on_cookie_check(self):
        """处理Cookie勾选事件"""
        if self.use_cookie.get():
            messagebox.showinfo("***cookie是你B站账号的登录信息***", "一、使用登录状态的cookie，可以爬取：\n    ①1080p高清视频\n    ②当前视频页的所有评论\n\n二、获取cookie的步骤，可以参考《使用说明》文件\n\n三、未使用、使用未登录、错误的cookie，仅能爬取360p的视频+少量评论\n\n注意：\n    登录状态下的cookie包涵了你的B站账号信息，请保持适当频率的爬取，切勿进行商业用途~~")
            self.cookie_text.config(state='normal')
            self.comment_check.config(state='normal')
            # 如果评论之前被勾选了，自动启用它的子选项
            if self.comment_var.get():
                self.toggle_comment_options()
        else:
            self.cookie_text.config(state='disabled')
            self.comment_check.config(state='disabled')
            self.comment_var.set(False)
            self.toggle_comment_options()

    def run_crawl(self):
        """运行按钮事件 - 所有函数都在这里执行"""
        global url
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入B站视频BV号/视频链接！")
            return

        print("=" * 50)
        print("开始执行爬取任务")
        print(f"视频地址/ID: {url}")

        if self.use_cookie.get():
            global cookie
            global headers
            cookie = self.cookie_text.get("1.0", "end-1c").strip()
            headers['cookie'] = cookie
            print(f"使用cookie: {cookie[:20]}...")

        # 1. 视频信息 - 勾选了才执行，video_info_keys='1'，否则'0'
        global video_info_keys
        video_info_keys = '1' if self.video_info_var.get() else '0'
        get_video_info(video_info_keys)  # 修改：总是调用，传入参数

        # 2. 视频子选项
        global video_key
        if self.video_var.get():
            video_key = ''
            if self.video_silent.get():
                video_key += '1'
            if self.video_normal.get():
                video_key += '2'
            if self.video_audio.get():
                video_key += '3'
            if video_key:
                get_video(video_key)

        # 3. 弹幕子选项
        if self.danmu_var.get():
            global keys
            keys = ''
            if self.danmu_time.get():
                keys += '1'
            if self.danmu_send_time.get():
                keys += '2'
            if self.danmu_type.get():
                keys += '3'
            if self.danmu_color.get():
                keys += '4'
            if self.danmu_id.get():
                keys += '5'
            if self.danmu_content.get():
                keys += '6'
            if self.danmu_txt.get():
                keys += '7'
            if self.danmu_excel.get():
                keys += '8'
            if self.danmu_md.get():
                keys += '9'
            if keys:
                get_demo(keys)

        # 4. 评论子选项
        if self.comment_var.get() and self.use_cookie.get():
            keys = ''
            if self.comment_username.get():
                keys += '0'
            if self.comment_avatar.get():
                keys += '1'
            if self.comment_content.get():
                keys += '2'
            if self.comment_like.get():
                keys += '3'
            if self.comment_vid.get():
                keys += '4'
            if self.comment_oid.get():
                keys += '5'
            if self.comment_rpid.get():
                keys += '6'
            if self.comment_root.get():
                keys += '7'
            if self.comment_level.get():
                keys += '8'
            if self.comment_gender.get():
                keys += '9'
            if self.comment_ip.get():
                keys += 'A'
            if self.comment_time.get():
                keys += 'B'
            if self.comment_excel.get():
                keys += 'X'
            if self.comment_txt.get():
                keys += 'Y'
            if self.comment_md.get():
                keys += 'Z'
            if keys:
                get_comments(keys)

        print("=" * 50)
        messagebox.showinfo("游戏开始！", "爬虫运行完毕0v0")


'''
勾选框函数之一：
    保存评论
不勾选cookie的情况下无法勾选该选项框
不勾选、勾选不全的情况下不执行
'''
def get_comments(get_comments_key):
    if get_comments_key == '':
        return
    flap = 0
    for i in '0123456789AB':
        if i in get_comments_key:
            flap = flap + 1
            break
    for i in 'XYZ':
        if i in get_comments_key:
            flap = flap + 1
            break
    if flap != 2:
        return

    if 'X' in get_comments_key:
        # Excel格式 - 使用制表符分隔，方便导入Excel
        open(f"{final_filename}_评论.xlsx", 'w', encoding='utf-8-sig')

    if 'Y' in get_comments_key:
        # 普通文本格式
        open(f"{final_filename}_评论.txt", 'w', encoding='utf-8')

    if 'Z' in get_comments_key:
        # Markdown格式
        open(f"{final_filename}_评论.md", 'w', encoding='utf-8')

    print(f"执行 get_comments 函数，参数 comments_key={get_comments_key}")

    async def run_comments():
        credential = Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            buvid3=buvid3
        )

        # 爬取全部评论
        all_comments = await get_all_comments(
            get_comments_key=get_comments_key,
            bvid=bvid,
            credential=credential,
            delay=5  # 每页间隔5秒
        )

        print(f"\n总共获取到 {len(all_comments)} 条评论")
        return all_comments

    # 执行异步函数
    asyncio.run(run_comments())


'''
把评论内容写入到文件
因B站的主评论和追评处于不同的网页里，如果有追评的情况下会递归调用
'''
async def print_comments(contents, video_oid, credential, get_comments_key, key=0):
    indent = "        " * key

    # 根据输出类型打开对应的文件（追加模式）
    file_handlers = {}

    if 'X' in get_comments_key:
        # Excel格式 - 使用制表符分隔，方便导入Excel
        file_handlers['X'] = open(f"{final_filename}_评论.xlsx", 'a', encoding='utf-8-sig')

    if 'Y' in get_comments_key:
        # 普通文本格式
        file_handlers['Y'] = open(f"{final_filename}_评论.txt", 'a', encoding='utf-8')

    if 'Z' in get_comments_key:
        # Markdown格式
        file_handlers['Z'] = open(f"{final_filename}_评论.md", 'a', encoding='utf-8')

    try:
        for index in contents:
            if 'X' in get_comments_key:
                # 追加写入execl表格
                if '0' in get_comments_key:
                    print(f'{indent}用户名：', index['member']['uname'])
                    file_handlers['X'].write(f'{indent}用户名：{index["member"]["uname"]}\n')
                if '1' in get_comments_key:
                    print(f'{indent}头像：', index['member']['avatar'])
                    file_handlers['X'].write(f'{indent}头像：{index["member"]["avatar"]}\n')
                if '2' in get_comments_key:
                    print(f'{indent}评论内容：', index['content']['message'], end='  ')
                    file_handlers['X'].write(f'{indent}评论内容：{index["content"]["message"]}')
                    if 'pictures' in index['content']:
                        print(f'{indent}图片：', index['content']['pictures'][0]['img_src'])
                        file_handlers['X'].write(f'  {indent}图片：{index["content"]["pictures"][0]["img_src"]}\n')
                    else:
                        print()
                        file_handlers['X'].write('\n')
                if '3' in get_comments_key:
                    print(f'{indent}点赞：', index['like'])
                    file_handlers['X'].write(f'{indent}点赞：{index["like"]}\n')
                if '4' in get_comments_key:
                    print(f'{indent}vid：', index['mid_str'])
                    file_handlers['X'].write(f'{indent}vid：{index["mid_str"]}\n')
                if '5' in get_comments_key:
                    print(f'{indent}会员：', index['member']['vip']['label']['text'])
                    file_handlers['X'].write(f'{indent}会员：{index["member"]["vip"]["label"]["text"]}\n')
                if '6' in get_comments_key:
                    print(f'{indent}rpid：', index['rpid_str'])
                    file_handlers['X'].write(f'{indent}rpid：{index["rpid_str"]}\n')
                if '7' in get_comments_key:
                    print(f'{indent}root：', index['rpid_str'])
                    file_handlers['X'].write(f'{indent}root：{index["rpid_str"]}\n')
                if '8' in get_comments_key:
                    print(f'{indent}等级：', index['member']['level_info']['current_level'])
                    file_handlers['X'].write(f'{indent}等级：{index["member"]["level_info"]["current_level"]}\n')
                if '9' in get_comments_key:
                    print(f'{indent}性别：', index['member']['sex'])
                    file_handlers['X'].write(f'{indent}性别：{index["member"]["sex"]}\n')
                if 'A' in get_comments_key:
                    try:
                        print(f"{indent}" + index['reply_control']['location'])  # IP属地
                        file_handlers['X'].write(f"{indent}{index['reply_control']['location']}\n")
                    except:
                        print(f'{indent}IP属地：未知（需cookie）')
                        file_handlers['X'].write(f'{indent}IP属地：未知（需cookie）\n')
                if 'B' in get_comments_key:
                    print(f'{indent}发布时间', datetime.datetime.fromtimestamp(index['ctime']))
                    file_handlers['X'].write(f'{indent}发布时间{datetime.datetime.fromtimestamp(index["ctime"])}\n')
                print(f'{indent}追评：', index['rcount'], '条')
                file_handlers['X'].write(f'{indent}追评：{index["rcount"]}条\n\n')

            if 'Y' in get_comments_key:
                # 追加写入txt文本

                if '0' in get_comments_key:
                    print(f'{indent}用户名：', index['member']['uname'])
                    file_handlers['Y'].write(f'{indent}用户名：{index["member"]["uname"]}\n')
                if '1' in get_comments_key:
                    print(f'{indent}头像：', index['member']['avatar'])
                    file_handlers['Y'].write(f'{indent}头像：{index["member"]["avatar"]}\n')
                if '2' in get_comments_key:
                    print(f'{indent}评论内容：', index['content']['message'], end='  ')
                    file_handlers['Y'].write(f'{indent}评论内容：{index["content"]["message"]}')
                    if 'pictures' in index['content']:
                        print(f'{indent}图片：', index['content']['pictures'][0]['img_src'])
                        file_handlers['Y'].write(f'  {indent}图片：{index["content"]["pictures"][0]["img_src"]}\n')
                    else:
                        print()
                        file_handlers['Y'].write('\n')
                if '3' in get_comments_key:
                    print(f'{indent}点赞：', index['like'])
                    file_handlers['Y'].write(f'{indent}点赞：{index["like"]}\n')
                if '4' in get_comments_key:
                    print(f'{indent}vid：', index['mid_str'])
                    file_handlers['Y'].write(f'{indent}vid：{index["mid_str"]}\n')
                if '5' in get_comments_key:
                    print(f'{indent}会员：', index['member']['vip']['label']['text'])
                    file_handlers['Y'].write(f'{indent}会员：{index["member"]["vip"]["label"]["text"]}\n')
                if '6' in get_comments_key:
                    print(f'{indent}rpid：', index['rpid_str'])
                    file_handlers['Y'].write(f'{indent}rpid：{index["rpid_str"]}\n')
                if '7' in get_comments_key:
                    print(f'{indent}root：', index['rpid_str'])
                    file_handlers['Y'].write(f'{indent}root：{index["rpid_str"]}\n')
                if '8' in get_comments_key:
                    print(f'{indent}等级：', index['member']['level_info']['current_level'])
                    file_handlers['Y'].write(f'{indent}等级：{index["member"]["level_info"]["current_level"]}\n')
                if '9' in get_comments_key:
                    print(f'{indent}性别：', index['member']['sex'])
                    file_handlers['Y'].write(f'{indent}性别：{index["member"]["sex"]}\n')
                if 'A' in get_comments_key:
                    try:
                        print(f"{indent}" + index['reply_control']['location'])  # IP属地
                        file_handlers['Y'].write(f"{indent}{index['reply_control']['location']}\n")
                    except:
                        print(f'{indent}IP属地：未知（需cookie）')
                        file_handlers['Y'].write(f'{indent}IP属地：未知（需cookie）\n')
                if 'B' in get_comments_key:
                    print(f'{indent}发布时间', datetime.datetime.fromtimestamp(index['ctime']))
                    file_handlers['Y'].write(f'{indent}发布时间{datetime.datetime.fromtimestamp(index["ctime"])}\n')
                print(f'{indent}追评：', index['rcount'], '条')
                file_handlers['Y'].write(f'{indent}追评：{index["rcount"]}条\n\n')

            if 'Z' in get_comments_key:
                # 追加写入md（其中如果有图片，就插入图片链接，使图片在md里显示）

                # 定义Markdown列表缩进
                # 主评论（第一层级）用 "- "
                # 追评（第二层级）用 "  - "
                # key=0 主评论，key>=1 追评
                md_indent = "- " if key == 0 else "  - " * key

                # 用户名（列表项主标记）
                if '0' in get_comments_key:
                    print(f"{indent * 2}用户名：{index['member']['uname']}")
                    file_handlers['Z'].write(f'{md_indent}**用户名：{index["member"]["uname"]}**\n')

                # 后续内容使用固定缩进（比列表标记多两个空格）
                content_indent = "  " if key == 0 else "    " * key

                if '1' in get_comments_key:
                    print(f'{indent * 2}头像：', index['member']['avatar'])
                    file_handlers['Z'].write(
                        f'{content_indent}头像：<img src="{index["member"]["avatar"]}" width="50" height="50">\n')

                if '2' in get_comments_key:
                    print(f'{indent * 2}评论内容：', index['content']['message'], end='  ')
                    file_handlers['Z'].write(f'{content_indent}评论内容：{index["content"]["message"]}')

                    if 'pictures' in index['content']:
                        print(f'{indent * 2}图片：', index['content']['pictures'][0]['img_src'])
                        file_handlers['Z'].write(
                            f'\n{content_indent}图片：<img src="{index["content"]["pictures"][0]["img_src"]}" width="300">\n')
                    else:
                        print()
                        file_handlers['Z'].write('\n')

                if '3' in get_comments_key:
                    print(f'{indent}点赞：', index['like'])
                    file_handlers['Z'].write(f'{content_indent}点赞：{index["like"]}\n')

                if '4' in get_comments_key:
                    print(f'{indent}vid：', index['mid_str'])
                    file_handlers['Z'].write(f'{content_indent}vid：{index["mid_str"]}\n')

                if '5' in get_comments_key:
                    print(f'{indent}会员：', index['member']['vip']['label']['text'])
                    file_handlers['Z'].write(f'{content_indent}会员：{index["member"]["vip"]["label"]["text"]}\n')

                if '6' in get_comments_key:
                    print(f'{indent}rpid：', index['rpid_str'])
                    file_handlers['Z'].write(f'{content_indent}rpid：{index["rpid_str"]}\n')

                if '7' in get_comments_key:
                    print(f'{indent}root：', index['rpid_str'])
                    file_handlers['Z'].write(f'{content_indent}root：{index["rpid_str"]}\n')

                if '8' in get_comments_key:
                    print(f'{indent}等级：', index['member']['level_info']['current_level'])
                    file_handlers['Z'].write(f'{content_indent}等级：{index["member"]["level_info"]["current_level"]}\n')

                if '9' in get_comments_key:
                    print(f'{indent}性别：', index['member']['sex'])
                    file_handlers['Z'].write(f'{content_indent}性别：{index["member"]["sex"]}\n')

                if 'A' in get_comments_key:
                    try:
                        print(f"{indent}" + index['reply_control']['location'])
                        file_handlers['Z'].write(f'{content_indent}{index["reply_control"]["location"]}\n')
                    except:
                        print(f'{indent}IP属地：未知（需cookie）')
                        file_handlers['Z'].write(f'{content_indent}IP属地：未知（需cookie）\n')

                if 'B' in get_comments_key:
                    print(f'{indent}发布时间', datetime.datetime.fromtimestamp(index['ctime']))
                    file_handlers['Z'].write(
                        f'{content_indent}发布时间：{datetime.datetime.fromtimestamp(index["ctime"])}\n')

                print(f'{indent}追评：', index['rcount'], '条')
                file_handlers['Z'].write(f'{content_indent}📝 追评：{index["rcount"]}条\n\n')

            for file in file_handlers.values():
                file.flush()

            root_id = index['rpid']
            reply_number = index['rcount']
            print()
            if index['replies'] is not None:
                try:
                    # 随机暂停一下，礼貌爬取
                    reply_page = 0
                    while reply_page * 10 < reply_number:
                        reply_page += 1
                        await asyncio.sleep(random.uniform(2, 3))
                        recomments_url = f"https://api.bilibili.com/x/v2/reply/reply?oid={video_oid}&type=1&root={root_id}&ps=10&pn={str(reply_page)}&web_location=333.788"
                        reply_comments = requests.get(url=recomments_url, headers=headers).json()

                        await print_comments(reply_comments['data']['replies'], video_oid, credential,
                                             get_comments_key=get_comments_key, key=key + 1)

                except Exception as e:
                    print(f'{indent}获取追评时出错QAQ：{e}')
            if key == 0 and 'Z' in get_comments_key:
                file_handlers['Z'].write('\n\n\n\n')
                for file in file_handlers.values():
                    file.flush()
    finally:
        # 确保所有文件都被关闭（只在最外层关闭）
        if key == 0:
            pass
            for file in file_handlers.values():
                file.close()
                print(f"✅ 数据已追加写入到文件")

'''
获取主评论内容
'''
async def get_all_comments(get_comments_key: str, bvid: str, credential: Credential, delay: int = 5):
    """
    批量获取视频所有评论
    :param get_comments_key:
    :param bvid: 视频BV号
    :param credential: 登录凭证
    :param delay: 每页间隔秒数
    :return: 所有评论的列表
    """
    # 获取视频信息
    if 'X' in get_comments_key:
        # Excel格式 - 使用制表符分隔，方便导入Excel
        open(f"{final_filename}_评论.xlsx", 'w', encoding='utf-8-sig')

    if 'Y' in get_comments_key:
        # 普通文本格式
        open(f"{final_filename}_评论.txt", 'w', encoding='utf-8')

    if 'Z' in get_comments_key:
        # Markdown格式
        open(f"{final_filename}_评论.md", 'w', encoding='utf-8')

    video_comments_response = video.Video(bvid=bvid, credential=credential)
    info = await video_comments_response.get_info()
    video_oid = info['aid']
    print(f"视频标题：{info['title']}")
    print(video_oid)
    all_replies = []
    page = 1
    has_more = True

    while has_more:
        print(f"\n正在爬取第 {page} 页...")

        try:
            # 获取当前页评论
            comments = await comment.get_comments(
                oid=video_oid,
                type_=CommentResourceType.VIDEO,
                page_index=page,
                order=OrderType.LIKE,  # TIME 按时间排序    LIKE 按热度排序
                credential=credential
            )
            # pprint.pprint(comments)
            comments_content = comments['replies']
            await print_comments(comments_content, key=0, video_oid=video_oid, get_comments_key=get_comments_key,
                                 credential=credential)

            time.sleep(random.uniform(5, 8))
            # 检查是否有评论
            if comments and comments.get('replies'):
                replies = comments['replies']
                all_replies.extend(replies)
                print(f"第 {page} 页获取到 {len(replies)} 条评论，累计 {len(all_replies)} 条")

                # 显示当前页的前几条作为预览
                for i, reply in enumerate(replies[:3], 1):
                    print(f"  {i}. {reply['member']['uname']}: {reply['content']['message'][:30]}...")

                # 检查是否还有下一页
                # 如果当前页评论数小于20，说明是最后一页
                if len(replies) < 10:
                    has_more = False
                    print("已到达最后一页")
                else:
                    page += 1
                    print(f"等待 {delay} 秒后继续爬取下一页...")
                    await asyncio.sleep(delay)
            else:
                print("当前页没有评论")
                has_more = False

        except Exception as e:
            print(f"爬取第 {page} 页时出错：{e}")
            has_more = False

    print(f"\n✅ 爬取完成！共获取 {len(all_replies)} 条主评论")
    return all_replies


'''
检验并初始化你的cookie
'''
def parse_bilibili_cookie(cookie_str: str):
    """
    从B站cookie字符串中提取sessdata、bili_jct、buvid3
    :param cookie_str: 完整的cookie字符串
    :return: (sessdata, bili_jct, buvid3) 元组
    """
    # 初始化
    _sessdata = ""
    _bili_jct = ""
    _buvid3 = ""

    # 按分号分割成多个键值对
    try:
        items = cookie_str.split(';')

        for item in items:
            item = item.strip()
            if item.startswith('SESSDATA='):
                _sessdata = item[9:]  # 去掉'SESSDATA='
            elif item.startswith('bili_jct='):
                _bili_jct = item[9:]  # 去掉'bili_jct='
            elif item.startswith('buvid3='):
                _buvid3 = item[7:]  # 去掉'buvid3='
    except:
        print('cookie有问题，爬取的内容将受限')
        time.sleep(2)
    return _sessdata, _bili_jct, _buvid3


if __name__ == "__main__":
    messagebox.showwarning('请注意','仅供学习参考，切勿进行商业用途')
    root = tk.Tk()
    app = BilibiliCrawlerGUI(root)
    root.mainloop()
