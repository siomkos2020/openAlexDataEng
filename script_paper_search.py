import argparse
import pandas as pd
from downloaders import *

parser = argparse.ArgumentParser()
parser.add_argument("--auth_tb_path", type=str, default="", 
                    help="包含openalex信息的作者表")
parser.add_argument("--input", type=str, default='', 
                    help="须要检索的作者、机构及其论文url，不提供时则检索auth_tb_path中全部的作者信息")
parser.add_argument("--n_proc", type=int, default=1, help="最大访问进程数")
parser.add_argument("--tgt_dir", type=str, default='./论文数据', help="下载后数据保存的目录")

args = parser.parse_args()


if __name__ == '__main__':
    try:
        auth_tb = pd.read_csv(args.auth_tb_path, 
                            usecols=['project_leader',
                                     'project_unit',
                                     'works_api_url'])
        auth_urls = zip(
                auth_tb['project_leader'].tolist(),
                auth_tb['project_unit'].tolist(),
                auth_tb['works_api_url'].tolist()
            )
        if args.input != '':
            auth2info = {(auth, inst): url for auth, inst, url in auth_urls}
            new_urls  = []
            with open(args.input, 'r', encoding='utf-8') as fp:
                line = fp.readline().strip()
                while line:
                    auth, inst = line.split('\t')
                    if (auth, inst) in auth2info:
                        new_urls.append((auth, inst, auth2info[(auth, inst)])) 
            auth_urls = new_urls 
    except ValueError:
        exit("列名存在问题，请检查")
    except Exception as e:
        exit(f"Error {e}")

    paperdownloader = OAPaperDownloader(n_process=args.n_proc)
    paperdownloader.download_papers(auth_urls, target_dir=args.tgt_dir)
    

    


