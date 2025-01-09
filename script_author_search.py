import argparse
from downloaders import *

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str, default='./待检索作者及机构.txt', help="须要检索的作者及机构信息文件")
parser.add_argument("--n_proc", type=int, default=4, help="最大访问进程数")
parser.add_argument("--tgt_dir", type=str, default='./作者数据', help="下载后数据保存的目录")

args = parser.parse_args()


if __name__ == '__main__':
    with open(args.input, 'r', encoding='utf-8') as fp:
        authors = [(x.strip().split('\t')[0], x.strip().split('\t')[1]) for x in fp.readlines()]

    downloader = OAAuthorDownloader(n_process=4)
    downloader.download_authors(authors, target_dir='./作者数据')


