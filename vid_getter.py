import os, sys, subprocess, time, datetime
import json
import urllib.request

from base_url import BASE_URL

# better signature getting?
#  https://github.com/drawrowfly/tiktok-scraper/blob/e566b84795722dc9a32a3850da4718c88359e448/README.md

this_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = this_dir + "/data"


HEADERS = {
    "user-agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
    "referer" : 'https://www.tiktok.com/',
}

LAST_SIG_PATH = data_dir + "/last_sig.txt"

def get_sig(revoke_cache=False):
    if not revoke_cache:
        if os.path.exists(LAST_SIG_PATH):
            sig = open(LAST_SIG_PATH, "rb").read().decode('latin1')
            if len(sig) > 0:
                return sig

    print("Starting server")
    os.chdir(this_dir + '/tiktok-signature')
    serverProc = subprocess.Popen(['node', 'server.js'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        line1 = serverProc.stdout.readline().strip()
        line2 = serverProc.stdout.readline().strip()
        if line2 != b"TikTok Signature server started":
            raise Exception("failed start server `%s`, `%s`" % (line1, line2))
        print("Starting browser")
        cmd = ['node', 'browser.js', BASE_URL]
        print(' '.join(cmd))
        sig = subprocess.check_output(cmd)
    finally:
        print("Killing server")
        serverProc.terminate()
    assert len(sig) > 0, "got empty sig"
    open(LAST_SIG_PATH, "wb").write(sig)

    return sig.decode('latin1').strip()



class DictObj:
    def __init__(self):
        pass
    def data(self):
        return self.__dict__

def get_info(url):
    req = urllib.request.Request(url, headers=HEADERS)
    res = urllib.request.urlopen(req)
    info_text = res.read()
    info_json = json.loads(info_text)
    open(data_dir + "/last_data.json", "w").write(json.dumps(info_json, indent=4))

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
        d.music_url = minf['playUrl'][0]

        text_extra = dt['textExtra']
        d.hash_tags = []
        for te in text_extra:
            name = te['HashtagName']
            if len(name) > 0:
                d.hash_tags.append(name)
            tag_user = te['UserId']   # append this to https://www.tiktok.com/share/user/  to get redirected to the user
            if len(tag_user) > 0:
                d.hash_tags.append(tag_user)

        print(len(data.items), iteminf['text'])
        #print(iteminf['createTime'])
        #print(iteminf['video']['urls'][0])
    return data


def get_sig_info():
    sig = get_sig()
    print("got sig `%s`" % sig)

    url = BASE_URL + "&_signature=" + sig
    data = get_info(url)
    if data is None:
        print("Failed to get vids, refreshing signature")
        sig = get_sig(revoke_cache=True)
        print("got sig2 `%s`" % sig)
        url = BASE_URL + "&_signature=" + sig
        data = get_info(url)
        if data is None:
            print("Failed to get vids with new signature")
            raise Exception("failed get_info twice")
    return data

def download(url):
    print("  downloading", url)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        res = urllib.request.urlopen(req)
        data = res.read();
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

    data = download(url)

    open(filepath, "wb").write(data)
    print("  saved", filepath)
    start = data.find(b'vid:')
    if start == -1:
        print("  did not find vid_id")
        return
    vid_id = data[start+4:start+36].decode('latin1')
    item.vid_id = vid_id

    no_watermark_url = "https://api2.musical.ly/aweme/v1/playwm/?video_id=" + vid_id
    data = download(no_watermark_url)
    open(nwm_filepath, "wb").write(data)
    print("  saved", filepath)


def save_metadata(dir, item):
    basename = item.create_time_str + "__" + item.item_id
    filepath = dir + "/" + basename + ".json"
    if os.path.exists(filepath):
        print("  json exists")
        return
    open(filepath, "w").write(json.dumps(item.data(), indent=4))
    print("  saved", filepath)


def main():
    data = get_sig_info()

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(data_dir + "/vid", exist_ok=True)

    #item = data.items[0]
    for idx, item in enumerate(data.items):
        print(idx, "Getting vid for", item.item_id)
        save_metadata(data_dir + "/vid", item)
        get_vid_file(item.vid_url, data_dir + "/vid", item)


if __name__ == "__main__":
    main()

