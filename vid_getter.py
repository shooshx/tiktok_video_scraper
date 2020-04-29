import os, sys, subprocess, time, datetime
import json
import urllib.request

from base_url import BASE_INFS  # map username to list URL

# better signature getting?
#  https://github.com/drawrowfly/tiktok-scraper/blob/e566b84795722dc9a32a3850da4718c88359e448/README.md

this_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = this_dir + "/data"


HEADERS = {
    "user-agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
    "referer" : 'https://www.tiktok.com/',
}

LAST_SIG_PATH = data_dir + "/last_sig_"

serverProc = [None]
def kill_server():
    if serverProc[0] is None:
        return
    print("Killing server")
    serverProc[0].terminate()

def get_sig(revoke_cache, base_url, base_inf, url_type):
    print("GET-SIG", base_inf.base_url)
    last_sig_path = LAST_SIG_PATH + base_inf.user + "_" + url_type
    if not revoke_cache and base_url == base_inf.base_url: # is it the first (not continuing url)
        if os.path.exists(last_sig_path):
            sig = open(last_sig_path, "rb").read().decode('latin1').strip()
            if len(sig) > 0:
                return sig

    print("Starting server")
    os.chdir(this_dir + '/tiktok-signature')
    if serverProc[0] is None:
        serverProc[0] = subprocess.Popen(['node', 'server.js'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        line1 = serverProc[0].stdout.readline().strip()
        line2 = serverProc[0].stdout.readline().strip()
        if line2 != b"TikTok Signature server started":
            raise Exception("failed start server `%s`, `%s`" % (line1, line2))

    print("Starting browser")
    cmd = ['node', 'browser.js', base_url]
    print(' '.join(cmd))
    sig = subprocess.check_output(cmd)

    assert len(sig) > 0, "got empty sig"
    open(last_sig_path, "wb").write(sig)

    return sig.decode('latin1').strip()



class DictObj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def update(self, d):
        self.__dict__.update(d.__dict__)

def json_dumper(obj):
    return obj.__dict__

def parse_inf_v1(info_json):
    if 'body' not in info_json:
        print("NO body:", info_json)
        return None
    body = info_json['body']

    data = DictObj()
    data.items = []
    data.hasMore = body['hasMore']
    data.maxCursor = body['maxCursor']
    data.minCursor = body['minCursor']

    vid_lst = info_json['body']['itemListData']
    for dt in vid_lst:
        iteminf = dt['itemInfos']
        d = DictObj()
        data.items.append(d)
        d.item_id = iteminf['id']   # add this to https://www.tiktok.com/@<username>/video/
        d.text = iteminf['text']
        d.create_time = iteminf['createTime']
        d.create_time_str = datetime.datetime.fromtimestamp(int(d.create_time)).strftime("%Y_%m_%d__%H_%M_%S")
        d.vid_url = iteminf['video']['urls'][0]

        d.play_count = iteminf['playCount']
        d.comment_count = iteminf['commentCount']
        d.heart_count = iteminf['diggCount']
        d.share_count = iteminf['shareCount']

        auth_stat = dt["authorStats"]
        d.author_followers = auth_stat['followerCount']
        d.author_hearts = auth_stat['heartCount']
        d.author_vid_count = auth_stat['videoCount']

        auth_inf = dt['authorInfos']
        d.author_user = auth_inf['uniqueId']
        d.author_sig = auth_inf['signature']
        d.author_nick = auth_inf['nickName']

        minf = dt['musicInfos']
        d.music_name = minf['musicName']
        d.music_author = minf['authorName']
        d.music_url = minf['playUrl'][0] if len(minf['playUrl']) > 0 else "None"

        text_extra = dt['textExtra']
        d.hash_tags = []
        for te in text_extra:
            name = te['HashtagName']
            if name is not None and len(name) > 0:
                d.hash_tags.append(name)
            tag_user = te['UserId']   # append this to https://www.tiktok.com/share/user/  to get redirected to the user
            if tag_user is not None and len(tag_user) > 0:
                d.hash_tags.append(tag_user)

        print(len(data.items), iteminf['text'])
        #print(iteminf['createTime'])
        #print(iteminf['video']['urls'][0])
    return data


def parse_inf_v2(info_json):
    body = info_json

    data = DictObj()
    data.items = []
    data.hasMore = body['hasMore']
    data.maxCursor = body['maxCursor']
    data.minCursor = body['minCursor']

    vid_lst = info_json['items']
    for dt in vid_lst:
        iteminf = dt
        d = DictObj()
        data.items.append(d)
        d.item_id = dt['id']   # add this to https://www.tiktok.com/@<username>/video/<id>
        d.text = dt['desc']
        d.create_time = dt['createTime']
        d.create_time_str = datetime.datetime.fromtimestamp(int(d.create_time)).strftime("%Y_%m_%d__%H_%M_%S")
        d.vid_url = dt['video']['playAddr']
        d.vid_dl_url = dt['video']['downloadAddr']  # same as above right now

        vid_stat = dt['stats']
        d.play_count = vid_stat['playCount']
        d.comment_count = vid_stat['commentCount']
        d.heart_count = vid_stat['diggCount']
        d.share_count = vid_stat['shareCount']

        auth_inf = dt['author']
        d.author_user = auth_inf['uniqueId']
        d.author_sig = auth_inf['signature']
        d.author_nick = auth_inf['nickname']

        minf = dt['music']
        d.music_name = minf['title']
        d.music_author = minf['authorName']
        d.music_url = minf['playUrl']

        if 'textExtra' in dt:
            text_extra = dt['textExtra']
            d.hash_tags = []
            for te in text_extra:
                name = te['hashtagName']
                if name is not None and len(name) > 0:
                    d.hash_tags.append(name)
                tag_user = te['userId']   # append this to https://www.tiktok.com/share/user/  to get redirected to the user
                if tag_user is not None and len(tag_user) > 0:
                    d.hash_tags.append(tag_user)

        print(len(data.items), d.text)
        #print(iteminf['createTime'])
        #print(iteminf['video']['urls'][0])
    return data

def parse_user_v2(dt):
    d = DictObj()

    auth_stat = dt["userInfo"]["stats"]
    d.author_followers = auth_stat['followerCount']
    d.author_following = auth_stat['followingCount']
    d.author_hearts = auth_stat['heartCount']
    d.author_vid_count = auth_stat['videoCount']
    d.author_digg_count = auth_stat['diggCount']
    return d


def get_info(url, url_type):
    info_text = download(url)
    if len(info_text) == 0:
        print("Empty reply")
        return None
    info_json = json.loads(info_text)
    open(data_dir + "/last_data_" + url_type + ".json", "w").write(json.dumps(info_json, indent=4))
    return info_json

def get_url_json(base_inf, base_url, url_type):
    sig = get_sig(False, base_url, base_inf, url_type)
    print("got sig `%s`" % sig)

    url = base_url + "&_signature=" + sig
    json_d = get_info(url, url_type)
    if json_d is None:
        print("Failed to get vids, refreshing signature")
        sig = get_sig(True, base_url, base_inf, url_type)
        print("got sig2 `%s`" % sig)
        url = base_url + "&_signature=" + sig
        json_d = get_info(url, url_type)
        if json_d is None:
            print("Failed to get vids with new signature")
            raise Exception("failed get_info twice")
    return json_d

def get_sig_info(base_inf, base_url, user_url):
    json_d = get_url_json(base_inf, base_url, "items")
    data = parse_inf_v2(json_d)

    if user_url is not None:
        json_d = get_url_json(base_inf, user_url, "user")
        user_data = parse_user_v2(json_d)
        return data, user_data

    return data

def download(url):
    print("  downloading", url)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        res = urllib.request.urlopen(req)
        data = res.read()
        return data
    except Exception as e:
        print("    error:", e, "retry")

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        res = urllib.request.urlopen(req)
        data = res.read();
        return data
    except Exception as e:
        print("    error2:", e)
        
    return b""


def get_vid_file(url, dir, item):
    basename = item.create_time_str + "__" + item.item_id
    filepath = dir + "/" + basename + ".mp4"
    nwm_filepath = dir + "/" + basename + "_nwm.mp4"
    if os.path.exists(filepath) and os.path.exists(nwm_filepath):
        print("  vids exists")
        return

    data = None
    if not os.path.exists(filepath):
        data = download(url)
        if data is not None and len(data) > 0:
            open(filepath, "wb").write(data)
            print("  saved", filepath)
        else:
            return # nothing to do at this point

    if os.path.exists(nwm_filepath):
        return
    if data is None: # did not download it
        data = open(filepath, "rb").read()
    start = data.find(b'vid:')
    if start == -1:
        print("  did not find vid_id")
        return
    vid_id = data[start+4:start+36].decode('latin1')
    item.vid_id = vid_id

    no_watermark_url = "https://api2.musical.ly/aweme/v1/playwm/?video_id=" + vid_id
    data = download(no_watermark_url)
    if data is not None and len(data) > 0:
        open(nwm_filepath, "wb").write(data)
        print("  saved", filepath)


def save_metadata(dir, item, user_data):
    item.update(user_data)
    basename = item.create_time_str + "__" + item.item_id
    filepath = dir + "/" + basename + ".json"
    if os.path.exists(filepath):
        print("  json exists")
        return
    open(filepath, "w").write(json.dumps(item, indent=4, default=json_dumper))
    print("  saved", filepath)


def get_all_vids(items_lst, to_dir, user_data):
    for idx, item in enumerate(items_lst):
        print(idx, "Getting vid for", item.item_id)
        get_vid_file(item.vid_url, to_dir, item)
        save_metadata(to_dir, item, user_data)


def get_latest(base_inf):
    data, user_data = get_sig_info(base_inf, base_inf.base_url, base_inf.user_url)

    os.makedirs(data_dir, exist_ok=True)
    vid_dir = data_dir + "/vid_" + base_inf.user
    os.makedirs(vid_dir, exist_ok=True)

    get_all_vids(data.items, vid_dir, user_data)


def get_all(base_inf):
    data = get_sig_info(base_inf, base_inf.base_url)
    all_items = data.items
    while data.hasMore:
        next_url = BASE_URL.replace("maxCursor=0", "maxCursor=" + str(data.maxCursor))
        data = get_sig_info(base_inf, next_url)
        all_items.extend(data.items)

        filepath = data_dir + "/all_items_" + base_inf.user + ".json"
        json.dump(all_items, open(filepath, "w"), default=json_dumper, indent=4)
        print("Saved", filepath, "items=", len(all_items))


def lst_conv_to_dict_obj(items_lst):
    return [DictObj(**d) for d in items_lst]



def main():
    #get_latest(BASE_INFS[0])
    get_latest(BASE_INFS[1])

    #os.makedirs(data_dir + "/vid_all", exist_ok=True)
    #items = lst_conv_to_dict_obj( json.load(open(data_dir + "/all_items__3_4_2020_utf8.json")) )
    #get_all_vids(items, data_dir + "/vid_all")



if __name__ == "__main__":
    try:
        main()
    finally:
        kill_server()



