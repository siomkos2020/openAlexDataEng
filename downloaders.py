import json
import os
import requests
import csv
import traceback
from tqdm import tqdm
import pandas as pd

from utils import *
from queue import Empty
import multiprocessing
from multiprocessing import Process, Manager, Queue

class AuthorApiReader(Process):
    r"""OpenAlex作者信息读取进程（生产者）
    Args:
        author_q  (multiprocessing.Queue): 作者机构名称队列，可在进程中共享;
        content_q (multiprocessing.Queue): 下载后作者信息存储队列，用于消费者消费;
        progress  (Manager.Value):         全局整数，用于记录下载进度;
    """
    def __init__(self, author_q: Queue, content_q: Queue, progress: object = None,
                 taskend: object = None) -> None:
        super().__init__()
        self.author_q  = author_q
        self.content_q = content_q
        self.progress = progress
        self.taskend  = taskend

    def run(self) -> None:
        r"""重写的Process的run函数，执行api访问、下载和处理逻辑。

        注意：
        - 函数中不能通过调用Queue().empty()来终止进程，容易发生阻塞;
        - 应该捕捉queue.Empty事件来判断进程是否终止
        """
        while True:
            try:
                # 获取英文形式的作者、机构名
                auth, inst, en_auth, en_inst = self.author_q.get(timeout=1)
                res = self._search_authors_by_name(en_auth)
                if isinstance(res, list):
                    for info in res:
                        aff_names = {x['institution']['display_name']: x['institution']["id"] 
                                     for x in info.get("affiliations", [])}
                        # 判断机构是否匹配
                        if en_inst in aff_names and info.get("id"):
                            # 生产后装载到队列中
                            json_info = json.dumps(info, separators=(',', ':'))
                            self.content_q.put(((
                                auth, inst, 
                                info.get("id"), 
                                info.get("display_name", pd.NA),
                                aff_names.get(inst), 
                                info.get("works_api_url", pd.NA),
                                info.get("display_name_alternatives", pd.NA),
                                info.get("created_date")), 
                                json_info))
                # 更新进度
                self.progress.value += 1
            except Empty:
                self.taskend.value = True
                break
            except Exception as e:
                print(f"Error {e}")
                break

    def _search_authors_by_name(self, author: str) -> any:
        r"""封装的根据作者姓名向openalex查询作者信息
        Args:
            author (str): 作者英文姓名
        """
        base_url = "https://api.openalex.org/authors"
        params = { 'filter': 'display_name.search:%s' % author }
        # 超时(10s)访问的处理
        try:
            response = requests.get(base_url, params=params, timeout=10)
        except requests.exceptions.RequestException:
            print(f"{author} 访问超时")
            return None
        
        if response.status_code == 200:
            authors = response.json()
            return authors['results']
        else:
            print(f"{author} 访问失败，Error: {response.status_code}")
            return None


class DiskWriter(Process):
    r"""作者信息下载进程（消费者）。
    Args:
        content_q (multiprocessing.Queue): 由读取进程生产的数据队列;
        csvfile   (str):                   指定csv格式的数据保存路径;
        jsonfile  (str):                   备份json格式数据保存路径;
    """
    def __init__(self, content_q: Queue, csvfile: str, jsonfile: str,
                task_end: bool = None) -> None:
        super().__init__()
        self.content_q = content_q
        self.csvfile   = csvfile
        self.jsonfile  = jsonfile
        # 判断任务是否结束
        self.task_end = task_end
    
    def run(self) -> None:
        r"""重写Process下的run函数，执行磁盘写入功能。"""
        with open(self.csvfile, 'a', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=',')
            with open(self.jsonfile, 'a', encoding='utf-8') as jsonwriter:
                while True:
                    # 这里注意使用empty时容易阻塞，因empty不是原子操作，改用try...except判断
                    try:
                        item = self.content_q.get(timeout=1)      # 使用timeout避免阻塞
                        self.content_q.task_done()                # 标记任务完成
                        # 写入文件系统
                        csvwriter.writerow(item[0])
                        jsonwriter.write(item[1] + '\n')
                    except Empty:
                        # 这里由于生产者速度慢使得空事件未必任务终止
                        if self.task_end.value:
                            break
                        else:
                            continue
                    except Exception as e:
                        print(f"Error: {e}")
                        traceback.print_exc()
                        break


