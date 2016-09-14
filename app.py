from gevent import monkey
monkey.patch_all()
import argparse
import logging
import signal
import pykka.debug
import checker

logging.basicConfig(level=logging.DEBUG)
signal.signal(signal.SIGUSR1, pykka.debug.log_thread_tracebacks)


def end_callback():
    print("END")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str)
    parser.add_argument("--timeout", type=int, default=3)
    parser.add_argument("--rate", type=float, default=10)
    parser.add_argument("--useragent", type=str, default="LinkChecker/0.1")
    args = parser.parse_args()

    create_timer = (lambda parent: checker.Timer.start(parent=parent,
                                                       timeout=args.timeout)
                    .proxy())
    create_pulse = (lambda parent: checker.Pulse.start(parent=parent,
                                                       rate=1 / args.rate)
                    .proxy())
    create_fetcher = (lambda parent:
                      checker.Fetcher.start(parent=parent,
                                            user_agent=args.useragent)
                      .proxy())
    (checker.Checker.start(base_url=args.url,
                           end_callback=end_callback,
                           create_timer=create_timer,
                           create_pulse=create_pulse,
                           create_fetcher=create_fetcher)
     .proxy()
     .run())
