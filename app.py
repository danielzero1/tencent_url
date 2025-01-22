import logging
import sys
import threading
import webbrowser

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import requests
import json
import base64
import time
import os
import zipfile
from urllib.parse import quote

# 设置日志记录
logging.basicConfig(level=logging.INFO, filename='app.log', filemode='w',
                    format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# 判断是否处于 PyInstaller 打包后的环境
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的临时解压目录在 sys._MEIPASS
    base_path = sys._MEIPASS
else:
    # 否则就使用脚本文件所在目录
    base_path = os.path.dirname(os.path.abspath(__file__))

# 拼接出 static 文件夹所在的真实路径
static_dir = os.path.join(base_path, "static")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 访问 / 时，返回 static/index.html
@app.get("/", response_class=HTMLResponse)
async def read_index():
    # 初始化cookie
    get_cookie_str()

    index_file = os.path.join(static_dir, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


def get_cookie_str():
    cookie_file = 'cookie.txt'
    if not os.path.exists(cookie_file):
        with open(cookie_file, 'w') as file:
            file.write('your_cookie_string_here')  # 默认的 cookie_str
        cookie_str = 'your_cookie_string_here'
    else:
        with open(cookie_file, 'r') as file:
            cookie_str = file.read().strip()

    # **新增：打印或日志记录一下 cookie_str，方便查看是否真的读取到**
    print(f"Debug: current cookie = {cookie_str}")
    logger.info(f"Debug: current cookie = {cookie_str}")

    return cookie_str


class QQMusic:
    def __init__(self):
        self.base_url = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
        self.guid = '10000'
        self.uin = '0'
        self.cookies = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        self._headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://y.qq.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        }
        self.mac_headers = {
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": "https://i.y.qq.com",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
            "content-type": "application/json",
            "accept": "application/json",
            "Host": "u.y.qq.com",
            "Connection": "Keep-Alive"
        }
        self.file_config = {
            '128': {'s': 'M500', 'e': '.mp3', 'bitrate': '128kbps'},
            '320': {'s': 'M800', 'e': '.mp3', 'bitrate': '320kbps'},
            'flac': {'s': 'F000', 'e': '.flac', 'bitrate': 'FLAC'},
            'master': {'s': 'AI00', 'e': '.flac', 'bitrate': 'Master'},
            'atmos_2': {'s': 'Q000', 'e': '.flac', 'bitrate': 'Atmos 2'},
            'atmos_51': {'s': 'Q001', 'e': '.flac', 'bitrate': 'Atmos 5.1'},
            'ogg_640': {'s': 'O801', 'e': '.ogg', 'bitrate': '640kbps'},
            'ogg_320': {'s': 'O800', 'e': '.ogg', 'bitrate': '320kbps'},
            'ogg_192': {'s': 'O600', 'e': '.ogg', 'bitrate': '192kbps'},
            'ogg_96': {'s': 'O400', 'e': '.ogg', 'bitrate': '96kbps'},
            'aac_192': {'s': 'C600', 'e': '.m4a', 'bitrate': '192kbps'},
            'aac_96': {'s': 'C400', 'e': '.m4a', 'bitrate': '96kbps'},
            'aac_48': {'s': 'C200', 'e': '.m4a', 'bitrate': '48kbps'}
        }
        self.song_url = 'https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg'
        self.lyric_url = 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg'

    def set_cookies(self, cookie_str):
        cookies = {}
        for cookie in cookie_str.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies[key] = value
        self.cookies = cookies

    def ids(self, url):
        """
        从不同类型的 URL 中提取歌曲 ID，支持重定向和 /songDetail/ URL 形式
        """
        
        # 移除片段标识符（#后面的部分）
        url = url.split('#')[0]
        
        # 如果URL中包含 'c6.y.qq.com'，则发送请求获取重定向后的URL
        if 'c6.y.qq.com' in url:
            response = requests.get(url, allow_redirects=False)
            url = response.headers.get('Location')  # 获取重定向的URL

        # 检查重定向后的URL中是否包含 'y.qq.com'，并根据情况提取 id
        if 'y.qq.com' in url:
            # 处理 /songDetail/ 形式的 URL
            if '/songDetail/' in url:
                index = url.find('/songDetail/') + len('/songDetail/')
                song_id = url[index:].split('/')[0]  # 提取 '/songDetail/' 后面的部分
                return song_id
            
            # 如果是带 id= 参数的 URL，提取 id 参数
            if 'id=' in url:
                index = url.find('id=') + 3
                song_id = url[index:].split('&')[0]  # 提取 'id' 的值
                return song_id

        # 如果都不匹配，返回 None
        return None

    def get_music_url(self, songmid, file_type='flac'):
        """
        获取音乐播放URL
        """
        if file_type not in self.file_config:
            raise ValueError("Invalid file_type. Choose from 'm4a', '128', '320', 'flac', 'ape', 'dts")

        file_info = self.file_config[file_type]
        file = f"{file_info['s']}{songmid}{songmid}{file_info['e']}"

        req_data = {
            'req_1': {
                'module': 'vkey.GetVkeyServer',
                'method': 'CgiGetVkey',
                'param': {
                    'filename': [file],
                    'guid': self.guid,
                    'songmid': [songmid],
                    'songtype': [0],
                    'uin': self.uin,
                    'loginflag': 1,
                    'platform': '20',
                },
            },
            'loginUin': self.uin,
            'comm': {
                'uin': self.uin,
                'format': 'json',
                'ct': 24,
                'cv': 0,
            },
        }

        response = requests.post(self.base_url, json=req_data, cookies=self.cookies, headers=self.headers)
        data = response.json()
        purl = data['req_1']['data']['midurlinfo'][0]['purl']
        if purl == '':
            # VIP
            return None

        url = data['req_1']['data']['sip'][1] + purl
        prefix = purl[:4]
        bitrate = next((info['bitrate'] for key, info in self.file_config.items() if info['s'] == prefix), '')

        return {'url': url.replace("http://", "https://"), 'bitrate': bitrate}

    def get_music_song(self, mid, sid):
        """
        获取歌曲信息
        """
        if sid != 0:
            # 如果有 songid（sid），使用 songid 进行请求
            req_data = {
                'songid': sid,
                'platform': 'yqq',
                'format': 'json',
            }
        else:
            # 如果没有 songid，使用 songmid 进行请求
            req_data = {
                'songmid': mid,
                'platform': 'yqq',
                'format': 'json',
            }

        # 发送请求并解析返回的 JSON 数据
        response = requests.post(self.song_url, data=req_data, cookies=self.cookies, headers=self.headers)
        data = response.json()
        #return data
        # 确保数据结构存在，避免索引错误
        if 'data' in data and len(data['data']) > 0:
            song_info = data['data'][0]
            album_info = song_info.get('album', {})
            singers = song_info.get('singer', [])
            singer_names = ', '.join([singer.get('name', 'Unknown') for singer in singers])

            # 获取专辑封面图片 URL
            album_mid = album_info.get('mid')
            img_url = f'https://y.qq.com/music/photo_new/T002R800x800M000{album_mid}.jpg?max_age=2592000' if album_mid else 'https://axidiqolol53.objectstorage.ap-seoul-1.oci.customer-oci.com/n/axidiqolol53/b/lusic/o/resources/cover.jpg'

            # 返回处理后的歌曲信息
            return {
                'name': song_info.get('name', 'Unknown'),
                'album': album_info.get('name', 'Unknown'),
                'singer': singer_names,
                'pic': img_url,
                'mid': song_info.get('mid', mid),
                'id': song_info.get('id', sid)
            }
        else:
            return {'msg': '信息获取错误/歌曲不存在'}

    def get_music_lyric_new(self, songid):
        """从QQ音乐电脑客户端接口获取歌词

        参数:
            songID (str): 音乐id

        返回值:
            dict: 通过['lyric']和['trans']来获取base64后的歌词内容

            其中 lyric为原文歌词 trans为翻译歌词
        """
        #url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
        payload = {
            "music.musichallSong.PlayLyricInfo.GetPlayLyricInfo": {
                "module": "music.musichallSong.PlayLyricInfo",
                "method": "GetPlayLyricInfo",
                "param": {
                    "trans_t": 0,
                    "roma_t": 0,
                    "crypt": 0,  # 1 define to encrypt
                    "lrc_t": 0,
                    "interval": 208,
                    "trans": 1,
                    "ct": 6,
                    "singerName": "",
                    "type": 0,
                    "qrc_t": 0,
                    "cv": 80600,
                    "roma": 1,
                    "songID": songid,
                    "qrc": 0,  # 1 define base64 or compress Hex
                    "albumName": "",
                    "songName": "",
                },
            },
            "comm": {
                "wid": "",
                "tmeAppID": "qqmusic",
                "authst": "",
                "uid": "",
                "gray": "0",
                "OpenUDID": "",
                "ct": "6",
                "patch": "2",
                "psrf_qqopenid": "",
                "sid": "",
                "psrf_access_token_expiresAt": "",
                "cv": "80600",
                "gzip": "0",
                "qq": "",
                "nettype": "2",
                "psrf_qqunionid": "",
                "psrf_qqaccess_token": "",
                "tmeLoginType": "2",
            },
        }

        # 发送请求获取歌词
        try:
            res = requests.post(self.base_url, json=payload, cookies=self.cookies, headers=self.headers)  # 确保使用 POST 请求
            res.raise_for_status()  # 检查请求是否成功
            d = res.json()  # 解析返回的 JSON 数据
            
            # 提取歌词数据
            lyric_data = d["music.musichallSong.PlayLyricInfo.GetPlayLyricInfo"]["data"]
            # 处理歌词内容
            if 'lyric' in lyric_data and lyric_data['lyric']:
                # 解码歌词
                lyric = base64.b64decode(lyric_data['lyric']).decode('utf-8')
                tylyric = base64.b64decode(lyric_data['trans']).decode('utf-8')
            else:
                lyric = ''  # 没有歌词的情况下返回空字符串
                tylyric = ''  # 没有歌词的情况下返回空字符串
            return {'lyric': lyric,'tylyric': tylyric}  # 返回包含歌词的字典

        except Exception as e:
            print(f"Error fetching lyrics: {e}")
            return {'error': '无法获取歌词'}


@app.get('/song')
async def get_song(request: Request):
    song_url = request.query_params.get('url')
    if not song_url:
        raise HTTPException(status_code=400, detail="url parameter is required")

    qqmusic = QQMusic()
    qqmusic.set_cookies(get_cookie_str())

    # 从传入的 URL 中提取 songmid 或 songid
    songmid = qqmusic.ids(song_url)
    if not songmid:
        raise HTTPException(status_code=400, detail="Invalid song URL")

    # 文件类型处理
    file_types = ['aac_48','aac_96','aac_192','ogg_96','ogg_192','ogg_320','ogg_640','atmos_51','atmos_2','master','flac','320','128']
    results = {}

    try:
        # 如果 songmid 是数字，视为 songid (sid)
        sid = int(songmid)
        mid = 0
    except ValueError:
        # 否则视为 songmid (mid)
        sid = 0
        mid = songmid
    # 获取歌曲信息
    info = qqmusic.get_music_song(mid, sid)
    # 对于每种文件类型，获取对应的音乐 URL
    for file_type in file_types:
        result = qqmusic.get_music_url(info['mid'], file_type)
        if result:
            results[file_type] = result
        time.sleep(0.1)
    lyric =  qqmusic.get_music_lyric_new(info['id'])

    # 构造 JSON 输出
    output = {
        'song': info,
        'lyric': lyric,
        'music_urls': results,
    }
    return JSONResponse(output)


@app.get('/download')
async def download_resources(song_url: str, cover: bool = Query(True), lyric: bool = Query(True)):
    qqmusic = QQMusic()
    qqmusic.set_cookies(get_cookie_str())

    songmid = qqmusic.ids(song_url)
    if not songmid:
        raise HTTPException(status_code=400, detail="Invalid song URL")

    file_types = ['master', 'atmos_51', 'atmos_2', 'flac', '320','128','ogg_640','ogg_320','ogg_192','ogg_96','aac_192', 'aac_96','aac_48']
    chosen_type = None  # 用于记录最终选到的音质类型

    try:
        sid = int(songmid)
        mid = 0
    except ValueError:
        sid = 0
        mid = songmid

    info = qqmusic.get_music_song(mid, sid)
    # 1) 找到可用的音质并记录 chosen_type
    for file_type in file_types:
        result = qqmusic.get_music_url(info['mid'], file_type)
        if result:
            music_url = result['url']
            chosen_type = file_type
            break

    if not music_url or not chosen_type:
        raise HTTPException(status_code=404, detail="High quality music file not found")

    # 2) 从 QQMusic 类里的 file_config 获取对应的文件后缀
    file_extension = qqmusic.file_config[chosen_type]['e']

    # 创建临时目录
    tmpdir = "temp_files"
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)

    zip_filename = os.path.join(tmpdir, f"{info['name']}.zip")
    with zipfile.ZipFile(zip_filename, 'w') as zip_file:
        # 下载并写入歌曲
        song_response = requests.get(music_url)
        song_filename = f"{info['name']}-{info['singer']}{file_extension}"
        song_filepath = os.path.join(tmpdir, song_filename)
        with open(song_filepath, 'wb') as song_file:
            song_file.write(song_response.content)
        zip_file.write(song_filepath, song_filename)

        # 下载并添加封面文件（如果选择了封面）
        if cover:
            cover_response = requests.get(info['pic'])
            cover_filename = f"{info['name']}-{info['singer']}.jpg"
            cover_filepath = os.path.join(tmpdir, cover_filename)
            with open(cover_filepath, 'wb') as cover_file:
                cover_file.write(cover_response.content)
            zip_file.write(cover_filepath, cover_filename)

        # 添加歌词文件（如果选择了歌词）
        if lyric:
            lyric_filename = f"{info['name']}-{info['singer']}.lrc"
            lyric_filepath = os.path.join(tmpdir, lyric_filename)
            with open(lyric_filepath, 'w', encoding='utf-8') as lyric_file:
                lyric_file.write(qqmusic.get_music_lyric_new(info['id'])['lyric'])
            zip_file.write(lyric_filepath, lyric_filename)

    # 使用 RFC 8187 规范设置 Content-Disposition 头
    quoted_filename = quote(f"{info['name']}.zip")
    content_disposition = f"attachment; filename*=utf-8''{quoted_filename}"

    return FileResponse(path=zip_filename, media_type='application/zip',
                        headers={"Content-Disposition": content_disposition})


if __name__ == "__main__":
    import uvicorn


    def open_browser():
        # 等待1秒，避免浏览器在服务尚未完全启动前发起请求
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:5122")


    # 启动浏览器的线程
    threading.Thread(target=open_browser).start()

    # 启动 FastAPI
    uvicorn.run(app, host="127.0.0.1", port=5122)