class OAAuthorDownloader:
    r"""用于检索OpenAlex数据库并批量下载作者数据的下载器。
    Args:
        n_process (int): 指定开启的OpenAlex读取进程数;
    """

    def __init__(self, n_process: int = 2) -> None:
        self.name_mapper = NameMapper()     # 中英文名称转换器
        self.n_process   = n_process        # 进程数

    def download_authors(self, authors: list, target_dir: str) -> any:
        r"""执行下载的主进程，采用“生成-消费者”模式实现。
        Args:
            authors    (list[tuple])：作者及其机构的列表数据。
            target_dir (str):         数据最终保存的目录
        
        Returns: None
        """
        # 创建数据保存的目录
        if not os.path.exists(target_dir): os.mkdir(target_dir)
        # 初始化保存路径
        tb_path = os.path.join(target_dir, 'author_db.csv')
        js_path = os.path.join(target_dir, 'author_info.txt')
        
        # 表数据的断点恢复，提取已访问的作者
        downloaded = set()
        if os.path.exists(tb_path):
            authors_db = pd.read_csv(tb_path)
            auth_list  = authors_db['project_leader'].tolist()
            inst_list  = authors_db['project_unit'].tolist()
            downloaded = set( zip(auth_list, inst_list) )
        else:
            # 表数据初始化
            with open(tb_path, 'w', newline='', encoding='utf-8') as fp:
                writer = csv.writer(fp, delimiter=',')
                writer.writerow(['project_leader', 'project_unit', 'openalex_id',
                                 'display_name', 'institutions_ids', 'works_api_url',
                                 'display_name_alternatives', 'created_date'])
        
        # 利用进程管理器执行主进程
        with Manager() as manager:
            author_q, content_q, total_steps = manager.Queue(), manager.Queue(), 0
            # 装载作者-机构数据
            for auth, inst in authors:
                if (auth, inst) not in downloaded:
                    author_q.put((auth, inst,
                                self.name_mapper.map_ch_name(auth),
                                self.name_mapper.map_ch_inst(inst)))
                    total_steps += 1
                    
            # 初始化监听器进程
            progress = manager.Value('i', 0)
            taskend  = manager.Value('taskend', False)
            listener = Process(target=progress_listener, args=(progress, total_steps, taskend))
            # 初始化OpenAlex读取进程
            reader_ps = [AuthorApiReader(author_q, content_q, progress, taskend=taskend) 
                            for _ in range(self.n_process)]
            # 初始化数据下载进程
            writer_ps = DiskWriter(content_q, tb_path, js_path, task_end=taskend)

            # 开启进程
            for proc in reader_ps + [writer_ps, listener]:
                proc.start()
            # 等待进程结束 
            for proc in reader_ps + [writer_ps, listener]:
                proc.join()


