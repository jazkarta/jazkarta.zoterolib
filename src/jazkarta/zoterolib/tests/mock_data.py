"""
The contents of this file were filled up by enabling `real_http` in the mocks by
setting the `REAL_HTTP` environment variable:

export REAL_HTTP=true

The http requests will be saved in the data folder to be replayed later.
"""
from hashlib import sha256
import json
import os
import six
import sys
import requests
import requests.api

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REAL_HTTP = bool(os.environ.get("REAL_HTTP"))


def alternative_get(url, params=None, **kwargs):
    result = requests.api.request('get', url, params=params, **kwargs)
    save_data(result, url)
    return result


if REAL_HTTP:
    requests.api.get = requests.get = alternative_get
RESPONSES_MAP = {}


def read_file(path):
    if sys.version_info.major < 3:
        with open(path, "r") as f:
            return f.read().decode("utf-8")
    else:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


for filename in os.listdir(DATA_DIR):
    if not filename.endswith(".txt"):
        continue
    hash = filename[:-4]
    url = read_file(os.path.join(os.path.dirname(__file__), "data", "%s.url" % hash))
    body = read_file(os.path.join(os.path.dirname(__file__), "data", "%s.txt" % hash))
    headers_txt = read_file(
        os.path.join(os.path.dirname(__file__), "data", "%s.headers.json" % hash)
    )
    headers = json.loads(headers_txt)
    RESPONSES_MAP[hash] = {
        "url": url,
        "body": body,
        "headers": headers,
    }


def fill_mocker(mock):
    for info in RESPONSES_MAP.values():
        mock.register_uri(
            "GET", info["url"], text=info["body"], headers=info["headers"]
        )


def save_data(result, url):
    """Function to save a response to a json and header file"""
    hash = get_hash(url)
    text = result.text
    if not six.PY3:
        text = text.encode("utf-8")
    open(os.path.join(DATA_DIR, hash + '.txt'), 'w').write(text)
    headers = dict(result.headers)
    if "Content-Encoding" in headers:
        del headers["Content-Encoding"]
    open(os.path.join(DATA_DIR, hash + '.headers.json'), 'w').write(json.dumps(headers))
    open(os.path.join(DATA_DIR, hash + '.url'), 'w').write(url)


def get_hash(url):
    return sha256(url.encode("utf-8")).hexdigest()
