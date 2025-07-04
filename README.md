## 1 功能使用

### 1.1 根据作者姓名及机构名批量下载作者基本数据

```Shell
python script_author_search.py --input [输入txt文件] --n_proc [执行的进程数] --tgt_dir [数据保存的目标目录]
```


- 参数解释：

  - input: 不可为空，须要下载的作者及机构信息，txt文件，作者、机构由\t隔开，文件示例如下：

  ```Shell
韩文报	中国人民解放军战略支援部队信息工程大学
胡磊	广州大学
吴世忠	中国信息安全产品测评认证中心
李子臣	清华大学
陈克非	上海交通大学
```


  - n_proc: 默认为1，运行的进程数，进程数越多执行速度越快，但有可能出错或负载过高；

  - tgt_dir: 文件保存的目标目录

- 返回：无返回值，程序将在tgt_dir地址下生成名为author_db.csv文件和author_info.txt文件；



### 1.2 根据作者表格数据下载作者发表的论文数据

```Shell
python script_paper_search.py --auth_tb_path [作者表格csv文件地址] --tgt_dir [文件下载的目标地址] --n_proc [执行的进程数]
```


- 参数解释：

  - auth_tb_path：作者相关的表格数据地址，csv格式，必须包含works_api_url字段；

  - tgt_dir：下载后论文数据的保存目录；

  - n_proc：运行的进程数；

- 返回：无返回值，程序将在tgt_dir地址下生成名为paper_db.csv文件和paper_info.txt文件；

