import time
from urllib import request
import html.parser
from urllib import parse
import pykka
import pykka.gevent


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


class Timer(pykka.gevent.GeventActor):
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


class Pulse(pykka.gevent.GeventActor):
    def __init__(self, parent, rate):
        super(Pulse, self).__init__()
        self._parent = parent
        self._rate = rate

    def run(self):
        self.beat()

    def beat(self):
        time.sleep(self._rate)
        self._parent.beat()
        self.actor_ref.proxy().beat()


class Fetcher(pykka.gevent.GeventActor):
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
            self._parent.cannot_fetch_url(url)
            self.stop()
            return
        self._parent.url_fetched(url, code, content_type, content)
        self.stop()


class Checker(pykka.gevent.GeventActor):
    def __init__(self, base_url, end_mailbox,
                 create_timer, create_pulse, create_fetcher):
        super().__init__()
        self._running = False
        self._timer = create_timer(self)
        self._pulse = create_pulse(self)
        self._create_fetcher = create_fetcher
        self._base_url = base_url
        self._to_check = set()
        self._being_checked = set()
        self._checked = set()
        self._end_mailbox = end_mailbox

    def run(self):
        if self._running:
            return

        self._running = True
        print("checking {}...".format(self._base_url))
        self._to_check.add(self._base_url)
        self._timer.run()
        self._pulse.run()
        self.beat()

    def timeout_reached(self):
        if not self._running:
            return

        print("timeout reached")
        self._timer.stop()
        self._pulse.stop()
        self._running = False
        self.stop()
        self._end_mailbox.put(True)

    def url_fetched(self, url, code, content_type, content):
        if not self._running:
            return

        self._timer.reset()

        status = "OK" if 200 <= code <= 300 else "BAD"
        print("{}[{}] {}".format(status, code, url))

        is_html = "text/html" in content_type
        try:
            links = (links_from_html(content.decode("utf-8"))
                     if is_html else [])
        except UnicodeDecodeError:
            links = []

        self._analyze_url_links(url, links)
        self._being_checked.remove(url)
        self._checked.add(url)

    def cannot_fetch_url(self, url):
        if not self._running:
            return

        print("ERROR[Cannot fetch url] {}".format(url))
        self._being_checked.discard(url)

    def _analyze_url_links(self, url, links):
        for link in links:
            if same_domain(self._base_url, link):
                full_url = parse.urljoin(url, link)
                all_urls = self._to_check | self._checked | self._being_checked
                is_new = full_url not in all_urls
                if is_new and http_url(full_url):
                    self._to_check.add(full_url)

    def beat(self):
        if not self._running:
            return

        try:
            url = self._to_check.pop()
        except KeyError:
            return
        self._being_checked.add(url)
        fetcher = self._create_fetcher(self)
        fetcher.fetch(url)
