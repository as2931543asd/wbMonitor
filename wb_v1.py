import time

import requests
import json
import os
from datetime import datetime

class WBMonitor:
    def __init__(self, uid_list=None, log_file='log/wbIds.txt'):
        self.req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://passport.weibo.cn/signin/login',
            'Connection': 'close',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3'
        }
        self.uid_list = uid_list or ['7875358430']
        self.log_file = log_file
        self.weibo_info_urls = []

        # Ensure log directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def fetch_weibo_info_urls(self):
        """Fetch the URLs for fetching user Weibo posts."""
        self.weibo_info_urls = []
        for uid in self.uid_list:
            user_info_url = f'https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}'
            response = requests.get(user_info_url, headers=self.req_headers)
            if response.status_code != 200:
                self._log('Error', f"Failed to fetch user info for UID {uid}.")
                continue
            try:
                tabs = response.json().get('data', {}).get('tabsInfo', {}).get('tabs', [])
                for tab in tabs:
                    if tab.get('tab_type') == 'weibo':
                        container_id = tab.get('containerid')
                        if container_id:
                            self.weibo_info_urls.append(
                                f'https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}&containerid={container_id}'
                            )
            except (KeyError, ValueError) as e:
                self._log('Error', f"Error processing user info response for UID {uid}: {e}")

    def fetch_existing_weibo_ids(self):
        """Fetch and log existing Weibo IDs."""
        existing_ids = set()
        for url in self.weibo_info_urls:
            response = requests.get(url, headers=self.req_headers)
            if response.status_code != 200:
                self._log('Error', f"Failed to fetch posts for URL {url}.")
                continue
            try:
                with open(self.log_file, 'a') as log_file:
                    cards = response.json().get('data', {}).get('cards', [])
                    for card in cards:
                        if card.get('card_type') == 9:
                            post_id = card.get('mblog', {}).get('id')
                            if post_id and post_id not in existing_ids:
                                log_file.write(post_id + '\n')
                                existing_ids.add(post_id)
            except (KeyError, ValueError) as e:
                self._log('Error', f"Error processing posts for URL {url}: {e}")
        self._log('Info', f"Fetched {len(existing_ids)} existing Weibo IDs.")

    def monitor_new_posts(self):
        """Monitor for new posts and return the latest post details."""
        logged_ids = self._read_logged_ids()
        for url in self.weibo_info_urls:
            response = requests.get(url, headers=self.req_headers)
            if response.status_code != 200:
                self._log('Error', f"Failed to fetch posts for URL {url}.")
                continue
            try:
                cards = response.json().get('data', {}).get('cards', [])
                for card in cards:
                    if card.get('card_type') == 9:
                        post = card.get('mblog', {})
                        post_id = post.get('id')
                        if post_id and post_id in logged_ids:
                            self._log_new_post(post)
                            return_dict={
                                'created_at': post.get('created_at'),
                                'text': post.get('text'),
                                'source': post.get('source'),
                                'nickName': post.get('user', {}).get('screen_name')
                            }
                            if 'pics' in post:
                                return_dict['picUrls'] = [j['large']['url'] for j in post.get('pics')]
                            return return_dict
            except (KeyError, ValueError) as e:
                self._log('Error', f"Error processing new posts for URL {url}: {e}")

    def _log_new_post(self, post):
        """Log a new post ID."""
        post_id = post.get('id')
        if post_id:
            with open(self.log_file, 'a') as log_file:
                log_file.write(post_id + '\n')
            self._log('Info', f"New post detected: {post_id}.")

    def _read_logged_ids(self):
        """Read previously logged post IDs."""
        try:
            with open(self.log_file, 'r') as log_file:
                return set(line.strip() for line in log_file)
        except FileNotFoundError:
            return set()

    def _log(self, level, message):
        """Log a message with a specified level."""
        print(f"[{level}] {message}")

def download_pic(url_list,pic_dir='pic'):
    pic_header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://weibo.com/",
    }
    for url in url_list:
        response = requests.get(url, headers=pic_header)
        if response.status_code == 200:
            # 提取图片名称（从URL中解析）
            image_name = f"{pic_dir}/{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.jpg"
            # 保存图片到当前目录
            with open(image_name, "wb") as file:
                file.write(response.content)
            print(f"图片已成功保存为: {image_name}")
        else:
            print(f"获取图片失败，状态码: {response.status_code}")
if __name__ == '__main__':
    wb_monitor = WBMonitor()
    wb_monitor.fetch_weibo_info_urls()
    wb_monitor.fetch_existing_weibo_ids()
    latest_post = wb_monitor.monitor_new_posts()
    while 1:
        time.sleep(5)
        if latest_post:
            if 'picUrls' in latest_post:
                download_pic(latest_post['picUrls'])
            print("New post details:", latest_post)
