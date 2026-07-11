import re
from collections import Counter
import json
import random
from jinja2 import Template
import datetime


class CreateRank:
    nginx_logs = [
        '/var/log/nginx/gekiyasutokka.com-access.log',
        '/var/log/nginx/gekiyasutokka.com-access.log.1'
    ]

    def __init__(self) -> None:

        self.rank = []
        """result"""

        # create master data from json
        self.read_def_json()

        # create sum result
        self.read_log()

        # sort rank. rank
        self.sort_rank()

        # insert dummy if not filled
        if len(self.rank) < 5:
            self.insert_dummy()

        # output to html
        self.output_jinja2()
        print('end')

    @staticmethod
    def crop_domain(url: str) -> tuple[bool, str | None]:
        if url == '-':
            return False, None
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = re.sub(r'\?.*', '', url)
        if url.startswith('fanblogs.jp/nightfly'):
            url = 'fanblogs.jp'
        elif url.startswith('blog.livedoor.jp/koredayo'):
            url = 'blog.livedoor.jp'
        else:
            url = re.sub(r'/.*', '', url)
            url = re.sub(r':\d+$', '', url)
        return True, url

    def read_log(self):
        """
        read files from nginx.
        aggrigate them
        """
        lines = []
        """line from nginx log file"""

        # read files to array
        for file_path in CreateRank.nginx_logs:
            with open(file_path, 'r') as file:
                lines += file.readlines()

        # parse
        lineformat = re.compile(
            r"""(?P<ipaddress>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[(?P<dateandtime>\d{2}\/[a-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} (\+|\-)\d{4})\] ((\"(GET|POST) )(?P<url>.+)(http\/1\.1")) (?P<statuscode>\d{3}) (?P<bytessent>\d+) (["](?P<refferer>(\-)|(.+))["]) (["](?P<useragent>.+)["])""", re.IGNORECASE)

        seen = set()
        total = []
        for line in lines:
            data = re.search(lineformat, line)
            if data:
                datadict = data.groupdict()
                referrer = datadict["refferer"]
                f, referrer = self.crop_domain(referrer)
                if f:
                    date_only = datadict["dateandtime"].split(':')[0]
                    key = (datadict["ipaddress"], date_only, referrer)
                    if key in seen:
                        continue
                    seen.add(key)
                    total.append(referrer)

        element_counts = Counter(total)
        out = ''
        results = {}
        for element, count in element_counts.items():
            out += f"{count} {element}\n"
            results[element] = count

        # output natural rank
        file_path = '/opt/nginx-access/natural.log'
        with open(file_path, 'w') as file:
            file.write(out+'\n')

        # return results
        self.logfile_result = results

    def read_def_json(self) -> dict:
        with open('/opt/nginx-access/rank.json', 'r') as file:
            site_master = json.load(file)

        site_trans = {}
        for match, li in site_master.items():
            site_trans[match] = {
                'name': li['name'],
                'url': li['link'],
            }
        self.file_from_json = site_trans

    def sort_rank(self):
        list_from_json = self.file_from_json
        results = self.logfile_result
        rank = []
        by_count = {}
        for domain, count in results.items():
            if domain in list_from_json:
                by_count.setdefault(count, []).append(domain)

        for count in sorted(by_count.keys(), reverse=True):
            domains = by_count[count]
            random.shuffle(domains)
            for domain in domains:
                rank.append(
                    {
                        'name': list_from_json[domain]['name'],
                        'url': list_from_json[domain]['url'],
                        'count': count,
                    }
                )
                if len(rank) >= 5:
                    break
            if len(rank) >= 5:
                break
        self.rank = rank
        self.lists = list_from_json
        return rank, list_from_json

    @staticmethod
    def daburi(s_name, s_dict) -> bool:
        for s_d in s_dict:
            if s_d['url'] == s_name:
                return True
        return False

    def insert_dummy(self) -> list:
        rank = self.rank
        lists = self.lists
        lists = list(lists.items())
        random.shuffle(lists)
        lists = dict(lists)
        while True:
            if len(rank) < 5:
                def insert_dummy():
                    for lis in lists:
                        if not self.daburi(lists[lis]['url'], rank):
                            rank.append(
                                {
                                    'name': lists[lis]['name'],
                                    'url': lists[lis]['url'],
                                    'count': 0,
                                }
                            )
                            return
                insert_dummy()
            else:
                break

        self.rank = rank
        return rank

    def output_jinja2(self):
        rank = self.rank
        with open('/opt/nginx-access/rank.html.j2', 'r') as file:
            template_string = file.read()
        template = Template(template_string)
        output = template.render(rank=rank)

        now = datetime.datetime.now()
        now_date = now.strftime("%Y-%m-%d %H:%M:%S")
        now_date = '<!--'+now_date+'-->'

        file_path = '/var/www/nginx/gekiyasutokka.com/simaccess'+'/rank.html'
        print(file_path)
        with open(file_path, 'w') as file:
            file.write(output+now_date)


cr = CreateRank()