class PaperApiReader(Process):
    def __init__(self, urls_q: Queue, content_q: Queue, lock, progress: object = None, 
                 cachefile: str = None, taskend: bool=None) -> None:
        super().__init__()
        self.urls_q  = urls_q
        self.content_q = content_q
        self.progress = progress
        self.taskend = taskend
        # 设立缓存功能
        self.cachefile = cachefile
        self.lock = lock

    def run(self) -> None:
        with open(self.cachefile, 'a', encoding='utf-8') as fp:
            while True:
                try:
                    # 获取英文形式的作者、机构、待访问url
                    auth, inst, paper_url = self.urls_q.get(timeout=1)
                    res = self._search_papers_by_url(paper_url)
                    if isinstance(res, list):
                        for info in res:
                            # 装载论文基本信息
                            paper_info = (
                                info.get("id", pd.NA),
                                info.get("title", pd.NA),
                                info.get("publication_date", pd.NA),
                                info.get("publication_year", pd.NA),
                                info.get("referenced_works", pd.NA),
                                info.get("cited_by_count",   pd.NA),
                                info.get("cited_by_api_url", pd.NA),
                                [x.get("author", {}).get("id") 
                                    for x in info.get("authorships")],
                                auth,
                                inst
                            )
                            # 装载json数据
                            jsdata = json.dumps(info, separators=(',', ':'))
                            self.content_q.put((paper_info, jsdata, paper_url))
                        # 缓存数据
                        self.lock.acquire()
                        fp.write(paper_url + "\n")
                        self.lock.release()
                    # 更新进度
                    self.progress.value += 1
                except Empty:
                    self.taskend = True
                    break
                except Exception as e:
                    print(f"Error {e}")
                    break

    def _search_papers_by_url(self, url: str) -> list:
        r"""封装的根据url向openalex查询论文数据
        Args:
            url (str): 待发起的api地址
        """
        # 超时(10s)访问的处理
        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.RequestException:
            print(f"{url} 访问超时")
            return None
        
        if response.status_code == 200:
            res = response.json()
            return res['results']
        else:
            print(f"{url} 访问失败，Error: {response.status_code}")
            return None


class OAPaperDownloader:
    def __init__(self, n_process: int = 2) -> None:
        self.n_process   = n_process        # 进程数
        # 创建缓存目录用于保存断点信息
        self.cache_dir = "./cache"
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)

    def download_papers(self, auth_urls: list, target_dir: str) -> any:
        # 创建数据保存的目录
        if not os.path.exists(target_dir): os.mkdir(target_dir)
        # 初始化保存路径
        tb_path = os.path.join(target_dir, 'paper_db.csv')
        js_path = os.path.join(target_dir, 'paper_info.txt')
        
        # 表数据的断点恢复，提取已访问的URL，利用实时缓存机制实现
        downloaded = set()
        cache_path = os.path.join(self.cache_dir, "OAPaperDownCache.txt")
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as fp:
                downloaded = set( x.strip() for x in fp.readlines() )
        # 初始化论文表数据
        if not os.path.exists(tb_path):
            with open(tb_path, 'w', newline='', encoding='utf-8') as fp:
                writer = csv.writer(fp, delimiter=',')
                writer.writerow(['openalex_id', 'title', 'publication_date',
                                'publication_year', 'referenced_works', 'cited_by_count',
                                'cited_by_api_url', 'author_ids', 'project_leader',
                                'project_unit'])
        
        # 利用进程管理器执行主进程
        with Manager() as manager:
            author_q, content_q, total_steps = manager.Queue(), manager.Queue(), 0
            # 装载作者-机构数据
            for auth, inst, url in auth_urls:
                if url not in downloaded:
                    author_q.put((auth, inst, url))
                    total_steps += 1
                    
            # 初始化监听器进程
            progress = manager.Value('i', 0)
            taskend  = manager.Value('task', False)
            listener = Process(target=progress_listener, args=(progress, total_steps, taskend))
            # 初始化OpenAlex读取进程
            lock = multiprocessing.Lock()
            reader_ps = [PaperApiReader(author_q, content_q, lock, progress, 
                                        cachefile=cache_path, taskend=taskend) 
                            for _ in range(self.n_process)]
            # 初始化数据下载进程
            writer_ps = DiskWriter(content_q, tb_path, js_path, task_end=taskend)

            # 开启进程
            for proc in reader_ps + [writer_ps, listener]:
                proc.start()
            # 等待进程结束 
            for proc in reader_ps + [writer_ps, listener]:
                proc.join()






