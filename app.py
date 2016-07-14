import sys
import logging
import signal
import pykka.debug
import checker

logging.basicConfig(level=logging.DEBUG)
signal.signal(signal.SIGUSR1, pykka.debug.log_thread_tracebacks)


def end_callback():
    print("END", flush=True)


if __name__ == "__main__":
    if not len(sys.argv) == 2:
        print("usage: app.py url")
        sys.exit()
    url = sys.argv[1]
    timeout = 3
    rate = 10
    user_agent = "LinkChecker/0.1"
    create_timer = lambda parent: checker.Timer.start(parent, timeout).proxy()
    create_pulse = lambda parent: checker.Pulse.start(parent, 1 / rate).proxy()
    create_fetcher = lambda parent: (checker.Fetcher.start(parent, user_agent)
                                     .proxy())
    (checker.Checker.start(url, end_callback,
                           create_timer, create_pulse, create_fetcher)
     .proxy()
     .run())
