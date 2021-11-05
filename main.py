# -*- coding: utf-8 -*-
import urllib3
import json
import re
import sys
import os
import time
import traceback
import math
from multiprocessing.dummy import Pool as ThreadPool

import requests
from lxml.html import fromstring

from dotenv import load_dotenv
load_dotenv()

urllib3.disable_warnings()

SIZE_GB_TRASHOLD_ERROR = 150

cook = {}

progress = {
    'current': None,
    'old': None,
    'max': None,
}


def url_read(url, decode='utf-8', headers=None):
  global cook

  head = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}
  if headers != None:
    head = headers
  html = ''
  tries = 0
  while tries < 10:
    try:
      html = requests.get(url, headers=head, verify=False, cookies=cook)
      cook = html.cookies
      html.encoding = decode
      html = html.text
    except Exception:
      tries += 1
    else:
      return html
  return 'Ошибка соединения'


def url_read_post(url, data, decode='utf-8', headers=''):
  global cook

  head = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}
  if headers != '':
    head = headers
  html = ''
  tries = 0
  while tries < 10:
    try:
      html = requests.post(
          url, headers=head, verify=False,
          data=data, cookies=cook
      )
      html.encoding = decode
      cook = html.cookies
      html = html.text
    except Exception:
      tries += 1
      time.sleep(1)
    else:
      return html
  return 'Ошибка соединения'


def RemTrash(string):
  string = re.sub("^[  \s]*", "", string)
  string = re.sub("[\s  ]*$", "", string)
  return string


def GetProfileGames(idi):
  result = []

  html = url_read("https://steamcommunity.com/id/" +
                  idi + "/games/?tab=all&sort=name")
  games_obj = re.search("var rgGames\s*\=\s*(\[\{[\s\S]*?\}\]);", html)
  if (games_obj):
    games_obj = json.loads(games_obj.group(1))
  else:
    return 0
  for game in games_obj:
    temp = {}
    temp['appid'] = str(game['appid'])
    temp['name'] = game['name']

    # temp['logo'] = game['logo']
    # temp['hours_forever'] = game['hours_forever']
    # temp['last_played'] = game['last_played']
    result.append(temp)

  return result


def GetGameSpace(appid):
  result = 0
  head = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Accept-Encoding": "gzip, deflate, sdch",
      "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4",
      "Cache-Control": "max-age=0",
      "Upgrade-Insecure-Requests": "1",
      "Cookie": "mature_content=1; birthtime=252442801; lastagecheckage=1-January-1978",
  }

  html = requests.get("https://store.steampowered.com/app/" +
                      appid, headers=head).text.lower()

  page = fromstring(html)
  pattern_arr = [
      "жесткий диск",
      "место на диске",
      "hard drive",
      "hard disk space",
      "место на жестком диске",
      "места на жестком диске"
  ]
  pattern_str = []
  for p in pattern_arr:
    pattern_str.append("contains(text(),'" + p + "')")
  pattern_str = ' or '.join(pattern_str)

  space_obj = page.xpath(".//li/strong[" + pattern_str + "]")
  if space_obj:
    space_obj_n = space_obj[0].getparent()
    space_obj_n = ''.join(space_obj_n.xpath(".//text()"))

    try:
      if(space_obj_n.replace(" ", "")[-2:] == ":\r" or space_obj_n.replace(" ", "")[-1:] == ':'):
        space_obj_n = ''.join(space_obj[1].getparent().xpath(".//text()"))
    except:
      space_obj_n = ''.join(space_obj[0].getparent().xpath(".//text()"))
    space_obj = space_obj_n

  else:
    space_obj = re.search("[\,\;][\s]([^,;]*?на ж[ёе]стком диске)", html)

    if not space_obj:
      space_obj = re.search("[\,\;][\s]([^,;]*?на диске)", html)
    if space_obj:
      space_obj = space_obj.group(1)

  if space_obj:
    try:
      space_obj = RemTrash(space_obj.replace(",", "."))
      # return space_obj
      digits = ''.join(ele for ele in space_obj if ele.isdigit() or ele == '.')
      digits = re.sub("^[\.]*", "", digits)
      digits = re.sub("[\.]*$", "", digits)

      digits = float(digits)

      if ("мб" in space_obj or "mb" in space_obj or "megabytes" in space_obj):
        digits = digits / 1000
      result = digits
    except:
      sys.stderr.write(
          json.dumps(
              {"appid": appid, "traceback": traceback.format_exc()}, ensure_ascii=False
          )
          + "\n"
      )

  global progress
  if progress['current'] is not None:

    progress['old'] = int(float(progress['current'])/progress['max']*100)

    progress['current'] += 1

    new_progress = int(float(progress['current'])/progress['max']*100)
    if new_progress-progress['old'] > 0:
      print('progress:', "{0}%".format(new_progress))

  return {"size": result, "appid": appid}


def GetSumSpace(games_array, thread_num=1, only_gb_digits=False, show_progress=False):
  summary = 0
  pool = ThreadPool(thread_num)
  seed = []
  for i in games_array:
    seed.append(i['appid'])

  if(show_progress):
    global progress

    progress['current'] = 0
    progress['max'] = float(len(seed))

  result = pool.map(GetGameSpace, seed)
  for r in result:
    if(r['size'] > SIZE_GB_TRASHOLD_ERROR):
      sys.stderr.write(json.dumps(
          {"appid": r['appid'], "size error": r['size']}, ensure_ascii=False) + "\n")
    else:
      summary += r['size']

  if(only_gb_digits):
    summary = math.ceil(summary)
    return summary
  if(summary > 1000):
    summary = summary/1000
    summary = round(summary, 2)
    return str(summary)+" ТБ"

  summary = round(summary, 2)
  return str(summary)+" ГБ"


def main():
  user_id = os.getenv('USER_ID')
  print('user:', user_id)

  games = GetProfileGames(user_id)

  space = GetSumSpace(games, 16, show_progress=True)

  print('space:', space)


main()
