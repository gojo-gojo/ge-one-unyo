from pprint import pprint
import base64
import urllib.request
import re
import os
from bs4 import BeautifulSoup
from dateutil.parser import parse
from datetime import datetime
import requests


"""
⬛使い方
python ./get.py
./save.jsonが生成される。
"""


class Scraping:

    def __init__(self) -> None:
        latest = self.get_current_time()

        time_diffs = []
        for late in latest:
            time_diff = datetime.now() - late
            # print(int(time_diff.seconds))

            # 範囲時間内なら終わる。
            if time_diff.seconds < 3600 * 3:
                print('new-正常時間内'+str(time_diff.seconds))
                exit(0)
            else:
                print('new-異常時間'+str(time_diff.seconds))

        # exitしなかった場合はメール送信
        print('mail sent')
        self.sendmail()

    def get_current_time(self) -> datetime:
        myurl = 'https://gekiyasutokka.com/'
        response = urllib.request.urlopen(myurl)
        # print(str(data))

        # response = requests.get(myurl, verify=False).text
        # print(response)
        soup = BeautifulSoup(response, "html.parser")

        dates = soup.find_all("span", class_="entry-date")
        kaeri = []
        for da in dates:
            ttime = re.sub(r' +（.*', '', da.text)
            ttime = re.sub(r'年|月', '-', ttime)
            ttime = re.sub(r'日 +', 'T', ttime)
            ttime = re.sub(r'時', ':', ttime)
            ttime = re.sub(r'分.*', '', ttime)
            ttime = parse(ttime)
            kaeri.append(ttime)
            if len(kaeri) == 5:
                return kaeri

    def sendmail(self):
        url = 'https://api.brevo.com/v3/smtp/email'
        myobj = {
            "sender": {
                "name": "gojo",
                "email": "gojo@gojo.run"
            },
            "to": [
                {
                    "email": "gojo@gojo.run",
                    "name": "gojo"
                },
                {
                    "email": "websitekanrinin@gmail.com",
                    "name": "websitekanrinin"
                }
            ],
            "subject": "new-記事間隔不良",
            "htmlContent": "new-記事間隔不良"
        }
        api_key = os.environ.get('BREVO_API_KEY')
        if not api_key:
            print('BREVO_API_KEY is not set')
            return

        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }

        x = requests.post(url, json=myobj, headers=headers)

        print(x.text)

        """
curl -s --request POST \
  --url https://api.brevo.com/v3/smtp/email \
  --header 'accept: application/json' \
  --header 'api-key: $BREVO_API_KEY' \
  --header 'content-type: application/json' \
  --data '{ 
   "sender":{ 
      "name":"gojo",
      "email":"gojo@gojo.run"
   },
   "to":[
      {  
         "email":"gojo@gojo.run",
         "name":"gojo"
      }
      ,
      {  
         "email":"websitekanrinin@gmail.com",
         "name":"websitekanrinin"
      }
   ],
   "subject":"'${body}'",
   "htmlContent":"'${body}'"
}'
        """


if __name__ == '__main__':
    # インスタンス生成
    sc = Scraping()

