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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str, help="Url to check.")
    parser.add_argument("--rate", type=float, default=10,
                        help="Requests per second. Defaults to 10.")
    parser.add_argument("--user-agent", type=str, default="LinkChecker/dev",
                        help=("User agent header for requests. "
                              "Defaults to \"LinkChecker/dev\"."))
    dev_group = parser.add_mutually_exclusive_group()
    dev_group.add_argument("--dev", dest="dev", action="store_true",
                           help="Run in dev mode.")
    dev_group.add_argument("--no-dev", dest="dev", action="store_false",
                           help="Don't run in dev mode. Default mode.")
    parser.set_defaults(dev=False)
    args = parser.parse_args()

    if args.dev:
        logging.basicConfig(level=logging.DEBUG)
        signal.signal(signal.SIGUSR1, pykka.debug.log_thread_tracebacks)

    end_mailbox = gevent.queue.Queue()

    create_pulse = (lambda parent: checker.Pulse.start(parent=parent,
                                                       rate=1 / args.rate)
                    .proxy())
    create_fetcher = (lambda parent:
                      checker.Fetcher.start(parent=parent,
                                            user_agent=args.user_agent)
                      .proxy())
    (checker.Checker.start(base_url=args.url,
                           end_mailbox=end_mailbox,
                           create_pulse=create_pulse,
                           create_fetcher=create_fetcher)
     .proxy()
     .run())

    gevent.joinall([gevent.spawn(end_proc, end_mailbox)])
