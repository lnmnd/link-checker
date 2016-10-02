from gevent import monkey
monkey.patch_all()
import argparse
import logging
import signal
import pykka.debug
import gevent
import gevent.queue
import checker


def end_proc(mailbox):
    mailbox.get()
    print("END")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str)
    parser.add_argument("--timeout", type=int, default=3)
    parser.add_argument("--rate", type=float, default=10)
    parser.add_argument("--useragent", type=str, default="LinkChecker/0.1")
    parser.add_argument("--dev", dest="dev", action="store_true")
    parser.add_argument("--no-dev", dest="dev", action="store_false")
    parser.set_defaults(dev=False)
    args = parser.parse_args()

    if args.dev:
        logging.basicConfig(level=logging.DEBUG)
        signal.signal(signal.SIGUSR1, pykka.debug.log_thread_tracebacks)

    end_mailbox = gevent.queue.Queue()

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
                           end_mailbox=end_mailbox,
                           create_timer=create_timer,
                           create_pulse=create_pulse,
                           create_fetcher=create_fetcher)
     .proxy()
     .run())

    gevent.joinall([gevent.spawn(end_proc, end_mailbox)])
