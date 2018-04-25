import time
from urllib import request
from urllib import parse
from lxml import etree


def href(element):
    return element.attrib['href'].split('#')[0]


def links_from_html(html):
    parser = etree.HTMLParser()
    root = etree.fromstring(html, parser)
    return map(href, root.xpath('//a[@href]'))


def same_domain(urla, urlb):
    purla = parse.urlparse(urla)
    purlb = parse.urlparse(urlb)
    nonetloc = purla.netloc == '' or purlb.netloc == ''
    return nonetloc or purla.netloc == purlb.netloc


def http_url(url):
    scheme = parse.urlparse(url).scheme
    return scheme == 'http' or scheme == 'https'


class Pulse:
    def __init__(self, ref, parent, rate):
        self._ref = ref
        self._parent = parent
        self._rate = rate

    def run(self):
        self.beat()

    def beat(self):
        time.sleep(self._rate)
        self._parent.beat()
        self._ref.beat()


class Fetcher:
    def __init__(self, ref, parent, user_agent, base_url):
        self._ref = ref
        self._parent = parent
        self._user_agent = user_agent
        self._base_url = base_url

    def fetch(self, url):
        headers = {
            'User-Agent': self._user_agent,
        }
        try:
            req = request.Request(url, headers=headers)
            res = request.urlopen(req)
            code = res.getcode()
            content_type = res.getheader('content-type')
            get_content = lambda: res.read()
        except request.HTTPError as e:
            code = getattr(e, 'code', 0)
            content_type = ''
            get_content = lambda: b''
        except Exception:
            self._parent.cannot_fetch_url(url)
            self._ref.stop()
            return

        if 'text/html' in content_type:
            try:
                links = links_from_html(get_content().decode('utf-8'))
            except UnicodeDecodeError:
                links = []
        else:
            links = []

        links = filter(self._wanted, links)
        self._parent.url_fetched(url, code, links)
        self._ref.stop()

    def _wanted(self, link):
        return same_domain(self._base_url, link)


class Checker:
    def __init__(self, ref, base_url, end_mailbox, create_pulse, create_fetcher):
        self._ref = ref
        self._running = False
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
        self._to_check.add(self._base_url)
        self._pulse.run()
        self.beat()

    def url_fetched(self, url, code, links):
        if not self._running:
            return

        status = 'OK' if 200 <= code < 300 else 'BAD'
        print('{}[{}] {}'.format(status, code, url), flush=True)

        self._analyze_url_links(url, links)
        self._being_checked.remove(url)
        self._checked.add(url)
        self._end_if_no_work()

    def cannot_fetch_url(self, url):
        if not self._running:
            return

        print('ERROR[Cannot fetch url] {}'.format(url), flush=True)
        self._being_checked.discard(url)
        self._end_if_no_work()

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

    def _analyze_url_links(self, url, links):
        for link in links:
            full_url = parse.urljoin(url, link)
            if not http_url(full_url):
                continue
            is_new = (full_url not in self._being_checked and
                      full_url not in self._to_check and
                      full_url not in self._checked)
            if is_new:
                self._to_check.add(full_url)

    def _end_if_no_work(self):
        if not self._being_checked and not self._to_check:
            self._pulse.stop()
            self._running = False
            self._ref.stop()
            self._end_mailbox.put(True)
