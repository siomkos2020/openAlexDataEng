
import os
import time
from tqdm import tqdm
from datetime import datetime
from pypinyin import lazy_pinyin

def progress_listener(progress, total_steps):
    """监听全局进度变量，并更新进度条"""
    with tqdm(total=total_steps) as pbar:
        while progress.value < total_steps:
            pbar.n = progress.value                 # 更新进度条当前进度
            pbar.last_print_n = progress.value      # 确保显示更新
            pbar.update(0)                          # 触发进度条刷新
            time.sleep(0.1)                         # 每隔一段时间检查进度


def get_current_date():
    date = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    return date.split(" ")[0]


class NameMapper:
    r"""A string mapper for translating Chinese names to English names.
    """
    def __init__(self) -> None:
        inst_en2ch, inst_ch2en = {}, {}
        with open('./meta_data/机构中英文对照表.txt', 'r', encoding='utf-8') as fr:
            lines = [x.strip().split('\t') for x in fr.readlines()]
            for x, y in lines:
                inst_ch2en[x] = y
                inst_en2ch[y] = x
        self.inst_en2ch = inst_en2ch
        self.inst_ch2en = inst_ch2en
    
    def map_ch_name(self, name: str) -> str:
        def ischinese(x: str) -> bool:
            r"""判断name中的每个字符是否都为中文"""
            for c in x:
                if c < '\u4e00' or c > '\u9fff':
                    return False
            return True
        
        if ischinese(name):
            strs = lazy_pinyin(name)
            return ''.join(strs[1:]) + " " + strs[0]
        return name

    def map_ch_inst(self, name: str) -> any:
        return self.inst_ch2en.get(name, None) 