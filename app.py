import sys
import time
import logging
import signal
from urllib import request
import html.parser
from urllib import parse
import pykka
import pykka.debug

logging.basicConfig(level=logging.DEBUG)
signal.signal(signal.SIGUSR1, pykka.debug.log_thread_tracebacks)


class LinkParser(html.parser.HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if not tag == "a":
            return

        for key, value in attrs:
            if key == "href":
                link_no_fragment = value.split("#")[0]
                self.links.add(link_no_fragment)
                break


def links_from_html(html):
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def same_domain(urla, urlb):
    purla = parse.urlparse(urla)
    purlb = parse.urlparse(urlb)
    nonetloc = purla.netloc == "" or purlb.netloc == ""
    return nonetloc or purla.netloc == purlb.netloc


def http_url(url):
    scheme = parse.urlparse(url).scheme
    return scheme == "http" or scheme == "https"


class Timer(pykka.ThreadingActor):
    def __init__(self, parent, timeout):
        super().__init__()
        self._parent = parent
        self._timeout = timeout
        self._seconds = 0

    def run(self):
        self.count()

    def reset(self):
        self._seconds = 0

    def count(self):
        time.sleep(1)
        self._seconds += 1
        if self._seconds == self._timeout:
            self._parent.timeout_reached()
        else:
            self.actor_ref.proxy().count()


class Fetcher(pykka.ThreadingActor):
    def __init__(self, parent, user_agent):
        super().__init__()
        self._parent = parent
        self._user_agent = user_agent

    def fetch(self, url):
        headers = {
            "User-Agent": self._user_agent,
        }
        try:
            req = request.Request(url, headers=headers)
            res = request.urlopen(req)
            code = res.getcode()
            content_type = res.getheader("content-type")
            content = res.read()
        except request.HTTPError as e:
            code = getattr(e, "code", 0)
            content_type = ""
            content = b""
        except Exception:
            self._parent.cannot_fetch_url(self, url)
            return
        self._parent.url_fetched(self, url, code, content_type, content)


class LinkChecker(pykka.ThreadingActor):
    def __init__(self, base_url, num_fetchers, timeout,
                 user_agent, end_callback):
        super().__init__()
        self._running = False
        self._base_url = base_url
        self._to_check = set()
        self._being_checked = set()
        self._checked = set()
        self._end_callback = end_callback

        self._timer = Timer.start(self, timeout).proxy()
        self._fetchers = [Fetcher.start(self, user_agent).proxy()
                          for _ in range(num_fetchers)]
        self._free_fetchers = set()
        for fetcher in self._fetchers:
            self._free_fetchers.add(fetcher)

    def run(self):
        if self._running:
            return

        print("checking {}...".format(self._base_url), flush=True)
        self._to_check.add(self._base_url)
        self._timer.run()
        self._check_urls()
        self._running = True

    def timeout_reached(self):
        if not self._running:
            return

        print("timeout reached", flush=True)
        self._timer.stop()
        for fetcher in self._fetchers:
            fetcher.stop()
        self._running = False
        self.stop()
        self._end_callback()

    def url_fetched(self, fetcher, url, code, content_type, content):
        if not self._running:
            return

        self._free_fetchers.add(fetcher)
        self._timer.reset()

        status = "OK" if 200 <= code <= 300 else "BAD"
        print("{}[{}] {}".format(status, code, url), flush=True)

        is_html = "text/html" in content_type
        try:
            links = (links_from_html(content.decode("utf-8"))
                     if is_html else [])
        except UnicodeDecodeError:
            links = []

        self._analyze_url_links(url, links)
        self._being_checked.remove(url)
        self._checked.add(url)
        self._check_urls()

    def cannot_fetch_url(self, fetcher, url):
        if not self._running:
            return

        print("ERROR[Cannot fetch url] {}".format(url), flush=True)
        self._free_fetchers.add(fetcher)
        self._being_checked.discard(url)
        self._check_urls()

    def _analyze_url_links(self, url, links):
        for link in links:
            if same_domain(self._base_url, link):
                full_url = parse.urljoin(url, link)
                all = self._to_check | self._checked | self._being_checked
                is_new = full_url not in all
                if is_new and http_url(full_url):
                    self._to_check.add(full_url)

    def _check_urls(self):
        if not self._to_check or not self._free_fetchers:
            return

        url = self._to_check.pop()
        self._being_checked.add(url)
        fetcher = self._free_fetchers.pop()
        fetcher.fetch(url)
        self._check_urls()


def end_callback():
    print("END", flush=True)


if __name__ == "__main__":
    if not len(sys.argv) == 2:
        print("usage: app.py url")
        sys.exit()
    url = sys.argv[1]
    num_fetchers = 8
    timeout = 3
    user_agent = "LinkChecker/0.1"
    link_checker = (LinkChecker
                    .start(url, num_fetchers, timeout,
                           user_agent, end_callback)
                    .proxy())
    link_checker.run()
