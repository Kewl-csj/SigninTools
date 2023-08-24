import configparser
import copy
import hashlib
import json
import logging
import random
import time
import requests

import core.common_Util as common_Util
import my_config as cf

# API_URL
TBS_URL = r'http://tieba.baidu.com/dc/common/tbs'
LIKES_URL = r'https://tieba.baidu.com/mo/q/newmoindex'
# LIKES_URL = r'http://c.tieba.baidu.com/c/f/forum/like'
# 客户端签到链接，经验值更高
SIGN_URL = r'http://c.tieba.baidu.com/c/c/forum/sign'

# 用iOS app store 接口获取app最新版本
TIEBA_VERSION = json.loads(requests.get(r'https://itunes.apple.com/lookup?id=477927812').text)['results'][0]['version']

AES_KEY = common_Util.private_crypt.get_aes_key()

HEADERS = {
    'Host': 'tieba.baidu.com',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2012K11AC Build/TKQ1.220829.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/104.0.5112.97 Mobile Safari/537.36 tieba/12.46.1.1',
}

_session = requests.Session()


def encode_data(data):
    """
    https://blog.csdn.net/qq_42339350/article/details/126386358
    这里的sign生成参考上面文档
    :param data:
    :return: md5后的sign
    """
    s = ''
    keys = data.keys()
    # 这里的sort很关键，必须要
    for i in sorted(keys):
        s += i + '=' + str(data[i])
    sign = hashlib.md5((s + 'tiebaclient!!!').encode('utf-8')).hexdigest().upper()
    data.update({'sign': str(sign)})
    return data


def get_tbs(bduss):
    """
    获取 tbs 参数
    :param bduss:
    :return:
    """
    logging.info('Getting tbs')
    headers = copy.copy(HEADERS)
    headers.update({'Cookie': f'BDUSS={bduss}'})
    try:
        tbs = _session.get(url=TBS_URL, headers=headers, timeout=5).json()['tbs']
    except Exception as e:
        logging.error(e)
        logging.info('failed get tbs')
    logging.info('get tbs end')
    return tbs


def get_likes(bduss):
    """
    获取用户关注的贴吧
    :param bduss:
    :return:
    """
    headers = copy.copy(HEADERS)
    headers.update({'cookie': f'BDUSS={bduss}'})
    like_response = _session.get(url=LIKES_URL, headers=headers, timeout=5).json()
    like_list = like_response['data']['like_forum']
    return like_list


def client_sign(bduss, tbs, fid, kw):
    """
    客户端贴吧签到接口
    :param bduss: 百度唯一标识，每次都一样，但是都有效
    :param tbs:
    :param fid: 贴吧唯一id
    :param kw: 贴吧名称
    :return:
    """
    # 这里用的是我自己手机RedmiK40抓的包,理论上都可以，服务端应该没做校验
    sign_data = {
        '_client_id': 'wappc_1692700560616_448',
        '_client_type': '2',
        '_client_version': TIEBA_VERSION,
        '_phone_imei': '000000000000000',
        'model': 'M2012K11AC',
        "net_type": "1",
    }
    sign_data.update({'BDUSS': bduss, 'tbs': tbs, 'fid': fid, 'kw': kw, 'timestamp': str(int(time.time()))})
    _data = encode_data(sign_data)
    _session.post(url=SIGN_URL, data=_data, timeout=5).json()


def user_signin(bduss):
    """
    每个用户签到所有贴吧
    :param bduss:
    :return:
    """
    tbs = get_tbs(bduss)

    # 是否存在还没签到的贴吧，如果本轮循环结束都签到完成，那么就不用再签到了
    need_sign_flag = True
    like_all_num = 0
    had_sign_num = 0

    # 最多循环3轮签到，有些时候贴吧就是无法签到，可能吧已经被封了
    for i in range(1, 4):
        if need_sign_flag:
            had_sign_num = 0
            logging.info(f'第 {i} 轮签到')
            i += 1
            like_list = get_likes(bduss)
            like_all_num = len(like_list)
            logging.info(f'找到 {like_all_num} 个关注的吧，开始签到')
            for x in like_list:
                if x.get('is_sign') == 0:
                    need_sign_flag = True
                    client_sign(bduss, tbs, x.get('forum_id'), x.get('forum_name'))
                    time.sleep(random.uniform(1, 2))
                elif x.get('is_sign') == 1:
                    need_sign_flag = False
                    had_sign_num += 1
        else:
            break

    return like_all_num, had_sign_num


def run():
    tieba_config = configparser.ConfigParser()
    tieba_cf_path = cf.com_config.get_tieba_cf_path()
    tieba_config.read(tieba_cf_path, encoding="utf-8")
    sections = tieba_config.sections()
    send_msg = ''
    for section in sections:
        _bduss = common_Util.private_crypt.decrypt_aes_ebc(tieba_config.get(section, 'encrypt_bduss'), AES_KEY)
        _name = tieba_config.get(section, 'name')
        logging.info(f'开始签到 {_name}')
        like_all_num, had_sign_num = user_signin(_bduss)
        msg = f'{_name}: 贴吧总数量：{like_all_num} 已签：{had_sign_num}，未签: {like_all_num - had_sign_num}' + '\n'
        logging.info(msg)
        send_msg += msg
    logging.info(send_msg)
    common_Util.send_message.send_pushplus(cf.com_config.PUSH_TOKEN, '百度贴吧签到', send_msg)


if __name__ == '__main__':
    run()
